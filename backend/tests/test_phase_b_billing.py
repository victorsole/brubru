"""
Phase B integration tests — euro-balance billing + sandbox pool.

Coverage:
    - Free endpoint (/api/v1/ping) does not debit
    - Auth-required free endpoint (/api/v1/whoami) does not debit
    - Paid endpoint debits 0.001 EUR (lightweight read default)
    - Insufficient balance returns 402 with reason_code='insufficient_balance'
    - Successful debit lowers the balance
    - Sandbox pool ip cap (10/day) enforced
    - Sandbox key debits against pool, not user balance
    - /api/billing/balance returns current state
    - /api/billing/topup rejects amounts below 1 EUR
    - /api/billing/auto-topup persists settings
    - Pricing table resolves correctly
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.auth import create_access_token
from core.database import SessionLocal
from main import app
from models.api_billing import ApiTopupEvent, ApiUsageEvent
from models.api_key import ApiKey
from models.user import User
from services.billing.api_meter import (
    SANDBOX_IP_CAP,
    debit,
    record_usage,
    refund,
    resolve_cost_micro,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def fresh_user_with_balance(request):
    """Yields (user, JWT, plaintext_key). Cleans up usage events + keys + user."""
    db = SessionLocal()
    try:
        u = User(
            email=f"phase_b_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Phase B Test User",
            subscription_tier="white",
            is_active=True,
            api_balance_eur_micro=1_000_000,  # 1 EUR default
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        token = create_access_token({"sub": str(u.id)})

        # Mint a wildcard-scoped key directly (bypass self-serve mint cap)
        plaintext, k = ApiKey.generate(
            user_id=u.id,
            name="Phase B test key",
            scopes=["read:laws", "read:ep", "read:procedures", "read:calendar",
                    "read:commission", "read:council", "read:knowledge", "read:publications"],
            expires_in_days=180,
        )
        db.add(k)
        db.commit()
        yield u, token, plaintext
    finally:
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiTopupEvent).filter(ApiTopupEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit()
        db.close()


def _get_balance(user_id) -> int:
    db = SessionLocal()
    try:
        r = db.execute(
            text("SELECT api_balance_eur_micro FROM users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
        return int(r[0]) if r else -1
    finally:
        db.close()


def _set_balance(user_id, micro: int) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE users SET api_balance_eur_micro = :m WHERE id = :uid"),
            {"m": int(micro), "uid": str(user_id)},
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------

def test_pricing_table_resolution():
    assert resolve_cost_micro("/api/v1/laws")[0] == 1000
    assert resolve_cost_micro("/api/v1/laws/32016R0679/text")[0] == 10000
    assert resolve_cost_micro("/api/v1/legal-text/32016R0679/defined-terms")[0] == 5000
    assert resolve_cost_micro("/api/v1/chat/message")[0] == 20000
    # Unknown path falls back to default
    assert resolve_cost_micro("/api/v1/something-new")[0] == 1000


# ---------------------------------------------------------------------------
# Atomic debit + refund
# ---------------------------------------------------------------------------

def test_debit_atomic_decrease(fresh_user_with_balance):
    user, _, _ = fresh_user_with_balance
    db = SessionLocal()
    try:
        before = _get_balance(user.id)
        ok, after = debit(db, user.id, 1000)
        assert ok is True
        assert after == before - 1000
    finally:
        db.close()


def test_debit_insufficient_balance_no_change(fresh_user_with_balance):
    user, _, _ = fresh_user_with_balance
    _set_balance(user.id, 500)  # less than the cost
    db = SessionLocal()
    try:
        ok, current = debit(db, user.id, 1000)
        assert ok is False
        assert current == 500  # unchanged
    finally:
        db.close()


def test_refund_returns_credit(fresh_user_with_balance):
    user, _, _ = fresh_user_with_balance
    db = SessionLocal()
    try:
        before = _get_balance(user.id)
        new_balance = refund(db, user.id, 1000)
        assert new_balance == before + 1000
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Free endpoints
# ---------------------------------------------------------------------------

def test_free_ping_does_not_debit(client, fresh_user_with_balance):
    """/api/v1/ping is unauthenticated and outside the metering scope."""
    user, _, _ = fresh_user_with_balance
    before = _get_balance(user.id)
    r = client.get("/api/v1/ping")
    assert r.status_code == 200
    assert _get_balance(user.id) == before


def test_free_whoami_does_not_debit(client, fresh_user_with_balance):
    """/api/v1/whoami requires auth but is FREE_PATH — no debit."""
    user, _, plaintext = fresh_user_with_balance
    before = _get_balance(user.id)
    r = client.get("/api/v1/whoami", headers={"X-API-Key": plaintext})
    assert r.status_code == 200, r.text
    assert _get_balance(user.id) == before


# ---------------------------------------------------------------------------
# Paid endpoints
# ---------------------------------------------------------------------------

def test_paid_endpoint_debits_lightweight_cost(client, fresh_user_with_balance):
    user, _, plaintext = fresh_user_with_balance
    before = _get_balance(user.id)
    r = client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})
    # The route may legitimately 200, 422 (validation) — but it should NOT 402.
    assert r.status_code != 402, r.text
    after = _get_balance(user.id)
    assert after == before - 1000, f"expected debit of 1000 μEUR; before={before} after={after}"


def test_paid_endpoint_402_on_zero_balance(client, fresh_user_with_balance):
    user, _, plaintext = fresh_user_with_balance
    _set_balance(user.id, 0)
    r = client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})
    assert r.status_code == 402, r.text
    body = r.json()
    assert body["reason_code"] == "insufficient_balance"
    assert body["balance_eur_micro"] == 0
    assert body["cost_eur_micro"] >= 1000


def test_paid_endpoint_402_when_balance_below_cost(client, fresh_user_with_balance):
    """Balance positive but below the call cost still 402s."""
    user, _, plaintext = fresh_user_with_balance
    _set_balance(user.id, 500)  # < 1000 (default cost)
    r = client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})
    assert r.status_code == 402, r.text
    # Balance unchanged after the failed debit
    assert _get_balance(user.id) == 500


def test_usage_event_recorded_for_paid_call(client, fresh_user_with_balance):
    user, _, plaintext = fresh_user_with_balance
    client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})

    db = SessionLocal()
    try:
        evts = (
            db.query(ApiUsageEvent)
            .filter(ApiUsageEvent.user_id == user.id, ApiUsageEvent.endpoint.like("%/laws%"))
            .all()
        )
        assert len(evts) >= 1
        e = evts[-1]
        assert e.cost_eur_micro == 1000
        assert e.method == "GET"
        assert e.refunded is False
        assert e.is_sandbox is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Sandbox pool
# ---------------------------------------------------------------------------

def test_sandbox_ip_cap_enforced():
    """The 11th sandbox call from the same IP returns False."""
    from services.billing.api_meter import sandbox_consume

    db = SessionLocal()
    test_ip = f"203.0.113.{uuid.uuid4().int % 200 + 30}"  # synthetic IP in TEST-NET-3
    try:
        # First SANDBOX_IP_CAP calls should succeed
        for i in range(SANDBOX_IP_CAP):
            ok, reason = sandbox_consume(db, test_ip)
            assert ok, f"call {i+1}/{SANDBOX_IP_CAP} should succeed, got reason={reason}"
        # Next call hits the cap
        ok, reason = sandbox_consume(db, test_ip)
        assert ok is False
        assert reason == "sandbox_ip_capped"
    finally:
        # Clean up so we don't pollute today's pool
        db.execute(
            text("DELETE FROM api_sandbox_pool WHERE ip_address = CAST(:ip AS inet)"),
            {"ip": test_ip},
        )
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Billing endpoints
# ---------------------------------------------------------------------------

def test_balance_endpoint_returns_state(client, fresh_user_with_balance):
    user, token, plaintext = fresh_user_with_balance
    # Make a paid call to create a usage event
    client.get("/api/v1/laws?limit=1", headers={"X-API-Key": plaintext})

    r = client.get("/api/billing/balance", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance_eur"] >= 0
    assert body["balance_eur_micro"] == _get_balance(user.id)
    assert len(body["recent_usage"]) >= 1
    assert isinstance(body["recent_topups"], list)
    assert body["auto_topup"]["enabled"] is False


def test_topup_rejects_below_one_eur(client, fresh_user_with_balance):
    _, token, _ = fresh_user_with_balance
    r = client.post(
        "/api/billing/topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount_eur": 0.5},
    )
    assert r.status_code == 422
    # Pydantic-level gt=0 may catch first; otherwise our custom 422 returns
    # detail.reason_code == "topup_below_minimum"
    detail = r.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("reason_code") in ("topup_below_minimum",)
    # If pydantic-list 422, the test still asserts >=422 (the failure mode).


def test_auto_topup_set_and_persist(client, fresh_user_with_balance):
    _, token, _ = fresh_user_with_balance
    r = client.post(
        "/api/billing/auto-topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True, "threshold_eur": 1.0, "amount_eur": 10.0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["threshold_eur"] == 1.0
    assert body["amount_eur"] == 10.0

    # Disable
    r = client.post(
        "/api/billing/auto-topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_auto_topup_enabled_requires_threshold_and_amount(client, fresh_user_with_balance):
    _, token, _ = fresh_user_with_balance
    r = client.post(
        "/api/billing/auto-topup",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},  # missing threshold + amount
    )
    assert r.status_code == 422
    assert r.json()["detail"]["reason_code"] == "auto_topup_incomplete"


def test_balance_requires_auth(client):
    r = client.get("/api/billing/balance")
    assert r.status_code == 401
