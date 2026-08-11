from flask import render_template, url_for
from flask_mail import Message
from celery import shared_task
from app import mail, create_app

@shared_task
def send_confirmation_email(email, token):
    app = create_app()
    with app.app_context():
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        html = render_template('email/confirm.html', confirm_url=confirm_url)
        subject = "Please confirm your email"
        msg = Message(subject=subject, recipients=[email], html=html)
        mail.send(msg)
