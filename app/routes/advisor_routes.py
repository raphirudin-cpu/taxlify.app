import os
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import db, Advisor, TaxYear, Quote, Feedback
from app.helpers import serve_advisor_logo
from sqlalchemy import func

advisor_bp = Blueprint('advisor', __name__)

# Route to serve advisor logo files
@advisor_bp.route('/advisor/<int:advisor_id>/Logo/<filename>')
def advisor_logo(advisor_id, filename):
    return serve_advisor_logo(advisor_id, filename)

@advisor_bp.route('/advisors')
@login_required
def advisors():
    user = current_user

    if current_user.role in ('advisor', 'admin'):
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    advisors = Advisor.query.all()

    advisors_data = []
    for adv in advisors:
        if not getattr(adv, 'name', None):
            continue

        logo_filename = os.path.basename(adv.logo) if adv.logo else ''
        logo_url = url_for('advisor.advisor_logo', advisor_id=adv.id, filename=logo_filename) if adv.logo else ''

        advisors_data.append({
            'id': adv.id,
            'logo': logo_url,
            'name': adv.name,
            'city': adv.city
        })

    tax_years = TaxYear.query.filter_by(user_id=user.id).all()
    all_quotes = Quote.query.filter(Quote.user_id == user.id).all()

    # Group quotes by tax_year
    quotes_by_year = {}
    for quote in all_quotes:
        key = str(quote.tax_year)
        if key not in quotes_by_year:
            quotes_by_year[key] = []
        quotes_by_year[key].append(quote)

    eligible_tax_years = []
    for ty in tax_years:
        if not ty.checklist_completed:
            continue
        if ty.advisor_id is not None:
            continue
        if ty.draft_tax_return_submitted or ty.final_tax_return_submitted:
            continue

        year_quotes = quotes_by_year.get(str(ty.year), [])
        
        # No quote at all → eligible
        if not year_quotes:
            eligible_tax_years.append({
                'id': ty.id,
                'year': ty.year,
                'deadline': ty.deadline.strftime("%Y-%m-%d") if ty.deadline else '',
                'rejected': False
            })
            continue

        # Check if all quotes for this year are rejected
        has_non_rejected = any(q.quote_status.lower() not in ['rejected'] for q in year_quotes if q.quote_status)
        if not has_non_rejected:
            eligible_tax_years.append({
                'id': ty.id,
                'year': ty.year,
                'deadline': ty.deadline.strftime("%Y-%m-%d") if ty.deadline else '',
                'rejected': True
            })


    advisor_ratings = {
        adv.id: db.session.query(func.avg(Feedback.rating)).filter_by(advisor_id=adv.id).scalar() or 0
        for adv in advisors
    }

    return render_template(
        'advisory.html',
        user=user,
        advisors=advisors_data,
        tax_years=tax_years,
        eligible_tax_years=eligible_tax_years,
        advisor_ratings=advisor_ratings
    )
