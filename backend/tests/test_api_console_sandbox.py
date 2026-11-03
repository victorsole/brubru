"""The public sandbox behind the API Console (Victor, 3 Nov 2026): a stranger reads live rows with no account,
inside caps that hold whoever owns the key, and every call says what it cost and what is left."""
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from models.api_key import ApiKey
from services.billing import api_meter


def _key(is_sandbox):
    k = ApiKey(scopes=["*"], key_hash="x", key_prefix="abcd", name="t")
    k.id, k.api_tier, k.is_sandbox, k.user_id = "k1", "free", is_sandbox, 1
    return k


def _client(monkeypatch, is_sandbox, role="admin", pool=(True, "", 7, 90)):
    """The real gate and the real header middleware; only the database calls are faked."""
    from api.v1 import _deps
    from api.v1._billing_middleware import BillingRefundMiddleware
    from core.database import get_db
    calls = {"pool": 0, "debit": 0}

    def fake_pool(db, ip):
        calls["pool"] += 1
        return pool

    def fake_debit(db, user_id, cost):
        calls["debit"] += 1
        return True, 1_990_000

    monkeypatch.setattr(_deps, "sandbox_consume_counted", fake_pool)
    monkeypatch.setattr(_deps, "debit", fake_debit)
    monkeypatch.setattr(_deps, "record_usage", lambda *a, **k: SimpleNamespace(id=None))
    app = FastAPI()
    app.add_middleware(BillingRefundMiddleware)

    @app.get("/api/v2/news/all")
    @app.get("/api/v2/extract")
    @app.get("/api/v2/predictions/{ref}/outcome")
    async def route(user=Depends(_deps.api_user_with_rate_limit)):
        return {"ok": True}

    @app.post("/api/v2/news/all")
    async def post_route(user=Depends(_deps.api_user_with_rate_limit)):
        return {"ok": True}

    async def fake_user(request: Request):
        request.state.api_key = _key(is_sandbox)
        request.state.api_key_is_sandbox = is_sandbox
        return SimpleNamespace(id=1, role=role, subscription_tier="blue")
    app.dependency_overrides[_deps.get_api_user] = fake_user
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app), calls


def test_the_sandbox_key_is_capped_though_an_admin_owns_it(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=True, role="admin")
    r = c.get("/api/v2/news/all?limit=5")
    assert r.status_code == 200 and calls == {"pool": 1, "debit": 0}
    assert r.headers["X-Brubru-Sandbox-Remaining"] == "7"
    assert r.headers["X-Brubru-Sandbox-Pool-Remaining"] == "90"
    assert r.headers["X-Brubru-Cost-Eur"] == "0"


def test_an_admin_key_stays_exempt_and_says_so(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=False, role="admin")
    r = c.get("/api/v2/news/all")
    assert r.status_code == 200 and calls == {"pool": 0, "debit": 0} and r.headers["X-Brubru-Cost-Eur"] == "0"


def test_a_paying_key_is_told_the_price_and_the_balance(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=False, role="user")
    r = c.get("/api/v2/news/all")
    assert r.status_code == 200 and calls == {"pool": 0, "debit": 1}
    assert r.headers["X-Brubru-Cost-Eur"] == "0.001" and r.headers["X-Brubru-Balance-Eur"] == "1.99"
    assert "X-Brubru-Sandbox-Remaining" not in r.headers
    assert c.get("/api/v2/predictions/2025-0001/outcome").headers["X-Brubru-Cost-Eur"] == "0.005"


@pytest.mark.parametrize("url,reason", [
    ("/api/v2/news/all?limit=26", "sandbox_too_large"),
    ("/api/v2/news/all?page=11", "sandbox_too_large"),
    ("/api/v2/news/all?format=xlsx", "sandbox_no_export"),
    ("/api/v2/extract?url=https://europa.eu", "sandbox_route_not_included"),
    ("/api/v2/predictions/2025-0001/outcome", "sandbox_route_not_included"),
])
def test_what_the_sandbox_refuses_costs_the_visitor_no_call(monkeypatch, url, reason):
    c, calls = _client(monkeypatch, is_sandbox=True)
    r = c.get(url)
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == reason and calls["pool"] == 0


def test_the_sandbox_only_reads(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=True)
    r = c.post("/api/v2/news/all")
    assert r.status_code == 403 and r.json()["detail"]["reason_code"] == "sandbox_method" and calls["pool"] == 0


@pytest.mark.parametrize("url", ["/api/v2/news/all?limit=25&page=10", "/api/v2/news/all?format=json", "/api/v2/news/all?limit=abc"])
def test_the_sandbox_serves_up_to_its_limits(monkeypatch, url):
    c, calls = _client(monkeypatch, is_sandbox=True)
    assert c.get(url).status_code == 200 and calls["pool"] == 1


def test_a_visitor_over_the_cap_is_told_nothing_is_left(monkeypatch):
    c, _ = _client(monkeypatch, is_sandbox=True, pool=(False, "sandbox_ip_capped", 0, 0))
    r = c.get("/api/v2/news/all")
    assert r.status_code == 429 and r.json()["detail"]["reason_code"] == "sandbox_ip_capped"
    assert r.headers["X-Brubru-Sandbox-Remaining"] == "0"


def test_the_price_route_answers_with_no_key_and_reads_the_meters_table():
    from main import app
    r = TestClient(app).get("/api/v2/pricing")
    assert r.status_code == 200
    d = r.json()
    assert d["default"]["cost_eur"] == 0.001 and d["sandbox"]["calls_per_visitor_per_day"] == api_meter.SANDBOX_IP_CAP
    assert any(x["cost_eur"] == 0.005 and "predictions" in x["pattern"] for x in d["routes"])
    assert all("/api/v1/" not in x["pattern"] for x in d["routes"])


def test_a_page_may_read_the_cost_headers():
    from main import app
    r = TestClient(app).options("/api/v2/pricing", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    mw = next(m for m in app.user_middleware if "CORS" in str(m.cls))
    for h in ("X-Brubru-Cost-Eur", "X-Brubru-Balance-Eur", "X-Brubru-Sandbox-Remaining", "X-RateLimit-Remaining", "X-Request-Id"):
        assert h in mw.kwargs["expose_headers"]
