"""Advisor-triggered AI analysis of an uploaded client document."""
import json

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.models import db, RequiredDocument, TaxYear, DocumentAnalysis
from app.security import require_role, advisor_is_bound, parse_int
from app.helpers import commit_or_rollback
from app.audit import log_action
from app.services.ai_intake import analyze_document, AINotConfigured, AIAnalysisError

ai_intake_bp = Blueprint('ai_intake', __name__)


@ai_intake_bp.route('/advisor/analyze_document', methods=['POST'])
@login_required
@require_role('advisor', 'admin')
def analyze():
    doc_id = parse_int(request.form.get('required_document_id'))
    if doc_id is None:
        flash("Fehlende Angaben.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    doc = RequiredDocument.query.get(doc_id)
    if not doc:
        flash("Dokument nicht gefunden.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))
    if not doc.file_path:
        flash("Für dieses Dokument wurde noch keine Datei hochgeladen.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    ty = TaxYear.query.filter_by(id=doc.tax_year_id).first()
    year = ty.year if ty else None
    if year is None or not advisor_is_bound(doc.user_id, year):
        flash("Zugriff verweigert.", "error")
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    back = redirect(url_for('documents.view_documents', year=year, user_id=doc.user_id))

    try:
        result = analyze_document(doc.file_path, document_name=(doc.file_path or '').split('/')[-1])
    except AINotConfigured:
        flash("KI-Analyse ist nicht konfiguriert (ANTHROPIC_API_KEY fehlt).", "error")
        return back
    except AIAnalysisError as e:
        flash(str(e), "error")
        return back

    # Replace any prior analysis for this document.
    DocumentAnalysis.query.filter_by(required_document_id=doc.id).delete()
    db.session.add(DocumentAnalysis(
        required_document_id=doc.id, user_id=doc.user_id, tax_year=year,
        doc_type=(result.get('doc_type') or '')[:100],
        summary=result.get('summary'),
        fields_json=json.dumps(result.get('fields') or [], ensure_ascii=False),
        confidence=(result.get('confidence') or '')[:20],
        model=(result.get('model') or '')[:60],
        created_by=current_user.id,
    ))
    if commit_or_rollback():
        log_action('document.analyze', target_type='required_document', target_id=doc.id,
                   detail=result.get('doc_type'))
        flash("KI-Analyse abgeschlossen.", "success")
    else:
        flash("Analyse konnte nicht gespeichert werden.", "error")
    return back
