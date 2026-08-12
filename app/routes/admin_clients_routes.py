# app/routes/admin_clients.py

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    send_from_directory, current_app, send_file
)
from flask_login import login_required, current_user
from app.models import (
    db, User, Advisor, TaxYear, Quote,
    Subscription, Plan, UserStatistics
)
from sqlalchemy import func
from datetime import date
import os
from app.security import require_role, current_advisor, advisor_is_client

admin_clients_bp = Blueprint('admin_clients', __name__, url_prefix='/admin')


@admin_clients_bp.route('/clients')
@login_required
@require_role('admin')
def admin_clients():
    today = date.today()

    client_ids = (
        db.session.query(TaxYear.user_id)
          .filter(TaxYear.advisor_id.isnot(None))
          .distinct()
          .all()
    )

    clients = []
    for (uid,) in client_ids:
        user = User.query.get(uid)
        if not user:
            continue

        tys = TaxYear.query.filter_by(user_id=uid).all()
        returns_count = len(tys)
        last_year = max((ty.year for ty in tys), default=None)

        open_tasks = 0
        for ty in tys:
            if ty.uploaded_documents and ty.documents_approved and ty.final_tax_return_submitted == 0:
                if not ty.draft_tax_return_submitted:
                    open_tasks += 1
                elif not ty.final_tax_return_submitted:
                    open_tasks += 1

        next_ty = (
            TaxYear.query
              .filter_by(user_id=uid)
              .filter(TaxYear.deadline >= today)
              .order_by(TaxYear.deadline)
              .first()
        )
        next_deadline = next_ty.deadline if next_ty else None

        stat = (
            UserStatistics.query
              .filter_by(user_id=uid)
              .order_by(UserStatistics.date.desc())
              .first()
        )
        if stat:
            stat_income     = float(stat.taxable_income)
            stat_assets     = float(stat.taxable_assets)
            stat_paid_taxes = float(stat.paid_taxes)
        else:
            stat_income = stat_assets = stat_paid_taxes = None

        clients.append({
            'id':              uid,
            'name':            f"{user.firstname} {user.lastname}",
            'email':           user.email,
            'phone':           user.phone or '—',
            'last_year':       last_year,
            'returns_count':   returns_count,
            'open_tasks':      open_tasks,
            'next_deadline':   next_deadline,
            'stat_income':     stat_income,
            'stat_assets':     stat_assets,
            'stat_paid_taxes': stat_paid_taxes,
        })

    return render_template('admin_clients.html', clients=clients)

