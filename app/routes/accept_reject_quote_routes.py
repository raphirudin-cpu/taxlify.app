from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Quote, TaxYear
from app.audit import log_action
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

quote_action_bp = Blueprint('quote_action', __name__)

@quote_action_bp.route('/quote_action', methods=['POST'])
@login_required
def quote_action():
    user_id = current_user.id
    tax_year = request.form.get('tax_year')
    advisor_id = request.form.get('advisor_id')
    action = request.form.get('action')

    if not (tax_year and advisor_id and action):
        flash("Missing required data.", "error")
        return redirect(url_for('dashboard.dashboard'))

    try:
        if action == 'accept':
            # Retrieve the Quote record for acceptance
            quote = Quote.query.filter_by(user_id=user_id, tax_year=tax_year).first()
            if not quote:
                raise Exception("Quote not found for acceptance.")
            # Update quote status
            quote.quote_status = 'Accepted'
            quote.accepted_on = datetime.utcnow()
            
            # Update the TaxYear record: assign the advisor and set the status
            tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
            if not tax_year_record:
                raise Exception("Tax year record not found.")
            tax_year_record.advisor_id = advisor_id
            tax_year_record.status = 'Quote accepted'
            
            flash("Quote accepted successfully.", "success")
        elif action == 'reject':
            # Retrieve the Quote record for rejection
            quote = Quote.query.filter_by(user_id=user_id, tax_year=tax_year).first()
            if not quote:
                raise Exception("Quote not found for rejection.")
            # Update quote status
            quote.quote_status = 'Rejected'
            
            # Update the TaxYear record status
            tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
            if not tax_year_record:
                raise Exception("Tax year record not found.")
            tax_year_record.status = 'Quote rejected'
            
            flash("Quote rejected successfully.", "success")
        else:
            raise Exception("Invalid action.")
        # Commit once after all changes
        db.session.commit()
        log_action('quote.' + action, target_type='tax_year', target_id=tax_year)
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error updating quote.", "error")
    except Exception as e:
        db.session.rollback()
        flash("Error.", "error")

    return redirect(url_for('dashboard.dashboard'))
