"""Funded projects show the source's word, find programmes by name, and their docs name real routes
(26 Oct 2026).

Three faults found on the live check after the 0.7 status backlog: a `status=signed` result showed
planned, ongoing or ended with no visible reason (the routes filtered on `source_status` without
returning it); the documented `framework_programme` examples (`Horizon Europe`, `Horizon 2020`)
matched nothing, since the column holds codes (HORIZON, H2020, ERASMUS2027); and the funding docs
named nine paths that are not routes (`/api/v1/funded-projects` and others, all 404).
"""
import importlib
import io
import json
import pathlib
import re
import sys
from contextlib import redirect_stdout
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from api.v1.funding_tenders_collections import FtFundedProjectItem, _project_to_item  # noqa: E402
from core.database import get_db  # noqa: E402
from services.funding import programme_codes as pc  # noqa: E402


# --- 1. the source's word is served ---------------------------------------------------------- #

def _row(**kw):
    base = dict(id="1cfbfdaa-756e-4c7e-899b-2d1176e12ff7", project_id="101230663", project_acronym=None,
                title="A project", objective=None, framework_programme="HORIZON", type_of_action=None,
                coordinator_name=None, coordinator_country=None, start_date=date(2027, 10, 1),
                end_date=date(2032, 9, 30), total_cost=None, eu_contribution=None, cost_currency="EUR",
                status="planned", source_status="signed", source_url="https://cordis.europa.eu/project/id/101230663",
                published_at=None, last_updated=None, keywords=None, scraped_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_an_item_shows_the_word_its_status_was_set_from():
    item = _project_to_item(_row())
    assert (item.status, item.source_status) == ("planned", "signed")
    assert _project_to_item(_row(source_status=None)).source_status is None
    assert "source_status" in FtFundedProjectItem.model_json_schema()["properties"]


def test_the_cordis_loader_stores_no_placeholder_for_an_empty_word():
    cordis = importlib.import_module("ingest_cordis_projects")
    kw = dict(organisations=[], topics=[], euroscivoc=[], legal_basis_details=[], web_links=[])
    assert cordis.normalise({"id": "1", "status": "SIGNED"}, {}, "fp7", **kw)["source_status"] == "signed"
    assert cordis.normalise({"id": "1", "status": ""}, {}, "fp7", **kw)["source_status"] is None
    nonh = importlib.import_module("ingest_ft_projects_nonh2020")
    for sql in (cordis._UPSERT_SQL, nonh.UPSERT):
        values = " ".join(sql.split("ON CONFLICT", 1)[0].split())
        # A new row waits as 'unknown' for the status rule; the source word goes to its own column.
        assert "'unknown', %(source_status)s" in values and "%(status)s" not in values


def test_a_change_to_the_served_word_is_a_change():
    sql = (BACKEND / "migrations" / "312_funded_projects_source_status_served.sql").read_text()
    assert "brubru_touch_if_changed('last_updated', 'scraped_at', '')" in sql
    assert sql.index("SET source_status = NULL WHERE source_status = 'unknown'") < sql.index("CREATE TRIGGER")


# --- 6. programmes found by name ------------------------------------------------------------- #

def test_names_find_the_codes_and_codes_answer_as_before():
    assert pc.named_codes("Horizon Europe") == ["HORIZON"]
    assert pc.named_codes("Horizon 2020") == ["H2020"]
    assert pc.named_codes("Creative Europe") == ["CREA2020", "CREA2027"]
    assert pc.named_codes("Erasmus+") == ["EPLUS2020", "ERASMUS2027"]       # the portal drops the '+'
    assert pc.named_codes("Seventh Framework Programme") == ["FP7"]
    for code_part in ("HORIZON", "horizon", "LIFE", "CEF", "2027", "FP7"):  # part of a code: unchanged
        assert pc.named_codes(code_part) == [], code_part
    assert pc.named_codes("+ +") == [] and pc.named_codes("Atlantis Programme") == []


def test_the_name_file_covers_the_codes_held_on_26_october():
    held = ("1HP,2HP,3HP,AGRIP,AGRIP2027,AMIF,AMIF2027,BMVI,CCEI,CEF,CEF2027,CERV,COSME,CREA2020,CREA2027,"
            "CUST,DIGITAL,EDF,EMFAF,EMFF,EPLUS2020,ERASMUS2027,ERDFTA,ESC2027,ESF,EU4H,EUAF,EURATOM2027,FISC,"
            "FP7,H2020,HERC,HORIZON,I3,IMCAP,IMCAP2027,IMREG,INNOVFUND,ISF,ISFB,ISFP,JTM,JUST,JUST2027,LIFE,"
            "LIFE2027,NDICI,PERI,PPPA2027,REC,RENEWFM,RFCS,RFCS2027,SMP,SOCPL,SRSP,TSI,UCPM,UCPM2027").split(",")
    assert pc.unnamed(held) == []
    assert pc.unnamed(held + ["EDIP2034", None]) == ["EDIP2034"]
    raw = json.loads((BACKEND / "config" / "ft_programme_codes.json").read_text())
    assert raw["$read"] == "2026-10-26" and all(v["name"] for v in raw["codes"].values())


class _RecordingQuery(Query):
    seen: list = []

    def count(self):
        _RecordingQuery.seen.append(str(self.statement.compile(dialect=postgresql.dialect(),
                                                               compile_kwargs={"literal_binds": True})))
        return 0

    def all(self):
        return []


def _list_sql(**params):
    from api.v2.funding import router
    _RecordingQuery.seen = []
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *e: _RecordingQuery(list(e)))
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/ft-funded-projects", params=params)
    assert r.status_code == 200, r.text
    return _RecordingQuery.seen[0]


