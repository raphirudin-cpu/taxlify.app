from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, TaxYear
from app.audit import log_action
from sqlalchemy.exc import SQLAlchemyError

draft_tax_return_action_bp = Blueprint('draft_tax_return_action', __name__)

@draft_tax_return_action_bp.route('/draft_tax_return_action', methods=['POST'])
@login_required
def draft_tax_return_action():
    user_id = current_user.id
    tax_year_value = request.form.get('tax_year')
    action = request.form.get('action')

    if not (tax_year_value and action):
        flash("Missing required data.", "error")
        return redirect(url_for('dashboard.dashboard'))

    try:
        # Retrieve the TaxYear record for the current user and specified tax year.
        tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year_value).first()
        if not tax_year_record:
            raise Exception("Tax year record not found.")

        if action == 'accept':
            # Accept the draft tax return:
            # Mark as submitted and approved, update status accordingly.
            tax_year_record.draft_tax_return_submitted = 1
            tax_year_record.draft_tax_return_approved = 1
            tax_year_record.status = 'Draft tax return approved'
            flash("Draft tax return accepted successfully.", "success")
        elif action == 'reject':
            # Reject the draft tax return:
            # Reset submission and approval flags, update status.
            tax_year_record.draft_tax_return_submitted = 0
            tax_year_record.draft_tax_return_approved = 0
            tax_year_record.status = 'Draft tax return rejected'
            flash("Draft tax return rejected successfully.", "success")
        elif action == 'draft':
            # Mark the draft tax return as submitted but not yet approved.
            tax_year_record.draft_tax_return_submitted = 1
            tax_year_record.draft_tax_return_approved = 0
            tax_year_record.status = 'Draft tax return submitted'
            flash("Draft tax return submitted successfully.", "success")
        else:
            raise Exception("Invalid action.")

        db.session.commit()
        log_action('draft.' + action, target_type='tax_year', target_id=tax_year_value)
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error updating draft tax return.", "error")
    except Exception as e:
        db.session.rollback()
        flash("Error.", "error")

    return redirect(url_for('dashboard.dashboard'))
