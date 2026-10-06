"""Every authenticated MCP request leaves one mcp_requests row (migration 274, 6 Oct 2026).

Why it exists: api_usage_events is written only after the scope check and the debit
succeed, so a refused or unknown call left no trace and /users read "0 calls" for a
client that was in fact connected. These tests pin the outcome mapping and the
fail-soft rule (unit, run in CI) and the end-to-end write (live, local only).
"""
from __future__ import annotations

import uuid

import pytest

from api import mcp_http as m


class _Key:
    def __init__(self):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()


class _Db:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, stmt, params=None):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(params)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _err(code):
    return {"jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": "x"}}


@pytest.mark.parametrize("method,resp,expected", [
    ("tools/list", {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}, ("listed", None)),
    ("tools/call", {"jsonrpc": "2.0", "id": 1, "result": {}}, ("ok", None)),
    ("tools/call", _err(m._ERR_SCOPE_MISSING), ("scope_missing", m._ERR_SCOPE_MISSING)),
    ("tools/call", _err(m._ERR_INSUFFICIENT_BALANCE), ("insufficient_balance", m._ERR_INSUFFICIENT_BALANCE)),
    ("tools/call", _err(m._ERR_TOOL_NOT_FOUND), ("unknown_tool", m._ERR_TOOL_NOT_FOUND)),
    ("tools/call", _err(m._ERR_TOOL_HANDLER_FAILED), ("handler_failed", m._ERR_TOOL_HANDLER_FAILED)),
    ("tools/call", _err(-32602), ("bad_arguments", -32602)),
    ("ping", _err(-32601), ("method_not_found", -32601)),
    ("tools/list", _err(m._ERR_KEY_EXPIRED), ("key_expired", m._ERR_KEY_EXPIRED)),
    ("tools/call", _err(-1), ("error", -1)),
])
def test_outcome_mapping(method, resp, expected):
    assert m._outcome_from_response(method, resp) == expected


def test_every_declared_outcome_is_allowed_by_the_table():
    """The CHECK constraint in migration 274 must accept every outcome the code can emit."""
    sql = open(__file__.replace("tests/test_mcp_requests.py", "migrations/274_mcp_requests.sql")).read()
    emitted = set(m._OUTCOME_BY_CODE.values()) | {"ok", "listed", "error"}
    missing = [o for o in emitted if f"'{o}'" not in sql]
    assert not missing, f"outcomes the code emits but the table rejects: {missing}"


def test_record_request_stores_method_tool_outcome_and_never_arguments():
    db, key = _Db(), _Key()
    m._record_request(db, key, "Brubru DPP", "tools/call", "dpp_law", {"result": {}}, "Claude-User", "key", False)
    assert db.commits == 1
    row = db.calls[0]
    assert row["m"] == "tools/call" and row["t"] == "dpp_law" and row["o"] == "ok"
    assert set(row) == {"k", "u", "s", "m", "t", "o", "c", "a", "cl", "p"}   # no arguments column


def test_record_request_is_fail_soft():
    db = _Db(fail=True)
    m._record_request(db, _Key(), "Brubru", "tools/call", "ask_brubru", {"result": {}}, "UA", "key", False)
    assert db.rollbacks == 1          # no exception escaped, the session was reset


def test_auth_failure_is_recorded_without_a_key():
    db = _Db()
    m._record_request(db, None, "Brubru", "tools/call", None, _err(m._ERR_AUTH_INVALID), "UA", "key", False)
    row = db.calls[0]
    assert row["k"] is None and row["u"] is None and row["o"] == "auth_invalid"


def test_long_values_are_truncated():
    db = _Db()
    m._record_request(db, _Key(), "S" * 200, "M" * 200, "T" * 200, {"result": {}}, "U" * 500, "key", False)
    row = db.calls[0]
    assert len(row["s"]) == 64 and len(row["m"]) == 80 and len(row["t"]) == 80 and len(row["cl"]) == 200
