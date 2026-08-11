# app/routes/settings.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    # Ensure the current user is a regular user
    if current_user.role != 'user':
        flash("Access denied.", "error")
        return redirect(url_for('auth.login'))

    user = current_user

    if request.method == 'POST':
        # Distinguish which form was submitted
        if request.form.get('form_name') == 'profile':
            # --- PROFILE UPDATE ---
            new_email = request.form.get('email').strip().lower()
            current_email = user.email.strip().lower()

            if new_email != current_email:
                existing_user = User.query.filter(
                    func.lower(User.email) == new_email,
                    User.id != user.id
                ).first()
                if existing_user:
                    flash("Email already in use", "error")
                    return redirect(url_for('settings.settings'))

            user.lastname             = request.form.get('name')
            user.firstname            = request.form.get('surname')
            user.street               = request.form.get('street')
            user.city                 = request.form.get('city')
            user.zipcode              = request.form.get('zip_code')
            user.birthday             = request.form.get('birthday')
            user.phone                = request.form.get('phone')
            user.email                = new_email
            user.contact_option       = request.form.get('contact_option')
            user.notify_status_changes= bool(request.form.get('notify_status_changes'))
            user.notify_new_requests  = bool(request.form.get('notify_new_requests'))
            user.notify_deadline      = bool(request.form.get('notify_deadline'))

            if user.first_login != 1:
                user.first_login = 1

            try:
                db.session.commit()
                flash("Settings saved successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error saving settings.", "error")

        elif request.form.get('form_name') == 'password':
            # --- PASSWORD CHANGE ---
            old_password     = request.form.get('old_password')
            new_password     = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            # Verify current password
            if not check_password_hash(user.password, old_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for('settings.settings'))

            # Check new password confirmation
            if new_password != confirm_password:
                flash("New passwords do not match.", "error")
                return redirect(url_for('settings.settings'))

            # Optional: enforce password strength
            if len(new_password) < 8:
                flash("New password must be at least 8 characters long.", "error")
                return redirect(url_for('settings.settings'))

            # Update password
            user.password = generate_password_hash(new_password)
            try:
                db.session.commit()
                flash("Password changed successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error changing password.", "error")

        # After handling either form, reload the page to show messages
        return redirect(url_for('settings.settings'))

    return render_template('settings.html', user=user)
