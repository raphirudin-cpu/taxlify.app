"""Phase C: client reminders + deadline extensions (Fristverlängerung)."""
from datetime import datetime, timedelta

from app import db as _db
from app.models import TaxYear, TaxYearExtension


def test_remind_sets_last_reminded_and_logs(app, client, login, monkeypatch,
                                            make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id, status="Open")
    login(advisor_user)

    # don't hit Celery/broker in tests
    import app.utils.email_tasks as et
    monkeypatch.setattr(et.send_reminder_email, "delay", lambda *a, **k: None)

    r = client.post("/advisor/remind",
                    data={"user_id": str(cli), "tax_year": "2024", "kind": "documents"})
    assert r.status_code == 302
    with app.app_context():
        t = TaxYear.query.filter_by(user_id=cli, year=2024).first()
        assert t.last_reminded_at is not None


def test_remind_rate_limited_within_24h(app, client, login, monkeypatch,
                                        make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    ty_id = make_tax_year(cli, 2024, advisor_id=adv_id, status="Open")
    login(advisor_user)
    with app.app_context():
        t = TaxYear.query.get(ty_id)
        t.last_reminded_at = datetime.utcnow() - timedelta(hours=1)
        _db.session.commit()

    import app.utils.email_tasks as et
    called = {"n": 0}
    monkeypatch.setattr(et.send_reminder_email, "delay",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    client.post("/advisor/remind",
                data={"user_id": str(cli), "tax_year": "2024", "kind": "documents"})
    assert called["n"] == 0  # skipped: reminded < 24h ago


def test_remind_rejects_bad_kind(app, client, login, make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(advisor_user)
    r = client.post("/advisor/remind",
                    data={"user_id": str(cli), "tax_year": "2024", "kind": "bogus"})
    assert r.status_code == 302
    with app.app_context():
        assert TaxYear.query.filter_by(user_id=cli, year=2024).first().last_reminded_at is None


def test_remind_forbidden_for_unbound_advisor(app, client, login, make_user,
                                              make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    make_advisor(advisor_user)          # advisor exists but is NOT bound to the year
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=None)
    login(advisor_user)
    r = client.post("/advisor/remind",
                    data={"user_id": str(cli), "tax_year": "2024", "kind": "documents"})
    assert r.status_code == 403


def test_extend_deadline_records_history(app, client, login, make_user,
                                         make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(advisor_user)

    r = client.post("/advisor/extend_deadline",
                    data={"user_id": str(cli), "tax_year": "2024",
                          "new_deadline": "2025-09-30", "note": "Kanton beantragt"})
    assert r.status_code == 302
    with app.app_context():
        t = TaxYear.query.filter_by(user_id=cli, year=2024).first()
        assert t.deadline.isoformat() == "2025-09-30"
        ext = TaxYearExtension.query.filter_by(tax_year_id=t.id).first()
        assert ext is not None and ext.new_deadline.isoformat() == "2025-09-30"
        assert ext.note == "Kanton beantragt"


def test_extend_deadline_forbidden_for_unbound_advisor(app, client, login, make_user,
                                                       make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=None)
    login(advisor_user)
    r = client.post("/advisor/extend_deadline",
                    data={"user_id": str(cli), "tax_year": "2024", "new_deadline": "2025-09-30"})
    assert r.status_code == 403
