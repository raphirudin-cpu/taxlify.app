from flask import Flask, url_for
from flask_mail import Message
from app import mail, create_app
from app.celery import celery

@celery.task(name='app.utils.email_tasks.send_welcome_email')
def send_welcome_email(email):
    app = create_app()
    with app.app_context():
        try:
            msg = Message(
                subject='Welcome to Simplify Tax',
                recipients=[email],
                html='<p>Welcome! Thanks for registering at Simplify Tax. We’re glad to have you onboard.</p>'
            )
            mail.send(msg)
            app.logger.info(f"[CELERY] Welcome email sent to {email}")
        except Exception as e:
            app.logger.error(f"[CELERY] Failed to send welcome email to {email}: {str(e)}")
            raise

@celery.task(name='app.utils.email_tasks.send_confirmation_email')
def send_confirmation_email(email, token):
    app = create_app()
    with app.app_context():
        try:
            confirm_link = url_for('auth.confirm_email', token=token, _external=True)
            msg = Message(
                subject='Confirm Your Email',
                recipients=[email],
                html=f'<p>Click <a href="{confirm_link}">here</a> to confirm your email.</p>'
            )
            mail.send(msg)
            app.logger.info(f"[CELERY] Confirmation email sent to {email}")
        except Exception as e:
            app.logger.error(f"[CELERY] Failed to send confirmation email to {email}: {str(e)}")
            raise

@celery.task(name='app.utils.email_tasks.send_password_reset_email')
def send_password_reset_email(email, token):
    app = create_app()
    with app.app_context():
        try:
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            msg = Message(
                subject='Reset Your Password',
                recipients=[email],
                html=f'<p>To reset your password, click <a href="{reset_link}">here</a>.</p>'
            )
            mail.send(msg)
            app.logger.info(f"[CELERY] Password reset email sent to {email}")
        except Exception as e:
            app.logger.error(f"[CELERY] Failed to send password reset email to {email}: {e}")
            raise