"""Phase A: audit log + delete-account regression tests."""
from datetime import date

from app import db as _db
from app.audit import log_action
from app.models import User, TaxYear, AuditLog


def test_log_action_writes_row(app, make_user):
    uid = make_user(role="user")
    with app.app_context():
        before = AuditLog.query.count()
        log_action("test.event", target_type="user", target_id=uid, detail="x", user_id=uid)
        assert AuditLog.query.count() == before + 1
        row = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert row.action == "test.event" and row.user_id == uid and row.created_at is not None


def test_delete_account_removes_user_and_data(app, client, login, make_user, make_tax_year):
    uid = make_user(role="user")
    make_tax_year(uid, 2024)
    login(uid)

    r = client.post("/settings/delete_account")
    assert r.status_code == 302
    assert "login" in r.headers["Location"]

    with app.app_context():
        assert _db.session.get(User, uid) is None
        assert TaxYear.query.filter_by(user_id=uid).count() == 0
        # the deletion itself is recorded, anonymized (user_id NULL)
        adel = AuditLog.query.filter_by(action="account.delete").order_by(AuditLog.id.desc()).first()
        assert adel is not None and adel.user_id is None


def test_advisor_cannot_self_delete(app, client, login, make_user):
    uid = make_user(role="advisor")
    login(uid)
    r = client.post("/settings/delete_account")
    assert r.status_code == 302  # bounced to support/settings
    with app.app_context():
        assert _db.session.get(User, uid) is not None  # still there
