from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import db, User
from app.security import require_role

advisor_tips_news_bp = Blueprint('advisor_tips_news', __name__)

@advisor_tips_news_bp.route('/advisor/tips_news')
@login_required
@require_role('advisor', 'admin')
def tips_news():
    return render_template('advisor_tips_news.html')
