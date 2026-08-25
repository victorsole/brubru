"""
Integration tests for /api/v1/laws, /api/v1/procedures,
/api/v1/legal-text/*, /api/v1/commissioners/{name}/agenda.

Focus on contract-level behaviour (auth, envelope shape, filter parsing);
upstream data is mocked or asserted loosely to keep tests fast and stable.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

from tests.conftest import TEST_API_BALANCE_MICRO


@pytest.fixture
def auth_headers():
    db = SessionLocal()
    try:
        user = User(
            email=f"test_v1_ds_{uuid.uuid4().hex[:8]}@example.com",
            full_name="v1 ds test",
            subscription_tier="blue",
            is_active=True,
            # Metered v1 endpoints debit before the handler runs; an unfunded
            # user 402s and the test reports a billing gate as a broken endpoint.
            api_balance_eur_micro=TEST_API_BALANCE_MICRO,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="ds-test")
        db.add(key)
        db.commit()
        yield {"X-API-Key": plaintext}
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


# ------------------------------------------------------------------ laws ---


def test_laws_unauth_returns_401():
    client = TestClient(app)
    r = client.get("/api/v1/laws")
    assert r.status_code == 401


def test_laws_returns_envelope_shape(auth_headers):
    client = TestClient(app)
    r = client.get("/api/v1/laws?limit=3", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # The v1 envelope is flat (PaginatedResponse in api/v1/_envelope.py):
    # pagination fields sit at the top level and the metadata block is
    # `op_core` (OP Core Metadata). The old nested `meta` key no longer
    # exists. This assertion could not notice the change while the test
    # was 402ing on an unfunded fixture.
    for field in ["total", "pages", "page", "limit", "has_more", "data", "op_core"]:
        assert field in body, f"missing {field} in {body.keys()}"
    assert body["limit"] == 3
    assert body["op_core"]["dct:publisher"].startswith("https://brubru.beresol.eu")
    assert isinstance(body["data"], list)
    assert len(body["data"]) <= 3


def test_laws_date_filter_parses(auth_headers):
    client = TestClient(app)
    r = client.get(
        "/api/v1/laws?published_from=2026-01-01&published_to=2026-01-31&limit=2",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["published_from"] == "2026-01-01"
    assert body["published_to"] == "2026-01-31"


# -------------------------------------------------------- procedures ---


def test_procedures_returns_envelope(auth_headers):
    client = TestClient(app)
    r = client.get("/api/v1/procedures?limit=2", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert body["limit"] == 2
    assert isinstance(body["data"], list)


def test_procedures_reject_bad_limit(auth_headers):
    client = TestClient(app)
    r = client.get("/api/v1/procedures?limit=500", headers=auth_headers)
    assert r.status_code == 422


# ------------------------------------------------------ legal-text ---


def test_legal_text_resolve_references_ok(auth_headers):
    client = TestClient(app)
    r = client.post(
        "/api/v1/legal-text/resolve-references",
        json={"text": "See Article 7 of Regulation (EU) 2024/1234.", "annotate_html": False},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert "refs" in r.json()


def test_legal_text_resolve_aliases_ok(auth_headers):
    client = TestClient(app)
    r = client.post(
        "/api/v1/legal-text/resolve-aliases",
        json={"text": "Under the GDPR and the Digital Services Act."},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "aliases" in body
    assert isinstance(body["aliases"], list)
    # Expect at least one hit for GDPR
    assert any(a.get("celex") for a in body["aliases"])


# ------------------------------------------------------ commissioners ---


def test_commissioner_unknown_name_returns_404(auth_headers):
    client = TestClient(app)
    with patch(
        "services.api_clients.commissioner_agenda_client.CommissionerAgendaClient.fetch_agenda",
        new=AsyncMock(return_value=(None, [])),
    ):
        r = client.get("/api/v1/commissioners/NotARealPerson/agenda", headers=auth_headers)
    assert r.status_code == 404


def test_commissioner_known_name_returns_envelope(auth_headers):
    from datetime import date
    from services.api_clients.commissioner_agenda_client import (
        CommissionerProfile,
        AgendaItem,
    )

    profile = CommissionerProfile(
        name="Raffaele Fitto",
        slug="raffaele-fitto",
        country="Italy",
        portfolio="Cohesion and Reforms",
        bio_url="https://commission.europa.eu/about/.../raffaele-fitto_en",
    )
    items = [
        AgendaItem(date=date(2026, 4, 15), title="Meeting with stakeholders", location="Brussels"),
    ]
    with patch(
        "services.api_clients.commissioner_agenda_client.CommissionerAgendaClient.fetch_agenda",
        new=AsyncMock(return_value=(profile, items)),
    ):
        client = TestClient(app)
        r = client.get("/api/v1/commissioners/Fitto/agenda", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # `commissioner_name` was a bespoke top-level field; the endpoint now returns
    # the standard v1 envelope, which carries no per-endpoint custom keys. The
    # commissioner is identified by the path, and the agenda lives in `data[]`.
    assert "commissioner_name" not in body, (
        "a bespoke envelope field reappeared -- v1 endpoints share one envelope"
    )
    assert body["total"] == 1
    assert body["data"][0]["title"] == "Meeting with stakeholders"
