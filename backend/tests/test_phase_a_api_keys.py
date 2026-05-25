"""
Phase A integration tests — self-serve mint + scope enforcement.

Exercises the new /api/me/api-keys surface and the path-pattern scope
enforcement in api.v1._deps, against a real DB session, using FastAPI's
TestClient mounted on the real application.

Coverage:
    - GET /api/me/api-keys/scopes returns the catalogue (no auth required)
    - POST /api/me/api-keys mints a key with chosen scopes + expiry
    - GET /api/me/api-keys lists the caller's keys (masked, no plaintext)
    - DELETE /api/me/api-keys/{id} revokes (and is idempotent)
    - 3-key active cap enforced (4th mint = 409)
    - Wildcard scope rejected from self-serve mint (422)
    - Unknown scope rejected (422)
    - Bad expiry rejected (422)
    - Scope-restricted key gets 403 on out-of-scope endpoint
    - Wildcard key works everywhere (admin/back-compat)
    - Sandbox key isolated to one active row
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token
from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    """Create a fresh active user + a JWT for them. Cleans up on teardown.

    Phase B: the user is credited with 10 EUR of API balance so Phase A
    tests that hit paid /api/v1/* endpoints don't trip the billing middleware.
    Phase B-specific tests set balance explicitly.
    """
    db = SessionLocal()
    try:
        u = User(
            email=f"phase_a_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Phase A Test User",
            subscription_tier="white",   # explicitly NOT blue — Phase A drops the gate
            is_active=True,
            api_balance_eur_micro=10_000_000,  # 10 EUR for paid v1 calls
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        token = create_access_token({"sub": str(u.id)})
        yield u, token
    finally:
        # cascade: clear usage events + keys, then user
        from models.api_billing import ApiUsageEvent
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
        db.close()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Scope catalogue
# ---------------------------------------------------------------------------

def test_scope_catalogue_is_public(client: TestClient):
    r = client.get("/api/me/api-keys/scopes")
    assert r.status_code == 200
    body = r.json()
    names = [s["name"] for s in body["scopes"]]
    assert "read:laws" in names
    assert "read:ep" in names
    assert "*" not in names
    assert body["max_active_keys"] == 3
    assert 180 in body["expiry_options_days"]


# ---------------------------------------------------------------------------
# Mint
# ---------------------------------------------------------------------------

def test_mint_succeeds_with_valid_payload(client: TestClient, fresh_user):
    user, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={
            "name": "Production",
            "scopes": ["read:laws", "read:calendar"],
            "expires_in_days": 180,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["key"].startswith("brubru_live_")
    assert body["scopes"] == ["read:laws", "read:calendar"]
    assert body["expires_at"] is not None
    assert body["name"] == "Production"
    # Plaintext never persisted: the key_prefix should match the first 4 hex
    # chars after the brubru_live_ prefix.
    plain = body["key"]
    assert body["key_prefix"] == plain[len("brubru_live_"):len("brubru_live_") + 4]


def test_mint_rejects_unknown_scope(client: TestClient, fresh_user):
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "Bad scope test", "scopes": ["read:laws", "read:bogus"], "expires_in_days": 180},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["reason_code"] == "invalid_scopes"


def test_mint_rejects_wildcard_scope(client: TestClient, fresh_user):
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "Wildcard test", "scopes": ["*"], "expires_in_days": 180},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["reason_code"] == "invalid_scopes"


def test_mint_rejects_bad_expiry(client: TestClient, fresh_user):
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "Bad expiry test", "scopes": ["read:laws"], "expires_in_days": 7},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["reason_code"] == "invalid_expiry"


def test_mint_rejects_short_name(client: TestClient, fresh_user):
    """Pydantic name min_length=3 fires before the handler runs (list-format 422)."""
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "ab", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 422
    # Pydantic returns detail as a list; check shape
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert any("name" in (e.get("loc") or []) for e in detail)


def test_mint_requires_auth(client: TestClient):
    r = client.post(
        "/api/me/api-keys",
        json={"name": "Auth test", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 3-key active cap
# ---------------------------------------------------------------------------

def test_three_key_active_cap(client: TestClient, fresh_user):
    _, token = fresh_user

    for i in range(3):
        r = client.post(
            "/api/me/api-keys",
            headers=_auth_headers(token),
            json={"name": f"Key {i + 1}", "scopes": ["read:laws"], "expires_in_days": 180},
        )
        assert r.status_code == 201, f"mint #{i + 1} failed: {r.text}"

    # 4th mint should fail at the cap
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "Key 4", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["reason_code"] == "key_cap_reached"
    assert body["max_active_keys"] == 3
    assert body["active_count"] == 3


def test_revoked_keys_dont_count_toward_cap(client: TestClient, fresh_user):
    _, token = fresh_user
    minted_ids: list[str] = []
    for i in range(3):
        r = client.post(
            "/api/me/api-keys",
            headers=_auth_headers(token),
            json={"name": f"Key {i + 1}", "scopes": ["read:laws"], "expires_in_days": 180},
        )
        assert r.status_code == 201
        minted_ids.append(r.json()["id"])

    # Revoke one
    r = client.delete(f"/api/me/api-keys/{minted_ids[0]}", headers=_auth_headers(token))
    assert r.status_code == 204

    # 4th mint should now succeed (only 2 active)
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "Key 4 (after revoke)", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# List + revoke
# ---------------------------------------------------------------------------

def test_list_excludes_plaintext_and_is_owner_scoped(client: TestClient, fresh_user):
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "ListMe", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 201

    r = client.get("/api/me/api-keys", headers=_auth_headers(token))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert "key" not in row  # plaintext NEVER returned on list
    assert row["name"] == "ListMe"
    assert row["scopes"] == ["read:laws"]
    assert row["is_active"] is True
    assert row["is_expired"] is False


def test_revoke_is_idempotent(client: TestClient, fresh_user):
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "RevokeMe", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    key_id = r.json()["id"]

    r1 = client.delete(f"/api/me/api-keys/{key_id}", headers=_auth_headers(token))
    assert r1.status_code == 204
    r2 = client.delete(f"/api/me/api-keys/{key_id}", headers=_auth_headers(token))
    assert r2.status_code == 204  # idempotent


def test_revoke_other_users_key_returns_404(client: TestClient, fresh_user):
    _, token = fresh_user
    # Use a random UUID — not owned by this user
    r = client.delete(f"/api/me/api-keys/{uuid.uuid4()}", headers=_auth_headers(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scope enforcement at the v1 layer
# ---------------------------------------------------------------------------

def _v1_error(body: dict) -> dict:
    """Pull reason_code/error fields from a v1 error response.

    The v1 layer flattens HTTPException detail dicts into the top-level
    response body alongside `request_id`. So a 403 with reason_code='scope_missing'
    surfaces as {"error": "...", "reason_code": "scope_missing", "request_id": "..."}.
    """
    return body


def test_scoped_key_403s_on_out_of_scope_endpoint(client: TestClient, fresh_user):
    """A key scoped only to read:laws gets 403 on a read:ep endpoint."""
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "LawsOnly", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    assert r.status_code == 201
    plaintext = r.json()["key"]

    # /api/v1/meps lives under read:ep — should be denied
    r = client.get("/api/v1/meps?limit=1", headers={"X-API-Key": plaintext})
    assert r.status_code == 403, r.text
    body = _v1_error(r.json())
    assert body["reason_code"] == "scope_missing"
    assert body["required_scope"] == "read:ep"


def test_scoped_key_allows_in_scope_endpoint(client: TestClient, fresh_user):
    """Same key with read:laws is allowed on /api/v1/laws."""
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "LawsOnly2", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    plaintext = r.json()["key"]
    r = client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})
    # /laws may legitimately return 200 (data present) or 422 (validation),
    # but it must NOT return 403 — the scope check should pass.
    assert r.status_code != 403, r.text


def test_free_authed_endpoint_accessible_without_scope(client: TestClient, fresh_user):
    """/api/v1/whoami goes through auth + scope but is in FREE_PATH_PATTERNS,
    so any valid key with any scope should reach 200.
    """
    _, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "MinimalKey", "scopes": ["read:laws"], "expires_in_days": 180},
    )
    plaintext = r.json()["key"]
    r = client.get("/api/v1/whoami", headers={"X-API-Key": plaintext})
    assert r.status_code == 200, r.text


def test_wildcard_key_works_everywhere(client: TestClient):
    """A wildcard key (admin-minted, scopes=['*']) passes scope check on every path.

    Uses an existing wildcard key from migration 078 backfill rather than
    minting one (self-serve mints can't request wildcard).
    """
    db = SessionLocal()
    try:
        wildcard_key = (
            db.query(ApiKey)
            .filter(
                ApiKey.scopes.op("@>")('["*"]'),
                ApiKey.revoked_at.is_(None),
            )
            .first()
        )
    finally:
        db.close()

    if wildcard_key is None:
        pytest.skip("No active wildcard key in DB (backfill not applied?)")

    # We can't curl with an arbitrary wildcard key because we don't have the
    # plaintext (only the hash is stored). Instead, verify via the model
    # helper that wildcard scope grants every scope.
    assert wildcard_key.grants_scope("read:laws") is True
    assert wildcard_key.grants_scope("read:ep") is True
    assert wildcard_key.grants_scope("read:misc") is True  # even uncatalogued
    assert wildcard_key.grants_scope(None) is True


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

def test_expired_key_returns_401_on_v1(client: TestClient, fresh_user):
    """Expired key blocked at the auth layer. Hits /whoami (auth-required + free path)."""
    user, token = fresh_user
    r = client.post(
        "/api/me/api-keys",
        headers=_auth_headers(token),
        json={"name": "ExpiresSoon", "scopes": ["read:laws"], "expires_in_days": 30},
    )
    plaintext = r.json()["key"]
    key_id = r.json()["id"]

    # Force-expire
    db = SessionLocal()
    try:
        k = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        k.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    # /whoami is authenticated, so the expiry check at auth time fires.
    r = client.get("/api/v1/whoami", headers={"X-API-Key": plaintext})
    assert r.status_code == 401, r.text
    body = _v1_error(r.json())
    assert body["reason_code"] == "key_expired"


# ---------------------------------------------------------------------------
# Sandbox isolation
# ---------------------------------------------------------------------------

def test_single_active_sandbox_constraint():
    """The partial unique index on (is_sandbox) WHERE is_sandbox AND not revoked
    means we can never accidentally end up with two active sandbox keys.
    """
    from sqlalchemy.exc import IntegrityError

    db = SessionLocal()
    try:
        # Find an existing user
        owner = db.query(User).filter(User.role == "admin").first()
        if owner is None:
            pytest.skip("No admin user in DB")

        # Check if sandbox already exists; if so, this test confirms the constraint
        existing = (
            db.query(ApiKey)
            .filter(ApiKey.is_sandbox.is_(True), ApiKey.revoked_at.is_(None))
            .count()
        )

        # Attempt to insert a SECOND sandbox row should violate the unique index
        _, k = ApiKey.generate(
            user_id=owner.id, name="Conflicting sandbox",
            scopes=["read:laws"], expires_in_days=None, is_sandbox=True,
        )
        db.add(k)

        if existing >= 1:
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
        else:
            db.commit()
            # Clean up so we don't leave a sandbox lying around
            k.revoked_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
