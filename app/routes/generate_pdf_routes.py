import io
from flask import Blueprint, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models import db, ChecklistAnswer, TaxYear, User
from app.security import advisor_is_bound
from app.utils.questions import questions  # Your questions dictionary

generate_pdf_bp = Blueprint('generate_pdf', __name__)

@generate_pdf_bp.route('/generate_pdf/<int:user_id>/<int:tax_year_id>')
@login_required
def generate_pdf(user_id, tax_year_id):
    # Retrieve tax year and user
    tax_year = TaxYear.query.filter_by(id=tax_year_id, user_id=user_id).first()
    if not tax_year:
        flash("Ungültiges Steuerjahr.", "error")
        return redirect(url_for('dashboard.dashboard'))

    user = User.query.get(user_id)
    if not user:
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Authorization: the client themselves, an admin, or the bound advisor.
    authorized = (
        current_user.id == user_id
        or current_user.role == 'admin'
        or (current_user.role == 'advisor' and advisor_is_bound(user_id, tax_year.year))
    )
    if not authorized:
        flash("Zugriff verweigert.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Get checklist answers
    answers = ChecklistAnswer.query.filter_by(tax_year_id=tax_year_id, user_id=user_id).all()
    checklist = {answer.step: answer.answers for answer in answers}

    # Generate PDF in memory
    buffer = io.BytesIO()
    try:
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Checklist for Tax Year {tax_year.year}")
        c.drawString(50, height - 70, f"User: {user.firstname} {user.lastname}")

        y = height - 100
        c.setFont("Helvetica", 12)

        for step, question in questions.items():
            if step in checklist:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, y, f"{question['question']}")
                y -= 20
                c.setFont("Helvetica", 12)
                c.drawString(60, y, f"Answer: {checklist[step]}")
                y -= 30
                if y < 50:
                    c.showPage()
                    y = height - 50

        c.save()
        buffer.seek(0)
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        flash("Fehler beim Erstellen des PDF.", "error")
        return redirect(url_for('dashboard.dashboard'))

    # Download filename
    filename = f"Checklist_{user.firstname}_{user.lastname}_{tax_year.year}.pdf".replace(" ", "_")

    # Return the file as a download
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
