from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, ChecklistAnswer, TaxYear
from app.security import tax_year_for_request, parse_int
from app.utils.questions import questions  # Import the questions dictionary

view_checklist_bp = Blueprint('view_checklist', __name__)

@view_checklist_bp.route('/checklist/view/<int:year>')
@login_required
def view_checklist(year):
    # Advisors/admins pass a customer id; ownership/binding is enforced below.
    customer_id = None
    if current_user.role in ('advisor', 'admin'):
        customer_id = parse_int(request.args.get('user_id'))
        if customer_id is None:
            flash("Kunden-ID erforderlich.", "error")
            return redirect(url_for('dashboard.dashboard'))

    tax_year = tax_year_for_request(year, customer_id=customer_id)
    if not tax_year:
        flash("Ungültiges Steuerjahr oder Zugriff verweigert.", "error")
        return redirect(url_for('dashboard.dashboard'))

    answers = ChecklistAnswer.query.filter_by(tax_year_id=tax_year.id, user_id=tax_year.user_id).all()
    checklist = {answer.step: answer.answers for answer in answers}

    return render_template('view_checklist.html', tax_year=tax_year, checklist=checklist, questions=questions)
