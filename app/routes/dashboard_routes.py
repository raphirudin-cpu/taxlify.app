from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_login import login_required, current_user, logout_user
from app.models import db, User, TaxYear, Quote, Feedback, Advisor, RequiredDocument, UserStatistics
from app.security import tax_year_for_request, advisor_is_bound, send_stored_file
from datetime import datetime, timedelta
import os

# Define Blueprint
dashboard_bp = Blueprint('dashboard', __name__)


def _deadline_urgency(deadline, today, three_months):
    if not deadline:
        return "muted"
    if deadline < today:
        return "danger"
    if deadline <= three_months:
        return "warning"
    return "muted"


_RAIL_STATE_LABEL = {"done": "Erledigt", "active": "Offen", "pending": "Ausstehend"}


def _rail(ty):
    """Five-step progress rail derived from status flags (view-only)."""
    def step(name, state):
        return {"name": name, "state": state, "label": _RAIL_STATE_LABEL[state]}

    checkliste = "done" if ty.checklist_completed else "active"

    if ty.advisor_id:
        offerte = "done"
    elif ty.status == "Review Quote":
        offerte = "active"
    else:
        offerte = "pending"

    if ty.documents_approved:
        dokumente = "done"
    elif ty.uploaded_documents or ty.additional_documents_request:
        dokumente = "active"
    else:
        dokumente = "pending"

    if ty.draft_tax_return_approved:
        entwurf = "done"
    elif ty.draft_tax_return_submitted:
        entwurf = "active"
    else:
        entwurf = "pending"

    einreichung = "done" if ty.final_tax_return_submitted else "pending"

    return [
        step("Checkliste", checkliste),
        step("Offerte", offerte),
        step("Dokumente", dokumente),
        step("Entwurf", entwurf),
        step("Einreichung", einreichung),
    ]


def _hero_action(open_years):
    """Pick the single most urgent open action across all tax years."""
    # 1) missing documents
    for t in open_years:
        if t.status == "Additional documents requested" or (t.advisor_id and not t.uploaded_documents):
            return {
                "headline": f"Belege für {t.year} hochladen",
                "sub": "Dein Treuhänder wartet auf deine Unterlagen.",
                "url": url_for("upload_documents.upload_documents", year=t.year),
                "cta": "Belege hochladen",
            }
    # 2) quote to review
    for t in open_years:
        if t.status == "Review Quote":
            return {
                "headline": f"Offerte für {t.year} prüfen",
                "sub": "Eine Offerte wartet auf deine Entscheidung.",
                "url": url_for("dashboard.dashboard"),
                "cta": "Offerte prüfen",
            }
    # 3) checklist incomplete
    for t in open_years:
        if not t.checklist_completed:
            return {
                "headline": f"Checkliste für {t.year} ausfüllen",
                "sub": "Beantworte ein paar Fragen, damit es weitergeht.",
                "url": url_for("checklist.checklist", year=t.year),
                "cta": "Checkliste ausfüllen",
            }
    # 4) draft to review
    for t in open_years:
        if t.draft_tax_return_submitted and not t.draft_tax_return_approved:
            return {
                "headline": f"Entwurf für {t.year} prüfen",
                "sub": "Dein Treuhänder hat einen Entwurf eingereicht.",
                "url": url_for("dashboard.dashboard"),
                "cta": "Entwurf prüfen",
            }
    return None

