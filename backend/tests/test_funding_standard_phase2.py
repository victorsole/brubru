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
    def fetchone(self): return self.rows[0] if self.rows else None
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


# The ORM-built lists (TED, funded projects, calls): the real query compiled for PostgreSQL.
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Query  # noqa: E402

COMPILED = []


class _CapturingQuery(Query):
    def _record(self):
        COMPILED.append(str(self.statement.compile(dialect=postgresql.dialect())))

    def count(self):
        self._record()
        return 0

    def all(self):
        self._record()
        return []


class _OrmDb(_Db):
    def query(self, *entities):
        return _CapturingQuery(list(entities))


def _orm_get(path, params):
    from api.v2.funding import router as funding
    COMPILED.clear()
    r = _client(funding, _OrmDb()).get(path, params=params)
    return r, list(COMPILED)


def test_the_ted_list_takes_country_status_the_created_window_and_the_orders():
    r, sql = _orm_get("/api/v2/funding/tenders", {"country": "be", "status": "open", "created_from": "2026-10-01",
                                                    "since": "2026-01-01", "order": "deadline"})
    assert r.status_code == 200, r.text
    count_sql, page_sql = sql
    assert "tenders.buyer_country = " in count_sql and "tenders.status = " in count_sql
    assert "tenders.created_at >= " in count_sql and "tenders.publication_date >= " in count_sql   # since = published_from
    assert "ORDER BY tenders.submission_deadline ASC NULLS LAST" in page_sql
    r, sql = _orm_get("/api/v2/funding/tenders", {"order": "updated_asc"})
    assert "ORDER BY tenders.updated_at ASC, tenders.id ASC" in sql[1]
    r, sql = _orm_get("/api/v2/funding/tenders", {})
    assert "ORDER BY tenders.publication_date DESC NULLS LAST, tenders.id DESC" in sql[1]          # unchanged default
    for bad in ({"status": "awarded"}, {"order": "title"}):
        assert _orm_get("/api/v2/funding/tenders", bad)[0].status_code == 400, bad


def test_the_funded_projects_list_takes_programme_country_the_windows_and_the_orders():
    r, sql = _orm_get("/api/v2/funding/ft-funded-projects", {"programme": "LIFE", "country": "GR", "created_from": "2026-10-01",
                                                               "published_from": "2025-01-01", "order": "recent"})
    assert r.status_code == 200, r.text
    count_sql, page_sql = sql
    assert "ft_funded_projects.framework_programme ILIKE" in count_sql
    assert "ft_funded_projects.coordinator_country IN" in count_sql
    assert "ft_funded_projects.scraped_at >= " in count_sql
    # The publication window reads the document date the item shows: the publication date, else a past start.
    assert "CASE WHEN (CURRENT_DATE >= date(ft_funded_projects.published_at))" in count_sql
    assert "ORDER BY CASE WHEN (CURRENT_DATE >= date(ft_funded_projects.published_at))" in page_sql and "DESC NULLS LAST" in page_sql
    r, sql = _orm_get("/api/v2/funding/ft-funded-projects", {})
    assert "ORDER BY ft_funded_projects.start_date DESC NULLS LAST, ft_funded_projects.id ASC" in sql[1]   # unchanged default
    assert _orm_get("/api/v2/funding/ft-funded-projects", {"order": "amount"})[0].status_code == 400


def test_the_calls_for_proposals_take_programme_as_framework_programme():
    r, sql = _orm_get("/api/v2/funding/ft-calls-for-proposals", {"programme": "HORIZON"})
    assert r.status_code == 200, r.text
    assert "ft_calls_for_proposals.framework_programme" in sql[0]


def test_the_funding_opportunities_take_the_windows_and_the_orders():
    r, sql = _orm_get("/api/v2/funding/funding-opportunities", {"created_from": "2026-10-01", "published_from": "2026-01-01",
                                                                  "until": "2026-06-30", "order": "recent"})
    assert r.status_code == 200, r.text
    count_sql, page_sql = sql
    assert "ft_calls_for_proposals.first_seen_at >= " in count_sql
    assert "ft_calls_for_proposals.published_at >= " in count_sql and "ft_calls_for_proposals.published_at <= " in count_sql
    assert "ORDER BY ft_calls_for_proposals.published_at DESC NULLS LAST, ft_calls_for_proposals.id DESC" in page_sql
    r, sql = _orm_get("/api/v2/funding/funding-opportunities", {"order": "created_asc"})
    assert "ORDER BY ft_calls_for_proposals.first_seen_at ASC, ft_calls_for_proposals.id ASC" in sql[1]
    r, sql = _orm_get("/api/v2/funding/funding-opportunities", {})
    assert "ORDER BY ft_calls_for_proposals.deadline DESC NULLS LAST, ft_calls_for_proposals.id DESC" in sql[1]   # unchanged default
    assert _orm_get("/api/v2/funding/funding-opportunities", {"order": "amount"})[0].status_code == 400


