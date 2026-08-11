import os
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, TaxYear, DocumentRequest  # DocumentRequest's tablename is 'additional_document_requests'
from app.security import require_role
from app.helpers import upload_path, commit_or_rollback

upload_additional_bp = Blueprint('upload_additional_documents', __name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_additional_bp.route('/upload_additional_documents/<int:year>', methods=['GET', 'POST'])
@login_required
@require_role('user')
def upload_additional_documents(year):
    user_id = current_user.id

    # Retrieve the TaxYear record for the given year and user.
    tax_year = TaxYear.query.filter_by(year=year, user_id=user_id).first()
    if not tax_year:
        flash("Tax year not found.", "error")
        return render_template('upload_additional_documents.html', tax_year=year, additional_documents=[])
    
    tax_year_id = tax_year.id

    # Query all additional document requests for this tax year and user.
    doc_requests = DocumentRequest.query.filter_by(tax_year_id=tax_year_id, user_id=user_id).all()

    if request.method == 'GET':
        # Prepare data for each document request.
        additional_documents_data = [
            {
                'id': doc.id,
                'request_text': doc.request_text,
                'file_path': doc.file_path  # This can be used to display upload status.
            }
            for doc in doc_requests
        ]
        return render_template('upload_additional_documents.html', tax_year=year, additional_documents=additional_documents_data)
    
    # POST: Process the file upload for a specific additional document request.
    if 'file' not in request.files:
        flash("No file part in the request.", "error")
        return redirect(url_for('upload_additional_documents.upload_additional_documents', year=year))
    
    file = request.files['file']
    document_id = request.form.get('id')
    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        document_id = None

    if file.filename == '':
        flash("No selected file.", "error")
        return redirect(url_for('upload_additional_documents.upload_additional_documents', year=year))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        target_dir = upload_path(user_id, year, "additional_documents")
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, filename)
        file.save(file_path)

        # Update the corresponding DocumentRequest record.
        doc_request = DocumentRequest.query.filter_by(
            id=document_id, user_id=user_id, tax_year_id=tax_year_id
        ).first()
        if doc_request:
            doc_request.file_path = file_path
            doc_request.uploaded_on = datetime.utcnow()
            tax_year.status = "Additional documents uploaded"
            tax_year.additional_documents_uploaded = 1
            if commit_or_rollback():
                flash("File uploaded successfully.", "success")
            else:
                flash("Error saving the uploaded file.", "error")
            return redirect(url_for('upload_additional_documents.upload_additional_documents', year=year))
        else:
            flash("Document request not found.", "error")
            return redirect(url_for('upload_additional_documents.upload_additional_documents', year=year))
    else:
        flash("Invalid file type.", "error")
        return redirect(url_for('upload_additional_documents.upload_additional_documents', year=year))
