"""Phase D2: time-tracking → client billing."""
from datetime import date
from decimal import Decimal

from app import db as _db
from app.models import TimeEntry, ClientInvoice, TeamMember


def _staff(app, adv_id, email, role="staff"):
    with app.app_context():
        tm = TeamMember(advisor_id=adv_id, email=email, role=role)
        _db.session.add(tm)
        _db.session.commit()


def test_add_time_entry(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)

    r = client.post("/advisor/time/add", data={
        "engagement": f"{cli}:2024", "minutes": "90",
        "rate": "200", "description": "Belege geprüft", "spent_on": "2024-05-01"})
    assert r.status_code == 302
    with app.app_context():
        e = TimeEntry.query.filter_by(user_id=cli, tax_year=2024).first()
        assert e is not None and e.minutes == 90
        assert e.amount == Decimal("300.00")  # 90/60 * 200
        assert e.advisor_id == adv_id and e.author_id == owner


def test_add_time_entry_forbidden_when_unbound(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    make_advisor(owner)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=None)  # not this firm's client
    login(owner)
    r = client.post("/advisor/time/add", data={
        "engagement": f"{cli}:2024", "minutes": "60", "rate": "100", "description": "x"})
    assert r.status_code == 403


def test_manager_creates_invoice_and_marks_billed(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)
    with app.app_context():
        _db.session.add(TimeEntry(advisor_id=adv_id, user_id=cli, tax_year=2024,
                                  author_id=owner, spent_on=date(2024, 5, 1),
                                  minutes=120, description="a", rate_chf=Decimal("150")))
        _db.session.add(TimeEntry(advisor_id=adv_id, user_id=cli, tax_year=2024,
                                  author_id=owner, spent_on=date(2024, 5, 2),
                                  minutes=30, description="b", rate_chf=Decimal("150")))
        _db.session.commit()

    r = client.post("/advisor/time/invoice", data={"user_id": str(cli), "tax_year": "2024"})
    assert r.status_code == 302
    with app.app_context():
        inv = ClientInvoice.query.filter_by(user_id=cli, tax_year=2024).first()
        assert inv is not None
        assert inv.minutes_total == 150
        assert inv.amount == Decimal("375.00")  # 2.5h * 150
        assert all(e.billed and e.invoice_id == inv.id
                   for e in TimeEntry.query.filter_by(user_id=cli, tax_year=2024).all())


def test_staff_cannot_create_invoice(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    staff = make_user(role="advisor", email="d2staff@example.com")
    _staff(app, adv_id, "d2staff@example.com", role="staff")
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(staff)
    with app.app_context():
        _db.session.add(TimeEntry(advisor_id=adv_id, user_id=cli, tax_year=2024,
                                  author_id=staff, spent_on=date(2024, 5, 1),
                                  minutes=60, description="a", rate_chf=Decimal("150")))
        _db.session.commit()
    r = client.post("/advisor/time/invoice", data={"user_id": str(cli), "tax_year": "2024"})
    assert r.status_code == 403


def test_cannot_delete_billed_entry(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)
    with app.app_context():
        e = TimeEntry(advisor_id=adv_id, user_id=cli, tax_year=2024, author_id=owner,
                      spent_on=date(2024, 5, 1), minutes=60, description="a",
                      rate_chf=Decimal("150"), billed=True)
        _db.session.add(e)
        _db.session.commit()
        eid = e.id
    r = client.post(f"/advisor/time/{eid}/delete")
    assert r.status_code == 302
    with app.app_context():
        assert TimeEntry.query.get(eid) is not None  # still there


def test_cancel_invoice_releases_entries(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)
    with app.app_context():
        inv = ClientInvoice(advisor_id=adv_id, user_id=cli, tax_year=2024,
                            minutes_total=60, amount=Decimal("150"), status="offen",
                            created_by=owner)
        _db.session.add(inv)
        _db.session.flush()
        _db.session.add(TimeEntry(advisor_id=adv_id, user_id=cli, tax_year=2024,
                                  author_id=owner, spent_on=date(2024, 5, 1), minutes=60,
                                  description="a", rate_chf=Decimal("150"),
                                  billed=True, invoice_id=inv.id))
        _db.session.commit()
        inv_id = inv.id

    r = client.post(f"/advisor/time/invoice/{inv_id}/status", data={"status": "storniert"})
    assert r.status_code == 302
    with app.app_context():
        assert ClientInvoice.query.get(inv_id).status == "storniert"
        e = TimeEntry.query.filter_by(user_id=cli, tax_year=2024).first()
        assert e.billed is False and e.invoice_id is None  # released for re-billing


def test_time_page_renders(app, client, login, make_user, make_advisor, make_tax_year):
    owner = make_user(role="advisor")
    adv_id = make_advisor(owner)
    cli = make_user(role="user", firstname="Rea", lastname="Muster")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)
    r = client.get("/advisor/time/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Zeit erfassen" in body and "Muster" in body
