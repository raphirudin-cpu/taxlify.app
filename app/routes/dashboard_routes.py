from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_login import login_required, current_user, logout_user
from app.models import db, User, TaxYear, Quote, Feedback, Advisor
from app.security import tax_year_for_request, advisor_is_bound, send_stored_file
from datetime import datetime, timedelta
import os

# Define Blueprint
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    flash_message = request.args.get('flash')
    if flash_message:
        flash(flash_message, "success")

    user_id = current_user.id
    user = User.query.get(user_id)

    if not user:
        logout_user() 
        return redirect(url_for('auth.login'))

    # Check if this is the first login; if so, redirect accordingly.
    if user.first_login == 0:
        flash("Please update your settings on your first login.", "error")
        if user.role in ('admin', 'advisor'):
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))
        else:
            return redirect(url_for('settings.settings'))

    # Redirect advisors to their dashboard
    if user.role in ('advisor', 'admin'):
        return redirect(url_for('advisor_dashboard.advisor_dashboard'))

    # Handle opening a new tax year
    if request.method == 'POST' and 'open_tax_year' in request.form:
        year = request.form['year']
        deadline = request.form['deadline']

        existing_tax_year = TaxYear.query.filter_by(user_id=user_id, year=year).first()
        if existing_tax_year:
            flash(f"The tax year {year} is already opened.", "error")
        else:
            new_tax_year = TaxYear(user_id=user_id, year=year, status='Open', deadline=deadline, advisor_id=None)
            db.session.add(new_tax_year)
            db.session.commit()
            flash("Tax year opened successfully.", "success")

    # Fetch tax years
    tax_years = TaxYear.query.filter_by(user_id=user_id).order_by(TaxYear.year.desc()).all()
    
    # Fetch quotes
    quotes = Quote.query.filter_by(user_id=user_id).all()
    requested_quotes = {q.tax_year: q for q in quotes}

    # Fetch feedback
    feedbacks = {f"{f.tax_year}_{f.advisor_id}": f.created_at for f in Feedback.query.filter_by(user_id=user_id).all()}

    # Query all advisors and create a dictionary keyed by advisor id.
    advisors = Advisor.query.all()
    advisor_dict = {advisor.id: advisor for advisor in advisors}

    today = datetime.utcnow().date()
    three_months = today + timedelta(days=90)

    return render_template(
        'dashboard.html',
        user=user,
        tax_years=tax_years,
        requested_quotes=requested_quotes,
        feedbacks=feedbacks,
        advisors=advisor_dict,
        today=today,
        three_months=three_months
    )

@dashboard_bp.route('/quote_details/<int:tax_year_id>')
@login_required
def quote_details(tax_year_id):
    # Retrieve the TaxYear record using its primary key
    tax_year_record = TaxYear.query.get(tax_year_id)
    if not tax_year_record:
        return jsonify({"error": "Tax year record not found"}), 404

    # Query the Quote using the tax_year value from the TaxYear record.
    quote = Quote.query.filter_by(user_id=current_user.id, tax_year=tax_year_record.year).first()
    if quote:
        advisor_record = None
        if quote.advisor_id:
            from app.models import Advisor  # make sure Advisor is imported
            advisor_record = Advisor.query.get(quote.advisor_id)
        advisor_name = f"{advisor_record.name}" if advisor_record else "N/A"
        
        # Build the download URL (ownership is enforced inside the route).
        file_url = url_for('dashboard.download_quote_file', quote_id=quote.id) if quote.file_path else ""
        
        data = {
            "advisor_name": advisor_name,
            "advisor_id": quote.advisor_id,
            "amount": quote.quote_amount,
            "comment": quote.comment,
            "file_url": file_url
        }
        return jsonify(data)
    else:
        return jsonify({"error": "Quote not found"}), 404

@dashboard_bp.route('/download_quote_file/<int:quote_id>')
@login_required
def download_quote_file(quote_id):
    quote = Quote.query.get(quote_id)
    if not quote:
        abort(404)
    role = current_user.role
    authorized = (
        (role == 'user' and quote.user_id == current_user.id)
        or role == 'admin'
        or (role == 'advisor' and advisor_is_bound(quote.user_id, quote.tax_year))
    )
    if not authorized:
        abort(403)
    return send_stored_file(quote.file_path, mimetype='application/pdf')

@dashboard_bp.route('/download_draft_tax_return/<int:user_id>/<int:year>', methods=['GET'])
@login_required
def download_draft_tax_return(user_id, year):
    record = tax_year_for_request(year, customer_id=user_id)
    if not record:
        flash("Tax year record not found or access denied.", "error")
        return redirect(url_for('dashboard.dashboard'))
    if not record.draft_file_path:
        flash(f"Draft tax return file not found for tax year {year}.", "error")
        return redirect(url_for('dashboard.dashboard'))
    return send_stored_file(record.draft_file_path, mimetype='application/pdf')

@dashboard_bp.route('/download_final_tax_return/<int:user_id>/<int:year>', methods=['GET'])
@login_required
def download_final_tax_return(user_id, year):
    record = tax_year_for_request(year, customer_id=user_id)
    if not record or not record.final_file_path:
        flash("Final tax return file not found or access denied.", "error")
        return redirect(url_for('dashboard.dashboard'))
    return send_stored_file(record.final_file_path, mimetype='application/pdf')

@dashboard_bp.route('/withdraw_quote/<int:tax_year_id>', methods=['POST'])
@login_required
def withdraw_quote(tax_year_id):
    # Retrieve the tax year record using the provided tax_year_id
    tax_year_record = TaxYear.query.get(tax_year_id)
    if not tax_year_record:
        flash("Tax year record not found.", "error")
        return jsonify({"error": "Tax year record not found"}), 404

    # Find the corresponding quote using the tax year (assuming 'tax_year' in Quote corresponds to TaxYear.year)
    quote = Quote.query.filter_by(user_id=current_user.id, tax_year=tax_year_record.year).first()
    if not quote or quote.quote_status != "Pending":
        flash("No pending quote found for this tax year.", "error")
        return jsonify({"error": "No pending quote found for this tax year"}), 404

    # Update the quote status to "Rejected" and the tax year status to "Quote withdrawn"
    quote.quote_status = "Rejected"
    tax_year_record.status = "Quote withdrawn"

    db.session.commit()
    flash("Quote withdrawn successfully.", "success")
    return jsonify({"success": "Quote withdrawn successfully."})


