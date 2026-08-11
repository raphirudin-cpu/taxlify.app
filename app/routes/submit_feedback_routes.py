from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from flask_login import login_required, current_user
from app.models import db, Feedback  # Ensure your Feedback model is defined and imported

feedback_bp = Blueprint('feedback', __name__)

@feedback_bp.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    # current_user is provided by Flask-Login; no need to check session manually.
    user_id = current_user.id
    
    # Retrieve form data
    advisor_id = request.form.get('advisor_id')
    tax_year_id = request.form.get('tax_year_id')
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    
    # Create a new Feedback record (assuming the Feedback model has the fields below)
    feedback = Feedback(
        user_id=user_id,
        advisor_id=advisor_id,
        tax_year=tax_year_id,
        rating=rating,
        comment=comment,
        created_at=datetime.utcnow()
    )
    
    try:
        db.session.add(feedback)
        db.session.commit()
        flash("Feedback submitted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error submitting feedback.", "error")
    
    # Redirect to the dashboard
    return redirect(url_for('dashboard.dashboard'))
