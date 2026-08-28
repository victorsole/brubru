"""
API v2 — "Brubru Proprietary Databases" integration tests.

Proves the three proprietary sources (guides / catalan / canon) follow the
exact v1 structure Jordi reviewed: shared auth/scope/billing dependency, the
canonical PaginatedResponse envelope, the canonical error envelope, and the 5
mandatory datapoints present on every item (even when null).

Per feedback_assert_body_not_just_status.md, every test asserts the RESPONSE
BODY contract — not merely a 2xx status.

Coverage:
    - guides list parity with v1 /knowledge-guides + detail full body
    - catalan list parity with v1 /catalan-translations + stats + body inline
    - canon list (whole catalogue) + filters + detail + include_body
    - the 5 datapoints present on every list item and detail
    - scope enforcement (read:knowledge vs read:laws) across the three sources
    - canonical 404 error envelope (reason_code + request_id)
    - paths are metered (balance debited)
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

BASE = "/api/v2/proprietary"
DATAPOINTS = {"public_url", "body_txt", "body_html", "document_date", "creation_date"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_prop_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 Proprietary Test User",
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
        json={"name": f"v2 prop {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


def _balance(user_id) -> int:
    db = SessionLocal()
    try:
        from sqlalchemy import text
        row = db.execute(
            text("SELECT api_balance_eur_micro FROM public.users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        db.close()


def _assert_envelope(body: dict) -> None:
    for k in ("total", "returned", "pages", "page", "limit", "has_more", "data"):
        assert k in body, f"missing envelope key {k!r}"
    # 5 datapoints present at envelope level (even when null).
    assert DATAPOINTS <= set(body.keys()), f"envelope missing datapoints: {DATAPOINTS - set(body.keys())}"


def _assert_item_datapoints(item: dict) -> None:
    assert DATAPOINTS <= set(item.keys()), f"item missing datapoints: {DATAPOINTS - set(item.keys())}"


# ---------------------------------------------------------------------------
# Guides (delegates to v1 /knowledge-guides)
# ---------------------------------------------------------------------------

def test_guides_list_parity_with_v1(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:knowledge"])
    h = {"X-API-Key": key}

    v1 = client.get("/api/v1/knowledge-guides?limit=5", headers=h)
    v2 = client.get(f"{BASE}/guides?limit=5", headers=h)
    assert v1.status_code == 200, v1.text
    assert v2.status_code == 200, v2.text
    b1, b2 = v1.json(), v2.json()
    _assert_envelope(b2)
    assert b1["total"] == b2["total"] > 0
    assert [i["id"] for i in b1["data"]] == [i["id"] for i in b2["data"]]
    assert all(i["title"] for i in b2["data"])
    # 5 datapoints present + body_txt populated on every item (body_html is not populated for guides).
    for item in b2["data"]:
        _assert_item_datapoints(item)
        assert item["public_url"]
        assert item["body_txt"], "guide body_txt must carry the markdown content"


def test_guides_detail_full_body(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:knowledge"])
    h = {"X-API-Key": key}
    gid = client.get(f"{BASE}/guides?limit=1", headers=h).json()["data"][0]["id"]
    r = client.get(f"{BASE}/guides/{gid}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == gid
    assert body["full_content_chars"] > 0
    assert body["content"], "guide detail must return full content"
    assert body["body_txt"], "guide detail body_txt must be populated"
    # body_html is intentionally not populated for guides


# ---------------------------------------------------------------------------
# Catalan (delegates to v1 /catalan-translations)
# ---------------------------------------------------------------------------

def test_catalan_list_parity_and_stats(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}

    v1 = client.get("/api/v1/catalan-translations?limit=3", headers=h)
    v2 = client.get(f"{BASE}/catalan?limit=3", headers=h)
    assert v1.status_code == 200 and v2.status_code == 200, (v1.text, v2.text)
    b1, b2 = v1.json(), v2.json()
    _assert_envelope(b2)
    assert b1["total"] == b2["total"] > 0
    assert [i["celex"] for i in b1["data"]] == [i["celex"] for i in b2["data"]]

    stats = client.get(f"{BASE}/catalan/stats", headers=h)
    assert stats.status_code == 200, stats.text
    s = stats.json()
    assert s["total"] > 0 and s["licence"] == "MIT"
    assert s["by_doc_type"], "stats must include by_doc_type breakdown"


def test_catalan_detail_body_populated_by_default(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    h = {"X-API-Key": key}
    # GDPR is a stable, large translation; v2 populates body by default (from cache).
    r = client.get(f"{BASE}/catalan/32016R0679", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["celex"] == "32016R0679"
    assert body["has_body"] is True
    assert body["body_html"], "v2 catalan detail must populate body_html by default"
    assert body["body_txt"], "v2 catalan detail must populate body_txt by default"

    # Opt-out for a lighter response.
    meta = client.get(f"{BASE}/catalan/32016R0679?body=none", headers=h).json()
    assert meta["body_html"] is None


# ---------------------------------------------------------------------------
# Canon (native — manifest-backed)
# ---------------------------------------------------------------------------

def test_canon_list_whole_catalogue(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:knowledge"])
    h = {"X-API-Key": key}
    r = client.get(f"{BASE}/canon?limit=100", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_envelope(body)
    assert body["total"] >= 20, "expected the full canon+deep-dive catalogue"
    slugs = {i["slug"] for i in body["data"]}
    assert "2024-1689_aiact" in slugs and "biotech-act" in slugs
    types = {i["report_type"] for i in body["data"]}
    assert types == {"canon", "deep_dive"}
    for item in body["data"]:
        _assert_item_datapoints(item)
        assert item["public_url"].startswith("https://brubru.beresol.eu/")
        # bodies populated from the DB cache on the list too
        assert item["body_html"], f"canon list {item['slug']} should have body_html"
        assert item["body_txt"], f"canon list {item['slug']} should have body_txt"
        # canon entries carry document_date (the act's publication date)
        if item["report_type"] == "canon" and item["celex"]:
            assert item["document_date"], f"canon {item['slug']} should have document_date"


def test_canon_filters(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:knowledge"])
    h = {"X-API-Key": key}
    pharma = client.get(f"{BASE}/canon?report_type=canon&legal_family=eu_pharmaceutical", headers=h)
    assert pharma.status_code == 200, pharma.text
    pb = pharma.json()
    # A lower bound, not an equality: the canon grows, and this assertion went
    # red on 28 Aug 2026 purely because the pharmaceutical family reached 10.
    # What the test is actually for is that the FILTER filters -- pinning the
    # exact size just fails every time the corpus does its job.
    assert pb["total"] >= 5, f"expected at least the 5 known pharma canon entries, got {pb['total']}"
    assert all(i["legal_family"] == "eu_pharmaceutical" for i in pb["data"])
    unfiltered = client.get(f"{BASE}/canon?report_type=canon", headers=h).json()["total"]
    assert pb["total"] < unfiltered, "legal_family filter returned the whole catalogue"

    bad = client.get(f"{BASE}/canon?report_type=nope", headers=h)
    assert bad.status_code == 400
    assert bad.json()["reason_code"] == "invalid_parameter"


def test_canon_detail_and_body(client, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:knowledge"])
    h = {"X-API-Key": key}
    r = client.get(f"{BASE}/canon/2024-1689_aiact", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slug"] == "2024-1689_aiact"
    assert body["celex"] == "32024R1689"
    _assert_item_datapoints(body)
    # body populated by DEFAULT (no opt-in needed), served from the DB cache
    assert body["body_html"], "canon detail must populate body_html by default"
    assert body["body_txt"], "canon detail must populate body_txt by default"

    # Catalan edition + opt-out
    ca = client.get(f"{BASE}/canon/2024-1689_aiact?lang=ca", headers=h).json()
    assert ca["body_html"], "ca edition body must be populated"
    meta = client.get(f"{BASE}/canon/2024-1689_aiact?include_body=false", headers=h).json()
    assert meta["body_html"] is None, "include_body=false omits body"


# ---------------------------------------------------------------------------
# Scope enforcement + error envelope + metering
# ---------------------------------------------------------------------------

def test_scope_enforcement(client, fresh_user):
    _, token = fresh_user
    h_know = {"X-API-Key": _mint(client, token, ["read:knowledge"])}
    h_laws = {"X-API-Key": _mint(client, token, ["read:laws"])}

    # read:knowledge can hit guides/canon but NOT catalan (read:laws)
    assert client.get(f"{BASE}/guides?limit=1", headers=h_know).status_code == 200
    assert client.get(f"{BASE}/canon?limit=1", headers=h_know).status_code == 200
    r = client.get(f"{BASE}/catalan?limit=1", headers=h_know)
    assert r.status_code == 403
    assert r.json()["reason_code"] == "scope_missing"

    # read:laws can hit catalan but NOT guides/canon
    assert client.get(f"{BASE}/catalan?limit=1", headers=h_laws).status_code == 200
    assert client.get(f"{BASE}/guides?limit=1", headers=h_laws).status_code == 403
    assert client.get(f"{BASE}/canon?limit=1", headers=h_laws).status_code == 403


def test_canon_404_error_envelope(client, fresh_user):
    _, token = fresh_user
    h = {"X-API-Key": _mint(client, token, ["read:knowledge"])}
    r = client.get(f"{BASE}/canon/does-not-exist", headers=h)
    assert r.status_code == 404
    body = r.json()
    # canonical FLAT error envelope (keys spread to top level on /api/v2/* paths)
    assert body["reason_code"] == "not_found"
    assert body["slug"] == "does-not-exist"
    assert "request_id" in body
    assert r.headers.get("X-Request-Id")


def test_paths_are_metered(client, fresh_user):
    user, token = fresh_user
    h = {"X-API-Key": _mint(client, token, ["read:knowledge"])}
    before = _balance(user.id)
    client.get(f"{BASE}/canon?limit=1", headers=h)
    after = _balance(user.id)
    assert after < before, "v2 proprietary paths must debit balance"
