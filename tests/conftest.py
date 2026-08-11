"""Pytest fixtures for the Simplify Taxes test suite.

The suite runs against a throwaway SQLite database so it needs no live
Supabase/Postgres connection. Environment variables are set *before* the app
is imported, because config.py reads required secrets at import time.
"""
import os
import tempfile

# --- must run before importing the app (config validates env at import) ------
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".sqlite")
os.close(_DB_FD)
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_PATH
os.environ.setdefault("MAIL_USERNAME", "test@example.com")
os.environ.setdefault("MAIL_PASSWORD", "test-password")
os.environ["APP_ENV"] = "testing"

import pytest  # noqa: E402

from config import TestingConfig  # noqa: E402
from app import create_app, db as _db  # noqa: E402
from app.models import User, Advisor, TaxYear, Quote  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app(TestingConfig)
    yield application
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _schema(app):
    """Fresh schema for every test (full isolation)."""
    with app.app_context():
        _db.create_all()
        yield
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    """Log a user in by id via the session (no CSRF/login round-trip needed)."""
    def _login(user_id):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True
    return _login


# --- object factories (return primary keys to avoid detached-instance issues) -

@pytest.fixture
def make_user(app):
    counter = {"n": 0}

    def _make(role="user", email=None, password="Password123", confirmed=True, **kw):
        with app.app_context():
            counter["n"] += 1
            addr = email or f"{role}{counter['n']}@example.com"
            user = User(email=addr, role=role, email_confirmed=confirmed,
                        first_login=True, **kw)
            user.set_password(password)
            _db.session.add(user)
            _db.session.commit()
            return user.id
    return _make


@pytest.fixture
def make_advisor(app):
    """Create an Advisor company record linked to an advisor/admin user.
    Returns the Advisor.id (the identity used by TaxYear.advisor_id / Quote.advisor_id).
    """
    counter = {"n": 0}

    def _make(user_id, name=None, city="Zurich", email=None):
        with app.app_context():
            counter["n"] += 1
            adv = Advisor(
                user_id=user_id,
                name=name or f"Firm {counter['n']}",
                city=city,
                email=email or f"firm{counter['n']}@example.com",
            )
            _db.session.add(adv)
            _db.session.commit()
            return adv.id
    return _make


@pytest.fixture
def make_tax_year(app):
    from datetime import date

    def _make(user_id, year, advisor_id=None, status="Open", **kw):
        with app.app_context():
            ty = TaxYear(
                user_id=user_id,
                year=year,
                status=status,
                deadline=date(year + 1, 3, 31),
                advisor_id=advisor_id,
                **kw,
            )
            _db.session.add(ty)
            _db.session.commit()
            return ty.id
    return _make


@pytest.fixture
def make_quote(app):
    def _make(user_id, tax_year, advisor_id, status="Pending", **kw):
        with app.app_context():
            q = Quote(user_id=user_id, tax_year=tax_year, advisor_id=advisor_id,
                      quote_status=status, **kw)
            _db.session.add(q)
            _db.session.commit()
            return q.id
    return _make
