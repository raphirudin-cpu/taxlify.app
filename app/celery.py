import os
from celery import Celery
from celery.schedules import crontab

# Railway (and most PaaS) expose the Redis service as REDIS_URL; fall back to it
# so the broker "just works" without a separate CELERY_BROKER_URL var.
_BROKER = (os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL")
           or "redis://localhost:6379/0")
_BACKEND = (os.environ.get("CELERY_RESULT_BACKEND") or os.environ.get("REDIS_URL")
            or "redis://localhost:6379/0")

celery = Celery(
    "simplify_taxes",
    broker=_BROKER,
    backend=_BACKEND,
)

# Configure the instance at import time so the standalone worker/beat process
# (which never calls create_app / make_celery) still gets the schedule + codecs.
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Weekly advisor digest — Mondays 07:00 UTC (needs `celery beat` running).
    beat_schedule={
        'weekly-advisor-digest': {
            'task': 'app.utils.email_tasks.enqueue_weekly_advisor_digests',
            'schedule': crontab(day_of_week='mon', hour=7, minute=0),
        },
    },
)


def make_celery(app):
    """Called from create_app (web process): apply app-config broker overrides
    and wrap tasks in an app context."""
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", _BROKER),
        result_backend=app.config.get("CELERY_RESULT_BACKEND", _BACKEND),
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
