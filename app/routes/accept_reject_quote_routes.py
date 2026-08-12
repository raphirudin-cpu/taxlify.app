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
        flash("Fehlende Angaben.", "error")
        return redirect(url_for('dashboard.dashboard'))

    reason = (request.form.get('comment') or '').strip() or None

    try:
        if action == 'accept':
            quote = Quote.query.filter_by(user_id=user_id, tax_year=tax_year).first()
            if not quote:
                raise Exception("Quote not found for acceptance.")
            quote.quote_status = 'Accepted'
            quote.accepted_on = datetime.utcnow()

            tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
            if not tax_year_record:
                raise Exception("Steuerjahr nicht gefunden.")
            tax_year_record.advisor_id = advisor_id
            tax_year_record.assigned_on = datetime.utcnow()   # for "newest clients" at advisor side
            tax_year_record.status = 'Quote accepted'

            flash("Offerte angenommen.", "success")
        elif action == 'reject':
            quote = Quote.query.filter_by(user_id=user_id, tax_year=tax_year).first()
            if not quote:
                raise Exception("Quote not found for rejection.")
            quote.quote_status = 'Rejected'
            quote.rejection_reason = reason   # e.g. "zu teuer"

            tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
            if not tax_year_record:
                raise Exception("Steuerjahr nicht gefunden.")
            tax_year_record.status = 'Quote rejected'

            flash("Offerte abgelehnt.", "success")
        else:
            raise Exception("Invalid action.")
        # Commit once after all changes
        db.session.commit()
        log_action('quote.' + action, target_type='tax_year', target_id=tax_year, detail=reason)
    except SQLAlchemyError:
        db.session.rollback()
        flash("Fehler beim Aktualisieren der Offerte.", "error")
    except Exception as e:
        db.session.rollback()
        flash(str(e) if str(e) else "Fehler.", "error")

    return redirect(url_for('dashboard.dashboard'))
