from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Quote, TaxYear
from app.security import parse_int
from app.audit import log_action
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

quote_action_bp = Blueprint('quote_action', __name__)

@quote_action_bp.route('/quote_action', methods=['POST'])
@login_required
def quote_action():
    user_id = current_user.id
    tax_year = parse_int(request.form.get('tax_year'))
    advisor_id = parse_int(request.form.get('advisor_id'))
    action = request.form.get('action')

    if tax_year is None or advisor_id is None or action not in ('accept', 'reject'):
        flash("Fehlende oder ungültige Angaben.", "error")
        return redirect(url_for('dashboard.dashboard'))

    reason = (request.form.get('comment') or '').strip() or None

    # The quote must belong to this client, this year, AND the named advisor —
    # so a client can't engage an advisor who never quoted them.
    quote = Quote.query.filter_by(
        user_id=user_id, tax_year=tax_year, advisor_id=advisor_id
    ).first()
    if not quote:
        flash("Offerte nicht gefunden.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Only an offer the advisor has actually sent can be decided on. A still-
    # 'Pending' request (no offer yet) or an already-decided quote is rejected —
    # this is what keeps a client from bypassing the advisor's slot check by
    # accepting their own un-answered request.
    if quote.quote_status != 'In Review':
        flash("Für diese Offerte liegt aktuell keine Entscheidung an.", "error")
        return redirect(url_for('dashboard.dashboard'))

    tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
    if not tax_year_record:
        flash("Steuerjahr nicht gefunden.", "error")
        return redirect(url_for('dashboard.dashboard'))

    try:
        if action == 'accept':
            quote.quote_status = 'Accepted'
            quote.accepted_on = datetime.utcnow()
            tax_year_record.advisor_id = quote.advisor_id   # authoritative, not form-supplied
            tax_year_record.assigned_on = datetime.utcnow()  # for "newest clients" at advisor side
            tax_year_record.status = 'Quote accepted'
            flash("Offerte angenommen.", "success")
        else:  # reject
            quote.quote_status = 'Rejected'
            quote.rejection_reason = reason   # e.g. "zu teuer"
            tax_year_record.status = 'Quote rejected'
            flash("Offerte abgelehnt.", "success")
        db.session.commit()
        log_action('quote.' + action, target_type='tax_year', target_id=tax_year, detail=reason)
    except SQLAlchemyError:
        db.session.rollback()
        flash("Fehler beim Aktualisieren der Offerte.", "error")

    return redirect(url_for('dashboard.dashboard'))
