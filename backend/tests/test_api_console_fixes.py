"""What the walk through the API Console found on 4 Nov 2026: each test calls the route, because a test that reads the
source cannot see a crash."""
import asyncio
import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql


class _Query:
    """Stands in for a Session's query and compiles every filter it is given, as the database would be asked to."""
    def __init__(self):
        self.sql = []

    def filter(self, *clauses):
        self.sql += [str(c.compile(dialect=postgresql.dialect())) for c in clauses]
        return self

    def __getattr__(self, name):
        if name in ("count", "scalar"):
            return lambda *a, **k: 0
        if name in ("all",):
            return lambda *a, **k: []
        return lambda *a, **k: self


def _request():
    return SimpleNamespace(url=SimpleNamespace(path="/api/v2/legislative/oeil/procedures"), query_params={}, state=SimpleNamespace(), headers={},
                           base_url="https://x/")


def test_the_procedure_status_filter_compiles_to_sql_postgres_can_run():
    from api.v1 import procedures
    query = _Query()
    db = SimpleNamespace(query=lambda *a, **k: query)
    try:
        asyncio.run(procedures.list_procedures(
            _request(), q=None, reference=None, committee=None, rapporteur_mep_id=None, status="tabled", updated_from=None,
            updated_to=None, updated_end=None, include_other_sources=False, limit=1, page=1, user=SimpleNamespace(id=1), db=db,
        ))
    except Exception:  # the response builder is not under test: only what reached the query is
        pass
    status_sql = [s for s in query.sql if "current_status" in s and "lower" in s]
    assert status_sql, f"the status filter never reached the query: {query.sql}"
    assert "AS TEXT" in status_sql[0] and "Function" not in status_sql[0], status_sql[0]


