"""
API v2 — "European Commission" domain tests.

Proves the EC sources delegate to the v1 Commission surface with identical
structure, on domain-rooted /api/v2/commission/* paths, under the same scopes
as v1 (read:commission, with the v1 exception preserved: meetings ->
read:calendar).

Covers the DB-backed sources; the live commissioners list/profile/agenda
(local JSON + live agenda pull) is exercised structurally by the OpenAPI
param/response parity checks, not here, to keep the suite deterministic.
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

COMM = "/api/v2/commission"

# (v2 tail, v1 path, scope) — DB-backed EC endpoints with a v1 twin.
DELEGATING = [
    ("commission-register-documents?limit=3", "/api/v1/commission-register-documents?limit=3", "read:commission"),
    ("rsb-opinions?limit=3", "/api/v1/rsb-opinions?limit=3", "read:commission"),
    ("infringements?limit=3", "/api/v1/infringements?limit=3", "read:commission"),
    ("consultations?limit=3", "/api/v1/consultations?limit=3", "read:commission"),
    ("tris-notifications?limit=3", "/api/v1/tris-notifications?limit=3", "read:commission"),
    ("meetings?limit=3", "/api/v1/meetings?limit=3", "read:calendar"),
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_comm_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 Commission Test User",
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
        json={"name": f"v2 comm {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


@pytest.mark.parametrize("tail,v1_path,scope", DELEGATING)
def test_commission_delegates_to_v1(client: TestClient, fresh_user, tail, v1_path, scope):
    _, token = fresh_user
    key = _mint(client, token, [scope])
    h = {"X-API-Key": key}
    v1 = client.get(v1_path, headers=h)
    v2 = client.get(f"{COMM}/{tail}", headers=h)
    assert v1.status_code == 200, v1.text
    assert v2.status_code == 200, v2.text
    b1, b2 = v1.json(), v2.json()
    assert set(b1.keys()) == set(b2.keys())
    assert b1["total"] == b2["total"]
    assert b1["data"] == b2["data"]


def test_commission_scope_enforced(client: TestClient, fresh_user):
    """A read:laws key must be rejected on an EC path that requires read:commission."""
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{COMM}/infringements?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403, r.text
    assert r.json().get("reason_code") == "scope_missing"


def test_meetings_uses_calendar_scope(client: TestClient, fresh_user):
    """meetings keeps the v1 read:calendar mapping, not read:commission."""
    _, token = fresh_user
    comm_only = _mint(client, token, ["read:commission"])
    r = client.get(f"{COMM}/meetings?limit=1", headers={"X-API-Key": comm_only})
    assert r.status_code == 403, r.text
    assert r.json().get("reason_code") == "scope_missing"
