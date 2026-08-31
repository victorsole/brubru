"""
API v2 — "European Parliament" domain tests.

Proves the EP sources delegate to the v1 EP surface with identical structure,
on domain-rooted /api/v2/parliament/* paths, under the same scopes as v1
(read:ep, with the two v1 exceptions preserved: webstreams -> read:calendar,
eprs -> read:knowledge).

Covers the DB-backed sources only; the live-pass-through MEPs source is
exercised structurally (param/response parity) by the OpenAPI checks, not here,
to keep the suite deterministic.
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

PARL = "/api/v2/parliament"

# (v2 tail, v1 path, scope) — DB-backed EP endpoints with a v1 twin.
DELEGATING = [
    ("votes?limit=3", "/api/v1/votes?limit=3", "read:ep"),
    ("resolutions?limit=3", "/api/v1/resolutions?limit=3", "read:ep"),
    ("ep-documents?limit=3", "/api/v1/ep-documents?limit=3", "read:ep"),
    ("reports?limit=3", "/api/v1/reports?limit=3", "read:ep"),
    ("opinions?limit=3", "/api/v1/opinions?limit=3", "read:ep"),
    ("amendments?limit=3", "/api/v1/amendments?limit=3", "read:ep"),
    ("texts-adopted?limit=3", "/api/v1/texts-adopted?limit=3", "read:ep"),
    ("texts-submitted?limit=3", "/api/v1/texts-submitted?limit=3", "read:ep"),
    ("parliamentary-questions?limit=3", "/api/v1/parliamentary-questions?limit=3", "read:ep"),
    ("committees/LIBE/work-items?limit=3", "/api/v1/committees/LIBE/work-items?limit=3", "read:ep"),
    ("webstreams?limit=3", "/api/v1/webstreams?limit=3", "read:calendar"),
    ("eprs?limit=3", "/api/v1/eprs?limit=3", "read:knowledge"),
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_parl_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 Parliament Test User",
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
        json={"name": f"v2 parl {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]



def _without_self(rows):
    """v2 items carry a `self` link; v1 items do not, deliberately.

    The link is built from the v2 item route, so emitting it on a v1 response
    would point a v1 client at a v2 URL. Delegation is still exact in every
    other respect, which is what this test is for, so the field is stripped
    before comparing rather than the assertion being weakened.
    """
    return [{k: v for k, v in r.items() if k != "self"} if isinstance(r, dict) else r
            for r in rows]

@pytest.mark.parametrize("tail,v1_path,scope", DELEGATING)
def test_parliament_delegates_to_v1(client: TestClient, fresh_user, tail, v1_path, scope):
    _, token = fresh_user
    key = _mint(client, token, [scope])
    h = {"X-API-Key": key}
    v1 = client.get(v1_path, headers=h)
    v2 = client.get(f"{PARL}/{tail}", headers=h)
    assert v1.status_code == 200, v1.text
    assert v2.status_code == 200, v2.text
    b1, b2 = v1.json(), v2.json()
    assert set(b1.keys()) == set(b2.keys())
    assert b1["total"] == b2["total"]
    assert _without_self(b1["data"]) == _without_self(b2["data"])


def test_parliament_scope_enforced(client: TestClient, fresh_user):
    """A read:laws key must be rejected on an EP path that requires read:ep."""
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{PARL}/votes?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403, r.text
    assert r.json().get("reason_code") == "scope_missing"


def test_webstreams_uses_calendar_scope(client: TestClient, fresh_user):
    """webstreams keeps the v1 read:calendar mapping, not read:ep."""
    _, token = fresh_user
    ep_only = _mint(client, token, ["read:ep"])
    r = client.get(f"{PARL}/webstreams?limit=1", headers={"X-API-Key": ep_only})
    assert r.status_code == 403, r.text
    assert r.json().get("reason_code") == "scope_missing"
