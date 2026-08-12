from flask import Blueprint, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Quote, Advisor
from app.security import require_role, current_advisor
from app.helpers import commit_or_rollback

reject_quote_bp = Blueprint('reject_quote', __name__)

@reject_quote_bp.route('/reject_quote', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def reject_quote():
    # Get the quote id from the form
    quote_id = request.form.get('id')
    if not quote_id:
        flash("Keine Offerten-ID angegeben.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    # Retrieve the advisor record for the current user
    advisor_record = current_advisor()
    if not advisor_record:
        flash("Treuhänder-Datensatz nicht gefunden.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    
    # Use the advisor's id from the Advisor table
    advisor_id = advisor_record.id

    # Update the quote's status to an allowed value ('Rejected')
    quote = Quote.query.filter_by(id=quote_id, advisor_id=advisor_id).first()
    if not quote:
        flash("Offerte nicht gefunden oder keine Berechtigung.", "error")
    else:
        quote.quote_status = 'Rejected'
        if commit_or_rollback():
            flash("Anfrage abgelehnt.", "success")
        else:
            flash("Fehler beim Ablehnen der Anfrage.", "error")

    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
