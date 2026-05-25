"""
API v2 — "Legislative data" / EUR-Lex source integration tests.

Proves the v2 foundation: the institution-rooted paths
(/api/v2/legislative/eur-lex/*) reuse the v1 auth/scope/billing dependency,
the canonical PaginatedResponse envelope, and the canonical error envelope —
i.e. they follow the exact structure of the v1 surface Jordi reviewed.

Coverage:
    - v2 /laws list is parity-equal to v1 /laws (same total, same CELEX page)
    - v2 cross-links (text_url) are rewritten to the v2 path, not v1
    - scope enforcement works on v2 paths (read:laws required; read:ep -> 403)
    - the canonical error envelope (reason_code + request_id) covers v2 404s
    - v2 paths are metered (balance debited)
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
            email=f"v2_eurlex_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 EUR-Lex Test User",
            subscription_tier="white",
            is_active=True,
            api_balance_eur_micro=10_000_000,  # 10 EUR
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
        json={"name": f"v2 test {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


def _balance(user_id) -> int:
    db = SessionLocal()
    try:
        row = db.execute(
            __import__("sqlalchemy").text(
                "SELECT api_balance_eur_micro FROM public.users WHERE id = :uid"
            ),
            {"uid": str(user_id)},
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Parity
# ---------------------------------------------------------------------------

def test_v2_laws_list_parity_with_v1(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}

    v1 = client.get("/api/v1/laws?limit=3", headers=h)
    v2 = client.get(f"{V2}/laws?limit=3", headers=h)
    assert v1.status_code == 200, v1.text
    assert v2.status_code == 200, v2.text

    b1, b2 = v1.json(), v2.json()
    # Same corpus -> same total + same envelope keys.
    assert b1["total"] == b2["total"]
    assert set(b1.keys()) == set(b2.keys())
    assert [i["celex"] for i in b1["data"]] == [i["celex"] for i in b2["data"]]

    # v2 cross-links point at the v2 surface.
    for item in b2["data"]:
        if item.get("text_url"):
            assert item["text_url"].startswith(V2 + "/laws/")


def test_v2_law_detail_parity_and_nativised_link(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}

    lst = client.get(f"{V2}/laws?limit=5", headers=h).json()
    celex = next((i["celex"] for i in lst["data"] if i.get("celex")), None)
    assert celex, "no CELEX available in corpus to test detail"

    v1 = client.get(f"/api/v1/laws/{celex}", headers=h)
    v2 = client.get(f"{V2}/laws/{celex}", headers=h)
    assert v1.status_code == 200 and v2.status_code == 200
    assert v1.json()["celex"] == v2.json()["celex"] == celex
    assert v2.json()["text_url"] == f"{V2}/laws/{celex}/text"


def test_v2_text_reaches_handler(client: TestClient, fresh_user):
    """The text endpoint does a live Cellar fetch, so its terminal status is
    environment-dependent (200 cache/live hit, 404 no body, 502 upstream).
    We assert the v2 request cleared auth + scope + billing and reached the
    handler — i.e. it is NOT 401/402/403 — and that a 200 is well-formed.
    Delegation guarantees byte-for-byte parity with v1 beyond that point."""
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}

    lst = client.get(f"{V2}/laws?limit=5", headers=h).json()
    celex = next((i["celex"] for i in lst["data"] if i.get("celex")), None)
    assert celex

    v2 = client.get(f"{V2}/laws/{celex}/text", headers=h)
    assert v2.status_code not in (401, 402, 403), v2.text
    assert v2.status_code in (200, 404, 502)
    if v2.status_code == 200:
        assert v2.json()["celex"] == celex
        assert v2.json()["format"] == "plain"


# ---------------------------------------------------------------------------
# Scope enforcement on v2 paths
# ---------------------------------------------------------------------------

def test_v2_out_of_scope_key_403s(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:ep"])  # NOT read:laws
    r = client.get(f"{V2}/laws?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["reason_code"] == "scope_missing"
    assert body["required_scope"] == "read:laws"


def test_v2_in_scope_key_not_403(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws?limit=1", headers={"X-API-Key": key})
    assert r.status_code != 403, r.text


# ---------------------------------------------------------------------------
# Canonical error envelope covers v2
# ---------------------------------------------------------------------------

def test_v2_error_envelope_on_missing_celex(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}/laws/99999Z9999", headers={"X-API-Key": key})
    assert r.status_code == 404, r.text
    body = r.json()
    # Canonical v1-style error shape — proves the error handler covers /api/v2/*.
    assert body["reason_code"] == "not_found"
    assert "request_id" in body
    assert r.headers.get("X-Request-Id")


# ---------------------------------------------------------------------------
# Billing covers v2
# ---------------------------------------------------------------------------

def test_v2_path_is_metered(client: TestClient, fresh_user):
    user, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    before = _balance(user.id)
    r = client.get(f"{V2}/laws?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    after = _balance(user.id)
    # Lightweight read = 1000 micro-euro debit.
    assert before - after == 1000


# ---------------------------------------------------------------------------
# Foundation wiring — deterministic unit checks (no network)
# ---------------------------------------------------------------------------

def test_v2_scope_mapping():
    from services.api_keys.scopes import resolve_required_scope
    assert resolve_required_scope("/api/v2/legislative/eur-lex/laws") == "read:laws"
    assert resolve_required_scope("/api/v2/legislative/eur-lex/identify") == "read:laws"
    assert resolve_required_scope("/api/v2/legislative/oeil/procedures") == "read:procedures"
    assert resolve_required_scope("/api/v2/legislative/legislative-train/carriages") == "read:procedures"
    assert resolve_required_scope("/api/v2/legislative/eurovoc/concepts/search") == "read:publications"
    # Uncatalogued v2 path denies by default (read:misc is not user-mintable).
    assert resolve_required_scope("/api/v2/legislative/unknown/foo") == "read:misc"


def test_v2_pricing_tiers():
    from services.billing.api_meter import resolve_cost_micro
    base = "/api/v2/legislative/eur-lex/laws/32016R0679"
    assert resolve_cost_micro(f"{base}/text")[0] == 10000
    assert resolve_cost_micro(f"{base}/recital-article-map")[0] == 5000
    assert resolve_cost_micro(f"{base}/defined-terms")[0] == 5000
    assert resolve_cost_micro("/api/v2/legislative/eur-lex/laws")[0] == 1000


# ---------------------------------------------------------------------------
# Delegated endpoints — deterministic parity (no upstream network)
# ---------------------------------------------------------------------------

def test_v2_identify_parity(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}
    v1 = client.get("/api/v1/identify?q=32016R0679", headers=h)
    v2 = client.get(f"{V2}/identify?q=32016R0679", headers=h)
    assert v1.status_code == 200 and v2.status_code == 200, v2.text
    assert v1.json()["kind"] == v2.json()["kind"]
    assert v1.json()["value"] == v2.json()["value"]


def test_v2_resolve_aliases_parity(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}
    payload = {"text": "Comparing GDPR and the AI Act on automated decisions"}
    v1 = client.post("/api/v1/legal-text/resolve-aliases", headers=h, json=payload)
    v2 = client.post(f"{V2}/resolve-aliases", headers=h, json=payload)
    assert v1.status_code == 200 and v2.status_code == 200, v2.text
    v1_celexes = {a["celex"] for a in v1.json()["aliases"]}
    v2_celexes = {a["celex"] for a in v2.json()["aliases"]}
    assert v1_celexes == v2_celexes
    assert "32016R0679" in v2_celexes  # GDPR resolved


def test_v2_resolve_references_reaches_handler(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.post(
        f"{V2}/resolve-references",
        headers={"X-API-Key": key},
        json={"text": "Article 5 of Regulation (EU) 2022/2065 prohibits dark patterns."},
    )
    assert r.status_code == 200, r.text
    assert "refs" in r.json()


# ---------------------------------------------------------------------------
# Network / cache-dependent endpoints — reach-handler proof (auth+scope+billing
# all cleared on the v2 path). Terminal status varies with upstream so we only
# assert it is NOT an auth/scope/billing rejection.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        "/identify/scan?text=See%20Regulation%20(EU)%202016/679.",
        "/verify-citation/32016R0679",
        "/laws/32016R0679/cellar",
        "/laws/32016R0679/relationships",
        "/laws/32016R0679/languages",
        "/laws/32016R0679/recital-article-map",
        "/laws/32016R0679/defined-terms",
        "/recent?published_from=2026-05-01&limit=2",
    ],
)
def test_v2_live_endpoints_reach_handler(client: TestClient, fresh_user, path):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{V2}{path}", headers={"X-API-Key": key})
    # Cleared auth (401), scope (403) and billing (402) — reached the handler.
    assert r.status_code not in (401, 402, 403), f"{path} -> {r.status_code}: {r.text[:300]}"


def test_v2_live_endpoint_out_of_scope_403(client: TestClient, fresh_user):
    """A read:ep key is rejected on every EUR-Lex path (read:laws gate)."""
    _, token = fresh_user
    key = _mint(client, token, ["read:ep"])
    r = client.get(f"{V2}/identify?q=32016R0679", headers={"X-API-Key": key})
    assert r.status_code == 403
    assert r.json()["required_scope"] == "read:laws"