def test_the_list_adds_the_named_codes_to_the_code_match():
    named = _list_sql(framework_programme="Horizon Europe")
    assert "ILIKE '%%Horizon Europe%%'" in named and "framework_programme IN ('HORIZON')" in named
    code = _list_sql(framework_programme="HORIZON")
    assert "ILIKE '%%HORIZON%%'" in code and " IN (" not in code


def test_the_status_job_reports_a_code_with_no_name(monkeypatch):
    mod = importlib.import_module("scripts.refresh_project_status")

    class _Db:
        def execute(self, stmt, params=None):
            return iter([("HORIZON",), ("EDIP2034",)])

        def close(self): pass

    monkeypatch.setattr(mod, "SessionLocal", _Db)
    monkeypatch.setattr(mod, "refresh", lambda db, apply: {})
    out = io.StringIO()
    with redirect_stdout(out):
        assert mod.main([]) == 0
    assert "[SYNC_STATUS] degraded: programme code(s) with no name" in out.getvalue()
    assert "EDIP2034" in out.getvalue() and "HORIZON" not in out.getvalue().split("degraded:")[1]


# --- 2. every path the funding docs name is a route ------------------------------------------ #

def test_every_path_the_funding_docs_name_is_a_route():
    from main import app
    routes = [r for r in app.routes if hasattr(r, "path")]
    patterns = [re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", re.sub(r"\{[^}:]+:path\}", ".+", r.path)) + "$")
                for r in routes]
    named = re.compile(r"/api/v[12]/[A-Za-z0-9_\-/{}.]+")
    broken = {}
    for r in routes:
        if not re.search(r"funding|ft-|eurio|calls-for|funded", r.path):
            continue
        doc = f"{getattr(r, 'description', '') or ''} {getattr(r, 'summary', '') or ''}"
        for m in named.findall(doc):
            path = re.sub(r"\{[^}]+\}", "X", m.rstrip("/.").split("?")[0])
            if not any(p.match(path) for p in patterns):
                broken.setdefault(m, set()).add(r.path)
    assert broken == {}, broken


def test_the_funding_examples_name_rows_that_exist():
    """The item examples named a topic and a project Brubru does not hold (HORIZON-CL5-2026-D2-01-01,
    101082345), so "Try it" answered 404 on 26 Oct 2026. They name held rows now; this keeps the
    retired ones from coming back (whether a row exists is checked on production, not here)."""
    for f in ("api/v1/funding_tenders_collections.py", "api/v1/infringements_funding.py",
              "api/v2/funding/funding_opportunities.py", "api/v2/funding/funding_tenders.py"):
        src = (BACKEND / f).read_text()
        assert "HORIZON-CL5-2026-D2-01-01" not in src and "101082345" not in src, f
