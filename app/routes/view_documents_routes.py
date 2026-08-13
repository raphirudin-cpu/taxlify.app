import os
import io
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort, current_app
from flask_login import login_required, current_user
from app.models import db, RequiredDocument, Quote, TaxYear, User
from app.security import tax_year_for_request, parse_int

view_documents_bp = Blueprint('documents', __name__)

def update_tax_year_status(user_id, tax_year):
    pending = RequiredDocument.query.filter_by(
        user_id=user_id, tax_year_id=tax_year.id, downloaded_on=None
    ).count()
    if pending == 0:
        tax_year.status = 'Documents Downloaded'
        db.session.commit()

@view_documents_bp.route('/documents/view/<int:year>', methods=['GET', 'POST'])
@login_required
def view_documents(year):
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

    uploaded_documents = RequiredDocument.query.filter_by(
        user_id=tax_year.user_id, tax_year_id=tax_year.id
    ).all()

    download_id = request.args.get('download_id')
    if download_id:
        try:
            document_id = int(download_id)
        except ValueError:
            abort(400, description="Invalid download_id")
        document = RequiredDocument.query.filter_by(
            id=document_id, user_id=tax_year.user_id, tax_year_id=tax_year.id
        ).first()
        if document:
            file_path = document.file_path
            if not os.path.exists(file_path):
                flash("Datei nicht gefunden.", "error")
                return redirect(url_for('documents.view_documents', year=tax_year.year, user_id=tax_year.user_id))
            document.downloaded_on = datetime.utcnow()
            db.session.commit()
            update_tax_year_status(tax_year.user_id, tax_year)
            return send_file(
                file_path,
                as_attachment=True,
                download_name=os.path.basename(file_path),
                mimetype="application/pdf"
            )
        else:
            flash("Dokument nicht gefunden.", "error")
            return redirect(url_for('documents.view_documents', year=tax_year.year, user_id=tax_year.user_id))

    # === Updated "Download All" section: in-memory ZIP ===
    if request.method == 'POST' and 'download_all' in request.form:
        user = User.query.get(tax_year.user_id)
        if user:
            firstname = user.firstname.strip().replace(" ", "_")
            lastname = user.lastname.strip().replace(" ", "_")
            username = f"{firstname}_{lastname}"
        else:
            username = str(tax_year.user_id)

        zip_filename = f"documents_{username}_{tax_year.year}.zip"
        zip_buffer = io.BytesIO()

        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for document in uploaded_documents:
                    file_path = document.file_path
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                            zipf.writestr(os.path.basename(file_path), file_data)
                    else:
                        flash(f"File not found: {file_path}", "error")
        except Exception:
            current_app.logger.exception("ZIP creation failed")
            flash("ZIP-Datei konnte nicht erstellt werden.", "error")
            return redirect(url_for('documents.view_documents', year=tax_year.year, user_id=tax_year.user_id))

        zip_buffer.seek(0)

        for document in uploaded_documents:
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
    from app.models import DocumentAnalysis
    from app.services.ai_intake import is_configured as ai_is_configured
    analyses_by_doc = {}
    doc_ids = [d.id for d in uploaded_documents]
    if doc_ids:
        for a in DocumentAnalysis.query.filter(DocumentAnalysis.required_document_id.in_(doc_ids)).all():
            analyses_by_doc[a.required_document_id] = a
    return render_template(
        'view_documents.html',
        tax_year=tax_year,
        uploaded_documents=uploaded_documents,
        client_user=User.query.get(tax_year.user_id),
        today=date.today(),
        analyses_by_doc=analyses_by_doc,
        ai_enabled=(current_user.role in ('advisor', 'admin') and ai_is_configured()),
    )
