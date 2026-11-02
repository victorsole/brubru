"""A key can be limited to named routes (Victor, 2 Nov 2026: an evaluator gets a taste of the API, not all of it).
A limit only narrows: the scope check still applies, and an ordinary key is untouched."""
import asyncio
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from models.api_key import ApiKey

TASTE = ["read:laws", "read:economy", "route:/api/v2/legislative/eur-lex/laws", "route:/api/v2/news/all"]


def _key(scopes):
    return ApiKey(scopes=scopes, key_hash="x", key_prefix="abcd", name="t")


def test_the_named_routes_their_items_and_nothing_else():
    k = _key(TASTE)
    assert k.route_limits == ["/api/v2/legislative/eur-lex/laws", "/api/v2/news/all"]
    assert k.grants_route("/api/v2/news/all") and k.grants_route("/api/v2/news/all/")
    assert k.grants_route("/api/v2/legislative/eur-lex/laws/32016R0679/text")
    assert not k.grants_route("/api/v2/news/allied")          # a route that merely starts the same
    assert not k.grants_route("/api/v2/news/latest")
    assert not k.grants_route("/api/v1/news/all")


def test_an_ordinary_key_has_no_limit():
    for scopes in (["*"], ["read:laws"], [], None):
        k = _key(scopes)
        assert k.route_limits == [] and k.grants_route("/api/v2/anything")


def _client(api_key):
    from api.v1 import _deps
    from core.database import get_db
    app = FastAPI()

    @app.get("/api/v2/news/all")
    @app.get("/api/v2/news/latest")
    @app.get("/api/v2/legislative/eur-lex/laws")
    async def route(user=Depends(_deps.api_user_with_rate_limit)):
        return {"ok": True}

    async def fake_user(request: Request):
        request.state.api_key = api_key
        return SimpleNamespace(id=1, role="admin", subscription_tier="blue")
    app.dependency_overrides[_deps.get_api_user] = fake_user
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _api_key(scopes):
    k = _key(scopes)
    k.id, k.api_tier, k.is_sandbox, k.user_id = "k1", "free", False, 1
    return k


def test_the_gate_refuses_a_route_outside_the_limit_and_says_why():
    c = _client(_api_key(TASTE))
    assert c.get("/api/v2/news/all").status_code == 200
    r = c.get("/api/v2/news/latest")
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == "route_not_included"


def test_a_limit_never_widens_a_scope():
    c = _client(_api_key(["read:economy", "route:/api/v2/legislative/eur-lex/laws"]))
    r = c.get("/api/v2/legislative/eur-lex/laws")           # named, but its scope is read:laws
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == "scope_missing"


def test_an_ordinary_key_passes_the_gate_as_before():
    assert _client(_api_key(["read:economy"])).get("/api/v2/news/latest").status_code == 200


def test_a_limited_key_opens_no_mcp_tool():
    from api.mcp_http import _dispatch_tools_call
    out = asyncio.run(_dispatch_tools_call(1, {"name": "ask_brubru", "arguments": {"question": "x"}}, None,
                                           _key(["read:laws", "route:/api/v2/news/all"]), SimpleNamespace(role="admin"), None, "r"))
    assert "error" in out and "not the MCP tools" in str(out["error"])
