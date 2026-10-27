"""Phase 2 of the funding standard: every funding list answers to the same parameters and fields.

Read from the app's own route table (the OpenAPI it serves), so a list added later is checked too.
"""
import pathlib
import sys

from fastapi import FastAPI

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

FUNDING = "/api/v2/funding/"


def _spec(router):
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    return app.openapi()


def _lists(spec):
    """The funding lists: GET routes whose last segment is not a path parameter; the files of a
    procedure (`.../{item_id}/documents`) are listed apart."""
    items, files = {}, {}
    for path, methods in spec["paths"].items():
        if not path.startswith(FUNDING) or "get" not in methods or path.rstrip("/").split("/")[-1].startswith("{"):
            continue
        params = {p["name"]: p for p in methods["get"].get("parameters", []) if p.get("in") == "query"}
        (files if path.endswith("/documents") else items)[path] = params
    return items, files


def test_every_funding_list_pages_by_50_up_to_200_with_bodies_on():
    from api.v2.funding import router
    items, files = _lists(_spec(router))
    assert len(items) >= 66, len(items)               # 66 item lists on 27 Oct 2026, beside 14 file lists
    wrong = {}
    for path, params in items.items():
        limit = params.get("limit", {}).get("schema", {})
        body = params.get("include_body", {}).get("schema", {})
        problems = []
        if limit.get("default") != 50:
            problems.append(f"limit default {limit.get('default')}")
        if (limit.get("maximum") or 0) < 200:
            problems.append(f"limit max {limit.get('maximum')}")
        if "include_body" not in params:
            problems.append("no include_body")
        elif body.get("default") is not True:
            problems.append(f"include_body default {body.get('default')}")
        if problems:
            wrong[path] = problems
    assert wrong == {}
    # A procedure's files keep bodies off: an extracted file text reaches 5 MB (27 Oct 2026).
    for path, params in files.items():
        assert params["include_body"]["schema"].get("default") is False, path


def test_a_folder_outside_funding_keeps_its_own_defaults():
    from fastapi import APIRouter
    from api.v2.economy_endpoints import register_resource
    router = APIRouter()
    register_resource(router, body_code="x", item_type="news", slug="x-news", noun="news items", body_name="X",
                      acronym="X", source="its site.", tag="v2-x")
    spec = _spec(router)
    params = {p["name"]: p for p in spec["paths"]["/api/v2/x-news"]["get"]["parameters"] if p.get("in") == "query"}
    assert params["limit"]["schema"].get("default") == 20 and params["limit"]["schema"].get("maximum") == 100
    assert params["include_body"]["schema"].get("default") is False


def test_include_body_false_takes_the_bodies_off_a_list_that_always_composes_them():
    from types import SimpleNamespace
    from api.v2.funding._standard import without_bodies
    env = SimpleNamespace(data=[SimpleNamespace(body_txt="t", body_html="<p>t</p>", title="x"), {"body_txt": "t", "title": "y"}])
    assert without_bodies(env, True).data[0].body_txt == "t"
    out = without_bodies(env, False)
    assert out.data[0].body_txt is None and out.data[0].body_html is None and out.data[0].title == "x"
    assert out.data[1]["body_txt"] is None and out.data[1]["title"] == "y"


# --- step 2: the parameters --------------------------------------------------------------------------- #
class _Rows:
    def __init__(self, rows): self.rows = rows
    def scalar(self): return len(self.rows)
    def fetchall(self): return self.rows
    def mappings(self): return self
    def all(self): return self.rows


class _Db:
    def __init__(self, rows=()):
        self.rows, self.sql = list(rows), []

    def execute(self, stmt, params=None):
        self.sql.append((str(stmt), dict(params or {})))
        return _Rows(self.rows)


def _client(router, db):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_an_agency_list_takes_the_publication_window_status_and_deadlines():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/ecdc-tenders", params={
        "published_from": "2026-01-01", "published_to": "2026-06-30", "status": "open",
        "deadline_from": "2026-11-01", "deadline_to": "2026-12-31"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "status = :status" in sql and params["status"] == "open"
    assert "deadline >= :deadline_from" in sql and "deadline < CAST(:deadline_to AS date) + 1" in sql
    assert str(params["since"]) == "2026-01-01" and str(params["until"]) == "2026-06-30"     # published_* are the window
    assert _client(funding, _Db()).get("/api/v2/funding/ecdc-tenders", params={"status": "live"}).status_code == 400
    # A list that is not procurement (F&T news) takes the window only.
    spec = _spec(funding)
    params = {p["name"] for p in spec["paths"]["/api/v2/funding/ft-news"]["get"]["parameters"]}
    assert {"published_from", "published_to"} <= params and not {"status", "deadline_from"} & params


def test_a_folder_outside_funding_gains_none_of_the_funding_filters():
    from fastapi import APIRouter
    from api.v2.economy_endpoints import register_resource
    router = APIRouter()
    register_resource(router, body_code="x", item_type="tender", slug="x-tenders", noun="tenders", body_name="X",
                      acronym="X", source="its site.", tag="v2-x", procurement=True)
    names = {p["name"] for p in _spec(router)["paths"]["/api/v2/x-tenders"]["get"]["parameters"]}
    assert not {"published_from", "status", "deadline_from"} & names


def test_a_cohesion_list_takes_country_in_both_spellings_the_windows_and_the_orders():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/eagf", params={
        "country": "GR", "created_from": "2026-10-01", "published_from": "2025-01-01", "order": "recent"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[-1]
    assert "upper(ms) = ANY(:ms)" in sql and params["ms"] == ["EL", "GR"]       # the CAP file writes both
    assert "created_at >= :created_from" in sql and "document_date >= :published_from" in sql
    assert "ORDER BY document_date DESC NULLS LAST, id DESC" in sql
    for order, fragment in (("amount", "ORDER BY total_eur DESC NULLS LAST"), ("updated_asc", "ORDER BY updated_at ASC, id ASC")):
        db = _Db()
        _client(funding, db).get("/api/v2/funding/eagf", params={"order": order})
        assert fragment in db.sql[-1][0], order
    db = _Db()
    _client(funding, db).get("/api/v2/funding/eagf")
    assert "ORDER BY total_eur DESC NULLS LAST, ms, id" in db.sql[-1][0]                # the list's own default
    assert _client(funding, _Db()).get("/api/v2/funding/eagf", params={"order": "title"}).status_code == 400
