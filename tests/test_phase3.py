"""Phase 3 regression tests: single upload root + boolean column."""
import os
from datetime import date

from sqlalchemy import Boolean

from app import db as _db
from app.helpers import upload_path
from app.models import TaxYear


def test_upload_path_is_under_single_app_uploads_root(app):
    with app.app_context():
        p = upload_path(31, 2024, "documents")
        expected = os.path.join(app.root_path, "uploads", "31", "2024", "documents")
        assert p == expected
        # Always inside the canonical root (never cwd-relative).
        assert p.startswith(os.path.join(app.root_path, "uploads") + os.sep)


def test_final_tax_return_submitted_column_is_boolean():
    assert isinstance(TaxYear.__table__.c.final_tax_return_submitted.type, Boolean)


def test_final_tax_return_submitted_roundtrips_from_integer_assignment(app, make_user):
    uid = make_user(role="user")
    with app.app_context():
        ty = TaxYear(user_id=uid, year=2024, status="Open", deadline=date(2025, 3, 31))
        ty.final_tax_return_submitted = 1  # legacy integer-style assignment from routes
        _db.session.add(ty)
        _db.session.commit()

        fetched = _db.session.get(TaxYear, ty.id)
        assert fetched.final_tax_return_submitted is True
        # The `== 0` / `== 1` filters used in admin routes still behave correctly.
        assert TaxYear.query.filter(TaxYear.final_tax_return_submitted == 0).count() == 0
        assert TaxYear.query.filter(TaxYear.final_tax_return_submitted == 1).count() == 1
