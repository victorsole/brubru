"""
API v2 — "Legislative data" remaining PROPOSED endpoints.

Covers the native EUR-Lex extras (views, lifecycle, consolidated, OJ,
summaries), OEIL /procedures/latest, the Legislative Train source, and the
EuroVoc /directories/legal-acts alias.
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

EL = "/api/v2/legislative/eur-lex"
OEIL = "/api/v2/legislative/oeil"
TRAIN = "/api/v2/legislative/legislative-train"
EV = "/api/v2/legislative/eurovoc"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_prop_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 Proposed Test User",
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


def _mint(client: TestClient, token: str, scopes: list[str]) -> str:
    r = client.post(
        "/api/me/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": f"v2 prop {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


# ---------------------------------------------------------------------------
# EUR-Lex proposed
# ---------------------------------------------------------------------------

def test_views_deterministic(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{EL}/laws/32016R0679/views", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["celex"] == "32016R0679"
    for code in ("txt", "all", "his", "nim", "lsu", "pdf"):
        assert code in body["views"]
        assert "32016R0679" in body["views"][code]
    assert "publications.europa.eu" in body["xml_notice"]


def test_summary_by_celex(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{EL}/laws/summaries/32016R0679", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["celex"] == "32016R0679"
    assert "CELEX:32016R0679" in body["lsu_url"]


@pytest.mark.parametrize(
    "path",
    [
        "/laws/32016R0679/lifecycle",
        "/laws/32016R0679/consolidated",
        "/oj/daily?date=2026-05-01&series=L&limit=2",
        "/oj/L/2016/119?limit=2",
        "/laws/summaries?q=data%20protection&limit=3",
    ],
)
def test_eurlex_proposed_reach_handler(client: TestClient, fresh_user, path):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])
    r = client.get(f"{EL}{path}", headers={"X-API-Key": key})
    assert r.status_code not in (401, 402, 403), f"{path} -> {r.status_code}: {r.text[:300]}"


# ---------------------------------------------------------------------------
# OEIL latest
# ---------------------------------------------------------------------------

def test_oeil_latest_reaches(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    r = client.get(f"{OEIL}/procedures/latest?days=30&limit=3", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    assert "data" in r.json()


def test_oeil_latest_not_captured_by_detail_route(client: TestClient, fresh_user):
    """/procedures/latest must hit the latest feed, not /procedures/{reference}."""
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    r = client.get(f"{OEIL}/procedures/latest", headers={"X-API-Key": key})
    assert r.status_code == 200
    # latest returns a paginated envelope, detail would return a single object
    assert "data" in r.json() and "total" in r.json()


# ---------------------------------------------------------------------------
# Legislative Train
# ---------------------------------------------------------------------------

def test_train_carriages_list_and_scope(client: TestClient, fresh_user):
    _, token = fresh_user
    # wrong scope first
    bad = _mint(client, token, ["read:laws"])
    r = client.get(f"{TRAIN}/carriages?limit=1", headers={"X-API-Key": bad})
    assert r.status_code == 403
    assert r.json()["required_scope"] == "read:procedures"
    # correct scope
    key = _mint(client, token, ["read:procedures"])
    r = client.get(f"{TRAIN}/carriages?limit=3", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    assert "data" in r.json()


def test_train_carriage_detail_and_404(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    h = {"X-API-Key": key}
    lst = client.get(f"{TRAIN}/carriages?limit=5", headers=h).json()
    if lst["data"]:
        cid = lst["data"][0]["id"]
        r = client.get(f"{TRAIN}/carriages/{cid}", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == cid
    r404 = client.get(f"{TRAIN}/carriages/zzz-not-a-real-id-999", headers=h)
    assert r404.status_code == 404
    assert r404.json()["reason_code"] == "not_found"


# ---------------------------------------------------------------------------
# EuroVoc directories alias
# ---------------------------------------------------------------------------

def test_directories_legal_acts(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:publications"])
    r = client.get(f"{EV}/directories/legal-acts?lang=en&limit=3", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    assert "data" in r.json()
