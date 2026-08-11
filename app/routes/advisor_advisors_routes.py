import os
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import db, Advisor, Feedback
from app.helpers import serve_advisor_logo
from app.security import require_role
from sqlalchemy import func

advisor_advisors_bp = Blueprint('advisor_advisors', __name__)

# Route to serve advisor logo files
@advisor_advisors_bp.route('/advisor/<int:advisor_id>/Logo/<filename>')
def advisor_logo(advisor_id, filename):
    return serve_advisor_logo(advisor_id, filename)

@advisor_advisors_bp.route('/advisor/advisors')
@login_required
@require_role('advisor', 'admin')
def advisors():
    # Fetch all advisors from the Advisor table
    advisors = Advisor.query.all()
    
    advisors_data = []
    for adv in advisors:
        # Ensure advisor has a name (or any required field)
        if not getattr(adv, 'name', None):
            continue
        # Calculate the average rating from the Feedback table
        avg_rating = db.session.query(func.avg(Feedback.rating)) \
            .filter(Feedback.advisor_id == adv.id).scalar()
        if avg_rating is None:
            avg_rating = 0
        
        # Extract only the filename if adv.logo already contains path segments.
        logo_filename = os.path.basename(adv.logo) if adv.logo else ''
        
        advisors_data.append({
            'id': adv.id,
            # Construct the logo URL using the advisor_logo route:
            'logo': url_for('advisor_advisors.advisor_logo', advisor_id=adv.id, filename=logo_filename) if adv.logo else '',
            'name': adv.name,
            'city': adv.city,
            'average_rating': avg_rating
        })

    return render_template('advisor_advisors.html', advisors=advisors_data)
