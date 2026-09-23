"""An authenticated MCP tool listing leaves one mcp_connections row per key,
server, client and day (migration 238, 23 Sep 2026).

It is the "connector active" signal for /users: proof a client with Brubru
installed was running that day, never proof anyone asked Brubru anything.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def keyed_user():
    db = SessionLocal()
    u = User(email=f"mcpconn_{uuid.uuid4().hex[:8]}@example.com", full_name="MCP conn test",
             subscription_tier="white", is_active=True, api_balance_eur_micro=1_000_000)
    db.add(u); db.commit(); db.refresh(u)
    plaintext, k = ApiKey.generate(user_id=u.id, name="mcp conn test",
                                   scopes=["read:knowledge", "read:laws"], expires_in_days=1)
    db.add(k); db.commit()
    try:
        yield u.id, plaintext
    finally:
        db.execute(text("DELETE FROM mcp_connections WHERE user_id = :u"), {"u": str(u.id)})
        db.execute(text("DELETE FROM api_usage_events WHERE user_id = :u"), {"u": str(u.id)})
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit(); db.close()


def _rows(uid):
    db = SessionLocal()
    try:
        return db.execute(text(
            "SELECT server, client, auth, listings FROM mcp_connections WHERE user_id = :u ORDER BY server"),
            {"u": str(uid)}).all()
    finally:
        db.close()


def _post(client, path, key, ua="Claude-User", **h):
    return client.post(path, json=LIST, headers={"Authorization": f"Bearer {key}", "User-Agent": ua, **h})


def test_listing_records_one_row_and_counts_repeats(client, keyed_user):
    uid, key = keyed_user
    assert "result" in _post(client, "/api/mcp", key).json()
    _post(client, "/api/mcp", key)
    assert _rows(uid) == [("Brubru", "Claude-User", "key", 2)]


def test_each_server_is_its_own_row(client, keyed_user):
    uid, key = keyed_user
    _post(client, "/api/mcp", key)
    _post(client, "/api/mcp/dpp", key)
    assert [r[0] for r in _rows(uid)] == ["Brubru", "Brubru DPP"]


def test_probe_listing_is_not_recorded(client, keyed_user):
    uid, key = keyed_user
    _post(client, "/api/mcp", key, **{"X-Brubru-Probe": "1"})
    assert _rows(uid) == []


def test_unauthenticated_listing_records_nothing(client, keyed_user):
    uid, _ = keyed_user
    client.post("/api/mcp", json=LIST, headers={"Authorization": "Bearer brubru_live_notakey"})
    assert _rows(uid) == []


def test_tool_call_is_not_a_connection_row(client, keyed_user):
    uid, key = keyed_user
    client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                  "params": {"name": "search_knowledge_guides", "arguments": {"q": "AI Act"}}},
                headers={"Authorization": f"Bearer {key}"})
    assert _rows(uid) == []
