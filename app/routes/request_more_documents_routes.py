from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, TaxYear, DocumentRequest
from app.security import require_role, tax_year_for_request
from app.helpers import commit_or_rollback

request_more_documents_bp = Blueprint('request_more_documents', __name__)

# New route: sets the customer ID in the session and redirects to the request form.
@request_more_documents_bp.route('/set_customer/<int:customer_id>/<int:year>', methods=['GET'])
@login_required
@require_role('advisor', 'admin')
def set_customer(customer_id, year):
    session['customer_id'] = customer_id
    return redirect(url_for('request_more_documents.request_more_documents', year=year))

# Existing route: loads the request form and processes document requests.
@request_more_documents_bp.route('/request_more_documents/<int:year>', methods=['GET', 'POST'])
@login_required
def request_more_documents(year):
    # For advisors/admins, retrieve the customer ID from the session.
    if current_user.role in ('advisor', 'admin'):
        customer_id = session.get('customer_id')
        if not customer_id:
            flash("Kunden-ID erforderlich.", "error")
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    else:
        customer_id = current_user.id

    if request.method == 'GET':
        # Render the form, passing the customer ID so the hidden input is populated.
        return render_template('request_more_documents.html', year=year, user_id=customer_id)
    
    # POST: Process the submitted document requests.
    requests_list = request.form.getlist('requests')

    # Retrieve the TaxYear record, enforcing advisor-client binding / ownership.
    tax_year = tax_year_for_request(year, customer_id=customer_id)
    if not tax_year:
        flash("Steuerjahr nicht gefunden oder Zugriff verweigert.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    
    # Save each non-empty document request.
    for req_text in requests_list:
        if req_text.strip():
            doc_req = DocumentRequest(
                tax_year_id=tax_year.id, 
                user_id=customer_id,
                request_text=req_text.strip()
            )
            db.session.add(doc_req)

    # Set the additional_documents_request column to 1
    tax_year.additional_documents_request = 1

    tax_year.status = 'Additional documents requested'

    if commit_or_rollback():
        flash("Dokumentenanfragen gespeichert.", "success")
    else:
        flash("Fehler beim Speichern der Anfragen.", "error")
    # Optionally, clear the customer_id from the session after processing.
    session.pop('customer_id', None)
    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
