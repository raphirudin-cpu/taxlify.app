"""Phase D3: AI document intake (classification + field extraction)."""
import json
import types

import pytest

from app import db as _db
from app.models import RequiredDocument, DocumentAnalysis


# --- service-level -----------------------------------------------------------

def test_analyze_raises_when_not_configured(app):
    from app.services.ai_intake import analyze_document, AINotConfigured
    with app.app_context():
        # TestingConfig sets no ANTHROPIC_API_KEY
        with pytest.raises(AINotConfigured):
            analyze_document("/tmp/whatever.pdf")


def test_analyze_parses_structured_output(app, tmp_path, monkeypatch):
    from app.services import ai_intake

    doc = tmp_path / "lohnausweis.pdf"
    doc.write_bytes(b"%PDF-1.4 fake")

    payload = {
        "doc_type": "Lohnausweis", "summary": "Lohnausweis 2024 der Muster AG.",
        "confidence": "hoch",
        "fields": [{"label": "Bruttolohn", "value": "CHF 92'000"}],
    }

    class _Resp:
        model = "claude-opus-5"
        content = [types.SimpleNamespace(type="text", text=json.dumps(payload))]

    class _Messages:
        def create(self, **kwargs):  # noqa: ANN001
            # sanity: a document block and the schema were passed
            assert kwargs["messages"][0]["content"][0]["type"] == "document"
            assert kwargs["output_config"]["format"]["type"] == "json_schema"
            return _Resp()

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)

    with app.app_context():
        app.config["ANTHROPIC_API_KEY"] = "sk-test"
        try:
            result = ai_intake.analyze_document(str(doc), document_name="lohnausweis.pdf")
        finally:
            app.config["ANTHROPIC_API_KEY"] = None
    assert result["doc_type"] == "Lohnausweis"
    assert result["fields"][0]["value"] == "CHF 92'000"
    assert result["model"] == "claude-opus-5"


# --- route-level -------------------------------------------------------------

def _make_doc(app, user_id, tax_year_id, path="/tmp/x.pdf"):
    with app.app_context():
        d = RequiredDocument(user_id=user_id, tax_year_id=tax_year_id,
                             document_name="Lohnausweis", file_path=path)
        _db.session.add(d)
        _db.session.commit()
        return d.id


def test_analyze_route_stores_result(app, client, login, monkeypatch,
                                     make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    ty_id = make_tax_year(cli, 2024, advisor_id=adv_id)
    doc_id = _make_doc(app, cli, ty_id)
    login(advisor_user)

    import app.routes.ai_intake_routes as routes
    monkeypatch.setattr(routes, "analyze_document", lambda *a, **k: {
        "doc_type": "Lohnausweis", "summary": "ok", "confidence": "hoch",
        "fields": [{"label": "Bruttolohn", "value": "CHF 90'000"}],
        "model": "claude-opus-5",
    })

    r = client.post("/advisor/analyze_document", data={"required_document_id": str(doc_id)})
    assert r.status_code == 302
    with app.app_context():
        a = DocumentAnalysis.query.filter_by(required_document_id=doc_id).first()
        assert a is not None and a.doc_type == "Lohnausweis"
        assert a.fields[0]["value"] == "CHF 90'000"


def test_analyze_route_reanalysis_replaces(app, client, login, monkeypatch,
                                           make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    ty_id = make_tax_year(cli, 2024, advisor_id=adv_id)
    doc_id = _make_doc(app, cli, ty_id)
    login(advisor_user)

    import app.routes.ai_intake_routes as routes
    monkeypatch.setattr(routes, "analyze_document", lambda *a, **k: {
        "doc_type": "Bankkontoauszug", "summary": "x", "confidence": "mittel",
        "fields": [], "model": "claude-opus-5"})
    client.post("/advisor/analyze_document", data={"required_document_id": str(doc_id)})
    client.post("/advisor/analyze_document", data={"required_document_id": str(doc_id)})
    with app.app_context():
        rows = DocumentAnalysis.query.filter_by(required_document_id=doc_id).all()
        assert len(rows) == 1  # replaced, not duplicated


def test_analyze_route_forbidden_for_unbound_advisor(app, client, login,
                                                     make_user, make_advisor, make_tax_year):
    advisor_user = make_user(role="advisor")
    make_advisor(advisor_user)  # exists but not bound to this year
    cli = make_user(role="user")
    ty_id = make_tax_year(cli, 2024, advisor_id=None)
    doc_id = _make_doc(app, cli, ty_id)
    login(advisor_user)

    r = client.post("/advisor/analyze_document", data={"required_document_id": str(doc_id)})
    assert r.status_code == 302
    with app.app_context():
        assert DocumentAnalysis.query.filter_by(required_document_id=doc_id).first() is None


def test_analyze_route_no_key_flashes(app, client, login,
                                      make_user, make_advisor, make_tax_year):
    # No monkeypatch: the real service raises AINotConfigured (no key in tests)
    advisor_user = make_user(role="advisor")
    adv_id = make_advisor(advisor_user)
    cli = make_user(role="user")
    ty_id = make_tax_year(cli, 2024, advisor_id=adv_id)
    doc_id = _make_doc(app, cli, ty_id)
    login(advisor_user)

    r = client.post("/advisor/analyze_document", data={"required_document_id": str(doc_id)})
    assert r.status_code == 302
    with app.app_context():
        assert DocumentAnalysis.query.filter_by(required_document_id=doc_id).first() is None
