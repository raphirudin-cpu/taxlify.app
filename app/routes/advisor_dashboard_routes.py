from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import db, TaxYear, User, Quote, Advisor, Feedback, UserStatistics, TeamMember
from app.security import require_role, current_advisor, advisor_is_bound, parse_int
from app.helpers import commit_or_rollback
from datetime import date, datetime

advisor_dashboard_bp = Blueprint('advisor_dashboard', __name__)

@advisor_dashboard_bp.route('/advisor/dashboard')
@login_required
@require_role('advisor', 'admin')
def advisor_dashboard():
    # Determine advisor_id based on user role
    advisor_ids = []

    if current_user.role == 'admin':
        # Admins: advisor record linked by user_id
        adv = current_advisor()
        if adv:
            advisor_ids = [adv.id]
    elif current_user.role == 'advisor':
        # Team-member advisors: lookup in team_members by email
        tm = TeamMember.query.filter_by(email=current_user.email).all()
        if tm:
            advisor_ids = [m.advisor_id for m in tm]
        else:
            # Advisor role user not linked to a company
            flash("Du bist noch keiner Firma zugeordnet. Bitte wende dich an deine Leitung.", "error")

    # Fetch tax years for this advisor_id
    rows = []
    if advisor_ids:
        rows = (
            db.session.query(TaxYear, User)
            .join(User, TaxYear.user_id == User.id)
            .filter(TaxYear.advisor_id.in_(advisor_ids))
            .order_by(TaxYear.year.desc())
            .all()
        )

    tax_years = []
    for ty, user in rows:
        # Skip any entries lacking an advisor_id, though filter already applies
        if ty.advisor_id is None:
            continue
        tax_years.append({
            'user_id': ty.user_id,
            'year': ty.year,
            'status': ty.status,
            'deadline': ty.deadline,
            'checklist_completed': ty.checklist_completed,
            'uploaded_documents': ty.uploaded_documents,
            'draft_tax_return_submitted': ty.draft_tax_return_submitted,
            'draft_tax_return_approved': ty.draft_tax_return_approved,
            'final_tax_return_submitted': ty.final_tax_return_submitted,
            'additional_documents_request': ty.additional_documents_request,
            'additional_documents_uploaded': ty.additional_documents_uploaded,
            'documents_approved': ty.documents_approved,
            'draft_rejection_comment': ty.draft_rejection_comment,
            'user_name': user.lastname,
            'user_surname': user.firstname,
            'final_submitted': ty.final_submitted,
            'created_at': ty.created_at,
        })

    # Split into pending vs completed
    pending_tax_years   = [ty for ty in tax_years if not ty['final_tax_return_submitted']]
    completed_tax_years = [ty for ty in tax_years if ty['final_tax_return_submitted']]

    return render_template(
        'advisor_dashboard.html',
        pending_tax_years=pending_tax_years,
        completed_tax_years=completed_tax_years,
        current_date=date.today(),
        is_admin=(current_user.role == 'admin'),
        is_team_member=(current_user.role == 'advisor')
    )

@advisor_dashboard_bp.route('/advisor/view_feedback')
@login_required
@require_role('advisor', 'admin')
def view_feedback():
    """
    AJAX endpoint for feedback modal.
    Expects query params: user_id, tax_year
    """
    user_id  = parse_int(request.args.get('user_id'))
    tax_year = parse_int(request.args.get('tax_year'))

    if user_id is None or tax_year is None:
        return "Missing parameters", 400

    # Advisors may only read feedback for clients they are engaged with.
    if current_user.role == 'advisor' and not advisor_is_bound(user_id, tax_year):
        abort(403)

    feedbacks = Feedback.query.filter_by(
        user_id=user_id,
        tax_year=tax_year
    ).order_by(Feedback.created_at.desc()).all()

    return render_template(
        'view_feedback.html',
        feedbacks=feedbacks
    )

@advisor_dashboard_bp.route('/advisor/get_statistic')
@login_required
@require_role('advisor', 'admin')
def get_statistic():
    user_id  = parse_int(request.args.get('user_id'))
    year_int = parse_int(request.args.get('tax_year'))
    if user_id is None or year_int is None:
        return jsonify({'exists': False}), 400

    # Advisors may only read statistics for clients they are engaged with.
    if current_user.role == 'advisor' and not advisor_is_bound(user_id, year_int):
        return jsonify({'exists': False}), 403

    stat_date = date(year_int, 12, 31)
    stat = UserStatistics.query.filter_by(
        user_id=user_id,
        date=stat_date
    ).first()

    if stat:
        return jsonify({
            'exists': True,
            'taxable_income': float(stat.taxable_income),
            'taxable_assets': float(stat.taxable_assets),
            'paid_taxes': float(stat.paid_taxes)
        })
    else:
        return jsonify({'exists': False})

@advisor_dashboard_bp.route('/advisor/add_statistic', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def add_statistic():
    user_id        = parse_int(request.form.get('user_id'))
    date_str       = request.form.get('date')
    taxable_income = request.form.get('taxable_income')
    taxable_assets = request.form.get('taxable_assets')
    paid_taxes     = request.form.get('paid_taxes')

    if user_id is None or not date_str:
        flash("Fehlende oder ungültige Daten.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Ungültiges Datum.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    # Advisors may only write statistics for clients they are engaged with.
    if current_user.role == 'advisor' and not advisor_is_bound(user_id, parsed_date.year):
        abort(403)

    existing = UserStatistics.query.filter_by(
        user_id=user_id,
        date=parsed_date
    ).first()

    if existing:
        existing.taxable_income = taxable_income
        existing.taxable_assets = taxable_assets
        existing.paid_taxes     = paid_taxes
    else:
        new_stat = UserStatistics(
            user_id=user_id,
            date=parsed_date,
            taxable_income=taxable_income,
            taxable_assets=taxable_assets,
            paid_taxes=paid_taxes
        )
        db.session.add(new_stat)

    if commit_or_rollback():
        flash("Zahlen gespeichert.", "success")
    else:
        flash("Fehler beim Speichern der Zahlen.", "error")
    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
