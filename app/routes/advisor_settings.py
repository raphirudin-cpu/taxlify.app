# app/routes/advisor_settings.py
import os
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User
from app.security import require_role
from app.helpers import commit_or_rollback

advisor_settings_bp = Blueprint('advisor_settings', __name__)

@advisor_settings_bp.route('/advisor/settings', methods=['GET', 'POST'])
@login_required
@require_role('advisor', 'admin')
def advisor_settings():
    user = current_user

    if request.method == 'POST':
        # 1) PROFILE UPDATE
        if 'update_settings' in request.form:
            lastname              = request.form.get('lastname')
            firstname             = request.form.get('firstname')
            street                = request.form.get('street')
            city                  = request.form.get('city')
            zip_code              = request.form.get('zip_code')
            birthday              = request.form.get('birthday')
            phone                 = request.form.get('phone')
            new_email             = request.form.get('email', '').strip().lower()
            contact_option        = request.form.get('contact_option')
            notify_status_changes = bool(request.form.get('notify_status_changes'))
            notify_new_requests   = bool(request.form.get('notify_new_requests'))
            notify_deadline       = bool(request.form.get('notify_deadline'))

            # Check email uniqueness
            if new_email and new_email != (user.email or '').lower():
                exists = User.query.filter(
                    func.lower(User.email) == new_email,
                    User.id != user.id
                ).first()
                if exists:
                    flash("Email already in use.", "error")
                    return redirect(url_for('advisor_settings.advisor_settings'))

            # Apply updates
            user.lastname              = lastname
            user.firstname             = firstname
            user.street                = street
            user.city                  = city
            user.zipcode               = zip_code
            user.birthday              = birthday
            user.phone                 = phone
            user.email                 = new_email
            user.contact_option        = contact_option
            user.notify_status_changes = notify_status_changes
            user.notify_new_requests   = notify_new_requests
            user.notify_deadline       = notify_deadline

            if commit_or_rollback():
                flash("Settings updated successfully.", "success")
            else:
                flash("Error updating settings.", "error")

        # 2) PASSWORD CHANGE
        elif 'change_password' in request.form:
            old_pw      = request.form.get('old_password')
            new_pw      = request.form.get('new_password')
            confirm_pw  = request.form.get('confirm_password')

            # Verify current password
            if not check_password_hash(user.password, old_pw):
                flash("Current password is incorrect.", "error")
                return redirect(url_for('advisor_settings.advisor_settings'))

            # Confirm new passwords match
            if new_pw != confirm_pw:
                flash("New passwords do not match.", "error")
                return redirect(url_for('advisor_settings.advisor_settings'))

            # Enforce a minimum length (optional)
            if len(new_pw) < 8:
                flash("New password must be at least 8 characters long.", "error")
                return redirect(url_for('advisor_settings.advisor_settings'))

            # Hash & save
            user.password = generate_password_hash(new_pw)
            if commit_or_rollback():
                flash("Password changed successfully.", "success")
            else:
                flash("Error changing password.", "error")

        # After either action, reload to show flashes
        return redirect(url_for('advisor_settings.advisor_settings'))

    # GET
    return render_template('advisor_settings.html', user=user)
