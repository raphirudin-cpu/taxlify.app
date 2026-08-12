# app/routes/settings.py
import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user, logout_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (
    db, User, TaxYear, Quote, Feedback, UserStatistics, Subscription, Invoice,
    TaxReturn, ChecklistAnswer, RequiredDocument, DocumentRequest, AuditLog,
)
from app.audit import log_action

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Client self-service account deletion: cascade the user's data + files.
    Advisors/admins have business data (quotes, clients, team) and must go
    through support."""
    if current_user.role != 'user':
        flash("Bitte kontaktiere den Support, um dein Konto zu löschen.", "error")
        return redirect(url_for('advisor_settings.advisor_settings'))

    uid = current_user.id
    try:
        # children referencing tax_years first, then user-scoped rows, then user
        for model in (ChecklistAnswer, RequiredDocument, DocumentRequest,
                      Quote, Feedback, UserStatistics, Subscription, Invoice,
                      TaxReturn, AuditLog):
            model.query.filter_by(user_id=uid).delete(synchronize_session=False)
        TaxYear.query.filter_by(user_id=uid).delete(synchronize_session=False)
        db.session.delete(User.query.get(uid))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("account deletion failed for user=%s", uid)
        flash("Konto konnte nicht gelöscht werden. Bitte kontaktiere den Support.", "error")
        return redirect(url_for('settings.settings'))

    # remove the user's uploaded files from both possible roots
    for root in (os.path.join(current_app.root_path, 'uploads', str(uid)),
                 os.path.abspath(os.path.join(current_app.root_path, '..', 'uploads', str(uid)))):
        if os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)

    log_action('account.delete', detail=f"user={uid}", user_id=None)  # anonymized, survives deletion
    logout_user()
    flash("Dein Konto wurde gelöscht.", "success")
    return redirect(url_for('auth.login'))

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    # Ensure the current user is a regular user
    if current_user.role != 'user':
        flash("Zugriff verweigert.", "error")
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
                    flash("E-Mail-Adresse wird bereits verwendet.", "error")
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
                flash("Einstellungen erfolgreich gespeichert.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Fehler beim Speichern der Einstellungen.", "error")

        elif request.form.get('form_name') == 'password':
            # --- PASSWORD CHANGE ---
            old_password     = request.form.get('old_password')
            new_password     = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            # Verify current password
            if not check_password_hash(user.password, old_password):
                flash("Das aktuelle Passwort ist nicht korrekt.", "error")
                return redirect(url_for('settings.settings'))

            # Check new password confirmation
            if new_password != confirm_password:
                flash("Die neuen Passwörter stimmen nicht überein.", "error")
                return redirect(url_for('settings.settings'))

            # Optional: enforce password strength
            if len(new_password) < 8:
                flash("Das neue Passwort muss mindestens 8 Zeichen lang sein.", "error")
                return redirect(url_for('settings.settings'))

            # Update password
            user.password = generate_password_hash(new_password)
            try:
                db.session.commit()
                flash("Passwort erfolgreich geändert.", "success")
            except Exception as e:
                db.session.rollback()
                flash("Fehler beim Ändern des Passworts.", "error")

        # After handling either form, reload the page to show messages
        return redirect(url_for('settings.settings'))

    return render_template('settings.html', user=user)
