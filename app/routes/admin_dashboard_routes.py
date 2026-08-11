# app/routes/admin_dashboard.py

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import (
    db, Advisor, Quote, Subscription, Plan, TaxYear, User
)
from sqlalchemy import func, extract
from datetime import date, timedelta
from app.security import require_role, current_advisor

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

@admin_dashboard_bp.route('/dashboard')
@login_required
@require_role('admin')
def admin_dashboard():
    # Find advisor_id
    adv = current_advisor()
    advisor_id = adv.id if adv else None
    today = date.today()

    # — KPI: Quote Conversion Rate
    q_accepted = Quote.query.filter_by(advisor_id=advisor_id, quote_status='Accepted').count()
    q_rejected = Quote.query.filter_by(advisor_id=advisor_id, quote_status='Rejected').count()
    conv_den = q_accepted + q_rejected
    quote_conversion = (q_accepted / conv_den * 100) if conv_den else None

    # — KPI: Revenue This Month (sum of accepted quote amounts)
    revenue_month = db.session.query(
        func.coalesce(func.sum(Quote.quote_amount), 0)
    ).filter(
        Quote.advisor_id == advisor_id,
        Quote.quote_status == 'Accepted',
        extract('year', Quote.accepted_on) == today.year,
        extract('month', Quote.accepted_on) == today.month
    ).scalar()

    # — KPI: Revenue Year-to-Date (sum of accepted quote amounts for the current year)
    revenue_ytd = db.session.query(
            func.coalesce(func.sum(Quote.quote_amount), 0)
        ).filter(
            Quote.advisor_id    == advisor_id,
            Quote.quote_status  == 'Accepted',
            extract('year', Quote.accepted_on) == today.year
        ).scalar()

    # — KPI: Average Turnaround Time (days between request and submission)
    q_times = (
        Quote.query
             .filter_by(advisor_id=advisor_id)
             .filter(Quote.submitted_on.isnot(None))
             .all()
    )
    if q_times:
        total_days = sum(
            (q.submitted_on.date() - q.created_at.date()).days
            for q in q_times
        )
        avg_turnaround = total_days / len(q_times)
    else:
        avg_turnaround = None

    # — Slot Usage Summary
    subs = Subscription.query.filter_by(user_id=current_user.id).all()
    total_purchased = total_used = 0
    low_slot_years = []
    for sub in subs:
        plan = Plan.query.get(sub.plan_id)
        purchased = plan.base_slots + sub.slots
        total_purchased += purchased

        used = TaxYear.query.filter_by(
            advisor_id=advisor_id,
            year=sub.tax_year
        ).count()
        total_used += used

        remaining = purchased - used
        if purchased and remaining / purchased < 0.1:
            low_slot_years.append(sub.tax_year)

    total_remaining = total_purchased - total_used

    # — Top 5 Years by Purchased Slots
    slots_list = []
    for sub in subs:
        plan     = Plan.query.get(sub.plan_id)
        purchased = plan.base_slots + sub.slots
        slots_list.append((sub.tax_year, purchased))

    # sort by purchased desc, then year desc
    slots_top5 = sorted(
        slots_list,
        key=lambda yr_slots: (-yr_slots[1], -yr_slots[0])
    )[:5]

    # — Document & Approval Pipeline
    pending_docs   = TaxYear.query.filter_by(
        advisor_id=advisor_id,
        uploaded_documents=1,
        documents_approved=0
    ).count()
    drafts_pending = TaxYear.query.filter_by(
        advisor_id=advisor_id,
        draft_tax_return_submitted=1,
        draft_tax_return_approved=0
    ).count()
    finals_ready   = TaxYear.query.filter_by(
        advisor_id=advisor_id,
        final_tax_return_submitted=1
    ).count()

    # — Task & Follow-Up Queue: only include if documents uploaded
    overdue_raw = (
        db.session.query(
            TaxYear,
            User.firstname.label('first'),
            User.lastname.label('last')
        )
        .join(User, TaxYear.user_id == User.id)
        .filter(
            TaxYear.advisor_id == advisor_id,
            TaxYear.deadline < today,
            TaxYear.uploaded_documents == True,           # <— only these
            TaxYear.documents_approved == True,           # <— ensure approved before draft/final
            TaxYear.final_tax_return_submitted == 0
        )
        .order_by(TaxYear.deadline)
        .all()
    )

    overdue_items = []
    for ty, first, last in overdue_raw:
        tasks = []
        # Draft only once docs are approved (we already filtered for approved)
        if not ty.draft_tax_return_submitted:
            tasks.append("Submit draft tax return")
        # Final only once draft is in
        elif not ty.final_tax_return_submitted:
            tasks.append("Submit final tax return")

        overdue_items.append({
            'client_name': f"{first} {last}",
            'tax_year':    ty.year,
            'deadline':    ty.deadline,
            'status':      ty.status,
            'tasks':       tasks
        })

    overdue_tasks = len(overdue_items)


    # — Upcoming Filing Deadlines (next 7 days)
    upcoming_deadlines = TaxYear.query.filter(
        TaxYear.advisor_id==advisor_id,
        TaxYear.deadline >= today,
        TaxYear.deadline <= today + timedelta(days=7)
    ).order_by(TaxYear.deadline).all()

    # — Quote Summary (existing) …
    quote_summary = {
        'total':     Quote.query.filter_by(advisor_id=advisor_id).count(),
        'pending':   Quote.query.filter_by(advisor_id=advisor_id, quote_status='Pending').count(),
        'in_review': Quote.query.filter_by(advisor_id=advisor_id, quote_status='In Review').count(),
        'accepted':  q_accepted,
        'rejected':  q_rejected
    }

    # — Top 5 Years by # of Quotes
    quotes_per_year = (
    db.session.query(
        Quote.tax_year,
        func.count(Quote.id).label('count')
    )
    .filter(Quote.advisor_id == advisor_id)
    .group_by(Quote.tax_year)
    .order_by(
        func.count(Quote.id).desc(),    # primary: highest counts first
        Quote.tax_year.desc()           # secondary: newest year first on ties
    )
    .limit(5)
    .all()
)
    
    return render_template('admin_dashboard.html',
        # KPIs
        quote_conversion=quote_conversion,
        revenue_month=revenue_month,
        revenue_ytd   = revenue_ytd,
        avg_turnaround=avg_turnaround,
        # Slot Usage
        total_purchased=total_purchased,
        total_used=total_used,
        total_remaining=total_remaining,
        low_slot_years=low_slot_years,
        slots_top5=slots_top5,
        # Document Pipeline
        pending_docs=pending_docs,
        drafts_pending=drafts_pending,
        finals_ready=finals_ready,
        # Tasks & Deadlines
        overdue_tasks=overdue_tasks,
        overdue_items=overdue_items,
        upcoming_deadlines=upcoming_deadlines,
        # Quote Summary
        quote_summary=quote_summary,
        quotes_per_year=quotes_per_year
    )
