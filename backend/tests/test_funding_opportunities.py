"""/funding/opportunities (funding standard Phase 3b, Victor's decisions of 29 Oct 2026): one list over TED,
the F&T Portal's tenders, calls and calls in cascade, and the agencies' funding items, each procedure once
on exact keys (O104). The page is checked on production in process (scratchpad opp_check.py): every item
equals its own list's item and `self` opens it; these tests pin the query and the routing."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Rows:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return 0
    def fetchall(self): return self.rows
    def mappings(self): return self
    def all(self): return self.rows


class _Db:
    def __init__(self): self.sql = []
    def execute(self, stmt, params=None):
        from sqlalchemy.dialects import postgresql
        compiled = stmt.compile(dialect=postgresql.dialect())
        self.sql.append((str(compiled), dict(compiled.params)))
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


def test_one_union_over_the_five_sources_without_the_copies_another_source_serves():
    db = _Db()
    r = _client(db).get("/api/v2/funding/opportunities")
    assert r.status_code == 200, r.text
    sql = db.sql[0][0]
    for table in ("FROM tenders", "FROM ft_calls_for_tenders", "FROM ft_calls_for_proposals", "FROM ft_cascade_calls",
                  "FROM economy_items"):
        assert table in sql, table
    # O104: each copy is left to the source that serves it, on an exact key
    assert "coalesce(tenders.source, '') = 'ft_portal'" in sql and "'FT-' || x.tender_reference = tenders.publication_number" in sql
    assert "x.publication_number = ft_calls_for_tenders.tender_reference" in sql
    assert "x.tender_reference = substring(economy_items.public_url from '/tender-details/([^/?#]+)$')" in sql
    assert "upper(x.topic_id) = upper(substring(economy_items.public_url from '/topic-details/([^/?#]+)$'))" in sql
    assert sql.count("NOT ft_calls_for_tenders.is_test") == 1 and "NOT ft_calls_for_proposals.is_test" in sql
    # one scan: the page carries its total; the default order is the newest first, ties broken stably
    assert "count(*) OVER ()" in sql
    assert "ORDER BY opp.document_date DESC NULLS LAST, opp.src DESC, opp.rid DESC" in sql


def test_the_filters_reach_the_query_and_bad_values_are_refused():
    db = _Db()
    r = _client(db).get("/api/v2/funding/opportunities", params={
        "status": "Open", "item_type": "grant", "body": "FTPortal", "country": "be", "programme": "Horizon",
        "deadline_from": "2026-11-01", "min_amount_eur": 1000, "order": "deadline"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    values = set(map(str, params.values()))
    assert {"open", "grant", "ftportal", "BE", "%Horizon%", "1000.0"} <= values, values
    assert "ORDER BY opp.deadline ASC NULLS LAST" in sql
    c = _client(_Db())
    assert c.get("/api/v2/funding/opportunities", params={"item_type": "funded_project"}).status_code == 400
    assert c.get("/api/v2/funding/opportunities", params={"order": "title"}).status_code == 400


def test_a_page_past_the_end_still_counts_the_total():
    db = _Db()
    r = _client(db).get("/api/v2/funding/opportunities", params={"page": 9999})
    assert r.status_code == 200
    assert len(db.sql) == 2 and "count(*) AS count_1" in db.sql[1][0]      # the page was empty: counted on its own


def test_self_points_at_each_sources_own_list():
    from api.v2.funding.opportunities import _ITEM_PATHS
    from main import app
    paths = {getattr(r, "path", None) for r in app.routes}
    for src, tpl in _ITEM_PATHS.items():
        route = tpl.replace("{}", "{item_id}")
        alt = {route, tpl.replace("{}", "{tender_reference:path}"), tpl.replace("{}", "{topic_id:path}"),
               tpl.replace("{}", "{publication_number}"), tpl.replace("{}", "{tender_id}")}
        assert alt & paths, (src, tpl)


def test_a_ted_item_says_its_source_and_links_its_copy_on_the_list_and_the_item_route():
    """O104 (a), Victor 29 Oct 2026: /tenders stays additive until the legacy date: each item says `source`
    (ted, or ft_portal for a portal notice copied in for the Tenderator) and `same_as` links the copy."""
    from sqlalchemy.orm import Query
    from models.tender import Tender

    def row(**kw):
        r = {c.name: None for c in Tender.__table__.columns}
        r.update(has_lots=False, cpv_codes=[], title="T", **kw)
        return SimpleNamespace(**r)
    rows = [row(id=7, publication_number="FT-abc-CN", source="ft_portal"), row(id=8, publication_number="9-2026", source="ted_api")]

    class Q(Query):
        def count(self): return len(rows)
        def all(self): return rows
        def first(self): return rows[0]

    class Db:
        def __init__(self): self.sql = []
        def query(self, *entities): return Q(list(entities))
        def execute(self, stmt, params=None):
            self.sql.append((str(stmt), dict(params or {})))
            pairs = [(7, "0f0e-uuid")] if "ft_calls_for_tenders x" in str(stmt) else []
            return SimpleNamespace(fetchall=lambda: pairs, all=lambda: [], scalar=lambda: 0)
    db = Db()
    listed = _client(db).get("/api/v2/funding/tenders").json()["data"]
    assert [(i["source"], i["same_as"]) for i in listed] == [
        ("ft_portal", ["http://testserver/api/v2/funding/ft-calls-for-tenders/0f0e-uuid"]), ("ted", [])]
    sql = next(q for q, p in db.sql if "ft_calls_for_tenders x" in q)
    assert "x.tender_reference = t.publication_number AND x.source_url LIKE '%ted.europa.eu%'" in sql
    assert "t.publication_number = 'FT-' || x.tender_reference" in sql
    item = _client(db).get("/api/v2/funding/tenders/7").json()
    assert (item["source"], item["same_as"]) == ("ft_portal", ["http://testserver/api/v2/funding/ft-calls-for-tenders/0f0e-uuid"])
