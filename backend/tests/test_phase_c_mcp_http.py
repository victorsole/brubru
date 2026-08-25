"""
Phase C integration tests — HTTP MCP transport (Brubru MCP at /api/mcp).

Coverage:
    GET /api/mcp                     -> probe returns server info, no auth
    POST initialize                  -> no auth required, returns capabilities
    POST tools/list  (no auth)       -> auth_missing
    POST tools/list  (auth)          -> the full published tool surface
    POST tools/call  (in-scope)      -> result + debit
    POST tools/call  (out-of-scope)  -> scope_missing JSON-RPC error
    POST tools/call  (0 balance)     -> insufficient_balance JSON-RPC error
    POST tools/call  (sandbox key)   -> succeeds, no user balance debit
    POST tools/call  (unknown tool)  -> tool_not_found
    POST tools/call  (bad args)      -> -32602 invalid params + refund
    POST notifications/initialized   -> ack, no error
    POST unknown method              -> -32601 method not found
    POST malformed JSON              -> -32700 parse error
    expired key                      -> key_expired JSON-RPC error
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.database import SessionLocal
from main import app
from models.api_billing import ApiUsageEvent
from models.api_key import ApiKey
from models.user import User

# The MCP tool surface, pinned BY NAME rather than by count.
#
# These tests asserted `== 6` from May 2026 until 25 Aug 2026 while the server
# actually exposed 15, so three of them failed continuously and the real surface
# was never tested against its real shape. A count also fails uninformatively:
# it says "something changed", not "search_sanctions disappeared".
#
# Adding a tool means adding it here deliberately -- which is the point, because
# every name below is a public contract with the MCP hosts (Claude, ChatGPT,
# Gemini CLI, Cursor) that connect to it.
EXPECTED_MCP_TOOLS = {
    "ask_brubru",
    "fetch",
    "get_calendar_events",
    "get_procedure_status",
    "list_brubru_datasets",
    "query_brubru_api",
    "search",
    "search_consultations",
    "search_eprs",
    "search_eu_legislation",
    "search_funding",
    "search_geographical_indications",
    "search_knowledge_guides",
    "search_lobbyists",
    "search_sanctions",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def user_with_key_full_scopes():
    """User with 1 EUR balance + key with all 8 read:* scopes."""
    db = SessionLocal()
    try:
        u = User(
            email=f"phase_c_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Phase C Test",
            subscription_tier="white",
            is_active=True,
            api_balance_eur_micro=1_000_000,
        )
        db.add(u); db.commit(); db.refresh(u)

        plaintext, k = ApiKey.generate(
            user_id=u.id, name="Phase C full",
            scopes=["read:laws", "read:procedures", "read:calendar", "read:ep",
                    "read:commission", "read:council", "read:knowledge", "read:publications"],
            expires_in_days=180,
        )
        db.add(k); db.commit()
        yield u, plaintext, k.id
    finally:
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit(); db.close()


@pytest.fixture
def user_with_key_laws_only():
    """User with balance + key scoped to read:laws ONLY (no read:knowledge)."""
    db = SessionLocal()
    try:
        u = User(
            email=f"phase_c_laws_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Phase C Laws Only",
            subscription_tier="white",
            is_active=True,
            api_balance_eur_micro=1_000_000,
        )
        db.add(u); db.commit(); db.refresh(u)
        plaintext, k = ApiKey.generate(
            user_id=u.id, name="Laws only", scopes=["read:laws"], expires_in_days=30
        )
        db.add(k); db.commit()
        yield u, plaintext
    finally:
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit(); db.close()


def _bal(user_id) -> int:
    db = SessionLocal()
    try:
        r = db.execute(text("SELECT api_balance_eur_micro FROM users WHERE id=:uid"),
                       {"uid": str(user_id)}).fetchone()
        return int(r[0]) if r else -1
    finally:
        db.close()


def _set_bal(user_id, micro):
    db = SessionLocal()
    try:
        db.execute(text("UPDATE users SET api_balance_eur_micro=:m WHERE id=:uid"),
                   {"m": int(micro), "uid": str(user_id)})
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

def test_get_probe(client):
    r = client.get("/api/mcp")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "Brubru"
    assert body["protocol"] == "Model Context Protocol"
    assert body["tools_available"] == len(EXPECTED_MCP_TOOLS)


# ---------------------------------------------------------------------------
# initialize handshake (no auth required)
# ---------------------------------------------------------------------------

def test_initialize_no_auth_required(client):
    r = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert r.status_code == 200
    body = r.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["serverInfo"]["name"] == "Brubru"
    assert "protocolVersion" in body["result"]


# ---------------------------------------------------------------------------
# tools/list
# ---------------------------------------------------------------------------

def test_tools_list_requires_auth(client):
    r = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == -32001  # _ERR_AUTH_MISSING


def test_tools_list_matches_the_published_surface(client, user_with_key_full_scopes):
    _, plaintext, _ = user_with_key_full_scopes
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    )
    body = r.json()
    assert "result" in body, body
    tools = body["result"]["tools"]
    assert {t['name'] for t in tools} == EXPECTED_MCP_TOOLS, (
        'the MCP tool surface changed; update EXPECTED_MCP_TOOLS deliberately '
        'and check the host connector docs'
    )
    # Each tool has proper MCP shape
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "inputSchema" in t
        assert t["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# tools/call — happy path with debit
# ---------------------------------------------------------------------------

def test_tools_call_search_eu_legislation_succeeds_and_debits(client, user_with_key_full_scopes):
    user, plaintext, _ = user_with_key_full_scopes
    before = _bal(user.id)
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "search_eu_legislation", "arguments": {"query": "data protection", "limit": 1}},
        },
    )
    body = r.json()
    assert "result" in body, body
    res = body["result"]
    assert res["isError"] is False
    # Content is JSON-encoded text — parse it back
    import json as _json
    payload = _json.loads(res["content"][0]["text"])
    assert "query" in payload
    assert payload["query"] == "data protection"
    # Balance debited by 5000 μEUR (COST_LIGHT_MCP)
    after = _bal(user.id)
    assert after == before - 5000


def test_tools_call_get_calendar_events_default_args(client, user_with_key_full_scopes):
    _, plaintext, _ = user_with_key_full_scopes
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0", "id": 11, "method": "tools/call",
            "params": {"name": "get_calendar_events", "arguments": {}},
        },
    )
    body = r.json()
    assert "result" in body, body
    assert body["result"]["isError"] is False


# ---------------------------------------------------------------------------
# tools/call — scope mismatch
# ---------------------------------------------------------------------------

def test_tools_call_scope_missing(client, user_with_key_laws_only):
    """Key has only read:laws; calling ask_brubru (read:knowledge) must error."""
    _, plaintext = user_with_key_laws_only
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0", "id": 20, "method": "tools/call",
            "params": {"name": "ask_brubru", "arguments": {"question": "What is GDPR?"}},
        },
    )
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == -32004
    assert body["error"]["data"]["required_scope"] == "read:knowledge"


# ---------------------------------------------------------------------------
# tools/call — insufficient balance
# ---------------------------------------------------------------------------

def test_tools_call_insufficient_balance(client, user_with_key_full_scopes):
    user, plaintext, _ = user_with_key_full_scopes
    _set_bal(user.id, 0)
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0", "id": 30, "method": "tools/call",
            "params": {"name": "search_eu_legislation", "arguments": {"query": "test"}},
        },
    )
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == -32005
    assert body["error"]["data"]["cost_eur_micro"] == 5000
    assert body["error"]["data"]["top_up_url"].endswith("/billing")


# ---------------------------------------------------------------------------
# tools/call — unknown tool
# ---------------------------------------------------------------------------

def test_tools_call_unknown_tool(client, user_with_key_full_scopes):
    _, plaintext, _ = user_with_key_full_scopes
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0", "id": 40, "method": "tools/call",
            "params": {"name": "bogus_tool", "arguments": {}},
        },
    )
    body = r.json()
    assert body["error"]["code"] == -32007


# ---------------------------------------------------------------------------
# tools/call — bad args (refund)
# ---------------------------------------------------------------------------

def test_tools_call_bad_args_refunds(client, user_with_key_full_scopes):
    """Missing required argument triggers a TypeError -> refund."""
    user, plaintext, _ = user_with_key_full_scopes
    before = _bal(user.id)
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={
            "jsonrpc": "2.0", "id": 50, "method": "tools/call",
            "params": {"name": "search_eu_legislation", "arguments": {}},  # missing `query`
        },
    )
    body = r.json()
    assert body["error"]["code"] == -32602
    # Balance refunded
    after = _bal(user.id)
    assert after == before


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_notifications_initialized_no_error(client):
    r = client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "error" not in body


# ---------------------------------------------------------------------------
# Method routing
# ---------------------------------------------------------------------------

def test_unknown_method_returns_method_not_found(client, user_with_key_full_scopes):
    _, plaintext, _ = user_with_key_full_scopes
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={"jsonrpc": "2.0", "id": 60, "method": "tools/bogus"},
    )
    body = r.json()
    assert body["error"]["code"] == -32601


def test_malformed_json_returns_parse_error(client):
    r = client.post("/api/mcp", content="this is not json", headers={"Content-Type": "application/json"})
    body = r.json()
    assert body["error"]["code"] == -32700


def test_missing_method_returns_invalid_request(client):
    r = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 70})
    body = r.json()
    assert body["error"]["code"] == -32600


# ---------------------------------------------------------------------------
# Expired key
# ---------------------------------------------------------------------------

def test_expired_key_returns_key_expired(client, user_with_key_full_scopes):
    user, plaintext, key_id = user_with_key_full_scopes
    db = SessionLocal()
    try:
        k = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        k.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()
    r = client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={"jsonrpc": "2.0", "id": 80, "method": "tools/list"},
    )
    body = r.json()
    assert body["error"]["code"] == -32003


# ---------------------------------------------------------------------------
# Bearer + X-API-Key equivalence
# ---------------------------------------------------------------------------

def test_x_api_key_header_works(client, user_with_key_full_scopes):
    _, plaintext, _ = user_with_key_full_scopes
    r = client.post(
        "/api/mcp",
        headers={"X-API-Key": plaintext},
        json={"jsonrpc": "2.0", "id": 90, "method": "tools/list"},
    )
    body = r.json()
    assert "result" in body, body
    assert {t["name"] for t in body["result"]["tools"]} == EXPECTED_MCP_TOOLS
