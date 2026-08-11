import os
from celery import Celery

_BROKER = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery = Celery(
    "simplify_taxes",
    broker=_BROKER,
    backend=_BACKEND,
)


def make_celery(app):
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", _BROKER),
        result_backend=app.config.get("CELERY_RESULT_BACKEND", _BACKEND),
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
