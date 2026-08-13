"""Phase D1: firm roles + per-client assignment."""
from app import db as _db
from app.models import TaxYear, TeamMember


def _make_firm(make_user, make_advisor):
    """Owner (admin) + Advisor firm. Returns (owner_user_id, advisor_id)."""
    owner = make_user(role="admin")
    adv_id = make_advisor(owner)
    return owner, adv_id


def _add_member(app, adv_id, email, role="staff"):
    with app.app_context():
        tm = TeamMember(advisor_id=adv_id, email=email, role=role)
        _db.session.add(tm)
        _db.session.commit()
        return tm.id


def test_owner_can_assign_client(app, client, login, make_user, make_advisor, make_tax_year):
    owner, adv_id = _make_firm(make_user, make_advisor)
    staff_user = make_user(role="advisor", email="staff1@example.com")
    _add_member(app, adv_id, "staff1@example.com", role="staff")
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)

    r = client.post("/advisor/assign",
                    data={"user_id": str(cli), "tax_year": "2024", "assignee_id": str(staff_user)})
    assert r.status_code == 302
    with app.app_context():
        t = TaxYear.query.filter_by(user_id=cli, year=2024).first()
        assert t.assignee_id == staff_user


def test_staff_sees_only_assigned(app, client, login, make_user, make_advisor, make_tax_year):
    owner, adv_id = _make_firm(make_user, make_advisor)
    staff_user = make_user(role="advisor", email="staff2@example.com")
    _add_member(app, adv_id, "staff2@example.com", role="staff")
    mine = make_user(role="user", email="mine@example.com", firstname="Mina", lastname="Meier")
    other = make_user(role="user", email="other@example.com", firstname="Otto", lastname="Ott")
    make_tax_year(mine, 2024, advisor_id=adv_id, assignee_id=staff_user)
    make_tax_year(other, 2024, advisor_id=adv_id)  # unassigned -> staff must NOT see it
    login(staff_user)

    html = client.get("/advisor/dashboard").get_data(as_text=True)
    # exactly one queue row (the assigned client); the unassigned one is hidden
    assert html.count('data-stage="') == 1
    assert "meier" in html.lower()


def test_staff_cannot_assign(app, client, login, make_user, make_advisor, make_tax_year):
    owner, adv_id = _make_firm(make_user, make_advisor)
    staff_user = make_user(role="advisor", email="staff3@example.com")
    _add_member(app, adv_id, "staff3@example.com", role="staff")
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(staff_user)

    r = client.post("/advisor/assign",
                    data={"user_id": str(cli), "tax_year": "2024", "assignee_id": str(staff_user)})
    assert r.status_code == 403


def test_manager_can_assign(app, client, login, make_user, make_advisor, make_tax_year):
    owner, adv_id = _make_firm(make_user, make_advisor)
    mgr = make_user(role="advisor", email="mgr@example.com")
    _add_member(app, adv_id, "mgr@example.com", role="manager")
    staff_user = make_user(role="advisor", email="staff4@example.com")
    _add_member(app, adv_id, "staff4@example.com", role="staff")
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(mgr)

    r = client.post("/advisor/assign",
                    data={"user_id": str(cli), "tax_year": "2024", "assignee_id": str(staff_user)})
    assert r.status_code == 302
    with app.app_context():
        assert TaxYear.query.filter_by(user_id=cli, year=2024).first().assignee_id == staff_user


def test_assign_rejects_outsider(app, client, login, make_user, make_advisor, make_tax_year):
    owner, adv_id = _make_firm(make_user, make_advisor)
    outsider = make_user(role="advisor", email="outsider@example.com")  # not a firm member
    cli = make_user(role="user")
    make_tax_year(cli, 2024, advisor_id=adv_id)
    login(owner)

    r = client.post("/advisor/assign",
                    data={"user_id": str(cli), "tax_year": "2024", "assignee_id": str(outsider)})
    assert r.status_code == 302
    with app.app_context():
        assert TaxYear.query.filter_by(user_id=cli, year=2024).first().assignee_id is None


def test_admin_can_set_member_role(app, client, login, make_user, make_advisor):
    owner, adv_id = _make_firm(make_user, make_advisor)
    make_user(role="advisor", email="staff5@example.com")
    member_id = _add_member(app, adv_id, "staff5@example.com", role="staff")
    login(owner)

    r = client.post("/admin/settings/set_member_role",
                    data={"member_id": str(member_id), "role": "manager"})
    assert r.status_code == 302
    with app.app_context():
        assert TeamMember.query.get(member_id).role == "manager"
