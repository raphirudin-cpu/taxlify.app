from flask import Blueprint, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Quote, TaxYear, Advisor  # Make sure Advisor is imported

quote_bp = Blueprint('quote', __name__)

@quote_bp.route('/request_quote', methods=['POST'])
@login_required
def request_quote():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    user_id = current_user.id

    # Collect form data
    advisor_id = request.form.get('advisor_id')
    tax_year = request.form.get('tax_year')
    deadline = request.form.get('deadline')

    # Validate and convert advisor_id to integer
    try:
        advisor_id = int(advisor_id)
    except (ValueError, TypeError):
        flash("Invalid advisor id.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Check if the advisor exists in the Advisor table
    advisor = Advisor.query.get(advisor_id)
    if not advisor:
        flash("Advisor not found.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Check if a quote for this year already exists regardless of the advisor
    existing_quote = Quote.query.filter_by(user_id=user_id, tax_year=tax_year).first()

    if existing_quote:
        if existing_quote.quote_status == 'Rejected':  # Adjust if needed
            existing_quote.advisor_id = advisor.id  # Use advisor.id (from Advisor table)
            existing_quote.quote_status = 'Pending'
            existing_quote.deadline = deadline

            # Update the tax year's status
            tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
            if tax_year_record:
                tax_year_record.status = "Quote requested"

            try:
                db.session.commit()
                flash("Quote updated and re-requested successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error updating and re-requesting quote.", "error")
        else:
            flash(f"A quote for the year {tax_year} already exists with a different status.", "error")
            return redirect(url_for('dashboard.dashboard'))
    else:
        # Insert a new quote using advisor.id
        new_quote = Quote(
            user_id=user_id,
            advisor_id=advisor.id,
            tax_year=tax_year,
            deadline=deadline,
            quote_status='Pending'
        )
        db.session.add(new_quote)

        # Update the tax year's status
        tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
        if tax_year_record:
            tax_year_record.status = "Quote requested"
        # Optionally, create a new TaxYear record if one doesn't exist:
        # else:
        #     new_tax_year = TaxYear(user_id=user_id, year=tax_year, status="Quote requested")
        #     db.session.add(new_tax_year)

        try:
            db.session.commit()
            flash("Quote requested successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash("Error requesting quote.", "error")

    return redirect(url_for('dashboard.dashboard'))