@admin_clients_bp.route('/clients/<int:user_id>/profile')
@login_required
@require_role('admin', 'advisor')
def client_profile(user_id):
    # if advisor, fetch their Advisor.id and confirm this client is theirs
    advisor_id = None
    if current_user.role == 'advisor':
        adv_rec = current_advisor()
        if not adv_rec:
            flash("Du bist keinem Treuhänder-Datensatz zugeordnet.", "danger")
            return redirect(url_for('dashboard.dashboard'))
        advisor_id = adv_rec.id
        if not advisor_is_client(user_id):
            flash("Zugriff verweigert.", "danger")
            return redirect(url_for('dashboard.dashboard'))

    client = User.query.get_or_404(user_id)
    today  = date.today()

    # base query: only years with an advisor assigned
    q = TaxYear.query.filter(
        TaxYear.user_id == user_id,
        TaxYear.advisor_id.isnot(None)
    )

    # advisors only see their own
    if advisor_id:
        q = q.filter(TaxYear.advisor_id == advisor_id)

    tys = q.order_by(TaxYear.year.desc()).all()

    years = [ty.year for ty in tys]
    first_year = min(years) if years else None
    last_year  = max(years) if years else None
    missing_years = (
        [y for y in range(first_year, last_year + 1) if y not in years]
        if first_year is not None else []
    )

    # Engagement & Compliance
    open_tasks = 0
    for ty in tys:
        if ty.uploaded_documents and ty.documents_approved and ty.final_tax_return_submitted == 0:
            if not ty.draft_tax_return_submitted or not ty.final_tax_return_submitted:
                open_tasks += 1

    next_ty = (
        TaxYear.query
          .filter_by(user_id=user_id)
          .filter(TaxYear.deadline >= today)
          .order_by(TaxYear.deadline)
          .first()
    )
    next_deadline = next_ty.deadline if next_ty else None

    subs_dates = [ty.final_submitted for ty in tys if ty.final_submitted]
    last_submission = max(subs_dates) if subs_dates else None

    # Quote Summary (unchanged)
    qobj = Quote.query.filter_by(user_id=user_id)
    total_quotes = qobj.count()
    pending      = qobj.filter_by(quote_status='Pending').count()
    in_review    = qobj.filter_by(quote_status='In Review').count()
    accepted     = qobj.filter_by(quote_status='Accepted').count()
    rejected     = qobj.filter_by(quote_status='Rejected').count()
    avg_amount   = (
        db.session.query(func.avg(Quote.quote_amount))
          .filter(Quote.user_id == user_id,
                  Quote.quote_status == 'Accepted')
          .scalar()
    ) or 0
    last_q = qobj.order_by(Quote.created_at.desc()).first()

    quotes_summary = {
        'total':      total_quotes,
        'pending':    pending,
        'in_review':  in_review,
        'accepted':   accepted,
        'rejected':   rejected,
        'average':    float(avg_amount),
        'last_status': last_q.quote_status if last_q else None,
        'last_date':   last_q.created_at    if last_q else None
    }

    # Financial Statistics (unchanged)
    stats = UserStatistics.query \
        .filter_by(user_id=user_id) \
        .order_by(UserStatistics.date.desc()) \
        .all()

     # Build the final list: only completed returns with a downloadable file
    tax_returns = []
    # get the Advisor record for the current user
    adv_rec = current_advisor()
    advisor_name = adv_rec.name if adv_rec else '—'

    for ty in tys:
        # skip returns not assigned to your company
        if adv_rec and ty.advisor_id != adv_rec.id:
            continue

        # only show completed returns
        if not ty.final_tax_return_submitted:
            continue

        # only show if there's a final file to download
        if not ty.final_file_path:
            continue

        tax_returns.append({
            'id':               ty.id,
            'year':             ty.year,
            'status':           ty.status,
            'advisor_name':     advisor_name,
            'final_file_path':  ty.final_file_path,
        })

    return render_template(
        'admin_client_profile.html',
        client          = client,
        first_year      = first_year,
        last_year       = last_year,
        returns_count   = len(years),
        missing_years   = missing_years,
        open_tasks      = open_tasks,
        next_deadline   = next_deadline,
        last_submission = last_submission,
        quotes_summary  = quotes_summary,
        stats           = stats,
        tax_returns     = tax_returns
    )

from flask import send_file

@admin_clients_bp.route(
    '/clients/<int:user_id>/download_final_tax_return/<int:year>'
)
@login_required
@require_role('advisor', 'admin')
def download_final_tax_return(user_id, year):
    # fetch the TaxYear for this client/year
    ty = TaxYear.query.filter_by(user_id=user_id, year=year).first_or_404()

    # if advisor, enforce company ownership
    if current_user.role == 'advisor':
        adv_rec = current_advisor()
        if not adv_rec or ty.advisor_id != adv_rec.id:
            flash("Zugriff verweigert.", "danger")
            return redirect(url_for('admin_clients.client_profile', user_id=user_id))

    # ensure there's a final file path
    if not ty.final_file_path:
        flash("Keine finale Steuererklärung verfügbar.", "warning")
        return redirect(url_for('admin_clients.client_profile', user_id=user_id))

    # compute absolute path under project root (uploads is sibling to app/)
    project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    abs_path = os.path.join(project_root, ty.final_file_path)

    if not os.path.isfile(abs_path):
        current_app.logger.warning("Final return file missing on disk: %s", abs_path)
        flash("Datei auf dem Server nicht gefunden.", "danger")
        return redirect(url_for('admin_clients.client_profile', user_id=user_id))

    return send_file(abs_path, as_attachment=True)
