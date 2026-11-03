"""API bundles (Victor, 3 Nov 2026): every route belongs somewhere, a user finds routes by bundle, and a key can be
limited to the bundles chosen when it is minted."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from models.api_key import ApiKey
from services.api_keys.bundles import API_BUNDLES, NOT_IN_A_BUNDLE, bundle_ids, bundles_of, path_in_bundles
from services.api_keys.scopes import all_self_serve_scopes


def _v2_get_paths():
    from main import app
    return sorted({r.path for r in app.routes if getattr(r, "path", "").startswith("/api/v2/") and "GET" in getattr(r, "methods", [])})


def test_every_route_has_a_bundle_and_nothing_else_is_left_out():
    outside = [p for p in _v2_get_paths() if not bundles_of(p) and not p.startswith(NOT_IN_A_BUNDLE)]
    assert not outside, f"{len(outside)} v2 routes sit in no bundle: {outside[:8]}"
    assert len(_v2_get_paths()) > 1000


def test_what_is_not_data_sits_in_no_bundle():
    for path in ("/api/v2/extract", "/api/v2/pricing", "/api/v2/bundles", "/api/v2/openapi.json"):
        assert bundles_of(path) == [], path


@pytest.mark.parametrize("path,bundle", [
    ("/api/v2/legislative/eur-lex/oj/daily", "official-journal"),
    ("/api/v2/legislative/eur-lex/recent", "official-journal"),
    ("/api/v2/legislative/eur-lex/laws", "legislation"),
    ("/api/v2/legislative/oeil/procedures", "legislation"),
    ("/api/v2/parliament/amendments", "legislation"),
    ("/api/v2/funding/opportunities", "funding-procurement"),
    ("/api/v2/hadea/calls", "funding-procurement"),
    ("/api/v2/eeas/tenders", "funding-procurement"),
    ("/api/v2/news/all", "news-events"),
    ("/api/v2/events/all", "news-events"),
    ("/api/v2/ema/news", "news-events"),
    ("/api/v2/eu-financial-institutions/eba/news", "news-events"),
    ("/api/v2/ema/news", "agencies-bodies"),
    ("/api/v2/hadea/calls", "agencies-bodies"),
    ("/api/v2/who-is-who/officials", "people"),
    ("/api/v2/parliament/meps", "people"),
    ("/api/v2/transparency-register", "people"),
    ("/api/v2/proprietary/brussels-lobbies", "people"),
    ("/api/v2/consultations/all", "consultations"),
    ("/api/v2/commission/infringements", "enforcement-markets"),
    ("/api/v2/open-data/datasets", "research-data"),
    ("/api/v2/ema/publications", "research-data"),
])
def test_each_route_lands_where_a_user_looks_for_it(path, bundle):
    assert bundle in bundles_of(path)


def test_the_official_journal_is_not_also_general_legislation_and_law_is_not_news():
    assert bundles_of("/api/v2/legislative/eur-lex/oj/daily") == ["official-journal"]
    assert "official-journal" not in bundles_of("/api/v2/legislative/eur-lex/laws")
    assert "news-events" not in bundles_of("/api/v2/legislative/eur-lex/laws")
    assert "agencies-bodies" not in bundles_of("/api/v2/funding/opportunities")
    assert bundles_of("/api/v2/who-is-who/officials") == ["people"]


def test_a_called_path_matches_like_its_template():
    for template, called in (("/api/v2/funding/opportunities/{id}", "/api/v2/funding/opportunities/123"),
                             ("/api/v2/news/{item_id}", "/api/v2/news/7"),
                             ("/api/v2/legislative/eur-lex/laws/{celex}/text", "/api/v2/legislative/eur-lex/laws/32016R0679/text"),
                             ("/api/v2/ema/news/{item_id}", "/api/v2/ema/news/abc")):
        assert bundles_of(template) == bundles_of(called) != []


def test_an_id_that_no_longer_exists_opens_nothing():
    assert not path_in_bundles("/api/v2/news/all", ["gone"])
    assert not path_in_bundles("/api/v2/news/all", [])


def _key(scopes):
    return ApiKey(scopes=scopes, key_hash="x", key_prefix="abcd", name="t")


def test_a_key_opens_its_bundles_and_nothing_else():
    k = _key(all_self_serve_scopes() + ["bundle:people", "bundle:official-journal"])
    assert k.bundle_limits == ["people", "official-journal"]
    assert k.grants_route("/api/v2/who-is-who/officials/9") and k.grants_route("/api/v2/legislative/eur-lex/oj/daily/")
    assert not k.grants_route("/api/v2/funding/opportunities")
    assert not k.grants_route("/api/v1/laws")


def test_an_ordinary_key_and_a_named_route_key_behave_as_before():
    assert _key(["read:laws"]).grants_route("/api/v2/anything") and _key(["*"]).bundle_limits == []
    assert _key(["route:/api/v2/news/all"]).grants_route("/api/v2/news/all")
    assert not _key(["route:/api/v2/news/all"]).grants_route("/api/v2/news/latest")
    both = _key(["route:/api/v2/news/all", "bundle:people"])
    assert both.grants_route("/api/v2/news/all") and both.grants_route("/api/v2/parliament/meps")
    assert not both.grants_route("/api/v2/news/latest")


def _gate(scopes):
    from api.v1 import _deps
    from core.database import get_db
    key = _key(scopes)
    key.id, key.api_tier, key.is_sandbox, key.user_id = "k1", "free", False, 1
    app = FastAPI()

    @app.get("/api/v2/parliament/meps")
    @app.get("/api/v2/funding/opportunities")
    async def route(user=Depends(_deps.api_user_with_rate_limit)):
        return {"ok": True}

    async def fake_user(request: Request):
        request.state.api_key = key
        return SimpleNamespace(id=1, role="admin", subscription_tier="blue")
    app.dependency_overrides[_deps.get_api_user] = fake_user
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_the_gate_refuses_outside_the_bundle_and_says_why():
    c = _gate(all_self_serve_scopes() + ["bundle:people"])
    assert c.get("/api/v2/parliament/meps").status_code == 200
    r = c.get("/api/v2/funding/opportunities")
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == "route_not_included"


def test_a_limit_never_widens_a_scope():
    r = _gate(["read:laws", "bundle:people"]).get("/api/v2/parliament/meps")
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == "scope_missing"


def test_a_key_limited_to_bundles_opens_no_mcp_tool():
    from api.mcp_http import _dispatch_tools_call
    out = asyncio.run(_dispatch_tools_call(1, {"name": "ask_brubru", "arguments": {"question": "x"}}, None,
                                           _key(["read:laws", "bundle:people"]), SimpleNamespace(role="admin"), None, "r"))
    assert "error" in out and "not the MCP tools" in str(out["error"])


class _MintDb:
    def add(self, obj):
        obj.id = "00000000-0000-0000-0000-000000000001"
        from datetime import datetime, timezone
        obj.created_at = datetime.now(timezone.utc)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def _mint_client(monkeypatch):
    import api.me_api_keys as mint
    from core.database import get_db
    monkeypatch.setattr(mint, "_count_active_keys", lambda db, uid: 0)
    monkeypatch.setattr(mint, "_count_recent_mints", lambda db, uid: 0)
    app = FastAPI()
    app.include_router(mint.router)
    app.dependency_overrides[get_db] = lambda: _MintDb()
    app.dependency_overrides[mint.get_current_user] = lambda: SimpleNamespace(id="00000000-0000-0000-0000-000000000002", email="t@example.test")
    return TestClient(app), mint.router.prefix


def test_minting_a_key_for_chosen_bundles(monkeypatch):
    c, prefix = _mint_client(monkeypatch)
    r = c.post(prefix, json={"name": "People only", "scopes": ["read:laws"], "bundles": ["people", "consultations"], "expires_in_days": 90})
    assert r.status_code in (200, 201), r.text
    scopes = r.json()["scopes"]
    assert "bundle:people" in scopes and "bundle:consultations" in scopes
    assert set(all_self_serve_scopes()) <= set(scopes)     # the bundle is the limit, so no route in it fails on a scope
    key = _key(scopes)
    assert key.grants_route("/api/v2/parliament/meps") and key.grants_scope("read:ep")
    assert not key.grants_route("/api/v2/funding/opportunities")


def test_minting_with_no_bundles_is_as_before(monkeypatch):
    c, prefix = _mint_client(monkeypatch)
    r = c.post(prefix, json={"name": "Everything", "scopes": ["read:laws"], "expires_in_days": 90})
    assert r.status_code in (200, 201) and r.json()["scopes"] == ["read:laws"]


@pytest.mark.parametrize("bundles", [["nonsense"], ["people", "nonsense"]])
def test_minting_refuses_an_unknown_bundle(monkeypatch, bundles):
    c, prefix = _mint_client(monkeypatch)
    r = c.post(prefix, json={"name": "Bad", "scopes": ["read:laws"], "bundles": bundles, "expires_in_days": 90})
    assert r.status_code == 422 and r.json()["detail"]["reason_code"] == "invalid_bundles"


def test_a_user_cannot_mint_a_route_or_bundle_entry_through_scopes(monkeypatch):
    c, prefix = _mint_client(monkeypatch)
    for entry in ("bundle:people", "route:/api/v2/news/all", "*"):
        assert c.post(prefix, json={"name": "Bad", "scopes": [entry], "expires_in_days": 90}).status_code == 422


def test_the_bundle_routes_answer_with_no_key_and_count_the_live_routes():
    from main import app
    c = TestClient(app)
    r = c.get("/api/v2/bundles")
    assert r.status_code == 200
    d = r.json()
    assert [b["id"] for b in d["data"]] == bundle_ids() and d["total"] == len(API_BUNDLES) == 9
    assert all(b["routes"] > 0 and b["lists"] > 0 for b in d["data"])
    one = c.get("/api/v2/bundles/official-journal")
    assert one.status_code == 200 and one.json()["total"] == next(b["routes"] for b in d["data"] if b["id"] == "official-journal")
    assert all("official-journal" in x["bundles"] for x in one.json()["data"])
    missing = c.get("/api/v2/bundles/nonsense")
    assert missing.status_code == 404 and "not_found" in missing.text


def test_the_spec_names_each_routes_bundles():
    from main import app
    spec = TestClient(app).get("/api/v2/openapi.json").json()
    assert spec["paths"]["/api/v2/funding/opportunities"]["get"]["x-brubru-bundles"] == ["funding-procurement"]
    assert set(spec["paths"]["/api/v2/ema/news"]["get"]["x-brubru-bundles"]) == {"news-events", "agencies-bodies"}
    assert spec["paths"]["/api/v2/extract"]["get"]["x-brubru-bundles"] == []
