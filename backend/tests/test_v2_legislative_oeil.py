"""
API v2 — "Legislative data" / OEIL (Legislative Observatory) source tests.

Proves the OEIL source delegates to v1 procedures with identical structure,
under the read:procedures scope, on domain-rooted v2 paths.
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

OEIL = "/api/v2/legislative/oeil"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user():
    db = SessionLocal()
    try:
        u = User(
            email=f"v2_oeil_{uuid.uuid4().hex[:8]}@example.com",
            full_name="V2 OEIL Test User",
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
        json={"name": f"v2 oeil {uuid.uuid4().hex[:6]}", "scopes": scopes, "expires_in_days": 180},
    )
    assert r.status_code == 201, r.text
    return r.json()["key"]


def test_oeil_list_parity_with_v1(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    h = {"X-API-Key": key}
    v1 = client.get("/api/v1/procedures?limit=3", headers=h)
    v2 = client.get(f"{OEIL}/procedures?limit=3", headers=h)
    assert v1.status_code == 200 and v2.status_code == 200, v2.text
    b1, b2 = v1.json(), v2.json()
    assert b1["total"] == b2["total"]
    assert set(b1.keys()) == set(b2.keys())
    assert [i["id"] for i in b1["data"]] == [i["id"] for i in b2["data"]]


def test_oeil_detail_reaches_and_parity(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    h = {"X-API-Key": key}
    lst = client.get(f"{OEIL}/procedures?limit=10", headers=h).json()
    ref = next((i["oeil_procedure_ref"] for i in lst["data"] if i.get("oeil_procedure_ref")), None)
    if not ref:
        pytest.skip("no procedure with an OEIL reference available")
    v1 = client.get(f"/api/v1/procedures/{ref}", headers=h)
    v2 = client.get(f"{OEIL}/procedures/{ref}", headers=h)
    assert v1.status_code == v2.status_code == 200, v2.text
    assert v1.json()["oeil_procedure_ref"] == v2.json()["oeil_procedure_ref"] == ref


def test_oeil_requires_read_procedures_scope(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:laws"])  # wrong scope
    r = client.get(f"{OEIL}/procedures?limit=1", headers={"X-API-Key": key})
    assert r.status_code == 403, r.text
    assert r.json()["required_scope"] == "read:procedures"


def test_oeil_error_envelope_on_missing_procedure(client: TestClient, fresh_user):
    _, token = fresh_user
    key = _mint(client, token, ["read:procedures"])
    r = client.get(f"{OEIL}/procedures/9999/9999(ZZZ)", headers={"X-API-Key": key})
    assert r.status_code == 404, r.text
    body = r.json()
    assert body["reason_code"] == "not_found"
    assert "request_id" in body