@dashboard_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    flash_message = request.args.get('flash')
    if flash_message:
        flash(flash_message, "success")

    user_id = current_user.id
    user = User.query.get(user_id)

    if not user:
        logout_user() 
        return redirect(url_for('auth.login'))

    # Check if this is the first login; if so, redirect accordingly.
    if user.first_login == 0:
        flash("Bitte aktualisiere deine Einstellungen bei der ersten Anmeldung.", "error")
        if user.role in ('admin', 'advisor'):
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))
        else:
            return redirect(url_for('settings.settings'))

    # Redirect advisors to their dashboard
    if user.role in ('advisor', 'admin'):
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    # Handle opening a new tax year
    if request.method == 'POST' and 'open_tax_year' in request.form:
        year = request.form['year']
        deadline = request.form['deadline']

        existing_tax_year = TaxYear.query.filter_by(user_id=user_id, year=year).first()
        if existing_tax_year:
            flash(f"Das Steuerjahr {year} ist bereits eröffnet.", "error")
        else:
            new_tax_year = TaxYear(user_id=user_id, year=year, status='Open', deadline=deadline, advisor_id=None)
            db.session.add(new_tax_year)
            db.session.commit()
            flash("Steuerjahr eröffnet.", "success")

    # Fetch tax years
    tax_years = TaxYear.query.filter_by(user_id=user_id).order_by(TaxYear.year.desc()).all()

    # Fetch quotes
    quotes = Quote.query.filter_by(user_id=user_id).all()
    requested_quotes = {q.tax_year: q for q in quotes}

    # Fetch feedback keys (which year+advisor combos already have a rating)
    feedbacks = {f"{f.tax_year}_{f.advisor_id}" for f in Feedback.query.filter_by(user_id=user_id).all()}

    advisor_dict = {a.id: a for a in Advisor.query.all()}

    today = datetime.utcnow().date()
    three_months = today + timedelta(days=90)

    open_years = [t for t in tax_years if not t.final_tax_return_submitted]
    completed_years = [t for t in tax_years if t.final_tax_return_submitted]

    # Per-open-year view cards
    year_cards = []
    for t in open_years:
        adv = advisor_dict.get(t.advisor_id) if t.advisor_id else None
        quote = requested_quotes.get(t.year)
        year_cards.append({
            "id": t.id,
            "year": t.year,
            "status": t.status,
            "deadline": t.deadline,
            "urgency": _deadline_urgency(t.deadline, today, three_months),
            "advisor_name": adv.name if adv else None,
            "advisor_city": adv.city if adv else None,
            "awaiting_decision": t.status == "Review Quote",
            "pending_quote": bool(quote and quote.quote_status == "Pending"),
            "quote_amount": quote.quote_amount if quote else None,
            "quote_advisor_id": quote.advisor_id if quote else None,
            "rail": _rail(t),
        })

    # Completed years table rows
    completed_cards = []
    for t in completed_years:
        adv = advisor_dict.get(t.advisor_id) if t.advisor_id else None
        completed_cards.append({
            "year": t.year,
            "advisor_name": adv.name if adv else "—",
            "advisor_id": t.advisor_id,
            "has_final": bool(t.final_file_path),
            "rated": f"{t.year}_{t.advisor_id}" in feedbacks,
        })

    # KPIs
    open_year_ids = [t.id for t in open_years]
    if open_year_ids:
        req_docs = RequiredDocument.query.filter(
            RequiredDocument.user_id == user_id,
            RequiredDocument.tax_year_id.in_(open_year_ids),
        ).all()
        docs_total = len(req_docs)
        docs_uploaded = sum(1 for d in req_docs if d.file_path)
    else:
        docs_total = docs_uploaded = 0

    next_deadline = min((t.deadline for t in open_years if t.deadline), default=None)

    latest_stat = (UserStatistics.query.filter_by(user_id=user_id)
                   .order_by(UserStatistics.date.desc()).first())

    kpis = {
        "open_count": len(open_years),
        "next_deadline": next_deadline,
        "docs_uploaded": docs_uploaded,
        "docs_total": docs_total,
        "tax_year_label": latest_stat.date.year if latest_stat and latest_stat.date else None,
        "tax_paid": latest_stat.paid_taxes if latest_stat else None,
    }

    hero = _hero_action(open_years)

    return render_template(
        'dashboard.html',
        user=user,
        hero=hero,
        year_cards=year_cards,
        completed_cards=completed_cards,
        kpis=kpis,
        advisors=advisor_dict,
    )

