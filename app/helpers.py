"""Small shared view-layer helpers to remove copy-paste across routes."""
import os

from flask import current_app, send_from_directory

from app import db


def upload_path(*parts):
    """Absolute path under the single canonical uploads root (``app/uploads``).

    Centralizes where files are stored so every upload lands in the same place
    the download routes read from. Previously some routes used
    ``current_app.root_path/uploads`` while additional-document uploads used
    ``os.getcwd()/uploads`` — a save/read mismatch this removes.
    """
    return os.path.join(current_app.root_path, 'uploads', *[str(p) for p in parts])


def serve_advisor_logo(advisor_id, filename):
    """Serve an advisor's logo from uploads/<advisor_id>/Logo/<filename>.

    Shared by the advisor / advisor_advisors / admin_settings blueprints, which
    previously each defined an identical copy of this route body.
    """
    directory = os.path.join(current_app.root_path, 'uploads', str(advisor_id), 'Logo')
    return send_from_directory(directory, filename)


def commit_or_rollback():
    """Commit the current session; on error roll back and log.

    Returns True on success, False on failure. Replaces the repeated
    ``try: db.session.commit() ... except Exception as e: flash(str(e))``
    blocks (which also leaked internal error details to users).
    """
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Database commit failed")
        return False