def test_the_tender_awards_take_country_and_the_amount_range():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/tender-awards", params={"country": "lu", "min_amount_eur": 1000, "max_amount_eur": 50000})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "n.buyer_country = :bc" in sql and params["bc"] == "LU"
    assert "n.awarded_value >= :min_eur" in sql and "n.awarded_value <= :max_eur" in sql and params["max_eur"] == 50000


def test_the_partner_announcements_take_the_published_window():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/partner-announcements", params={"published_from": "2026-09-01", "published_to": "2026-09-30"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "s.requested_date >= :start" in sql and str(params["start"]) == "2026-09-01" and str(params["end"]) == "2026-09-30"


def test_the_startup_and_entrepreneur_lists_take_the_publication_window_and_the_orders():
    r, sql = _orm_get("/api/v2/funding/startups", {"programme": "HORIZON", "published_from": "2026-01-01", "order": "recent"})
    assert r.status_code == 200, r.text
    assert "ft_calls_for_proposals.framework_programme ILIKE" in sql[0] and "ft_calls_for_proposals.published_at >= " in sql[0]
    assert "ORDER BY ft_calls_for_proposals.published_at DESC NULLS LAST" in sql[1]
    assert "ORDER BY ft_calls_for_proposals.deadline DESC NULLS LAST" in _orm_get("/api/v2/funding/startups", {})[1][1]
    r, sql = _orm_get("/api/v2/funding/entrepreneur-instruments", {"deadline_from": "2026-11-01", "deadline_to": "2026-12-31",
                                                                     "until": "2026-06-30", "order": "oldest"})
    assert r.status_code == 200, r.text
    assert "ft_calls_for_proposals.deadline >= " in sql[0] and "ft_calls_for_proposals.deadline <= " in sql[0]
    assert "ft_calls_for_proposals.published_at <= " in sql[0]
    assert "ORDER BY ft_calls_for_proposals.published_at ASC NULLS LAST" in sql[1]
    for path in ("/api/v2/funding/startups", "/api/v2/funding/entrepreneur-instruments"):
        assert _orm_get(path, {"order": "amount"})[0].status_code == 400, path


def test_the_fts_lists_take_a_country_code_the_amount_range_and_the_publication_window():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/eu-funding-recipients", params={
        "country": "gr", "min_amount_eur": 10, "max_amount_eur": 500, "published_from": "2025-01-01", "to": "2025-12-31"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "c.country_code = :ctry" in sql and params["ctry"] == "EL"          # a code, never a substring of a name
    assert "c.beneficiary_amount_eur <= :max_amt" in sql and params["max_amt"] == 500
    assert "coalesce(e.document_date, e.creation_date) >= :since" in sql and str(params["until"]) == "2025-12-31"
    db = _Db()
    _client(funding, db).get("/api/v2/funding/eu-funding-recipients", params={"country": "Spain"})
    assert "c.country ILIKE :ctry" in db.sql[0][0] and db.sql[0][1]["ctry"] == "%Spain%"
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/international-cooperation", params={
        "country": "UA", "max_amount_eur": 1000000, "published_from": "2025-01-01"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "c.country_code = :ctry" in sql and params["ctry"] == "UA" and "c.beneficiary_amount_eur <= :max_amt" in sql
    assert "coalesce(e.document_date, e.creation_date) >= :published_from" in sql


def test_partners_take_max_amount_and_all_takes_the_publication_window():
    from api.v2.funding import router as funding
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/partners", params={"q": "battery", "max_amount_eur": 250000})
    assert r.status_code == 200, r.text
    assert any("sum(amount_eur) IS NOT NULL) AND " in sql and "<= :max_amt" in sql and params.get("max_amt") == 250000
               for sql, params in db.sql)         # an organisation with no known amount is not "at most"
    db = _Db()
    r = _client(funding, db).get("/api/v2/funding/all", params={"published_from": "2026-10-01", "published_to": "2026-10-28"})
    assert r.status_code == 200, r.text
    sql, params = db.sql[0]
    assert "document_date >= :since" in sql and str(params["since"]) == "2026-10-01" and str(params["until"]) == "2026-10-28"


