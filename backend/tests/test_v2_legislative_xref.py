"""
API v2 — "Legislative data" / EUR-Lex crown jewels: resolve + xref.

Proves the native (non-delegated) endpoints: /laws/resolve (any identifier ->
canonical CELEX + ELI) and /laws/{celex}/xref (aggregate cross-reference graph
with law_xref cache write-through), under read:laws, on domain-rooted v2 paths.
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

V2 = "/api/v2/legislative/eur-lex"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_xref_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 Xref Test User",
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
        json={"name": f"v2 xref {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


def _balance(user_id) -> int:
    from sqlalchemy import text
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT api_balance_eur_micro FROM public.users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------

def test_resolve_alias_gdpr(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/resolve?id=GDPR", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["celex"] == "32016R0679"
    assert body["resolved_via"] == "alias"
    assert body["brubru_url"].endswith("/laws/32016R0679")


def test_resolve_raw_celex(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/resolve?id=32016R0679", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["celex"] == "32016R0679"
    assert body["resolved_via"] == "celex"


def test_resolve_does_not_collide_with_detail_route(client: TestClient, fresh_user):
    """/laws/resolve must hit the resolver, not /laws/{celex} with celex='resolve'."""
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/resolve?id=AI%20Act", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    assert "resolved_via" in r.json()  # resolver shape, not a LawItem/404


def test_resolve_unrecognised_degrades(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/resolve?id=qwertyuiopzxcv", headers={"X-API-Key": key})
    assert r.status_code in (200, 422), r.text
    if r.status_code == 200:
        assert r.json()["celex"] is None
    else:
        assert r.json()["reason_code"] == "unresolved_identifier"


def test_resolve_requires_read_laws(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:ep"])
    r = client.get(f"{V2}/laws/resolve?id=GDPR", headers={"X-API-Key": key})
    assert r.status_code == 403
    assert r.json()["required_scope"] == "read:laws"


# ---------------------------------------------------------------------------
# xref
# ---------------------------------------------------------------------------

def test_xref_aggregates_and_caches(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}
    # Force a fresh compute (write-through), then read the cache.
    first = client.get(f"{V2}/laws/32016R0679/xref?refresh=true", headers=h)
    assert first.status_code == 200, first.text
    assert first.json()["celex"] == "32016R0679"
    assert first.json()["cached"] is False
    assert first.json()["relation_total"] >= 0

    second = client.get(f"{V2}/laws/32016R0679/xref", headers=h)
    assert second.status_code == 200, second.text
    assert second.json()["cached"] is True  # served from law_xref


def test_xref_priced_as_heavy(client: TestClient, fresh_user):
    user, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    before = _balance(user.id)
    r = client.get(f"{V2}/laws/32016R0679/xref", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    after = _balance(user.id)
    assert before - after == 5000  # heavy-compute tier


def test_xref_404_unknown_celex(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/99999Z9999/xref", headers={"X-API-Key": key})
    assert r.status_code == 404, r.text
    assert r.json()["reason_code"] == "not_found"


def test_xref_browse_all_lists_index(client: TestClient, fresh_user):
    """The browse-all /xref lists the cross-reference index (not a single celex)."""
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}
    # Ensure at least one row exists in the index.
    client.get(f"{V2}/laws/32016R0679/xref?refresh=true", headers=h)
    r = client.get(f"{V2}/xref?limit=50", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body and "total" in body
    assert body["total"] >= 1
    assert all("celex" in item for item in body["data"])


def test_xref_browse_requires_read_laws(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:ep"])
    r = client.get(f"{V2}/xref?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403
    assert r.json()["required_scope"] == "read:laws"
