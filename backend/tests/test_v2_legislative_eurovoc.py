"""
API v2 — "Legislative data" / EuroVoc & vocabularies source tests.

Proves the EuroVoc source delegates to v1 cellar_discover (EuroVoc) and v1
vocabularies (authority NALs), under the read:publications scope, on
domain-rooted v2 paths.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token
from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

EV = "/api/v2/legislative/eurovoc"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_ev_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 EuroVoc Test User",
            subscription_tier="white",
            is_active=True,
            api_balance_eur_micro=10_000_000,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        token = create_access_token({"sub": str(u.id)})
        yield u, token
    finally:
        from models.api_billing import ApiUsageEvent
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
        db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mint(client: TestClient, token: str, scopes: list[str]) -> str:
    r = client.post(
        "/api/me/api-keys",
        headers=_auth(token),
        json={"name": f"v2 ev {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


def test_authority_parity_with_v1(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:publications"])
    h = {"X-API-Key": key}
    v1 = client.get("/api/v1/vocabularies/corporate-bodies?lang=en&limit=3", headers=h)
    v2 = client.get(f"{EV}/authority/corporate-bodies?lang=en&limit=3", headers=h)
    assert v1.status_code == 200 and v2.status_code == 200, v2.text
    b1, b2 = v1.json(), v2.json()
    assert b1["total"] == b2["total"]
    assert [i["uri"] for i in b1["data"]] == [i["uri"] for i in b2["data"]]


def test_authority_unknown_table_404(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:publications"])
    r = client.get(f"{EV}/authority/not-a-table", headers={"X-API-Key": key})
    assert r.status_code == 404, r.text
    assert r.json()["reason_code"] == "not_found"


def test_eurovoc_requires_read_publications_scope(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])  # wrong scope
    r = client.get(f"{EV}/authority/corporate-bodies?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403, r.text
    assert r.json()["required_scope"] == "read:publications"


@pytest.mark.parametrize(
    "path",
    [
        "/concepts/search?q=artificial%20intelligence&limit=3",
        "/concepts/3030/acts?limit=3",
        "/authority/procedures?lang=en&limit=5",
    ],
)
def test_eurovoc_endpoints_reach_handler(client: TestClient, fresh_user, path):
    _, token = fresh_user
    key = _mint(client, token, ["read:publications"])
    r = client.get(f"{EV}{path}", headers={"X-API-Key": key})
    assert r.status_code not in (401, 402, 403), f"{path} -> {r.status_code}: {r.text[:300]}"