# --- step 3: the shared fields ------------------------------------------------------------------------ #
SHARED = ("item_type", "title", "summary", "status", "body_code", "body_name", "amount_eur")


def _item_properties(spec, op):
    comps = spec["components"]["schemas"]
    name = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    data = comps[name].get("properties", {}).get("data")
    if data:
        name = data["items"]["$ref"].split("/")[-1]
    return comps[name]["properties"]


def test_every_funding_list_and_item_route_declares_the_seven_shared_fields():
    from api.v2.funding import router
    spec = _spec(router)
    routes = {p: m["get"] for p, m in spec["paths"].items() if p.startswith(FUNDING) and "get" in m and "/documents" not in p}
    assert len(routes) >= 130, len(routes)          # 66 lists and 64 item routes on 28 Oct 2026
    missing = {p: [f for f in SHARED if f not in _item_properties(spec, op)] for p, op in routes.items()}
    assert {p: m for p, m in missing.items() if m} == {}
    from api.v2.funding._standard import SHARED_FIELDS_DOC
    lists = [p for p in routes if not p.endswith("}")]
    assert len(lists) >= 66 and [p for p in lists if SHARED_FIELDS_DOC not in routes[p].get("description", "")] == []


def test_the_summary_is_the_items_own_text_cut_at_a_word_end_and_amounts_are_euros_only():
    from services.funding.shared_fields import cut_summary, eur
    assert cut_summary(None) is None and cut_summary("  \n ") is None
    assert cut_summary("Expected  Outcome:\n\nshort") == "Expected Outcome: short"
    assert cut_summary("<p>Baulos 1.1<br />Hauptbaulos &amp; R&D</p>") == "Baulos 1.1 Hauptbaulos & R&D"
    s = cut_summary("abcdefg " * 50)                 # 400 characters: character 300 falls inside a word
    assert len(s) <= 301 and s.endswith("…") and s[:-1].split(" ")[-1] == "abcdefg"
    assert eur(100, "EUR") == 100.0 and eur(100, " eur ") == 100.0
    assert eur(100, None) is None and eur(100, "GBP") is None and eur(None, "EUR") is None


def _fresh_body_names():
    import services.funding.shared_fields as sf
    sf._BODY_NAMES.clear()
    sf._BODY_NAMES_READ_AT = None
    return sf


def test_body_names_read_the_directory_once_and_the_funds_from_their_own_list():
    from types import SimpleNamespace
    sf = _fresh_body_names()
    db = _Db([SimpleNamespace(code="ema", name="European Medicines Agency")])
    assert sf.body_names(db, ["ema", "erdf", None]) == {"ema": "European Medicines Agency",
                                                        "erdf": "European Regional Development Fund"}
    assert sf.body_names(db, ["ema"]) == {"ema": "European Medicines Agency"}
    assert sf.body_names(db, ["nobody"]) == {"nobody": None}           # not read again within 15 minutes
    assert len(db.sql) == 1 and "FROM economy_bodies" in db.sql[0][0]


def test_an_agency_list_names_its_body_and_states_no_amount():
    from datetime import datetime
    from types import SimpleNamespace
    from api.v2.funding import router as funding
    _fresh_body_names()
    row = SimpleNamespace(id=7, body_code="ecdc", item_type="tender", title="T", summary="S", source_kind="html",
                          public_url="https://x.eu/7", body_txt="b", body_html="<p>b</p>", document_date=None,
                          creation_date=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2),
                          tender_reference="ECDC/2026/OP/0012", status="open", deadline=None,
                          code="ecdc", name="European Centre for Disease Prevention and Control")
    r = _client(funding, _Db([row])).get("/api/v2/funding/ecdc-tenders")
    assert r.status_code == 200, r.text
    it = r.json()["data"][0]
    assert {f: it[f] for f in SHARED} == {"item_type": "tender", "title": "T", "summary": "S", "status": "open",
                                          "body_code": "ecdc", "amount_eur": None,
                                          "body_name": "European Centre for Disease Prevention and Control"}


