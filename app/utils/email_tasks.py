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

# ---------------------------------------------------------------------------
# Phase C: reminders + weekly advisor digest
# ---------------------------------------------------------------------------

_REMINDER_SUBJECTS = {
    'documents': 'Erinnerung: Belege hochladen',
    'quote': 'Erinnerung: Offerte prüfen',
    'draft': 'Erinnerung: Entwurf prüfen',
}
_REMINDER_BODIES = {
    'documents': "{advisor} wartet auf deine Belege für das Steuerjahr {year}.",
    'quote': "Eine Offerte von {advisor} für das Steuerjahr {year} wartet auf deine Entscheidung.",
    'draft': "{advisor} hat einen Entwurf für das Steuerjahr {year} eingereicht. Bitte prüfe ihn.",
}


@celery.task(name='app.utils.email_tasks.send_reminder_email')
def send_reminder_email(email, kind, year, advisor_name):
    app = create_app()
    with app.app_context():
        subject = _REMINDER_SUBJECTS.get(kind, 'Erinnerung')
        body = _REMINDER_BODIES.get(kind, '').format(advisor=advisor_name or 'Dein Treuhänder', year=year)
        try:
            mail.send(Message(subject=subject, recipients=[email], html=f"<p>{body}</p>"))
            app.logger.info("[CELERY] Reminder (%s) sent to %s", kind, email)
        except Exception as e:
            app.logger.error("[CELERY] Reminder to %s failed: %s", email, e)
            raise


@celery.task(name='app.utils.email_tasks.send_advisor_digest')
def send_advisor_digest(advisor_id):
    """Weekly summary for one advisor company (sent to the owning manager)."""
    from datetime import date, timedelta
    from app.models import Advisor, TaxYear, User, Quote
    app = create_app()
    with app.app_context():
        adv = Advisor.query.get(advisor_id)
        if not adv:
            return
        recipient = User.query.get(adv.user_id)
        if not recipient or not recipient.email:
            return

        today = date.today()
        soon = today + timedelta(days=14)
        upcoming = (TaxYear.query
                    .filter(TaxYear.advisor_id == advisor_id,
                            TaxYear.deadline >= today, TaxYear.deadline <= soon,
                            TaxYear.final_tax_return_submitted.is_(False))
                    .order_by(TaxYear.deadline).all())
        overdue = (TaxYear.query
                   .filter(TaxYear.advisor_id == advisor_id, TaxYear.deadline < today,
                           TaxYear.final_tax_return_submitted.is_(False)).count())
        pending_quotes = Quote.query.filter_by(advisor_id=advisor_id, quote_status='Pending').count()
        docs_to_approve = TaxYear.query.filter_by(
            advisor_id=advisor_id, uploaded_documents=True, documents_approved=False).count()

        rows = "".join(
            f"<li>{t.year} — Frist {t.deadline.strftime('%d.%m.%Y')}</li>" for t in upcoming
        ) or "<li>Keine Fristen in den nächsten 14 Tagen.</li>"

        html = (
            f"<h2>Wochenübersicht — {adv.name}</h2>"
            f"<p><strong>Fristen (nächste 14 Tage):</strong></p><ul>{rows}</ul>"
            f"<p>Überfällig: <strong>{overdue}</strong> · "
            f"Offene Anfragen: <strong>{pending_quotes}</strong> · "
            f"Dokumente zur Freigabe: <strong>{docs_to_approve}</strong></p>"
        )
        try:
            mail.send(Message(subject="Taxlify — deine Wochenübersicht",
                              recipients=[recipient.email], html=html))
            app.logger.info("[CELERY] Digest sent to %s", recipient.email)
        except Exception as e:
            app.logger.error("[CELERY] Digest to %s failed: %s", recipient.email, e)
            raise


@celery.task(name='app.utils.email_tasks.enqueue_weekly_advisor_digests')
def enqueue_weekly_advisor_digests():
    """Fan out a digest task per advisor. Scheduled by celery beat (weekly)."""
    from app.models import Advisor
    app = create_app()
    with app.app_context():
        ids = [a.id for a in Advisor.query.all()]
    for aid in ids:
        send_advisor_digest.delay(aid)
    return len(ids)
