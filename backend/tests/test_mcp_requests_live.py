"""End to end: the real handler writes mcp_requests for ok, refused, unknown and unsupported
requests (migration 274). Reads and writes production data: local only, never in CI."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.database import SessionLocal
from main import app
from models.api_key import ApiKey
from models.user import User

pytestmark = pytest.mark.live


@pytest.fixture
def keyed():
    db = SessionLocal()
    u = User(email=f"mcpreq_{uuid.uuid4().hex[:8]}@example.com", full_name="MCP req test",
             subscription_tier="white", is_active=True, api_balance_eur_micro=1_000_000)
    db.add(u); db.commit(); db.refresh(u)
    plain_ok, k_ok = ApiKey.generate(user_id=u.id, name="req ok", scopes=["read:knowledge", "read:laws"], expires_in_days=1)
    plain_none, k_none = ApiKey.generate(user_id=u.id, name="req noscope", scopes=[], expires_in_days=1)
    db.add_all([k_ok, k_none]); db.commit()
    try:
        yield u.id, plain_ok, plain_none
    finally:
        db.execute(text("DELETE FROM mcp_requests WHERE user_id = :u"), {"u": str(u.id)})
        db.execute(text("DELETE FROM mcp_connections WHERE user_id = :u"), {"u": str(u.id)})
        db.execute(text("DELETE FROM api_usage_events WHERE user_id = :u"), {"u": str(u.id)})
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit(); db.close()


def _post(path, key, body, **h):
    return TestClient(app).post(path, json=body, headers={"Authorization": f"Bearer {key}", "User-Agent": "Claude-User", **h})


def _rows(uid):
    db = SessionLocal()
    try:
        return db.execute(text("SELECT method, tool, outcome, error_code, is_probe FROM mcp_requests "
                               "WHERE user_id = :u ORDER BY id"), {"u": str(uid)}).all()
    finally:
        db.close()


def test_every_kind_of_request_leaves_a_row(keyed):
    uid, ok, noscope = keyed
    p = "/api/mcp/dpp"
    _post(p, ok, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    _post(p, ok, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "no_such_tool", "arguments": {}}})
    _post(p, ok, {"jsonrpc": "2.0", "id": 3, "method": "ping"})
    _post(p, noscope, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "ask_dpp", "arguments": {"question": "x"}}})
    _post(p, ok, {"jsonrpc": "2.0", "id": 5, "method": "tools/list"}, **{"X-Brubru-Probe": "1"})
    rows = _rows(uid)
    got = [(r[0], r[1], r[2]) for r in rows]
    assert ("tools/list", None, "listed") in got
    assert ("tools/call", "no_such_tool", "unknown_tool") in got
    assert ("ping", None, "method_not_found") in got
    assert ("tools/call", "ask_dpp", "scope_missing") in got
    assert rows[-1][4] is True            # the probe header is recorded
    assert len(rows) == 5