def test_the_cohesion_rows_carry_the_compositions_all_serves():
    from api.v2.funding import funding_all
    from api.v2.funding.cohesion_cap import SHARED_SQL as payment
    from api.v2.funding.cohesion_eusf import SHARED_SQL as solidarity
    from api.v2.funding.cohesion_finances import SHARED_SQL as allocation
    cte = funding_all._union_cte(False)
    assert allocation in cte and solidarity in cte and payment in cte
    assert "—" not in cte and "coalesce(round(" not in cte      # no em-dash; an unknown total is not "EUR 0"
    assert "round(eusf_grant_paid_meur * 1000000) AS amount_eur" in solidarity


def test_an_outcome_names_its_indicator_and_its_fund_as_the_finances_list_does():
    from api.v2.funding.cohesion_outcomes import _row_to_item
    row = dict(id=1, public_url=None, document_date=None, creation_date=None, updated_date=None, ms="FR", ms_name="France",
               cci=None, programme_short_title="France - ESF+", policy_objective_name="Social Europe",
               specific_objective_name=None, category_of_region=None, indicator_type_output_result=None, ind_code="EECO01",
               indicator_short_name="Participants", indicator_long_name="Number of participants", measurement_unit="persons",
               baseline_value=None, milestone_value_2024=None, target_value_2029=1200000.0, decided_value=None,
               implemented_value=None, body_txt=None, body_html=None, fund="ESF+")
    it = _row_to_item(row, with_body=False)
    assert (it.item_type, it.body_code, it.body_name) == ("cohesion_indicator", "esf", "European Social Fund Plus")
    assert it.title == "Number of participants (France - ESF+)"
    assert it.summary == "EECO01 · FR · Social Europe · target 2029: 1200000 persons"
    assert it.status is None and it.amount_eur is None
    assert _row_to_item({**row, "fund": "Interreg Funds"}, with_body=False).body_code == "interreg"


def test_the_ft_portal_items_summarise_their_own_text_and_keep_other_currencies_out_of_amount_eur():
    from types import SimpleNamespace
    from api.v1.funding_tenders_collections import _tender_to_item
    from api.v2.funding.ft_cascade_calls import _item
    base = dict(id=1, tender_reference="R", contracting_authority="eu-LISA", title="T", description="Lot 1:  hosting\nservices",
                contract_type="services", status="open", estimated_value=5.0, deadline=None, source_url="https://x.eu",
                documents_url=None, cpv_codes=[], published_at=None, content_updated_at=None, last_updated=None,
                first_seen_at=None)
    it = _tender_to_item(SimpleNamespace(**base, value_currency="EUR"))
    assert (it.item_type, it.summary, it.body_code, it.amount_eur) == ("tender", "Lot 1: hosting services", "ftportal", 5.0)
    assert _tender_to_item(SimpleNamespace(**base, value_currency="GBP")).amount_eur is None
    call = _item(dict(id=2, call_id="16842", title="C", summary_src="Task description\nWe fund  pilots.",
                      indicative_budget=60000.0, budget_currency="EUR", body_txt="x", body_html="x"), with_body=False)
    assert (call.summary, call.amount_eur, call.body_code) == ("We fund pilots.", 60000.0, "ftportal")


def test_a_partner_summary_keeps_its_counts_after_its_country():
    from types import SimpleNamespace
    from api.v2.funding.partners import _item
    r = SimpleNamespace(key="pic:1", name="CNRS", short_name=None, pic="1", vat=None, country="FR", city=None,
                        activity_type=None, is_sme=None, projects=3, coordinated=1, payments=2, contracts=0, awards=0,
                        announcements=0, eu_contribution=None, amount_eur=None, matches=[], last_day=None, created=None,
                        changed=None)
    it = _item(r, "https://x")
    assert (it.item_type, it.title) == ("organisation", "CNRS")
    assert it.summary == "FR · 3 projects (1 coordinated) · 2 payments (0 contracts)"


