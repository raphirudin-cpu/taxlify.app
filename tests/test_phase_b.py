"""Phase B: assignment date, reject-with-comment, draft review."""
from app import db as _db
from app.models import TaxYear


def test_quote_accept_sets_assigned_on(app, client, login, make_user, make_advisor, make_tax_year, make_quote):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, status="Review Quote")
    make_quote(cli, 2024, adv_id, status="Pending")
    login(cli)

    r = client.post("/quote_action", data={"tax_year": "2024", "advisor_id": str(adv_id), "action": "accept"})
    assert r.status_code == 302
    with app.app_context():
        t = TaxYear.query.filter_by(user_id=cli, year=2024).first()
        assert t.assigned_on is not None and t.status == "Quote accepted"


def test_quote_reject_stores_reason(app, client, login, make_user, make_advisor, make_tax_year, make_quote):
    from app.models import Quote
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    make_tax_year(cli, 2024, status="Review Quote")
    make_quote(cli, 2024, adv_id, status="Pending")
    login(cli)

    client.post("/quote_action", data={"tax_year": "2024", "advisor_id": str(adv_id), "action": "reject", "comment": "zu teuer"})
    with app.app_context():
        q = Quote.query.filter_by(user_id=cli, tax_year=2024).first()
        assert q.rejection_reason == "zu teuer" and q.quote_status == "Rejected"


def test_draft_reject_stores_comment(app, client, login, make_user, make_tax_year):
    cli = make_user(role="user")
    make_tax_year(cli, 2024, status="Draft tax return submitted", draft_tax_return_submitted=True)
    login(cli)

    client.post("/draft_tax_return_action", data={"tax_year": "2024", "action": "reject", "comment": "Bitte anpassen"})
    with app.app_context():
        t = TaxYear.query.filter_by(user_id=cli, year=2024).first()
        assert t.draft_rejection_comment == "Bitte anpassen"
        assert t.status == "Draft tax return rejected"
        assert not t.draft_tax_return_approved


def test_dashboard_shows_draft_review_actions(app, client, login, make_user, make_tax_year):
    cli = make_user(role="user")
    make_tax_year(cli, 2024, status="Draft tax return submitted",
                  checklist_completed=True, draft_tax_return_submitted=True)
    login(cli)
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Entwurf annehmen" in r.get_data(as_text=True)
