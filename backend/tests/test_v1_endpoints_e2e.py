"""
End-to-end test of /api/v1/* via the real FastAPI app.

Covers:
    - /api/v1/ping (unauthenticated)
    - /api/v1/whoami with a valid key (200, returns tier)
    - /api/v1/whoami without a key (401)
    - /api/v1/whoami with a bad key (401)
    - Rate limit headers on successful responses
    - Rate limit 429 after 60 calls

Uses the real DB via SessionLocal; cleans up after itself.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

from tests.conftest import TEST_API_BALANCE_MICRO


@pytest.fixture
def blue_user_and_key():
    db = SessionLocal()
    try:
        user = User(
            email=f"test_v1_{uuid.uuid4().hex[:8]}@example.com",
            full_name="v1 test",
            subscription_tier="blue",
            is_active=True,
            # Metered v1 endpoints debit before the handler runs; an unfunded
            # user 402s and the test reports a billing gate as a broken endpoint.
            api_balance_eur_micro=TEST_API_BALANCE_MICRO,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="v1-test")
        db.add(key)
        db.commit()
        db.refresh(key)
        yield user, plaintext, key.id
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


def test_ping_unauthenticated():
    client = TestClient(app)
    r = client.get("/api/v1/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "v1"
    assert "time" in body


def test_whoami_missing_key_returns_401():
    client = TestClient(app)
    r = client.get("/api/v1/whoami")
    assert r.status_code == 401


def test_whoami_bad_key_returns_401():
    client = TestClient(app)
    r = client.get("/api/v1/whoami", headers={"X-API-Key": "brubru_live_" + "f" * 48})
    assert r.status_code == 401


def test_whoami_valid_key_returns_200_with_rate_limit_headers(blue_user_and_key):
    user, plaintext, _ = blue_user_and_key
    client = TestClient(app)
    r = client.get("/api/v1/whoami", headers={"X-API-Key": plaintext, "X-Brubru-Probe": "1"})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "blue"
    assert body["user_id"] == str(user.id)
    assert body["rate_limit_limit"] == 60
    # Headers set by middleware
    assert r.headers.get("X-RateLimit-Limit") == "60"
    assert r.headers.get("X-RateLimit-Remaining") is not None


def test_rate_limit_kicks_in_after_60_calls(blue_user_and_key):
    user, plaintext, _ = blue_user_and_key
    client = TestClient(app)
    headers = {"X-API-Key": plaintext, "X-Brubru-Probe": "1"}  # probe: suite traffic must not count as user activity

    # Burn through the window
    for _ in range(60):
        r = client.get("/api/v1/whoami", headers=headers)
        assert r.status_code == 200

    # 61st must be 429 with Retry-After
    r = client.get("/api/v1/whoami", headers=headers)
    assert r.status_code == 429
    assert r.headers.get("Retry-After") is not None
    assert int(r.headers.get("Retry-After")) >= 1
