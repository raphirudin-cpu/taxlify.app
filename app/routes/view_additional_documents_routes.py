import os
import io
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort, current_app
from flask_login import login_required, current_user
from app.models import db, DocumentRequest, TaxYear, User
from app.security import tax_year_for_request, parse_int

view_additional_bp = Blueprint('additional_documents', __name__)

def update_tax_year_status(user_id, tax_year):
    pending = DocumentRequest.query.filter_by(
        user_id=user_id, tax_year_id=tax_year.id, downloaded_on=None
    ).count()
    if pending == 0:
        tax_year.status = 'Additional Documents Downloaded'
        db.session.commit()

def resolve_absolute_path(file_path, user_id, year):
    # If stored path is relative, rebuild it using app root
    if not os.path.isabs(file_path):
        return os.path.join(current_app.root_path, 'uploads', str(user_id), str(year), 'AdditionalDocuments', file_path)
    return file_path

@view_additional_bp.route('/additional_documents/view/<int:year>', methods=['GET', 'POST'])
@login_required
def view_additional_documents(year):
    customer_id = None
    if current_user.role in ('advisor', 'admin'):
        raw = request.form.get('user_id') if request.method == 'POST' else request.args.get('user_id')
        customer_id = parse_int(raw)
        if customer_id is None:
            flash("Kunden-ID erforderlich.", "error")
            return redirect(url_for('dashboard.dashboard'))

    # Enforces ownership (user) / advisor-client binding / admin access.
    tax_year = tax_year_for_request(year, customer_id=customer_id)
    if not tax_year:
        flash("Ungültiges Steuerjahr oder Zugriff verweigert.", "error")
        return redirect(url_for('dashboard.dashboard'))

    additional_documents = DocumentRequest.query.filter_by(
        user_id=tax_year.user_id, tax_year_id=tax_year.id
    ).all()

    # --- Individual download ---
    download_id = request.args.get('download_id')
    if download_id:
        try:
            document_id = int(download_id)
        except ValueError:
            abort(400, description="Invalid download_id")
        document = DocumentRequest.query.filter_by(
            id=document_id, user_id=tax_year.user_id, tax_year_id=tax_year.id
        ).first()
        if document:
            abs_path = resolve_absolute_path(document.file_path, tax_year.user_id, tax_year.year)
            if not os.path.exists(abs_path):
                flash("Datei nicht gefunden.", "error")
                return redirect(url_for('additional_documents.view_additional_documents', year=tax_year.year, user_id=tax_year.user_id))
            document.downloaded_on = datetime.utcnow()
            db.session.commit()
            update_tax_year_status(tax_year.user_id, tax_year)
            return send_file(
                abs_path,
                as_attachment=True,
                download_name=os.path.basename(abs_path),
                mimetype="application/pdf"
            )
        else:
            flash("Dokument nicht gefunden.", "error")
            return redirect(url_for('additional_documents.view_additional_documents', year=tax_year.year, user_id=tax_year.user_id))

    # --- Download all as in-memory ZIP ---
    if request.method == 'POST' and 'download_all' in request.form:
        user = User.query.get(tax_year.user_id)
        if user:
            firstname = user.firstname.strip().replace(" ", "_")
            lastname = user.lastname.strip().replace(" ", "_")
            username = f"{firstname}_{lastname}"
        else:
            username = str(tax_year.user_id)

        zip_filename = f"additional_documents_{username}_{tax_year.year}.zip"
        zip_buffer = io.BytesIO()

        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for document in additional_documents:
                    abs_path = resolve_absolute_path(document.file_path, tax_year.user_id, tax_year.year)
                    if abs_path and os.path.exists(abs_path):
                        with open(abs_path, 'rb') as f:
                            zipf.writestr(os.path.basename(abs_path), f.read())
                    else:
                        flash(f"File not found: {abs_path}", "error")
        except Exception:
            current_app.logger.exception("ZIP creation failed")
            flash("ZIP-Datei konnte nicht erstellt werden.", "error")
            return redirect(url_for('additional_documents.view_additional_documents', year=tax_year.year, user_id=tax_year.user_id))

        zip_buffer.seek(0)

        for document in additional_documents:
            document.downloaded_on = datetime.utcnow()
        db.session.commit()
        update_tax_year_status(tax_year.user_id, tax_year)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )

    from datetime import date
    return render_template(
        'view_additional_documents.html',
        tax_year=tax_year,
        additional_documents=additional_documents,
        client_user=User.query.get(tax_year.user_id),
        today=date.today(),
    )