# --- step 4: one name per concept, the older names kept beside --------------------------------------- #
# Each list's legacy names (28 Oct 2026). A name dropped, or a legacy mark lost, fails here.
LEGACY = {
    "tenders": {"official_name", "submission_deadline", "publication_date", "ted_url", "updated_at", "last_synced_at"},
    "ft-calls-for-tenders": {"contract_type", "value_currency", "source_url", "published_at", "last_updated"},
    "ft-calls-for-proposals": {"source_url", "published_at", "last_updated"},
    "startups": {"source_url", "published_at", "last_updated"},
    "entrepreneur-instruments": {"source_url", "published_at", "last_updated"},
    "ft-funded-projects": {"source_url", "published_at", "last_updated"},
    "funding-opportunities": {"programme", "short_summary", "source_url", "published_at", "last_updated"},
    "eu-funding-recipients": {"project_start", "project_end"},
    "international-cooperation": {"project_start", "project_end"},
    "partners": {"vat"},
    "justice": {"tender_reference"}, "innovation-fund": {"tender_reference"}, "cedefop-grants": {"tender_reference"},
}


def test_every_legacy_name_points_at_a_standard_field_the_same_item_carries():
    import re
    from api.v2.funding import router
    spec = _spec(router)
    routes = {p: m["get"] for p, m in spec["paths"].items() if p.startswith(FUNDING) and "get" in m and "/documents" not in p}
    seen = {}
    for path, op in routes.items():
        props = _item_properties(spec, op)
        old = {k for k, v in props.items() if v.get("deprecated")}
        for k in old:
            standard = re.findall(r"`(\w+)`", props[k].get("description", "").split("read ", 1)[-1])
            assert standard and all(s in props and not props[s].get("deprecated") for s in standard), (path, k, standard)
        if not path.endswith("}"):
            seen[path[len(FUNDING):]] = old
    assert {p: o for p, o in seen.items() if o} == LEGACY


def _ted_row(**kw):
    from types import SimpleNamespace
    from models.tender import Tender
    row = {c.name: None for c in Tender.__table__.columns}
    row.update(id=5, publication_number="620225-2026", title="T", has_lots=False, cpv_codes=[], **kw)
    return SimpleNamespace(**row)


class _RowsQuery(_CapturingQuery):
    ROWS = []

    def count(self):
        return len(self.ROWS)

    def all(self):
        return list(self.ROWS)

    def first(self):
        return self.ROWS[0] if self.ROWS else None


class _RowsDb(_Db):
    def query(self, *entities):
        return _RowsQuery(list(entities))


def test_a_ted_notice_carries_the_standard_names_on_the_list_and_the_item_route():
    from datetime import datetime
    from api.v2.funding import router as funding
    _RowsQuery.ROWS = [_ted_row(official_name="Agence X", submission_deadline=datetime(2026, 12, 1, 12),
                                publication_date=datetime(2026, 10, 1), ted_url="https://ted.europa.eu/x",
                                documents_url="https://ec.europa.eu/info/funding-tenders/x", estimated_value_currency="EUR")]
    client = _client(funding, _RowsDb())
    for path in ("/api/v2/funding/tenders", "/api/v2/funding/tenders/5"):
        r = client.get(path)
        assert r.status_code == 200, (path, r.text)
        it = r.json()["data"][0] if path.endswith("tenders") else r.json()
        assert (it["contracting_authority"], it["official_name"]) == ("Agence X", "Agence X"), path
        assert it["deadline"] == it["submission_deadline"] == "2026-12-01T12:00:00", path
        assert it["documents_url"] == "https://ec.europa.eu/info/funding-tenders/x", path


def test_the_ft_portal_tenders_name_the_contract_nature_as_ted_and_match_it_in_any_case():
    from types import SimpleNamespace
    from api.v1.funding_tenders_collections import _tender_to_item
    base = dict(id=1, tender_reference="R", contracting_authority="eu-LISA", title="T", description=None, status="open",
                estimated_value=5.0, deadline=None, source_url="https://x.eu", documents_url=None, cpv_codes=[],
                published_at=None, content_updated_at=None, last_updated=None, first_seen_at=None)
    it = _tender_to_item(SimpleNamespace(**base, contract_type="Services", value_currency="GBP"))
    assert (it.contract_nature, it.contract_type) == ("services", "Services")
    assert (it.estimated_value_currency, it.value_currency) == ("GBP", "GBP")
    assert _tender_to_item(SimpleNamespace(**base, contract_type=None, value_currency=None)).contract_nature is None
    # O93: the portal writes Services; an exact match on the lower-cased word found 14 of 1,473.
    for params in ({"contract_nature": "Services"}, {"contract_type": "services"}):
        r, sql = _orm_get("/api/v2/funding/ft-calls-for-tenders", params)
        assert r.status_code == 200, r.text
        assert "lower(ft_calls_for_tenders.contract_type) = " in sql[0], params


