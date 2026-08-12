"""Best-effort activity logging.

`log_action` records an AuditLog row. It NEVER raises into the caller and must be
called *after* the underlying action has committed (it opens its own commit), so
a failed audit write can't roll back real work.
"""
from flask import request, has_request_context, current_app
from flask_login import current_user

from app import db
from app.models import AuditLog

_UNSET = object()  # lets callers force user_id=None (anonymous) vs. "not provided"


def log_action(action, target_type=None, target_id=None, detail=None, user_id=_UNSET):
    try:
        uid = user_id
        if uid is _UNSET:
            uid = None
            if has_request_context() and getattr(current_user, "is_authenticated", False):
                uid = current_user.id
        ip = request.remote_addr if has_request_context() else None
        entry = AuditLog(
            user_id=uid,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            detail=(str(detail)[:1000] if detail is not None else None),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.exception("audit log write failed for action=%s", action)
        except Exception:
            pass
