"""22 funding endpoints served updated_date null on every item (read 20 Oct 2026).

Cohesion finances and outcomes (8 funds each), EAFRD, EAGF, the Solidarity Fund, funded projects,
funding opportunities and programmes. Their tables kept updated_at / last_updated, stamped on every
run, so serving it would have reported every row changed every night; migration 306 puts the
change-only trigger on them, and the routes now serve the column and filter on it. These call the
real routes with a session that records the SQL they send.
"""
import pathlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402

CHANGED = datetime(2026, 10, 17, 22, 0, tzinfo=timezone.utc)


class _Row(dict):
    """A result row read either way: r["col"], r.col, r._mapping."""
    __getattr__ = dict.__getitem__

    @property
    def _mapping(self):
        return self


class _Rows:
    def __init__(self, rows): self.rows = [_Row(r) for r in rows]
    def mappings(self): return self
    def all(self): return self.rows
    def fetchall(self): return self.rows
    def scalar(self): return len(self.rows)


class _Db:
    def __init__(self, row):
        self.row, self.sql = row, []

    def execute(self, stmt, params=None):
        self.sql.append((str(stmt), dict(params or {})))
        return _Rows([self.row])


def _client(router, db):
    app = FastAPI()
    app.include_router(router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_cohesion_finances_serve_and_filter_their_change_date():
    from api.v2.funding import cohesion_finances as cf
    row = {"id": 1, "public_url": "https://cohesiondata.ec.europa.eu/funds/erdf/21-27", "document_date": None,
           "creation_date": CHANGED, "updated_date": CHANGED, "fund": "ERDF", "ms": "ES", "cci": "2021ES16RFPR001",
           "cci_title": "Plurirregional - ES - ERDF", "dg": "REGIO", "status": "Adopted by EC", "status_date": None,
           "financial_allocation_category": None, "y2021": 1.0, "y2022": 1.0, "y2023": 1.0, "y2024": 1.0,
           "y2025": 1.0, "y2026": 1.0, "y2027": 1.0, "total_non_flexible_amount": 1.0, "total_flexible_amount": 1.0,
           "total": 7.0, "share_of_fa_in_total": None, "body_txt": None, "body_html": None}
    db = _Db(row)
    r = _client(cf.router, db).get("/api/v2/funding/erdf", params={"updated_from": "2026-10-17", "updated_to": "2026-10-18"})
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["updated_date"].startswith("2026-10-17")
    sql, params = db.sql[-1]
    assert "updated_at AS updated_date" in sql and "updated_at >= :uf" in sql and "updated_at <= :ut" in sql
    assert params["ut"].hour == 23   # a bare date covers the whole day


def test_the_solidarity_fund_serves_its_change_date():
    from api.v2.funding import cohesion_eusf as ce
    row = {"id": 7, "year_of_occurrence": 2023, "cci_number": "2023ES16SPO001", "applicant_country": "ES",
           "name_of_disaster": "Floods", "disaster_type": "Flood", "status": "Accepted", "category": "Major",
           "total_direct_damage_meur": 1.0, "eligible_emergency_cost_meur": None,
           "damage_pct": None, "eusf_grant_paid_meur": 1.0, "public_url": "https://ec.europa.eu/x",
           "document_date": None, "creation_date": CHANGED, "updated_date": CHANGED}
    db = _Db(row)
    r = _client(ce.router, db).get("/api/v2/funding/eusf", params={"updated_from": "2026-10-01"})
    assert r.status_code == 200, r.text
    assert r.json()["data"][0]["updated_date"].startswith("2026-10-17")
    assert "updated_at >= :uf" in db.sql[-1][0]


def test_programmes_link_their_own_page_and_carry_the_lists_dates():
    from api.v2.funding import funding_programmes as fp
    r = _client(fp.router, _Db({})).get("/api/v2/funding/programmes", params={"limit": 100})
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    horizon = next(i for i in items if i["acronym"] == "Horizon Europe")
    assert horizon["public_url"].endswith("/programmes/horizon")
    assert len({i["public_url"] for i in items}) > len(items) // 2
    # The list's own $created / $updated (the config moves $updated whenever it is revised).
    created, updated = fp._config_dates()
    assert horizon["creation_date"].startswith(created.date().isoformat())
    assert horizon["updated_date"].startswith(updated.date().isoformat())
    assert created.date().isoformat() == "2026-06-15"


def test_funded_projects_and_opportunities_map_their_change_column():
    from api.v1 import funding_tenders_collections as fc
    from api.v1 import infringements_funding as inf
    import inspect
    assert "updated_date=r.last_updated" in inspect.getsource(fc._project_to_item)
    # funding-opportunities reads ft_calls_for_proposals since 23 Oct 2026 (its change column).
    assert "updated_date=r.content_updated_at" in inspect.getsource(inf._funding_to_item)
    for fn in (fc.list_funded_projects, inf.list_funding_opportunities):
        params = inspect.signature(fn).parameters
        assert "updated_from" in params and "updated_to" in params


def test_international_cooperation_matches_programmes_on_the_indexed_summary():
    # 20 Oct 2026: an ILIKE over 188,187 bodies made a 10-item page take 70-77 s.
    from api.v2.funding import international_cooperation as ic
    row = {"id": 1, "title": "MINISTRY OF FINANCE", "summary": "MINISTRY | EUR 1 | Neighbourhood, Development and International Cooperation | Ukraine",
           "public_url": "https://ec.europa.eu/budget/financial-transparency-system/index.html#2025-x",
           "body_txt": "Beneficiary: MINISTRY\nProgramme: Neighbourhood, Development and International Cooperation\nYear: 2025",
           "body_html": None, "document_date": None, "creation_date": CHANGED, "updated_at": CHANGED, "source_kind": "fts"}
    db = _Db(row)
    r = _client(ic.router, db).get("/api/v2/funding/international-cooperation", params={"programme": "ndici", "limit": 5})
    assert r.status_code == 200, r.text
    sql = db.sql[-1][0]
    assert "summary ILIKE :prog" in sql and "body_txt ILIKE :prog" not in sql


def test_international_cooperation_counts_once_per_window():
    from api.v2.funding import international_cooperation as ic
    ic._TOTALS.clear()
    row = {"id": 1, "title": "A", "summary": "A | Humanitarian Aid (HUMA)", "public_url": "https://x", "body_txt": "Beneficiary: A",
           "body_html": None, "document_date": None, "creation_date": CHANGED, "updated_at": CHANGED, "source_kind": "fts"}
    db = _Db(row)
    client = _client(ic.router, db)
    for page in (1, 2):
        assert client.get("/api/v2/funding/international-cooperation", params={"programme": "humanitarian", "page": page}).status_code == 200
    assert sum(1 for sql, _ in db.sql if sql.startswith("SELECT count(*)")) == 1
