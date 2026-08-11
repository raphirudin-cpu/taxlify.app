"""Regression tests for the advisor statistics / feedback / profile IDOR gaps
found in the final audit: an advisor must not read or write a client's
financial data unless they are engaged with that client.
"""
from app import db as _db
from app.models import UserStatistics


def _unbound_advisor_and_victim(make_user, make_advisor, make_tax_year, year=2023):
    advisor_user = make_user(role="advisor")
    make_advisor(advisor_user)              # advisor company exists, but not bound
    victim = make_user(role="user")
    make_tax_year(victim, year)             # advisor_id is None -> unbound
    return advisor_user, victim


def test_advisor_cannot_read_unbound_client_statistics(
    client, login, make_user, make_advisor, make_tax_year
):
    advisor_user, victim = _unbound_advisor_and_victim(make_user, make_advisor, make_tax_year)
    login(advisor_user)
    r = client.get(f"/advisor/get_statistic?user_id={victim}&tax_year=2023")
    assert r.status_code == 403


def test_advisor_cannot_write_unbound_client_statistics(
    client, login, make_user, make_advisor, make_tax_year, app
):
    advisor_user, victim = _unbound_advisor_and_victim(make_user, make_advisor, make_tax_year)
    login(advisor_user)
    r = client.post("/advisor/add_statistic", data={
        "user_id": str(victim), "date": "2023-12-31",
        "taxable_income": "100", "taxable_assets": "200", "paid_taxes": "30",
    })
    assert r.status_code == 403
    with app.app_context():
        assert UserStatistics.query.filter_by(user_id=victim).count() == 0


def test_advisor_cannot_read_unbound_client_feedback(
    client, login, make_user, make_advisor, make_tax_year
):
    advisor_user, victim = _unbound_advisor_and_victim(make_user, make_advisor, make_tax_year)
    login(advisor_user)
    r = client.get(f"/advisor/view_feedback?user_id={victim}&tax_year=2023")
    assert r.status_code == 403


def test_advisor_cannot_view_unbound_client_profile(
    client, login, make_user, make_advisor, make_tax_year
):
    advisor_user, victim = _unbound_advisor_and_victim(make_user, make_advisor, make_tax_year)
    login(advisor_user)
    r = client.get(f"/admin/clients/{victim}/profile")
    assert r.status_code == 302
    assert "dashboard" in r.headers["Location"]


def test_advisor_can_write_bound_client_statistics(
    client, login, make_user, make_advisor, make_tax_year, app
):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    bound_client = make_user(role="user")
    make_tax_year(bound_client, 2023, advisor_id=adv_id)   # bound
    login(advisor_user)
    r = client.post("/advisor/add_statistic", data={
        "user_id": str(bound_client), "date": "2023-12-31",
        "taxable_income": "100", "taxable_assets": "200", "paid_taxes": "30",
    })
    assert r.status_code == 302  # success -> redirect
    with app.app_context():
        assert UserStatistics.query.filter_by(user_id=bound_client).count() == 1


def test_advisor_details_requires_login(client):
    r = client.get("/advisor/details?advisor_id=1")
    assert r.status_code == 302
    assert "login" in r.headers["Location"]
