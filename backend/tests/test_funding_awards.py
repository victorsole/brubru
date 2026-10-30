"""/funding/awards (funding standard Phase 3c, Victor's decision of 30 Oct 2026): one list over the funded
projects, the FTS beneficiaries' commitments and the EU bodies' TED award notices; every row served (no
exact key joins them), each FTS line linking its project. The page is checked on production in process;
these tests pin the query, the routing and the project link."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return 0
    def fetchall(self): return self.rows
    def all(self): return self.rows


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


def test_one_union_over_the_three_sources_each_with_its_own_search_and_default():
    db = _Db()
    r = _client(db).get("/api/v2/funding/awards", params={"q": "hydrogen"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "FROM ft_funded_projects WHERE NOT ft_funded_projects.is_test" in sql
    assert "FROM economy_items e LEFT JOIN fts_commitments c ON c.economy_item_id = e.id" in sql
    assert "FROM ted_award_notices n WHERE n.superseded_by IS NULL" in sql          # as /tender-awards by default
    # each list's own full-text search (each has its index)
    assert "@@ websearch_to_tsquery('english', :q)" in sql and "e.search_vector @@ plainto_tsquery('english', :q)" in sql
    assert params["q"] == "hydrogen"
    # each source ordered and cut on its own (its index serves it), merged in one total order (src + rid)
    assert sql.count("ORDER BY document_date DESC NULLS LAST, src DESC, rid DESC LIMIT :side_limit") == 3
    assert sql.endswith("ORDER BY document_date DESC NULLS LAST, src DESC, rid DESC LIMIT :limit OFFSET :offset")
    assert params["side_limit"] == 50 + 0
    count_sql = db.sql[1][0]
    assert count_sql.startswith("SELECT (SELECT count(*) FROM (") and count_sql.count("count(*)") == 3


def test_the_filters_reach_the_query_and_bad_values_are_refused():
    db = _Db()
    r = _client(db).get("/api/v2/funding/awards", params={
        "item_type": "funding_recipient", "status": "Ended", "body": "Commission", "country": "gr", "programme": "Horizon Europe",
        "published_from": "2025-01-01", "updated_from": "2026-10-01", "min_amount_eur": 5000, "order": "amount"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert (params["item_type"], params["status"], params["body"]) == ("funding_recipient", "ended", "commission")
    assert set(params["countries"]) == {"EL", "GR"} and params["programme"] == "%Horizon Europe%"
    assert params["min_amount_eur"] == 5000 and "ORDER BY amount_eur DESC NULLS LAST, src DESC, rid DESC" in sql
    assert "updated_date >= :updated_from" in sql and "document_date >= :published_from" in sql
    c = _client(_Db())
    assert c.get("/api/v2/funding/awards", params={"item_type": "tender"}).status_code == 400
    assert c.get("/api/v2/funding/awards", params={"order": "deadline"}).status_code == 400


def test_a_deep_page_cuts_each_source_at_its_offset_plus_limit():
    db = _Db()
    assert _client(db).get("/api/v2/funding/awards", params={"page": 4, "limit": 20}).status_code == 200
    params = db.sql[0][1]
    assert (params["offset"], params["limit"], params["side_limit"]) == (60, 20, 80)


def test_an_fts_line_links_its_project_only_when_brubru_holds_it():
    from api.v2.funding import _fts
    items = [SimpleNamespace(project_id="101039426", project=None), SimpleNamespace(project_id="999", project=None),
             SimpleNamespace(project_id=None, project=None)]

    class Db:
        def execute(self, stmt, params=None):
            assert "FROM ft_funded_projects" in str(stmt) and sorted(params["ids"]) == ["101039426", "999"]
            return _Rows([SimpleNamespace(project_id="101039426")])
    _fts.with_projects(Db(), items, "https://api.example/")
    assert [i.project for i in items] == ["https://api.example/api/v2/funding/ft-funded-projects/101039426", None, None]


def test_self_points_at_each_sources_own_list():
    from api.v2.funding.awards import _ITEM_PATHS
    from main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/v2/funding/ft-funded-projects/{project_id:path}" in paths
    assert "/api/v2/funding/eu-funding-recipients/{item_id}" in paths
    assert "/api/v2/funding/tender-awards/{publication_number}" in paths
    assert set(_ITEM_PATHS) == {"project", "fts", "ted_award"}
