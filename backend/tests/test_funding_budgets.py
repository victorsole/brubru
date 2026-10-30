"""/funding/budgets (funding standard Phase 3d, Victor's decisions of 30 Oct 2026): one list over the
cohesion allocations, the Solidarity Fund cases and the CAP payments; money only (no indicators) and
without the CAP files' EU-total rows. The page is checked on production in process; these tests pin the
query, the routing and each item's own builder."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return 0
    def fetchall(self): return self.rows
    def all(self): return self.rows
    def mappings(self): return self


class _Db:
    def __init__(self): self.sql = []
    def execute(self, stmt, params=None):
        self.sql.append((str(stmt), dict(params or {})))
        return _Rows([])


def _client(db):
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.funding import router
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_one_union_over_the_three_money_sources_without_the_eu_totals():
    db = _Db()
    r = _client(db).get("/api/v2/funding/budgets", params={"q": "flood"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "FROM eu_cohesion_finances" in sql and "FROM eu_solidarity_fund" in sql and "FROM eu_cap_payments" in sql
    assert "eu_cohesion_outcomes" not in sql                                        # money only
    assert "FROM eu_cap_payments WHERE ms IS DISTINCT FROM 'TOTAL'" in sql          # O102: the EU totals left out
    # each list's own q
    assert "(cci_title ILIKE :q OR body_txt ILIKE :q)" in sql and "(name_of_disaster ILIKE :q OR body_txt ILIKE :q)" in sql
    assert params["q"] == "%flood%"
    # the default is each fund's own: the largest amount first, then a key unique across the union
    assert "ORDER BY amount_eur DESC NULLS LAST, src DESC, rid DESC LIMIT :limit OFFSET :offset" in sql
    count_sql = db.sql[1][0]
    assert count_sql.startswith("SELECT count(*) FROM (") and count_sql.count("UNION ALL") == 2


def test_the_filters_reach_the_query_and_bad_values_are_refused():
    db = _Db()
    r = _client(db).get("/api/v2/funding/budgets", params={
        "item_type": "cohesion_allocation", "status": "Adopted", "body": "ERDF", "country": "gr",
        "programme": "regional development", "published_from": "2025-01-01", "updated_from": "2026-10-25",
        "min_amount_eur": 1000000, "order": "recent"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert (params["item_type"], params["status"], params["body"]) == ("cohesion_allocation", "adopted", "erdf")
    assert set(params["countries"]) == {"EL", "GR"}
    assert params["programme_funds"] == ["erdf"] and params["programme"] == "%regional development%"
    assert "updated_date >= :updated_from" in sql and "document_date >= :published_from" in sql
    assert params["min_amount_eur"] == 1000000 and "ORDER BY document_date DESC NULLS LAST, src DESC, rid DESC" in sql
    # a word that is not a standard status matches the fund's own word
    db2 = _Db()
    assert _client(db2).get("/api/v2/funding/budgets", params={"status": "Adopted by MS"}).status_code == 200
    assert db2.sql[0][1]["source_status"] == "%Adopted by MS%" and "source_status ILIKE :source_status" in db2.sql[0][0]
    c = _client(_Db())
    assert c.get("/api/v2/funding/budgets", params={"item_type": "cohesion_indicator"}).status_code == 400
    assert c.get("/api/v2/funding/budgets", params={"order": "deadline"}).status_code == 400


def test_each_row_is_built_by_its_own_lists_builder_and_links_its_own_item():
    from api.v2.funding import budgets
    calls = []

    class Db:
        def execute(self, stmt, params=None):
            sql = str(stmt); calls.append(sql)
            if "FROM eu_cohesion_finances" in sql:
                return _Rows([{"id": 7, "fund": "ESF", "body_code": "esf", "item_type": "cohesion_allocation", "status": "Adopted by MS",
                               "title": "Programme", "body_txt": "t", "body_html": "<p>t</p>"}])
            if "FROM eu_cap_payments" in sql:
                return _Rows([{"id": 3, "fund": "EAGF", "body_code": "eagf", "item_type": "cap_payment", "ms": "FR"}])
            raise AssertionError(sql)
    rows = [SimpleNamespace(src="cap", rid=3), SimpleNamespace(src="alloc", rid=7)]
    routes = {("esf", "cohesion_allocation"): "/api/v2/funding/esf-plus/{row_id}", ("eagf", "cap_payment"): "/api/v2/funding/eagf/{row_id}"}
    out = budgets._build(Db(), rows, False, "https://h", routes)
    assert [d["self"] for d in out] == ["https://h/api/v2/funding/eagf/3", "https://h/api/v2/funding/esf-plus/7"]
    alloc = out[1]
    assert (alloc["status"], alloc["source_status"], alloc["body_name"]) == ("adopted", "Adopted by MS", "European Social Fund Plus")
    assert alloc["body_txt"] is None and alloc["body_html"] is None              # include_body=false
    assert any("FROM eu_cohesion_finances WHERE id = ANY(:ids)" in s for s in calls)


def test_every_fund_has_the_item_route_self_points_at():
    from api.v2.funding.funding_all import _item_routes
    from main import app
    routes = _item_routes(app)
    for fund in ("erdf", "esf", "cf", "jtf", "interreg", "emfaf", "amif", "isf"):
        assert (fund, "cohesion_allocation") in routes, fund
    assert ("eusf", "solidarity_case") in routes
    assert ("eagf", "cap_payment") in routes and ("eafrd", "cap_payment") in routes
    assert all("{row_id}" in routes[k] for k in routes if k[1] in ("cohesion_allocation", "solidarity_case", "cap_payment"))
