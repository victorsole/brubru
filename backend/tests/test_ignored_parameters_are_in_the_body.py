"""A parameter the endpoint does not accept is reported in the JSON body, not only in a header (23 Oct 2026).

On 20 Oct a session read /api/v2/funding/eu-funding-recipients through the Brubru MCP tool, which
relays the body alone. It sent `department=CNECT`, got all 188,187 rows with the warning only in
X-Brubru-Unknown-Params, and concluded the endpoint "only filters by organisation name". The body
now opens with `ignored_parameters` and `accepted_parameters`. These call the real auth dependency,
the real route and the real middleware function from main.py.
"""
import pathlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from api.v1._query_guard import check_query_params  # noqa: E402
from core.database import get_db  # noqa: E402

SEEN = datetime(2026, 10, 16, 2, 0, tzinfo=timezone.utc)


class _Row(dict):
    __getattr__ = dict.__getitem__


class _Result:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return len(self.rows)
    def fetchall(self): return self.rows


class _Db:
    row = _Row(id=2214392, body_code="commission", item_type="funding_recipient",
               title="RAMBOLL MANAGEMENT, CONSULTING", summary="EUR 102,400",
               public_url="https://ec.europa.eu/budget/financial-transparency-system/index.html#2025-x",
               document_date=SEEN, creation_date=SEEN, source_kind="xlsx", updated_at=SEEN)

    def execute(self, stmt, params=None):
        return _Result([self.row])


def _guarded_user(request: Request):
    # The production dependency runs this exact call first (api/v1/_deps.py); the rest of it
    # (scope, rate limit, euro debit) is not what these tests are about.
    check_query_params(request)
    return SimpleNamespace(id=1, role="admin")


def _client():
    import main
    from api.v2.funding import eu_funding_recipients as fr
    app = FastAPI()
    app.include_router(fr.router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: _Db()
    app.dependency_overrides[api_user_with_rate_limit] = _guarded_user
    app.middleware("http")(main._v1_rate_limit_headers)
    return TestClient(app)


def test_the_real_auth_dependency_records_the_ignored_parameter_before_anything_else():
    from api.v2.funding import eu_funding_recipients as fr
    route = next(r for r in fr.router.routes if r.path == "/eu-funding-recipients")
    request = Request({"type": "http", "method": "GET", "path": "/api/v2/funding/eu-funding-recipients",
                       "query_string": b"department=CNECT&q=study", "headers": [], "route": route})
    request.state.api_key = SimpleNamespace(grants_scope=lambda scope: False, api_tier="free")
    with pytest.raises(HTTPException) as refused:          # the scope check comes after the guard
        import asyncio
        asyncio.run(api_user_with_rate_limit(request, user=SimpleNamespace(id=1), db=None))
    assert refused.value.status_code == 403
    assert request.state.unknown_query_params == ["department"]
    assert "q" in request.state.accepted_query_params


def test_the_body_opens_with_what_was_not_applied():
    r = _client().get("/api/v2/funding/eu-funding-recipients",
                      params={"department": "CNECT", "subject": "observatory", "q": "study", "include_body": "false"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body)[:2] == ["ignored_parameters", "accepted_parameters"]
    assert body["ignored_parameters"] == ["department", "subject"]
    assert {"q", "since", "until", "include_body", "page", "limit"} <= set(body["accepted_parameters"])
    assert body["total"] == 1 and body["data"][0]["id"] == 2214392        # the page itself is untouched
    assert r.headers["X-Brubru-Unknown-Params"] == "department,subject"   # the header stays
    assert int(r.headers["content-length"]) == len(r.content)


def test_nothing_is_added_when_every_parameter_was_applied():
    r = _client().get("/api/v2/funding/eu-funding-recipients", params={"q": "study", "include_body": "false"})
    assert r.status_code == 200
    assert "ignored_parameters" not in r.json() and "X-Brubru-Unknown-Params" not in r.headers


def test_a_list_body_and_an_error_pass_unchanged():
    import main
    app = FastAPI()

    @app.get("/api/v2/x/list")
    def as_list(request: Request, q: str = None):
        check_query_params(request)
        return [1, 2]

    @app.get("/api/v2/x/missing")
    def missing(request: Request, q: str = None):
        check_query_params(request)
        raise HTTPException(status_code=404, detail="no such item")

    app.middleware("http")(main._v1_rate_limit_headers)
    client = TestClient(app)
    r = client.get("/api/v2/x/list", params={"foo": "1"})
    assert r.json() == [1, 2] and r.headers["X-Brubru-Unknown-Params"] == "foo"
    r = client.get("/api/v2/x/missing", params={"foo": "1"})
    assert r.status_code == 404 and "ignored_parameters" not in r.json()
