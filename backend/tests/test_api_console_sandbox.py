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
    calls = {"pool": 0, "debit": 0, "sql": []}

    class _Db:  # records what the gate asks the database itself to do (O213: the sandbox's statement timeout)
        def execute(self, stmt, *a, **k):
            calls["sql"].append(str(stmt))

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
    app.dependency_overrides[get_db] = lambda: _Db()
    return TestClient(app), calls


def test_the_sandbox_key_is_capped_though_an_admin_owns_it(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=True, role="admin")
    r = c.get("/api/v2/news/all?limit=5")
    assert r.status_code == 200 and (calls["pool"], calls["debit"]) == (1, 0)
    assert r.headers["X-Brubru-Sandbox-Remaining"] == "7"
    assert r.headers["X-Brubru-Sandbox-Pool-Remaining"] == "90"
    assert r.headers["X-Brubru-Cost-Eur"] == "0"


def test_an_admin_key_stays_exempt_and_says_so(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=False, role="admin")
    r = c.get("/api/v2/news/all")
    assert r.status_code == 200 and (calls["pool"], calls["debit"]) == (0, 0) and r.headers["X-Brubru-Cost-Eur"] == "0"


def test_a_paying_key_is_told_the_price_and_the_balance(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=False, role="user")
    r = c.get("/api/v2/news/all")
    assert r.status_code == 200 and (calls["pool"], calls["debit"]) == (0, 1)
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


def _big_answer_client(monkeypatch, is_sandbox, size):
    c, _ = _client(monkeypatch, is_sandbox=is_sandbox)
    app = c.app
    from api.v1 import _deps

    @app.get("/api/v2/big")
    async def big(user=Depends(_deps.api_user_with_rate_limit)):
        return {"data": "x" * size}
    return c


def test_a_sandbox_answer_too_large_is_refused_with_a_reason(monkeypatch):
    r = _big_answer_client(monkeypatch, True, api_meter.SANDBOX_MAX_BYTES + 10).get("/api/v2/big", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 403 and r.json()["reason_code"] == "sandbox_too_large"
    assert len(r.content) < 1000 and r.headers["X-Brubru-Sandbox-Remaining"] == "7"


def test_a_sandbox_answer_under_the_size_is_served_and_a_paying_key_has_no_such_limit(monkeypatch):
    assert _big_answer_client(monkeypatch, True, 1000).get("/api/v2/big").status_code == 200
    r = _big_answer_client(monkeypatch, False, api_meter.SANDBOX_MAX_BYTES + 10).get("/api/v2/big")
    assert r.status_code == 200 and len(r.content) > api_meter.SANDBOX_MAX_BYTES


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


class _PoolDb:
    """Stands in for the database in sandbox_consume_counted: the visitor's own row comes back at `ip_count`; the
    day's total is whatever the query computes from `rows`, so the test reads the SQL the function really sends."""

    def __init__(self, ip_count, rows):
        self.ip_count, self.rows, self.total_sql = ip_count, rows, None

    def execute(self, clause, params):
        sql = str(clause)
        if sql.lstrip().startswith("INSERT"):
            return SimpleNamespace(fetchone=lambda: (self.ip_count,))
        self.total_sql, cap = sql, params.get("cap")
        assert "SUM(" in sql and params.get("d")
        counted = [min(n, cap) if "LEAST(count_today, :cap)" in sql and cap is not None else n for n in self.rows]
        return SimpleNamespace(scalar=lambda: sum(counted))

    def commit(self):
        pass


def test_a_visitors_refused_presses_do_not_use_up_everyones_pool():
    """Victor, 6 Nov 2026: raise the pool before the console is marketed. A visitor whose own 10 are spent keeps
    pressing: on 4 Nov one connection's 11 presses all counted against the shared pool."""
    assert api_meter.SANDBOX_GLOBAL_CAP == 1000 and api_meter.SANDBOX_IP_CAP == 10
    db = _PoolDb(ip_count=1, rows=[40, 1])  # one visitor pressed 40 times, a new one presses once
    ok, reason, ip_left, pool_left = api_meter.sandbox_consume_counted(db, "198.51.100.2")
    assert (ok, reason, ip_left) == (True, "", 9)
    assert pool_left == 1000 - 11, db.total_sql
    assert "LEAST(count_today, :cap)" in db.total_sql


def test_the_price_route_tells_the_raised_pool():
    from main import app
    d = TestClient(app).get("/api/v2/pricing").json()["sandbox"]
    assert d["calls_per_day_in_total"] == 1000 and d["calls_per_visitor_per_day"] == 10


# O213 (6 Nov 2026): one heavy filter or sort from a stranger held a database connection, and with it the whole
# API, for a minute. Each sandbox statement now stops after SANDBOX_STATEMENT_TIMEOUT_MS; nobody else's does.
@pytest.mark.parametrize("is_sandbox, role, timed", [(True, "admin", True), (False, "admin", False), (False, "user", False)])
def test_only_the_sandbox_gets_a_statement_timeout(monkeypatch, is_sandbox, role, timed):
    from api.v1 import _deps
    c, calls = _client(monkeypatch, is_sandbox=is_sandbox, role=role)
    assert c.get("/api/v2/news/all?limit=5").status_code == 200
    expected = [f"SET LOCAL statement_timeout = {_deps.SANDBOX_STATEMENT_TIMEOUT_MS}"] if timed else []
    assert calls["sql"] == expected


def test_a_refused_sandbox_call_sets_nothing(monkeypatch):
    c, calls = _client(monkeypatch, is_sandbox=True, pool=(False, "sandbox_ip_capped", 0, 0))
    assert c.get("/api/v2/news/all").status_code == 429 and calls["sql"] == []


def _timeout_app(pgcode):
    from sqlalchemy.exc import OperationalError
    from api.v1._errors import register_v1_error_handlers

    class _Orig(Exception):
        pass
    orig = _Orig("canceling statement due to statement timeout")
    orig.pgcode = pgcode
    app = FastAPI()
    register_v1_error_handlers(app)

    @app.get("/api/v2/slow")
    @app.get("/api/chat/slow")
    def slow():
        raise OperationalError("SELECT 1", {}, orig)
    return TestClient(app, raise_server_exceptions=False)


def test_a_statement_stopped_by_the_timeout_answers_504_and_says_why():
    r = _timeout_app("57014").get("/api/v2/slow")
    assert r.status_code == 504 and r.json()["reason_code"] == "query_timeout"
    assert "took too long" in r.json()["error"] and r.headers.get("X-Request-Id")
    assert _timeout_app("57014").get("/api/chat/slow").status_code == 504


def test_any_other_database_error_stays_a_500():
    r = _timeout_app("08006").get("/api/v2/slow")
    assert r.status_code == 500 and "query_timeout" not in r.text
