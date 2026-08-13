"""Centralized authorization helpers.

This module replaces the copy-pasted ``if current_user.role not in (...)``
checks and, crucially, provides the ownership/binding logic that most routes
were missing (the source of the IDOR vulnerabilities).

Data-model conventions (important):
- ``Advisor.id`` is the advisor identity used throughout the app.
- ``TaxYear.advisor_id`` and ``Quote.advisor_id`` both store an ``Advisor.id``
  (NOT a ``User.id``), even though the FK column points at ``user.id``.
  ``TaxYear.advisor_id`` is set when a client accepts a quote.
"""
import os
from functools import wraps

from flask import abort, current_app, send_file
from flask_login import current_user

from app.models import Advisor, Quote, TaxYear, TeamMember, User


def require_role(*roles):
    """Abort with 403 unless the logged-in user has one of ``roles``.

    Use *below* ``@login_required`` so authentication is handled first; this
    still guards against an unauthenticated user reaching the view directly.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_advisor():
    """Return the Advisor record for the logged-in user, or None."""
    if not current_user.is_authenticated:
        return None
    return Advisor.query.filter_by(user_id=current_user.id).first()


def firm_advisor():
    """Return the Advisor (firm) the current user belongs to, whether they own
    the record or are a team member. None if unaffiliated."""
    if not current_user.is_authenticated:
        return None
    owned = Advisor.query.filter_by(user_id=current_user.id).first()
    if owned:
        return owned
    tm = TeamMember.query.filter_by(email=current_user.email).first()
    if tm:
        return Advisor.query.get(tm.advisor_id)
    return None


def firm_team_role():
    """The current user's role within their firm: 'owner' | 'manager' | 'staff' | None.
    Whoever holds the Advisor record is the 'owner'; team members carry their own
    'manager'/'staff' role."""
    if not current_user.is_authenticated:
        return None
    if Advisor.query.filter_by(user_id=current_user.id).first():
        return 'owner'
    tm = TeamMember.query.filter_by(email=current_user.email).first()
    return tm.role if tm else None


def can_manage_firm():
    """Owners and managers may manage the team and assign clients."""
    return firm_team_role() in ('owner', 'manager')


def firm_members(advisor):
    """Users who can be assigned engagements in this firm: the owner plus every
    team member that has an advisor-role account. Returns a list of Users."""
    if not advisor:
        return []
    members = []
    owner = User.query.get(advisor.user_id)
    if owner:
        members.append(owner)
    emails = [tm.email for tm in TeamMember.query.filter_by(advisor_id=advisor.id).all()]
    if emails:
        for u in User.query.filter(User.email.in_(emails)).all():
            if u.id != (owner.id if owner else None):
                members.append(u)
    return members


def current_advisor_ids():
    """All Advisor.ids the current user acts under: the firm they own plus every
    firm they are a team member of. Empty if unaffiliated."""
    if not current_user.is_authenticated:
        return []
    ids = set()
    owned = Advisor.query.filter_by(user_id=current_user.id).first()
    if owned:
        ids.add(owned.id)
    for tm in TeamMember.query.filter_by(email=current_user.email).all():
        ids.add(tm.advisor_id)
    return list(ids)


def advisor_is_bound(customer_id, year):
    """True if the current advisor (owner or team member) is engaged on this
    client's tax year — via an assigned ``TaxYear.advisor_id`` or a linking quote.
    """
    ids = current_advisor_ids()
    if not ids:
        return False
    ty = TaxYear.query.filter_by(user_id=customer_id, year=year).first()
    if ty and ty.advisor_id in ids:
        return True
    return Quote.query.filter(
        Quote.user_id == customer_id, Quote.tax_year == year,
        Quote.advisor_id.in_(ids)
    ).first() is not None


def advisor_is_client(customer_id):
    """True if the current advisor's firm is engaged with this client on ANY tax
    year (assigned TaxYear or a quote). Gates client-level views not scoped to a year.
    """
    ids = current_advisor_ids()
    if not ids:
        return False
    if TaxYear.query.filter(TaxYear.user_id == customer_id,
                            TaxYear.advisor_id.in_(ids)).first():
        return True
    return Quote.query.filter(Quote.user_id == customer_id,
                              Quote.advisor_id.in_(ids)).first() is not None


def tax_year_for_request(year, customer_id=None):
    """Resolve the TaxYear the current user is authorized to act on.

    - ``user``:    always their own tax year (``customer_id`` ignored).
    - ``admin``:   any client's tax year (``customer_id`` or self).
    - ``advisor``: only clients they are bound to (see ``advisor_is_bound``).

    Returns a ``TaxYear`` or ``None``. ``None`` means "not found or not
    authorized" — callers should treat both the same (no info leak).
    """
    role = getattr(current_user, "role", None)

    if role == "user":
        return TaxYear.query.filter_by(user_id=current_user.id, year=year).first()

    if role == "admin":
        uid = customer_id if customer_id is not None else current_user.id
        return TaxYear.query.filter_by(user_id=uid, year=year).first()

    if role == "advisor":
        if customer_id is None:
            return None
        if not advisor_is_bound(customer_id, year):
            return None
        return TaxYear.query.filter_by(user_id=customer_id, year=year).first()

    return None


def parse_int(value):
    """Best-effort int parse; returns None on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Safe file serving -------------------------------------------------------

def _allowed_upload_roots():
    """Absolute, real paths of the two directories uploads may live under."""
    return [
        os.path.realpath(os.path.join(current_app.root_path, "uploads")),
        os.path.realpath(os.path.join(current_app.root_path, "..", "uploads")),
    ]


def _within(path, root):
    return path == root or path.startswith(root + os.sep)


def _resolve_candidates(stored_path):
    """Yield candidate absolute locations for a stored (abs or relative) path."""
    if os.path.isabs(stored_path):
        yield os.path.realpath(stored_path)
        return
    rel = stored_path[len("uploads/"):] if stored_path.startswith("uploads/") else stored_path
    for root in _allowed_upload_roots():
        yield os.path.realpath(os.path.join(root, rel))
        yield os.path.realpath(os.path.join(root, stored_path))


def send_stored_file(stored_path, download_name=None, mimetype=None):
    """Serve a file recorded in the DB, confined to the uploads directories.

    Defense in depth: even though the path comes from our own DB, we verify the
    resolved real path stays inside an allowed uploads root before serving, so a
    poisoned or malformed ``file_path`` can never read arbitrary files.
    Aborts 404 if nothing valid is found. Ownership must be checked by the
    caller *before* calling this.
    """
    if not stored_path:
        abort(404)
    roots = _allowed_upload_roots()
    for candidate in _resolve_candidates(stored_path):
        if os.path.isfile(candidate) and any(_within(candidate, r) for r in roots):
            return send_file(
                candidate,
                as_attachment=True,
                download_name=download_name or os.path.basename(candidate),
                mimetype=mimetype,
            )
    abort(404)