def test_the_ft_call_lists_order_by_recent_and_oldest_beside_their_legacy_names():
    for path, table in (("/api/v2/funding/ft-calls-for-proposals", "ft_calls_for_proposals"),
                        ("/api/v2/funding/ft-calls-for-tenders", "ft_calls_for_tenders")):
        for order, expected in (("recent", "published_at DESC NULLS LAST"), ("published_desc", "published_at DESC NULLS LAST"),
                                ("oldest", "published_at ASC NULLS LAST"), (None, "deadline DESC NULLS LAST")):
            r, sql = _orm_get(path, {"order": order} if order else {})
            assert r.status_code == 200, (path, order, r.text)
            assert f"ORDER BY {table}.{expected}" in sql[1], (path, order)


def test_the_other_lists_carry_the_standard_names_with_the_same_values():
    from datetime import date
    from types import SimpleNamespace
    from api.v1.infringements_funding import FundingItem
    from api.v2.funding import router as funding
    from api.v2.funding._fts import FtsItem
    from api.v2.funding.partners import _item
    fts = FtsItem(id=1, title="B", project_start=date(2025, 1, 1), project_end=date(2027, 12, 31))
    assert (fts.start_date, fts.end_date) == (date(2025, 1, 1), date(2027, 12, 31))
    call = FundingItem(id="x", topic_id="T", title="t", source_url="https://x.eu", programme="Horizon Europe (HORIZON)")
    assert call.framework_programme == "Horizon Europe (HORIZON)"
    r = SimpleNamespace(key="vat:BE0123", name="X", short_name=None, pic=None, vat="BE0123", country="BE", city=None,
                        activity_type=None, is_sme=None, projects=0, coordinated=0, payments=1, contracts=0, awards=0,
                        announcements=0, eu_contribution=None, amount_eur=None, matches=[], last_day=None, created=None,
                        changed=None)
    assert (_item(r, "https://x").vat_number, _item(r, "https://x").vat) == ("BE0123", "BE0123")
    _fresh_body_names()
    items = _client(funding, _Db()).get("/api/v2/funding/programmes", params={"limit": 200}).json()["data"]
    assert len(items) > 50 and all(i["id"] == i["acronym"] for i in items)


def test_a_grant_list_names_its_reference_as_the_calls_do():
    from datetime import datetime
    from types import SimpleNamespace
    from api.v2.funding import router as funding
    for path, body, ref, name in (("justice", "just", "JUST-2027-JTRA", "topic_id"),
                                  ("innovation-fund", "innovfund", "INNOVFUND-2025-NZT-PILOTS", "topic_id"),
                                  ("cedefop-grants", "cedefop", "GP/DVQ/ReferNet_FPA/001/26", "call_id")):
        _fresh_body_names()
        row = SimpleNamespace(id=7, body_code=body, item_type="grant", title="T", summary="S", source_kind="api",
                              public_url="https://x.eu/7", body_txt="b", body_html="<p>b</p>", document_date=None,
                              creation_date=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2),
                              tender_reference=ref, status="open", deadline=None, code=body, name="N")
        client = _client(funding, _Db([row]))
        for it in (client.get(f"/api/v2/funding/{path}").json()["data"][0], client.get(f"/api/v2/funding/{path}/7").json()):
            other = {"topic_id": "call_id", "call_id": "topic_id"}[name]
            assert (it[name], it["tender_reference"], it[other]) == (ref, ref, None), path
    # A tender list keeps tender_reference as its own name.
    spec = _spec(funding)
    assert "topic_id" not in _item_properties(spec, spec["paths"]["/api/v2/funding/ecdc-tenders"]["get"])


def test_all_filters_item_type_beside_its_legacy_name_type():
    from api.v2.funding import router as funding
    for params in ({"item_type": "cap_payment"}, {"type": "cap_payment"}):
        db = _Db()
        r = _client(funding, db).get("/api/v2/funding/all", params=params)
        assert r.status_code == 200, r.text
        assert any("item_type = :it" in sql and p.get("it") == "cap_payment" for sql, p in db.sql), params
    assert _client(funding, _Db()).get("/api/v2/funding/all", params={"item_type": "x"}).status_code == 400
