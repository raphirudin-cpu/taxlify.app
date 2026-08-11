"""HTTP-level authorization / IDOR regression tests.

Each test pins a boundary that a Phase 1/2 fix established, so a future change
that re-opens the hole fails loudly.
"""


# --- IDOR: cross-user file downloads ----------------------------------------

def test_user_cannot_download_another_users_draft_return(
    client, login, make_user, make_tax_year
):
    victim = make_user(role="user")
    attacker = make_user(role="user")
    # Victim has a 2023 return with a draft file; attacker has no 2023 return.
    make_tax_year(
        victim, 2023,
        draft_file_path="uploads/x/2023/Tax Return/Draft/secret.pdf",
        draft_tax_return_submitted=1,
    )
    login(attacker)
    resp = client.get(f"/download_draft_tax_return/{victim}/2023")
    # Attacker is scoped to their OWN id -> no such tax year -> redirect, no file.
    assert resp.status_code == 302
    assert "dashboard" in resp.headers["Location"]


def test_user_cannot_download_another_users_final_return(
    client, login, make_user, make_tax_year
):
    victim = make_user(role="user")
    attacker = make_user(role="user")
    make_tax_year(
        victim, 2022,
        final_file_path="uploads/x/2022/Tax Return/Final/secret.pdf",
        final_tax_return_submitted=1,
    )
    login(attacker)
    resp = client.get(f"/download_final_tax_return/{victim}/2022")
    assert resp.status_code == 302
    assert "dashboard" in resp.headers["Location"]


def test_user_cannot_download_another_users_quote_file(
    client, login, make_user, make_advisor, make_quote
):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    victim = make_user(role="user")
    attacker = make_user(role="user")
    quote_id = make_quote(
        victim, 2023, adv_id, status="Accepted",
        file_path="uploads/x/2023/Quotes/quote.pdf",
    )
    login(attacker)
    resp = client.get(f"/download_quote_file/{quote_id}")
    # Not the attacker's quote, attacker isn't the advisor -> forbidden.
    assert resp.status_code == 403


# --- Unauthenticated upload endpoints (were wide open) ----------------------

def test_unauthenticated_cannot_upload_draft_return(client):
    resp = client.post("/upload_tax_return", data={"user_id": "1", "tax_year_id": "2023"})
    assert resp.status_code == 302
    assert "login" in resp.headers["Location"]


def test_unauthenticated_cannot_upload_final_return(client):
    resp = client.post("/upload_final_tax_return", data={"user_id": "1", "tax_year_id": "2023"})
    assert resp.status_code == 302
    assert "login" in resp.headers["Location"]


# --- Role gating -------------------------------------------------------------

def test_regular_user_forbidden_from_advisor_dashboard(client, login, make_user):
    login(make_user(role="user"))
    assert client.get("/advisor/dashboard").status_code == 403


def test_regular_user_forbidden_from_advisor_ajax_endpoints(client, login, make_user):
    login(make_user(role="user"))
    assert client.get("/advisor/get_statistic?user_id=1&tax_year=2023").status_code == 403
    assert client.get("/advisor/view_feedback?user_id=1&tax_year=2023").status_code == 403


def test_advisor_forbidden_from_user_only_statistics(client, login, make_user):
    # Regression for the broken `role not in ('user')` string check.
    login(make_user(role="advisor"))
    assert client.get("/statistics").status_code == 403


def test_user_can_reach_own_statistics(client, login, make_user):
    login(make_user(role="user"))
    assert client.get("/statistics").status_code == 200


def test_admin_can_reach_advisor_dashboard(client, login, make_user):
    login(make_user(role="admin"))
    assert client.get("/advisor/dashboard").status_code == 200


# --- Advisor <-> client binding ---------------------------------------------

def test_advisor_cannot_view_unbound_client_documents(
    client, login, make_user, make_advisor, make_tax_year
):
    advisor_user = make_user(role="advisor")
    make_advisor(advisor_user)                       # company exists...
    victim = make_user(role="user")
    make_tax_year(victim, 2023)                       # ...but advisor_id is None (unbound)
    login(advisor_user)
    resp = client.get(f"/documents/view/2023?user_id={victim}")
    assert resp.status_code == 302                    # denied -> redirect, not 200
    assert "dashboard" in resp.headers["Location"]


def test_advisor_can_view_bound_client_documents(
    client, login, make_user, make_advisor, make_tax_year
):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    client_user = make_user(role="user")
    make_tax_year(client_user, 2023, advisor_id=adv_id)   # bound
    login(advisor_user)
    resp = client.get(f"/documents/view/2023?user_id={client_user}")
    assert resp.status_code == 200
