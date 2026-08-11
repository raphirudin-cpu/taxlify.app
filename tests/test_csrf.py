"""CSRF protection is active and rejects tokenless state-changing requests."""
from config import CsrfTestingConfig
from app import create_app


def test_tokenless_post_is_rejected():
    app = create_app(CsrfTestingConfig)
    c = app.test_client()
    # CSRFProtect runs before the view, so this never touches the DB.
    resp = c.post("/auth/login", data={"email": "a@b.com", "password": "x"})
    assert resp.status_code == 400


def test_login_page_exposes_a_csrf_token():
    app = create_app(CsrfTestingConfig)
    c = app.test_client()
    resp = c.get("/auth/login")
    assert resp.status_code == 200
    assert b"csrf_token" in resp.data
