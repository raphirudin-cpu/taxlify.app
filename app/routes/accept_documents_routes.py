from flask import Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.models import db
from app.security import require_role, tax_year_for_request, parse_int
from app.audit import log_action
from sqlalchemy.exc import SQLAlchemyError

documents_action_bp = Blueprint('documents_action', __name__)

@documents_action_bp.route('/documents_action', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def documents_action():
    # Retrieve the customer user id and tax year (named tax_year_id) from the form.
    customer_id_int = parse_int(request.form.get('user_id'))
    tax_year_int = parse_int(request.form.get('tax_year_id'))
    action = request.form.get('action')

    # Check that required form fields were provided.
    if customer_id_int is None or tax_year_int is None or not action:
        flash("Fehlende oder ungültige Angaben.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    try:
        # Ownership: acting advisor must be bound to this client's tax year.
        tax_year_record = tax_year_for_request(tax_year_int, customer_id=customer_id_int)
        if not tax_year_record:
            raise Exception("Steuerjahr nicht gefunden oder Zugriff verweigert.")

        # Update the documents_approved field and tax year status based on the action.
        if action == 'accept':
            tax_year_record.documents_approved = 1
            tax_year_record.status = 'Documents approved'
            flash("Dokumente freigegeben.", "success")
        elif action == 'reject':
            tax_year_record.documents_approved = 0
            tax_year_record.status = 'Documents rejected'
            flash("Dokumente abgelehnt.", "success")
        else:
            raise Exception("Invalid action.")
        
        db.session.commit()
        log_action('documents.' + action, target_type='tax_year', target_id=tax_year_int)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("documents_action DB error")
        flash("Fehler beim Aktualisieren der Dokumente.", "error")
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning("documents_action failed: %s", e)
        flash(str(e), "error")

    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
