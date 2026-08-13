from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, TaxYear, ChecklistAnswer, RequiredDocument
from app.utils.questions import questions, document_names  # questions + upload-slot labels

checklist_bp = Blueprint('checklist', __name__)

@checklist_bp.route('/checklist/<int:year>', methods=['GET', 'POST'])
@login_required
def checklist(year):
    user = current_user
    step = int(request.args.get('step', 1))  # Default to step 1 if not provided

    tax_year = TaxYear.query.filter_by(year=year, user_id=user.id).first()
    if not tax_year:
        flash("Ungültiges Steuerjahr.", "error")
        return redirect(url_for('dashboard.dashboard'))

    total = len(questions)

    if request.method == 'POST':
        step = int(request.form.get('step', step))  # Get step from form to ensure it's updated
        answer = request.form.get('answers', '').strip()

        if not answer:
            flash("Bitte beantworte die Frage.", "error")
            return render_template('checklist.html', tax_year=tax_year, step=step,
                                   question=questions.get(step), total=total, saved_answer=answer)

        # Retrieve the question details
        question_data = questions.get(step, {})
        question_requires_doc = question_data.get("requires_document", False)

        # Determine the numeric document flag (1 if required, 0 if not)
        if question_requires_doc:
            if step == 20:
                # For step 20, require a document if answer is either "Angestellt" or "Selbständig"
                doc_flag = 1 if answer in ["Angestellt", "Selbständig"] else 0
            else:
                # For other steps, require a document if answer (in lowercase) equals "ja"
                doc_flag = 1 if answer.lower() == "ja" else 0
        else:
            doc_flag = 0

        # ✅ Ensure each step has a unique entry
        existing_answer = ChecklistAnswer.query.filter_by(tax_year_id=tax_year.id, step=step, user_id=user.id).first()

        if existing_answer:
            print(f"Updating Step {step} answer...")
            existing_answer.answers = answer
            existing_answer.document_required = doc_flag
        else:
            print(f"Adding Step {step} answer...")
            new_entry = ChecklistAnswer(
                tax_year_id=tax_year.id,
                step=step,
                answers=answer,
                user_id=user.id,
                document_required=doc_flag
            )
            db.session.add(new_entry)

        try:
            db.session.commit()  # Commit the answer transaction
        except Exception as e:
            db.session.rollback()
            flash("Datenbankfehler.", "error")
            return render_template('checklist.html', tax_year=tax_year, step=step,
                                   question=questions.get(step), total=total, saved_answer=answer)

        # ✅ Determine the next step
        next_step = step + 1
        if "skip_if" in question_data and answer in question_data["skip_if"]:
            next_step = question_data["skip_if"][answer]

        # ✅ Final Step Completion
        if next_step > len(questions):
            tax_year.checklist_completed = True
            tax_year.status = "Checklist Completed"
            required_docs_count = RequiredDocument.query.filter_by(tax_year_id=tax_year.id).count()
            if required_docs_count == 0:
                tax_year.uploaded_documents = 1
            db.session.commit()
            flash("Checkliste abgeschlossen.", "success")
            return redirect(url_for('dashboard.dashboard'))

        # ✅ Save required document entry if doc_flag is 1 (without redirecting to an upload page)
        if doc_flag == 1:
            print(f"Saving required document for Step {step}...")
            required_doc = RequiredDocument(
                user_id=user.id,
                tax_year_id=tax_year.id,
                document_name=document_names.get(step) or question_data["question"]
            )
            db.session.add(required_doc)
            db.session.commit()

        return redirect(url_for('checklist.checklist', year=year, step=next_step))

    saved = ChecklistAnswer.query.filter_by(tax_year_id=tax_year.id, step=step, user_id=user.id).first()
    saved_answer = saved.answers if saved else None
    return render_template('checklist.html', tax_year=tax_year, step=step,
                           question=questions.get(step), total=total, saved_answer=saved_answer)
