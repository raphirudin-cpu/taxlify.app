from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import db, User
from app.security import require_role

# Create Blueprint
tips_news_bp = Blueprint('tips_news', __name__)

@tips_news_bp.route('/tips_news')
@login_required
@require_role('user')
def tips_news():
    return render_template('tips_news.html')