@dashboard_bp.route('/quote_details/<int:tax_year_id>')
@login_required
def quote_details(tax_year_id):
    # Retrieve the TaxYear record using its primary key
    tax_year_record = TaxYear.query.get(tax_year_id)
    if not tax_year_record:
        return jsonify({"error": "Tax year record not found"}), 404

    # Query the Quote using the tax_year value from the TaxYear record.
    quote = Quote.query.filter_by(user_id=current_user.id, tax_year=tax_year_record.year).first()
    if quote:
        advisor_record = None
        if quote.advisor_id:
            from app.models import Advisor  # make sure Advisor is imported
            advisor_record = Advisor.query.get(quote.advisor_id)
        advisor_name = f"{advisor_record.name}" if advisor_record else "N/A"
        
        # Build the download URL (ownership is enforced inside the route).
        file_url = url_for('dashboard.download_quote_file', quote_id=quote.id) if quote.file_path else ""
        
        data = {
            "advisor_name": advisor_name,
            "advisor_id": quote.advisor_id,
            "amount": quote.quote_amount,
            "comment": quote.comment,
            "file_url": file_url
        }
        return jsonify(data)
    else:
        return jsonify({"error": "Quote not found"}), 404

@dashboard_bp.route('/download_quote_file/<int:quote_id>')
@login_required
def download_quote_file(quote_id):
    quote = Quote.query.get(quote_id)
    if not quote:
        abort(404)
    role = current_user.role
    authorized = (
        (role == 'user' and quote.user_id == current_user.id)
        or role == 'admin'
        or (role == 'advisor' and advisor_is_bound(quote.user_id, quote.tax_year))
    )
    if not authorized:
        abort(403)
    return send_stored_file(quote.file_path, mimetype='application/pdf')

@dashboard_bp.route('/download_draft_tax_return/<int:user_id>/<int:year>', methods=['GET'])
@login_required
def download_draft_tax_return(user_id, year):
    record = tax_year_for_request(year, customer_id=user_id)
    if not record:
        flash("Tax year record not found or access denied.", "error")
        return redirect(url_for('dashboard.dashboard'))
    if not record.draft_file_path:
        flash(f"Draft tax return file not found for tax year {year}.", "error")
        return redirect(url_for('dashboard.dashboard'))
    return send_stored_file(record.draft_file_path, mimetype='application/pdf')

@dashboard_bp.route('/download_final_tax_return/<int:user_id>/<int:year>', methods=['GET'])
@login_required
def download_final_tax_return(user_id, year):
    record = tax_year_for_request(year, customer_id=user_id)
    if not record or not record.final_file_path:
        flash("Final tax return file not found or access denied.", "error")
        return redirect(url_for('dashboard.dashboard'))
    return send_stored_file(record.final_file_path, mimetype='application/pdf')

@dashboard_bp.route('/withdraw_quote/<int:tax_year_id>', methods=['POST'])
@login_required
def withdraw_quote(tax_year_id):
    # Retrieve the tax year record using the provided tax_year_id
    tax_year_record = TaxYear.query.get(tax_year_id)
    if not tax_year_record:
        flash("Tax year record not found.", "error")
        return jsonify({"error": "Tax year record not found"}), 404

    # Find the corresponding quote using the tax year (assuming 'tax_year' in Quote corresponds to TaxYear.year)
    quote = Quote.query.filter_by(user_id=current_user.id, tax_year=tax_year_record.year).first()
    if not quote or quote.quote_status != "Pending":
        flash("No pending quote found for this tax year.", "error")
        return jsonify({"error": "No pending quote found for this tax year"}), 404

    # Update the quote status to "Rejected" and the tax year status to "Quote withdrawn"
    quote.quote_status = "Rejected"
    tax_year_record.status = "Quote withdrawn"

    db.session.commit()
    flash("Quote withdrawn successfully.", "success")
    return jsonify({"success": "Quote withdrawn successfully."})


