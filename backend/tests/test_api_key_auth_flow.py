"""
End-to-end test for API key authentication.

Exercises the six decision paths of get_api_user against an in-memory
FastAPI TestClient, using real DB for the ApiKey / User rows and cleaning up.
"""

import uuid
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth_api_key import get_api_user
from core.database import SessionLocal
from models.api_key import ApiKey
from models.user import User


@pytest.fixture
def test_app():
    app = FastAPI()

    @app.get("/protected")
    def protected(user: User = Depends(get_api_user)):
        return {"user_id": str(user.id), "tier": user.subscription_tier}

    return app


@pytest.fixture
def blue_user_with_key():
    """Create a Professional (blue) user + a fresh API key. Yields (user, plaintext) then cleans up."""
    db = SessionLocal()
    try:
        user = User(
            email=f"test_api_key_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Blue User",
            subscription_tier="blue",
            is_active=True,
        )
        db.add(user)
        db.flush()

        plaintext, key = ApiKey.generate(user_id=user.id, name="test")
        db.add(key)
        db.commit()
        db.refresh(key)
        db.refresh(user)
        yield user, plaintext, key.id
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


@pytest.fixture
def yellow_user_with_key():
    """Non-Professional user. Should be blocked at tier check."""
    db = SessionLocal()
    try:
        user = User(
            email=f"test_yellow_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Test Yellow",
            subscription_tier="yellow",
            is_active=True,
        )
        db.add(user)
        db.flush()
        plaintext, key = ApiKey.generate(user_id=user.id, name="test")
        db.add(key)
        db.commit()
        yield plaintext
    finally:
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()


def _err(json_body):
    """Extract canonical error fields from either wrapped or unwrapped response body."""
    detail = json_body.get("detail", json_body)
    if isinstance(detail, dict):
        return detail.get("error", ""), detail.get("reason_code", "")
    return str(detail), ""


def test_missing_header_returns_401(test_app):
    client = TestClient(test_app)
    r = client.get("/protected")
    assert r.status_code == 401
    msg, code = _err(r.json())
    assert "Missing API key" in msg
    assert code == "auth_missing_key"


def test_wrong_prefix_returns_401(test_app):
    client = TestClient(test_app)
    r = client.get("/protected", headers={"X-API-Key": "sk_live_notours"})
    assert r.status_code == 401
    msg, code = _err(r.json())
    assert "Invalid API key format" in msg
    assert code == "auth_invalid_format"


def test_unknown_key_returns_401(test_app):
    client = TestClient(test_app)
    r = client.get(
        "/protected",
        headers={"X-API-Key": "brubru_live_" + "0" * 48},
    )
    assert r.status_code == 401
    msg, code = _err(r.json())
    assert "not found" in msg.lower() or "revoked" in msg.lower()
    assert code == "auth_key_not_found"


def test_valid_key_returns_200(test_app, blue_user_with_key):
    user, plaintext, _ = blue_user_with_key
    client = TestClient(test_app)
    r = client.get("/protected", headers={"X-API-Key": plaintext})
    assert r.status_code == 200
    assert r.json()["tier"] == "blue"
    assert r.json()["user_id"] == str(user.id)


def test_revoked_key_returns_401(test_app, blue_user_with_key):
    from datetime import datetime
    user, plaintext, key_id = blue_user_with_key

    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        key.revoked_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    client = TestClient(test_app)
    r = client.get("/protected", headers={"X-API-Key": plaintext})
    assert r.status_code == 401


def test_non_blue_tier_returns_403(test_app, yellow_user_with_key):
    plaintext = yellow_user_with_key
    client = TestClient(test_app)
    r = client.get("/protected", headers={"X-API-Key": plaintext})
    assert r.status_code == 403
    msg, code = _err(r.json())
    assert "Professional" in msg
    assert code == "tier_insufficient"
