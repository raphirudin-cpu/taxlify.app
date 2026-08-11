import os
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, RequiredDocument, TaxYear
from app.security import require_role
from app.helpers import upload_path
from datetime import datetime

upload_bp = Blueprint('upload_documents', __name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_bp.route('/upload_documents/<int:year>', methods=['GET', 'POST'])
@login_required
@require_role('user')
def upload_documents(year):
    user_id = current_user.id

    # Query for the tax year using the given year and user_id
    tax_year = TaxYear.query.filter_by(year=year, user_id=user_id).first()
    if not tax_year:
        flash("Tax year not found.", "error")
        return render_template('upload_documents.html', tax_year=year, required_documents=[])
    
    tax_year_id = tax_year.id

    # Fetch required documents
    required_documents = RequiredDocument.query.filter_by(user_id=user_id, tax_year_id=tax_year_id).all()

    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file part'})
        file = request.files['file']
        document_id = request.form.get('id')
        try:
            document_id = int(document_id)
        except (TypeError, ValueError):
            document_id = None

        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No selected file'})
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Single canonical uploads root (see app.helpers.upload_path).
            target_dir = upload_path(user_id, year, "documents")
            os.makedirs(target_dir, exist_ok=True)

            file_path = os.path.join(target_dir, filename)
            file.save(file_path)

            # Update or insert RequiredDocument
            if document_id:
                document = RequiredDocument.query.filter_by(
                    user_id=user_id, tax_year_id=tax_year_id, id=document_id
                ).first()
            else:
                document = None

            if document:
                document.file_path = file_path
                document.uploaded_on = datetime.utcnow()
            else:
                new_document = RequiredDocument(
                    user_id=user_id,
                    tax_year_id=tax_year_id,
                    document_name=filename,
                    file_path=file_path,
                    uploaded_on=datetime.utcnow()
                )
                db.session.add(new_document)

            db.session.commit()

            # Check if all documents have been uploaded
            all_docs = RequiredDocument.query.filter_by(user_id=user_id, tax_year_id=tax_year_id).all()
            if all_docs and all(doc.file_path for doc in all_docs):
                tax_year.uploaded_documents = 1
                tax_year.status = "Documents uploaded"
                db.session.commit()

            return jsonify({'status': 'success', 'message': 'File uploaded successfully.'})

    documents_json = [{'id': doc.id, 'document_name': doc.document_name} for doc in required_documents]
    return render_template('upload_documents.html', tax_year=year, required_documents=documents_json)
