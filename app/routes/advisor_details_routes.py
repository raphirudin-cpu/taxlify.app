import os
from flask import Blueprint, render_template, request, url_for
from flask_login import login_required
from app.models import db, Advisor, Feedback, User
from sqlalchemy import desc

advisor_details_bp = Blueprint('advisor_details', __name__)

@advisor_details_bp.route('/advisor/details')
@login_required
def advisor_details():
    advisor_id = request.args.get('advisor_id')
    if not advisor_id:
        return "Advisor ID is required.", 400

    try:
        advisor_id = int(advisor_id)
    except ValueError:
        return "Invalid Advisor ID.", 400

    # Fetch the advisor using the Advisor model
    advisor = Advisor.query.filter_by(id=advisor_id).first()
    if not advisor:
        return "Advisor not found.", 404

    # Build the logo URL similar to the advisors page logic
    if advisor.logo:
        logo_filename = os.path.basename(advisor.logo)
        logo_url = url_for('advisor.advisor_logo', advisor_id=advisor.id, filename=logo_filename)
    else:
        logo_url = url_for('static', filename='no_logo.png')

    # Fetch feedback with a join to get user details
    feedbacks_query = (
        db.session.query(Feedback, User)
        .join(User, Feedback.user_id == User.id)
        .filter(Feedback.advisor_id == advisor_id)
        .order_by(desc(Feedback.created_at))
        .all()
    )
    feedbacks = []
    ratings_total = 0
    ratings_count = 0

    for feedback, user in feedbacks_query:
        feedback_data = {
            'rating': feedback.rating,
            'comment': feedback.comment,
            'user_name': user.lastname,  # or any preferred format
            'user_surname': user.firstname,
            'created_at': feedback.created_at
        }
        feedbacks.append(feedback_data)
        ratings_total += feedback.rating
        ratings_count += 1

    average_rating = ratings_total / ratings_count if ratings_count > 0 else 0

    # The "Offerte anfragen" primary only makes sense in the client marketplace,
    # where the openQuote() JS exists. Advisors/admins view the read-only directory.
    from flask_login import current_user
    can_quote = current_user.is_authenticated and current_user.role == 'user'

    return render_template(
        'advisor_details.html',
        advisor=advisor,
        logo=logo_url,
        feedbacks=feedbacks,
        average_rating=average_rating,
        can_quote=can_quote,
    )