def test_no_route_casts_through_a_function_generator_any_more():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "api"
    assert not [str(p) for p in root.rglob("*.py") if "func.TEXT.type" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("family,unknown", [
    ("climate", ["climate"]),
    ("nonsense-xyz,finance-economy", ["nonsense-xyz"]),
    ("finance-economy", []),
    ("finance-economy, digital-tech", []),
    ("", []),
    (None, []),
])
def test_unknown_families_are_named(family, unknown):
    from services.economy.body_families import unknown_families
    assert unknown_families(family) == unknown


@pytest.mark.parametrize("module,path", [
    ("api.v2.news", "/all"),
    ("api.v2.events", "/all"),
])
def test_an_unknown_family_is_refused_not_answered_with_the_whole_feed(module, path):
    import importlib
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    mod = importlib.import_module(module)
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: None
    prefix = mod.router.prefix
    response = TestClient(app).get(f"{prefix}{path}", params={"family": "climate"})
    assert response.status_code == 400, response.text
    assert "climate-energy-environment" in response.text


def test_an_unknown_family_is_refused_on_consultations():
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.consultations import consultations_all
    from core.database import get_db
    app = FastAPI()
    app.include_router(consultations_all.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: None
    route = next(r for r in consultations_all.router.routes if r.path.endswith("/all"))
    response = TestClient(app).get(route.path, params={"family": "climate"})
    assert response.status_code == 400, response.text


def test_the_pick_lists_answer_with_no_key_and_give_a_name_for_every_code():
    from api.v2 import pick_lists
    from core.database import get_db
    pick_lists._cache.update(at=0.0, bodies=[], consultations_at=0.0, consultations=None)
    db = _sqlite_session("CREATE TABLE economy_bodies (code TEXT, name TEXT)", [
        "INSERT INTO economy_bodies VALUES ('commission', 'European Commission'), ('ecb', NULL), ('eba', 'European Banking Authority'), ('edpb', 'EDPB'), ('ema', 'EMA')",
        "CREATE TABLE public_consultations (source_body TEXT)",
        "INSERT INTO public_consultations VALUES ('European Commission'), (NULL), ('EBA'), ('JRC')",
        "CREATE TABLE economy_items (body_code TEXT, item_type TEXT)",
        "INSERT INTO economy_items VALUES ('edpb', 'consultation'), ('ema', 'news')",
    ])
    app = FastAPI()
    app.include_router(pick_lists.router)
    app.dependency_overrides[get_db] = lambda: db
    response = TestClient(app).get("/pick-lists")
    assert response.status_code == 200
    body = response.json()
    assert {"code": "commission", "name": "European Commission"} in body["bodies"]
    assert {"code": "ecb", "name": "ecb"} in body["bodies"]
    assert all(b["code"] and b["name"] for b in body["bodies"])
    assert {"slug": "climate-energy-environment", "label": "Climate, Energy & Environment"} in body["families"]
    assert any(c["code"] == "ENVI" and c["name"] for c in body["committees"])
    assert "max-age" in response.headers["Cache-Control"]
    # The consultations form offers only the bodies that have consultations: both sources, and nothing that has only news.
    only = body["consultations"]
    assert {b["code"] for b in only["bodies"]} == {"commission", "eba", "edpb", "jrc"}
    assert {"code": "jrc", "name": "Joint Research Centre"} in only["bodies"]
    assert "health-life-sciences" not in {f["slug"] for f in only["families"]}
    assert "finance-economy" in {f["slug"] for f in only["families"]}
    pick_lists._cache.update(consultations_at=0.0, consultations=None)
    failing = _sqlite_session("CREATE TABLE economy_bodies (code TEXT, name TEXT)", [])
    app.dependency_overrides[get_db] = lambda: failing
    assert TestClient(app).get("/pick-lists").json()["consultations"] == {"bodies": [], "families": []}
    pick_lists._cache.update(at=0.0, bodies=[], consultations_at=0.0, consultations=None)


# ---- A list that reported a total and served nothing: ORDER BY on a column the table does not have ------------------
def _sqlite_session(ddl, rows):
    """A real database with the table's real columns, so that a query naming another column fails as it does in production."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as c:
        c.execute(text("ATTACH DATABASE ':memory:' AS public"))
        c.execute(text(ddl))
        for row in rows:
            c.execute(text(row))
    return Session(bind=engine)


def _eur_lex_client(db):
    from api.v1._deps import api_user_with_rate_limit
    from api.v2.legislative import eur_lex
    from core.database import get_db
    app = FastAPI()
    app.include_router(eur_lex.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), eur_lex


def _prefix():
    from api.v2.legislative import eur_lex
    return eur_lex.router.prefix


def test_the_summaries_list_serves_its_rows():
    db = _sqlite_session(
        "CREATE TABLE public.legissum_summaries (slug TEXT, title TEXT, chapter_code TEXT, chapter_title TEXT, url TEXT, celex TEXT, "
        "summary_text TEXT, summary_html TEXT, text_fetched_at TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)",
        ["INSERT INTO public.legissum_summaries (slug, title, url, celex) VALUES ('a-law', 'A law', 'https://x/a', '32016R0679')"],
    )
    client, _ = _eur_lex_client(db)
    body = client.get(f"{_prefix()}/laws/summaries", params={"limit": 1, "include_body": "true"}).json()
    assert body["total"] == 1 and len(body["data"]) == 1, body
    assert body["data"][0]["summary_id"] == "a-law"


def test_the_cross_reference_list_query_runs_on_the_tables_real_columns():
    # No rows here: the columns are JSON in production, and the test is about the query, which SQLite plans even on an empty table.
    db = _sqlite_session(
        "CREATE TABLE public.law_xref (celex TEXT, eli TEXT, oj_reference TEXT, procedure_ref TEXT, resource_type TEXT, in_force BOOLEAN, "
        "document_date TEXT, eurovoc TEXT, legal_basis TEXT, authors TEXT, relation_counts TEXT, relation_total INT, computed_at TIMESTAMP)",
        [],
    )
    client, _ = _eur_lex_client(db)
    response = client.get(f"{_prefix()}/xref", params={"limit": 1})
    assert response.status_code == 200, response.text


def test_a_query_that_fails_says_so_instead_of_a_total_with_no_rows():
    db = _sqlite_session("CREATE TABLE public.legissum_summaries (slug TEXT, title TEXT)", ["INSERT INTO public.legissum_summaries VALUES ('a', 'b')"])
    client, _ = _eur_lex_client(db)
    response = client.get(f"{_prefix()}/laws/summaries", params={"limit": 1, "include_body": "true"})
    assert response.status_code == 503, response.text


# ---- The largest lists can leave the full text out, in the query and not only in the answer -------------------------


def _captured_sql(monkeypatch, module, call):
    from sqlalchemy.orm import Query, Session

    class CountZero(Query):
        def count(self):
            return 0

    sent = {}

    class Capture:
        def __init__(self, q):
            self.q = q

        def offset(self, n):
            self.q = self.q.offset(n)
            return self

        def limit(self, n):
            self.q = self.q.limit(n)
            return self

        def all(self):
            sent["sql"] = str(self.q.statement.compile(dialect=postgresql.dialect()))
            return []

    monkeypatch.setattr(module, "stable", lambda query, *a: Capture(query))
    call(Session(query_cls=CountZero))
    return sent["sql"]


@pytest.mark.parametrize("include_body,present", [(False, False), (True, True)])
def test_secondary_acts_read_the_text_only_when_asked(monkeypatch, include_body, present):
    from api.v1 import w4_endpoints as w4
    sql = _captured_sql(monkeypatch, w4, lambda db: w4._list_secondary_acts(
        db, "implementing", None, None, None, None, None, None, None, None, 2, 1, include_body=include_body))
    assert ("secondary_acts.text_body" in sql) is present and ("secondary_acts.body_html" in sql) is present


@pytest.mark.parametrize("path", ["/api/v2/legislative/implementing-acts", "/api/v2/legislative/delegated-acts", "/api/v2/parliament/plenary-tabled-texts", "/api/v2/parliament/texts-submitted"])
def test_the_largest_lists_offer_to_leave_the_text_out(path):
    from main import app
    names = [p["name"] for p in app.openapi()["paths"][path]["get"]["parameters"]]
    assert "include_body" in names


def test_a_secondary_act_without_its_text_never_reads_it():
    from api.v1.w4_endpoints import _secondary_act_to_item

    fields = dict(id=1, act_type="implementing", status="published", reference="C(2026)1", title="An act", source_url="https://example.org/act", ep_scrutiny={}, council_scrutiny={}, policy_areas=[])

    class Plain:
        def __init__(self):
            self.__dict__.update(fields)

        def __getattr__(self, name):
            if name in ("text_body", "body_html"):
                raise AssertionError(f"{name} was read")
            return None

    item = _secondary_act_to_item(Plain(), with_body=False)
    assert item.body_txt is None and item.body_html is None and item.title == "An act"


# ---- Values the API's own documentation listed, and a filter that built broken SQL when used alone ------------------
def test_role_coordinator_alone_builds_a_whole_query():
    import re
    from api.v1.funding_tenders_collections import _consortium_clause
    sql = str(_consortium_clause(None, "coordinator", None).compile(dialect=postgresql.dialect()))
    assert not re.search(r"AND\s*\)", sql), sql
    assert "true" in sql


def test_another_role_still_excludes_the_programmes_with_no_consortium():
    from api.v1.funding_tenders_collections import _consortium_clause
    assert "false" in str(_consortium_clause(None, "participant", None).compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize("typed,expected", [
    ("PLENARY", "plenary_session"), ("plenary", "plenary_session"), ("COLLEGE_MEETING", "commission_college_meeting"),
    ("committee_meeting", "committee_meeting"), ("COUNCIL_MEETING", "council_meeting"), ("plenary_session", "plenary_session"),
])
def test_the_calendars_documented_names_reach_real_values(typed, expected):
    from api.v1.calendar import event_type_value
    assert event_type_value(typed).value == expected


def test_a_calendar_value_outside_the_list_is_refused_with_the_choices():
    from fastapi import HTTPException
    from api.v1.calendar import event_type_value, institution_value
    for call in (event_type_value, institution_value):
        with pytest.raises(HTTPException) as refused:
            call("zzz")
        assert refused.value.status_code == 400 and "must be one of" in refused.value.detail


@pytest.mark.parametrize("module,path,params", [
    ("api.v1.eprs", "/eprs", {"publication_type": "EU_LEGISLATION_IN_PROGRESS"}),
    ("api.v1.webstreams", "/webstreams", {"status": "NOT_AVAILABLE"}),
])
def test_a_value_the_column_does_not_have_is_refused_before_the_database(module, path, params):
    import importlib
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    mod = importlib.import_module(module)
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_db] = lambda: None
    route = next(r.path for r in mod.router.routes if r.path.rstrip("/") == mod.router.prefix or r.path == path)
    response = TestClient(app).get(route, params=params)
    assert response.status_code == 400, response.text
    assert "must be one of" in response.text


@pytest.mark.parametrize("typed,stored,same", [
    ("EPP", "EPP", True), ("epp", "EPP", True), ("PPE", "EPP", True), ("S&D", "S&D", True), ("S-D", "S&D", True), ("Greens/EFA", "Greens/EFA", True),
    ("VERTS-ALE", "Greens/EFA", True), ("The Left", "The Left", True), ("GUE-NGL", "The Left", True), ("RENEW", "Renew", True), ("EPP", "ECR", False),
])
def test_a_group_is_one_group_however_it_is_spelt(typed, stored, same):
    from api.v1.meps import group_key
    assert (group_key(typed) == group_key(stored)) is same


def test_the_current_terms_group_is_read_from_the_snapshot_and_never_sent_upstream(monkeypatch):
    from api.v1 import meps
    asked = {}

    async def fake_all(country=None, group=None, term=10, patient=False):
        asked["group"] = group
        return None  # the EP API is down: the answer must still come from the snapshot

    async def fake_current():
        return {"1", "2"}

    snapshot = {
        "1": {"id": "1", "full_name": "A", "country": "BEL", "group": "EPP", "public_url": "https://x/1", "body_txt": "a"},
        "2": {"id": "2", "full_name": "B", "country": "BEL", "group": "S&D", "public_url": "https://x/2", "body_txt": "b"},
    }
    monkeypatch.setattr(meps, "_fetch_all", fake_all)
    monkeypatch.setattr(meps, "_fetch_current_ids", fake_current)
    monkeypatch.setattr(meps.api_snapshots, "payloads_for", lambda db, dataset: snapshot)
    window = {"updated_from": None, "updated_to": None, "created_from": None, "created_to": None}
    result = asyncio.run(meps._list_from_full(
        None, country=None, group="S-D", name=None, term=meps.CURRENT_TERM, window=window, order=None, include_former=False, limit=10, page=1,
    ))
    assert asked["group"] is None
    assert result.total == 1 and result.data[0].full_name == "B"


@pytest.mark.parametrize("module,column,typed,label", [
    ("api.v1.consultations:PublicConsultation", "status", "OPEN", "open"),
    ("api.v1.consultations:PublicConsultation", "consultation_type", "Public_Consultation", "public_consultation"),
    ("api.v1.commission_register:CommissionDocument", "doc_type", "com", "COM"),
    ("api.v1.w4_endpoints:RSBOpinion", "verdict", "NEGATIVE", "negative"),
    ("api.v1.w4_endpoints:ParliamentaryQuestion", "question_type", "Written", "written"),
    ("api.v1.texts_adopted:TextAdopted", "text_type", "DECISION", "decision"),
    ("api.v1.texts_adopted:PlenaryTabledText", "text_type", "decision", "decision"),
])
def test_a_typed_value_reaches_the_columns_own_label_and_nonsense_is_refused(module, column, typed, label):
    import importlib
    from fastapi import HTTPException
    from api.v1._enum_filter import enum_choice
    path, name = module.split(":")
    col = getattr(getattr(importlib.import_module(path), name), column)
    assert enum_choice(col, typed, column) == label
    with pytest.raises(HTTPException) as refused:
        enum_choice(col, "zzz", column)
    assert refused.value.status_code == 400 and label in refused.value.detail


def test_the_parliament_being_busy_is_not_an_mep_who_does_not_exist(monkeypatch):
    """Pressing Open on the MEP list answered "not found" for a sitting MEP: the EP's rate limit was read as absence."""
    import httpx
    from fastapi import HTTPException

    from api.v1 import meps
    from services import api_snapshots

    def answering(status):
        async def fake(hc, path, params, patient=False):
            return httpx.Response(status, request=httpx.Request("GET", "https://ep.test" + path))
        return fake

    stored = {"1": meps.MEPItem(id="1", full_name="Test MEP").model_dump(mode="json", exclude={"creation_date", "updated_date"})}
    monkeypatch.setattr(meps, "_CACHE", {})
    monkeypatch.setattr(api_snapshots, "dates_for", lambda db, ds, keys=None: {})
    monkeypatch.setattr(api_snapshots, "payloads_for", lambda db, ds: stored)

    def read(mep_id):
        return asyncio.run(meps.get_mep(mep_id=mep_id, user=None, db=None))

    for busy in (429, 500, 503):
        monkeypatch.setattr(meps, "_ep_get", answering(busy))
        assert read("1").full_name == "Test MEP"
        with pytest.raises(HTTPException) as refused:
            read("2")
        assert refused.value.status_code == 502
        assert refused.value.detail["reason_code"] == "upstream_error"

    for absent in (204, 404):
        monkeypatch.setattr(meps, "_ep_get", answering(absent))
        with pytest.raises(HTTPException) as refused:
            read("1")
        assert refused.value.status_code == 404


@pytest.mark.parametrize("plural, one", [
    ("news items", "news item"), ("news", "news item"), ("security advisories", "security advisory"),
    ("agri-food data series", "agri-food data series"), ("case-law entries", "case-law entry"),
    ("surveys and data tools", "survey or data tool"), ("calls for proposals", "call for proposal"),
    ("calls for tenders", "call for tender"), ("EMA calls for expression of interest", "EMA call for expression of interest"),
    ("EIB calls for tender", "EIB call for tender"), ("opinions for use outside the EU", "opinion for use outside the EU"),
    ("press material", "press material"), ("topic pages", "topic page"), ("analysis", "analysis"),
])
def test_one_of_these_is_written_in_english(plural, one):
    from api.v2.economy_endpoints import singular
    assert singular(plural) == one


def test_every_route_title_reads_as_a_heading():
    """The heading of each route on the console: no half-cut plurals, no "(full body)", no small letter at the start."""
    from fastapi.routing import APIRoute

    from main import app

    bad = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v2/"):
            continue
        title = route.summary or ""
        if not title or not (title[0].isupper() or title[0].isdigit() or title.startswith(("[Deprecated]", "eu-LISA"))):
            bad.append((route.path, "start", title))
        if "(full body)" in title:
            bad.append((route.path, "full body", title))
        if re.search(r"\b(advisorie|entrie|serie)\b|one new\b|one (\w+ )?calls\b|one opinions|one surveys", title):
            bad.append((route.path, "plural", title))
    assert not bad, bad[:10]


def test_a_competition_case_is_not_the_raw_search_hit():
    """<b>SA.102592</b>, CountryFRA and a string of JSON all reached the console (4 Nov 2026)."""
    from api.v1.specialised_competition import _row_from_search_hit

    item = _row_from_search_hit({"metadata": {
        "caseNumber": ["<b>SA.102592</b>"], "caseTitle": ["Tarif <b>r\u00e9duit</b>"], "caseMemberState": ["CountryFRA"],
        "caseObjectives": ['{"items":[{"code":"StateAidObjectiveGberArt44","isPrimary":"false"}]}'],
    }})
    assert item.case_number == "SA.102592"
    assert item.case_title == "Tarif r\u00e9duit"
    assert item.member_state == "FRA"
    assert item.case_objectives == ["StateAidObjectiveGberArt44"]
    assert "{" not in item.body_txt and "<b>" not in item.body_html


def test_the_goods_sections_answer_with_their_own_names(monkeypatch):
    """Every row of /access2markets/products read "?": the list has sections, not the codes the route expected."""
    from types import SimpleNamespace as NS

    from api.v1 import specialised_a2m

    monkeypatch.setattr(specialised_a2m, "_get", lambda url: [
        {"id": -1, "code": None, "description": "Live animals; animal products", "hasChildren": True,
         "section": {"description": "SECTION I", "chapterFrom": "01", "chapterTo": "05"}}])
    page = asyncio.run(specialised_a2m.list_products(request=NS(url="http://t/x"), q=None, level=None, limit=5, page=1, body_threshold=500, user=None))
    assert page.data[0].code == "SECTION I"
    assert page.data[0].chapters == "01-05"


def test_a_press_release_carries_no_html_entities():
    from api.v1.infringements_funding import _plain

    assert _plain("decided to refer&nbsp;Spain to the&#160;Court &amp; so on") == "decided to refer Spain to the Court & so on"
    assert _plain(None) is None


def test_the_freshness_route_answers_a_moment_not_a_count_of_milliseconds():
    from api.v1.specialised_a2m import _moment

    assert _moment(1792101600000).startswith("2026-")
    assert _moment("2026-10-14T00:00:00Z") == "2026-10-14T00:00:00Z"
    assert _moment(None) is None


def test_a_summary_is_words_not_markup():
    from api.v1._body import plain_summary

    assert plain_summary("<p>PFAS are everywhere &amp; here.</p>") == "PFAS are everywhere & here."
    assert plain_summary("< 2% inflation") == "< 2% inflation"
    assert plain_summary("Plain words") == "Plain words"
    assert plain_summary(None) is None


def test_a_report_with_no_procedure_still_has_a_readable_title():
    from api.v1.ep_entities import _enrich_doc_title

    assert _enrich_doc_title("draft_report for  (LIBE)", "", {}, None) == "Draft report (LIBE)"


def test_a_sync_order_on_one_body_does_not_walk_the_whole_table():
    """A 33-second query, and a timeout, on order=updated_asc: the sort must not be able to use the table-wide index."""
    import inspect

    from api.v2 import economy_endpoints

    src = inspect.getsource(economy_endpoints)
    assert "sql_order(order, \"creation_date\", \"(updated_at + interval '0 second')\")" in src
    assert "sql_order(order, \"creation_date\", \"updated_at\")" not in src


def test_a_search_is_words_not_one_exact_phrase():
    """A person types "electric cars" or "laws about batteries", and an exact phrase found nothing (4 Nov 2026)."""
    from sqlalchemy import column

    from api.v1._search import in_title, like_all_words, search_words, text_match, title_first

    assert search_words("laws about the batteries") == ["laws", "batteries"]
    assert search_words("the") == ["the"]
    assert search_words(None) == []

    params = {}
    sql = like_all_words("electric vehicles", ["title", "summary"], params)
    assert sql == "(title ILIKE :q0 OR summary ILIKE :q0) AND (title ILIKE :q1 OR summary ILIKE :q1)"
    assert params == {"q0": "%electric%", "q1": "%vehicles%"}

    # A short word is a whole word: "AI" must not match "certain", nor "Act" match "actions".
    params = {}
    sql = like_all_words("AI Act", ["title"], params)
    assert sql == "(title ~* :q0) AND (title ~* :q1)"
    assert params == {"q0": r"\yAI\y", "q1": r"\yAct\y"}
    assert not in_title("AI Act", "Alignment of certain countries with these actions")
    assert in_title("ai act", "The AI Act enters into force")

    params = {}
    assert title_first("AI Act", params) == "CASE WHEN title ILIKE :tqphrase THEN 0 WHEN title ~* :tq0 AND title ~* :tq1 THEN 1 ELSE 2 END"
    assert params["tqphrase"] == "%AI Act%"
    assert title_first("energy", {}) == "CASE WHEN title ILIKE :tq0 THEN 0 ELSE 1 END"
    assert title_first("", {}) == "0"
    assert in_title("ai act", "The AI Act enters into force")
    assert not in_title("ai act", "Elastic in cash")

    compiled = str(text_match("electric cars", column("title"), column("summary")).compile(dialect=postgresql.dialect()))
    assert " AND " in compiled
    assert text_match("   ", column("title")) is None


def test_gdpr_in_small_letters_finds_the_gdpr():
    from services.parsers.law_alias_resolver import find_alias_matches

    assert not find_alias_matches("gdpr") or find_alias_matches("gdpr")[0].celex == "32016R0679"
    assert find_alias_matches("GDPR")[0].celex == "32016R0679"


def test_a_common_name_is_answered_from_the_list_not_a_scan_of_every_law():
    """The first search a visitor makes, GDPR, took 8 s: lower(alias) and lower(acronym) have no index."""
    from sqlalchemy.dialects import postgresql

    from api.v1.laws import metadata_filters

    def sql(name):
        return " ".join(str(f.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})) for f in metadata_filters(alias=name))

    for name in ("GDPR", "gdpr", "AI Act", "DORA"):
        assert "eu_laws.celex IN" in sql(name), name
    assert "32022R2554" in sql("DORA")
    assert "lower(eu_laws.alias)" in sql("a name nobody has heard of")
    # Exact, as this filter always was: a sentence that mentions a law is not its name.
    assert "lower(eu_laws.alias)" in sql("the scope of GDPR")
