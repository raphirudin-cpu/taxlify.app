import os
from flask import request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from app.models import db, TaxYear
from app.security import require_role, tax_year_for_request, parse_int
from app.helpers import upload_path
from app.audit import log_action
from flask import Blueprint

submit_tax_return_bp = Blueprint('submit_tax_return', __name__)

MAX_FILE_SIZE = 5_000_000  # 5 MB
ALLOWED_EXTENSIONS = {'pdf', 'xlsx', 'xls', 'doc', 'docx'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@submit_tax_return_bp.route('/upload_tax_return', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def upload_tax_return():
    if 'tax_return_file' not in request.files:
        flash("Keine Datei oder Formulardaten empfangen.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    user_id = parse_int(request.form.get('user_id'))
    year = parse_int(request.form.get('tax_year_id'))  # form field carries the YEAR
    file = request.files['tax_return_file']

    if user_id is None or year is None:
        flash("Ungültige Angaben.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    # Ownership: the acting advisor must be bound to this client's tax year.
    tax_year_record = tax_year_for_request(year, customer_id=user_id)
    if not tax_year_record:
        flash("Steuerjahr nicht gefunden oder Zugriff verweigert.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    if not file.filename or not _allowed(file.filename):
        flash("Nicht unterstützte oder fehlende Datei.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    file.seek(0, os.SEEK_END)
    if file.tell() > MAX_FILE_SIZE:
        file.seek(0)
        flash("Datei ist zu gross.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    file.seek(0)

    if tax_year_record.draft_tax_return_submitted == 1:
        flash("Entwurf wurde bereits eingereicht.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    filename = secure_filename(file.filename)
    upload_directory = upload_path(user_id, year, "Tax Return", "Draft")
    os.makedirs(upload_directory, exist_ok=True)
    file_path = os.path.join(upload_directory, filename)

    try:
        file.save(file_path)
    except Exception:
        current_app.logger.exception("Draft tax return upload failed")
        flash("Fehler beim Hochladen der Datei.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    try:
        tax_year_record.draft_file_path = file_path
        tax_year_record.draft_tax_return_submitted = 1
        tax_year_record.status = "Draft tax return submitted"
        db.session.commit()
        log_action('draft.submit', target_type='tax_year', target_id=year, detail=f"user={user_id}")
        flash("Entwurf erfolgreich eingereicht.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Draft tax return DB update failed")
        flash("Fehler beim Speichern.", "error")

    return redirect(url_for('advisor_dashboard.advisor_dashboard'))
