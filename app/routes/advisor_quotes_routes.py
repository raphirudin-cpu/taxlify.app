import os
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from app.models import db, Quote, User, TaxYear, Advisor
from app.security import require_role, current_advisor

advisor_quotes_bp = Blueprint('advisor_quotes', __name__, url_prefix='/advisor')

@advisor_quotes_bp.route('/quotes')
@login_required
@require_role('advisor', 'admin')
def advisor_quotes():
    # find advisor ID (admins without one go to settings)
    advisor_record = current_advisor()
    if not advisor_record:
        if current_user.role == 'admin':
            return redirect(url_for('admin_settings.advisor_settings'))
        flash("You are not part of an Advisor Company yet, reach out to your manager.", "error")
        return render_template('advisor_quotes.html',
                               accepted_quotes=[], submitted_quotes=[], quote_requests=[])

    advisor_id = advisor_record.id

    # 1) Accepted quotes
    accepted_statuses = ['Accepted', 'Draft Tax Return in Review', 'Tax Return Approved']
    ac_q = (
        db.session.query(Quote, User, TaxYear)
          .join(User, Quote.user_id == User.id)
          .join(TaxYear, (Quote.tax_year == TaxYear.year) & (Quote.user_id == TaxYear.user_id))
          .filter(Quote.advisor_id == advisor_id,
                  Quote.quote_status.in_(accepted_statuses))
          .order_by(Quote.tax_year.desc())
          .all()
    )
    accepted_quotes = [{
        'id': q.id,
        'tax_year': q.tax_year,
        'user_id': q.user_id,
        'name': u.lastname,
        'surname': u.firstname,
        'deadline': ty.deadline,
        'quote_status': q.quote_status,
        'quote_amount': q.quote_amount,
        'final_submitted': q.final_submitted,
        'accepted_on': q.accepted_on,
        'file_path': q.file_path
    } for q, u, ty in ac_q]

    # 2) Submitted (In Review)
    inrev_q = (
        db.session.query(Quote, User)
          .join(User, Quote.user_id == User.id)
          .filter(Quote.advisor_id == advisor_id,
                  Quote.quote_status == 'In Review')
          .order_by(Quote.tax_year.desc(), Quote.created_at.desc())
          .all()
    )
    submitted_quotes = [{
        'id': q.id,
        'tax_year': q.tax_year,
        'user_id': q.user_id,
        'name': u.lastname,
        'surname': u.firstname,
        'quote_amount': q.quote_amount,
        'quote_status': q.quote_status,
        'submitted_on': getattr(q, 'submitted_on', None),
        'file_path': q.file_path
    } for q, u in inrev_q]

    # 3) Pending requests
    pend_q = (
        db.session.query(Quote, User)
          .join(User, Quote.user_id == User.id)
          .filter(Quote.advisor_id == advisor_id,
                  Quote.quote_status == 'Pending')
          .order_by(Quote.tax_year.desc(), Quote.created_at.desc())
          .all()
    )
    quote_requests = [{
        'id': q.id,
        'tax_year': q.tax_year,
        'user_id': q.user_id,
        'name': u.lastname,
        'surname': u.firstname,
        'created_at': q.created_at,
        'file_path': q.file_path
    } for q, u in pend_q]

    return render_template(
        'advisor_quotes.html',
        accepted_quotes=accepted_quotes,
        submitted_quotes=submitted_quotes,
        quote_requests=quote_requests
    )

@advisor_quotes_bp.route('/download/<int:quote_id>')
@login_required
def download_quote_file(quote_id):
    quote = Quote.query.get_or_404(quote_id)

    # check advisor permission
    advisor_record = current_advisor()
    if not advisor_record or quote.advisor_id != advisor_record.id:
        flash("Access denied.", "danger")
        return redirect(url_for('advisor_quotes.advisor_quotes'))

    if not quote.file_path or not os.path.isfile(quote.file_path):
        flash("File not found.", "error")
        return redirect(url_for('advisor_quotes.advisor_quotes'))

    return send_file(quote.file_path, as_attachment=True)
