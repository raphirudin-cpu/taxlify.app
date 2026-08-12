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
        flash("Fehlende Angaben.", "error")
        return redirect(url_for('dashboard.dashboard'))

    reason = (request.form.get('comment') or '').strip() or None

    try:
        # Retrieve the TaxYear record for the current user and specified tax year.
        tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year_value).first()
        if not tax_year_record:
            raise Exception("Steuerjahr nicht gefunden.")

        if action == 'accept':
            tax_year_record.draft_tax_return_submitted = 1
            tax_year_record.draft_tax_return_approved = 1
            tax_year_record.draft_rejection_comment = None
            tax_year_record.status = 'Draft tax return approved'
            flash("Entwurf angenommen.", "success")
        elif action == 'reject':
            tax_year_record.draft_tax_return_submitted = 0
            tax_year_record.draft_tax_return_approved = 0
            tax_year_record.draft_rejection_comment = reason   # why the client rejected the draft
            tax_year_record.status = 'Draft tax return rejected'
            flash("Entwurf abgelehnt.", "success")
        elif action == 'draft':
            tax_year_record.draft_tax_return_submitted = 1
            tax_year_record.draft_tax_return_approved = 0
            tax_year_record.status = 'Draft tax return submitted'
            flash("Entwurf eingereicht.", "success")
        else:
            raise Exception("Invalid action.")

        db.session.commit()
        log_action('draft.' + action, target_type='tax_year', target_id=tax_year_value, detail=reason)
    except SQLAlchemyError:
        db.session.rollback()
        flash("Fehler beim Aktualisieren des Entwurfs.", "error")
    except Exception as e:
        db.session.rollback()
        flash(str(e) if str(e) else "Fehler.", "error")

    return redirect(url_for('dashboard.dashboard'))
