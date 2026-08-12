from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from app.models import User
from app.utils.email_token import generate_confirmation_token, confirm_token
from app.utils.email_tasks import send_confirmation_email
from app.audit import log_action

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
# Note: the Flask-Login manager and user_loader live in app/__init__.py.

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role in ('admin', 'advisor'):
            return redirect(url_for('advisor_dashboard.advisor_dashboard'))
        else:
            return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.email_confirmed:
                flash('Bitte bestätige zuerst deine E-Mail-Adresse.', 'error')
                return redirect(url_for('auth.login'))

            login_user(user)
            log_action('auth.login')
            flash('Erfolgreich angemeldet.', 'success')
            if user.role in ('admin', 'advisor'):
                return redirect(url_for('advisor_dashboard.advisor_dashboard'))
            else:
                return redirect(url_for('dashboard.dashboard'))
        else:
            log_action('auth.login_failed', detail=email)
            flash('E-Mail oder Passwort ist falsch.', 'error')

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        country = request.form.get('country')
        account_type = request.form.get('account_type')

        if password != confirm_password:
            flash('Die Passwörter stimmen nicht überein.', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Diese E-Mail ist bereits registriert.', 'error')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        is_retail = (account_type == 'individual')
        is_institution = (account_type == 'institution')

        new_user = User(
            email=email,
            password=hashed_password,
            role=role,
            country=country,
            retail=is_retail,
            institutional=is_institution,
            email_confirmed=False
        )
        db.session.add(new_user)
        db.session.commit()

        from app.utils.email_tasks import send_confirmation_email, send_welcome_email

        token = generate_confirmation_token(email)
        try:
            send_welcome_email.delay(email)
            send_confirmation_email.apply_async((email, token), countdown=10)
            current_app.logger.info(f"Welcome and confirmation emails queued for {email}")
        except Exception as e:
            current_app.logger.error(f"Failed to queue emails for {email}: {str(e)}")
            flash('E-Mails konnten nicht gesendet werden. Bitte kontaktiere den Support.', 'error')

        log_action('auth.register', target_type='user', target_id=new_user.id, detail=role, user_id=new_user.id)
        flash('Registrierung erfolgreich. Bitte bestätige deine E-Mail-Adresse.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/confirm/<token>', methods=['GET'])
def confirm_email(token):
    current_app.logger.info(f"[DEBUG] Reached confirm route with token: {token}")
    email = confirm_token(token)
    if not email:
        flash('Der Bestätigungslink ist ungültig oder abgelaufen.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first_or_404()

    if user.email_confirmed:
        flash('Konto bereits bestätigt. Bitte melde dich an.', 'error')
    else:
        user.email_confirmed = True
        db.session.commit()
        flash('Dein Konto ist bestätigt. Danke!', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    log_action('auth.logout')
    logout_user()
    flash('Du wurdest abgemeldet.', 'success')
    return redirect(url_for('auth.login'))

from app.utils.password_reset_token import generate_password_reset_token, confirm_password_reset_token
from app.utils.email_tasks import send_password_reset_email

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_password_reset_token(email)
            send_password_reset_email.delay(email, token)
        flash('Falls die E-Mail existiert, wurde ein Link zum Zurücksetzen gesendet.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_password_reset_token(token)
    if not email:
        flash('Der Link ist ungültig oder abgelaufen.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        if password != confirm:
            flash('Die Passwörter stimmen nicht überein.', 'error')
            return render_template('reset_password.html', token=token)

        user = User.query.filter_by(email=email).first_or_404()
        user.password = generate_password_hash(password)
        db.session.commit()
        flash('Passwort erfolgreich zurückgesetzt. Du kannst dich jetzt anmelden.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)
