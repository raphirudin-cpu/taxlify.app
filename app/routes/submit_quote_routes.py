import os
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Quote, Advisor, TaxYear, Subscription, Plan
from app.security import require_role, current_advisor
from app.helpers import commit_or_rollback, upload_path

submit_quote_bp = Blueprint('submit_quote', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 5000000  # 5 MB limit

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@submit_quote_bp.route('/submit_quote', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def submit_quote():
    quote_id = request.form.get('id')
    user_id = request.form.get('user_id')
    tax_year = int(request.form.get('tax_year'))
    quote_amount = request.form.get('quote_amount')
    comment = request.form.get('comment')

    advisor_record = current_advisor()
    if not advisor_record:
        flash("Treuhänder-Datensatz nicht gefunden.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    advisor_id = advisor_record.id

    # Check slot availability for this tax year
    subs = Subscription.query.filter_by(user_id=current_user.id).all()
    available_for_year = False
    for sub in subs:
        plan = Plan.query.get(sub.plan_id)
        purchased = plan.base_slots + sub.slots
        used = TaxYear.query.filter_by(advisor_id=advisor_id, year=sub.tax_year).count()
        remaining = purchased - used
        if sub.tax_year == tax_year and remaining > 0:
            available_for_year = True
            break

    if not available_for_year:
        flash("Für dieses Steuerjahr sind keine Slots mehr verfügbar.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    file_path = None
    file = request.files.get('file')
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("Nur PDF-, DOC- und DOCX-Dateien sind erlaubt.", "error")
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))

        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > MAX_FILE_SIZE:
            flash("Die Datei ist zu gross.", "error")
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))

        upload_dir = upload_path(user_id, tax_year, 'Quotes')
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(file.filename)
        target_file = os.path.join(upload_dir, filename)
        try:
            file.save(target_file)
            file_path = target_file
        except Exception as e:
            flash("Fehler beim Hochladen der Datei.", "error")
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    try:
        quote_amount = float(quote_amount)
        if quote_amount < 0:
            flash("Ungültiger Offertenbetrag.", "error")
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    except ValueError:
        flash("Ungültiger Offertenbetrag.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    quote = Quote.query.filter_by(id=quote_id, advisor_id=advisor_id).first()
    if not quote:
        flash("Offerte nicht gefunden oder keine Berechtigung.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    quote.quote_amount = quote_amount
    quote.comment = comment
    quote.quote_status = 'In Review'
    quote.submitted_on = datetime.now()
    if file_path is not None:
        quote.file_path = file_path

    tax_year_record = TaxYear.query.filter_by(user_id=user_id, year=tax_year).first()
    if tax_year_record:
        tax_year_record.status = "Review Quote"

    if commit_or_rollback():
        flash("Offerte gesendet.", "success")
    else:
        flash("Fehler beim Senden der Offerte.", "error")

    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
