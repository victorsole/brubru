"""Phase 1 of the funding standard: partners (26 Oct 2026).

A partner search on 20-21 Oct found no consortium leads: the FTS recipients were text with `q` as the
only filter (department=CNECT returned the whole table), funded projects could not be filtered by
organisation, and nothing grouped activities by organisation. Covered here: the FTS file's own
columns (migration 313), the recipients and international-cooperation routes on them, the PICs the
CORDIS loader dropped, the funded-project consortium filters, one country code across sources, the
VAT -> PIC pairing (migration 314) and /funding/partners.
"""
import importlib
import io
import pathlib
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402
from services.funding import countries  # noqa: E402

HEADER = ["Year", "Budget", "Reference of the Legal Commitment (LC)", "Reference (Budget)", "Name of beneficiary",
          "Main registration number of beneficiary", "VAT number of beneficiary", "Not-for-profit organisation (NFPO)",
          "Non-governmental organisation (NGO)", "Coordinator", "Address", "City", "Postal code", "Beneficiary country",
          "NUTS2", "Beneficiary’s contracted amount (EUR)", "Beneficiary’s estimated contracted amount (EUR)",
          "Beneficiary’s estimated consumed amount (EUR)", "Commitment contracted amount (EUR) (A)",
          "Additional/Reduced amount (EUR) (B)", "Commitment  total amount (EUR) (A+B)", "Commitment consumed amount (EUR)",
          "Source of (estimated) detailed amount", "Expense type", "Call ID", "Project ID", "Project Acronym",
          "Subject of grant or contract", "Responsible department", "Budget line number", "Budget line name",
          "Programme name", "Beneficiary type", "Project start date", "Project end date", "Type of contract*",
          "Management type", "Benefiting country", "Count"]


def _row(name, lc, amount, ben_amount, coord, vat, country, call="N/A - Not applicable", project="N/A - Not applicable"):
    return ["2025", "EU budget", lc, lc + ".1", name, "123", vat, "No", "No", coord, "STREET 1", "MADRID", "28001",
            country, "ES30", ben_amount, ben_amount, 1.0, amount, 0, amount, 1.0, "split", "Operational", call, project,
            "ACR", "Soil health study", "CNECT - Communications Networks", "0101", "Line", "Horizon Europe",
            "Private Companies", datetime(2025, 1, 1), datetime(2027, 12, 31), "Action Grant", "Direct management",
            "Spain 100%", "1"]


def _xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


RAW = None


def _raw():
    global RAW
    if RAW is None:
        RAW = _xlsx([
            _row("AGENCIA ESTATAL CSIC", "LC.1", 1000000, 400000, "Yes", "ES Q2818002D", "Spain", "HORIZON-CL6-2025", "101112434"),
            _row("SOME FIRM SL", "LC.1", 1000000, 600000, "No", "ESB65577462", "Spain"),
            _row("*****", "LC.2", 50, 50, "No", None, "Spain"),
            # Most 2025 rows give no legal commitment ("N/A - Not applicable"); the key keeps the cell as the loader read it.
            _row("THIRD SA", "N/A - Not applicable", 70, 70, "No", None, "Greece"),
        ])
    return RAW


# --- A1: the FTS file's columns ----------------------------------------------------------------- #

def test_the_fts_reader_gives_every_column_and_the_loaders_own_keys():
    from services.scrapers import commission_funding as cf
    recs = list(cf.fts_records(_raw(), 2025))
    with mock.patch.object(cf.requests, "get", lambda *a, **k: mock.Mock(content=_raw(), status_code=200)):
        items = cf.ingest_eu_funding_recipients(year=2025)
    assert [r["key"] for r in recs] == [i.guid for i in items] and len(recs) == 3      # "*****" skipped by both
    assert recs[2]["lc_reference"] is None                                           # served as no value
    csic = recs[0]
    assert csic["is_coordinator"] is True and csic["beneficiary_amount_eur"] == 400000.0
    assert csic["commitment_total_eur"] == 1000000.0 and csic["project_id"] == "101112434"
    assert csic["project_start"] == date(2025, 1, 1) and csic["dg"].startswith("CNECT")
    assert recs[1]["call_id"] is None and recs[1]["is_coordinator"] is False          # "N/A - Not applicable" is no value


def test_the_writer_puts_the_columns_beside_the_stored_rows():
    sfc = importlib.import_module("sync_fts_commitments")
    from services.scrapers import commission_funding as cf
    keys = [r["key"] for r in cf.fts_records(_raw(), 2025)]
    executed = []

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None): executed.append(("execute", sql))
        def fetchall(self): return [(keys[0], 11), ("gonekey00000", 99)]

    conn = SimpleNamespace(cursor=lambda: _Cur(), commit=lambda: executed.append(("commit",)))
    written = []
    with mock.patch.object(sfc, "read_fts_file", lambda y: (y, _raw())), \
         mock.patch.object(sfc.psycopg2.extras, "execute_values", lambda cur, sql, rows, page_size: written.extend(rows)):
        assert sfc.sync_year(conn, 2025, apply=True) == (1, 2, 1)                      # written, unstored, stale
    row = dict(zip(("economy_item_id",) + sfc.COLUMNS, written[0]))
    assert row["economy_item_id"] == 11 and row["vat_key"] == "ESQ2818002D" and row["country_code"] == "ES"


# --- one country code, one VAT key ---------------------------------------------------------------- #

def test_the_sources_meet_on_one_country_code():
    assert countries.country_code("Czech Republic") == "CZ" == countries.country_code("Czechia")
    assert countries.country_code("Greece") == "EL" and countries.country_code("United Kingdom") == "UK"
    assert countries.country_code("Cote d'Ivoire") == countries.country_code("Côte d’Ivoire") == "CI"
    assert countries.country_code("Kosovo (under UNSCR 1244/99)") == "XK"
    assert countries.country_code("Republ") is None                                   # cut short in the file: no guess
    assert countries.eu_code("gr") == "EL" and countries.both_styles("UK") == ["GB", "UK"]
    assert countries.vat_key("es q2818002-d") == "ESQ2818002D" and countries.vat_key(" - ") is None


# --- the recipient lists on the columns ----------------------------------------------------------- #

class _Db:
    def __init__(self):
        self.calls = []

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        return SimpleNamespace(scalar=lambda: 0, fetchall=lambda: [], fetchone=lambda: None)


def _client(db):
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_recipients_filter_on_the_file_columns_and_take_the_partner_search_parameters():
    db = _Db()
    r = _client(db).get("/api/v2/funding/eu-funding-recipients",
                        params={"department": "CNECT", "coordinator": "true", "min_amount_eur": 50000, "vat": "es q2818002d"})
    assert r.status_code == 200, r.text
    sql, params = db.calls[-1]
    assert "LEFT JOIN fts_commitments c" in sql and "c.dg ILIKE :dg" in sql and params["dg"] == "%CNECT%"
    assert "c.is_coordinator = :coord" in sql and "c.beneficiary_amount_eur >= :min_amt" in sql
    assert params["vat"] == "ESQ2818002D" and "c.vat_key = :vat" in sql and "body_txt ILIKE" not in sql


def test_international_cooperation_reads_the_columns_not_the_text():
    db = _Db()
    r = _client(db).get("/api/v2/funding/international-cooperation", params={"programme": "ipa3", "country": "Ukraine"})
    assert r.status_code == 200, r.text
    sql = " ".join(c[0] for c in db.calls)
    assert "c.programme ILIKE :prog" in sql and "c.country ILIKE :ctry" in sql and "body_txt ILIKE" not in sql


def test_a_recipient_item_carries_the_beneficiarys_own_amount():
    from api.v2.funding import _fts
    r = SimpleNamespace(id=7, title="CSIC", summary=None, source_kind="fts", public_url="u", document_date=None,
                        creation_date=None, updated_at=None, beneficiary="CSIC", country="Spain", city="MADRID",
                        nuts2=None, beneficiary_amount_eur=400000, commitment_total_eur=1000000, funding_type="Action Grant",
                        programme="Horizon Europe", dg="CNECT", lc_reference="LC.1", year=2025, subject="Soil",
                        is_coordinator=True, beneficiary_type=None, is_nfpo=None, is_ngo=None, registration_number=None,
                        vat_number=None, call_id=None, project_id="101112434", project_acronym=None, project_start=None,
                        project_end=None, budget_line_name=None, management_type=None, body_txt=None, body_html=None)
    item = _fts.to_item(r, with_body=False)
    assert (item.amount_eur, item.commitment_total_eur) == (400000.0, 1000000.0)


# --- A2: PICs kept, consortium filters -------------------------------------------------------------- #

def test_the_cordis_loader_keeps_each_organisations_pic():
    import zipfile
    cordis = importlib.import_module("ingest_cordis_projects")
    csv_text = ('"projectID";"organisationID";"vatNumber";"name";"role";"country";"SME";"activityType"\n'
                '"101";"999991722";"ESQ2818002D";"CSIC";"coordinator";"ES";"false";"REC"\n'
                '"101";"912743326";"";"LOMARTOV SL";"participant";"ES";"true";"PRC"\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("organization.csv", csv_text)
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
        full, coord = cordis.load_full_org_map(z), cordis.load_coordinator_map(z)
    assert [o["pic"] for o in full["101"]] == ["999991722", "912743326"] and coord["101"]["pic"] == "999991722"
    kw = dict(organisations=full["101"], topics=[], euroscivoc=[], legal_basis_details=[], web_links=[])
    assert cordis.normalise({"id": "101", "status": "SIGNED"}, coord["101"], "horizon", **kw)["coordinator_pic"] == "999991722"
    assert "coordinator_pic = COALESCE(EXCLUDED.coordinator_pic, ft_funded_projects.coordinator_pic)" in cordis._UPSERT_SQL


def _project_sql(**params):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Query
    seen = []

    class _Q(Query):
        def count(self):
            seen.append(self.statement.compile(dialect=postgresql.dialect()))
            return 0

        def all(self):
            return []

    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(query=lambda *e: _Q(list(e)))
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    r = TestClient(app).get("/api/v2/funding/ft-funded-projects", params=params)
    return r, (str(seen[0]), seen[0].params) if seen else (None, None)


def test_projects_filter_on_one_consortium_member():
    r, (sql, params) = _project_sql(organisation="999991722", role="Coordinator", participant_country="GR")
    assert r.status_code == 200, r.text
    assert "organisations @> CAST(" in sql and "jsonb_array_elements(ft_funded_projects.organisations)" in sql
    assert '"pic": "999991722"' in params["contains"] and '"role": "coordinator"' in params["contains"]
    assert params["pc"] == "EL" and params["pcs"] == ["EL", "GR"]                       # one country, both spellings
    r, (sql, params) = _project_sql(organisation="Consejo Superior", role="participant")
    assert params["org_like"] == "%Consejo Superior%" and "AND false" in sql             # outside CORDIS only coordinators
    assert _project_sql(role="chief")[0].status_code == 400


def test_projects_q_is_full_text_and_country_takes_both_spellings():
    r, (sql, params) = _project_sql(q="soil health", topic="HORIZON-CL6-2025", keyword="soil", coordinator_country="GB")
    assert "websearch_to_tsquery('english', %(q)s)" in sql and "coalesce(ft_funded_projects.keywords" in sql
    assert params["topic_code_1"] == "HORIZON-CL6-2025%" and set(params["coordinator_country_1"]) == {"GB", "UK"}


def test_a_project_item_carries_its_consortium():
    from api.v1.funding_tenders_collections import _project_to_item
    r = SimpleNamespace(id="x", project_id="101", project_acronym=None, title="T", objective="O", framework_programme="HORIZON",
                        type_of_action=None, coordinator_name="CSIC", coordinator_country="ES", coordinator_pic="999991722",
                        organisations=[{"pic": "999991722", "name": "CSIC", "role": "coordinator", "country": "ES",
                                        "ec_contribution": 1.5, "vat": "X", "nuts_code": "ES30"}],
                        start_date=None, end_date=None, total_cost=None, eu_contribution=None, cost_currency="EUR",
                        status="ongoing", source_status="signed", source_url="u", published_at=None, last_updated=None,
                        keywords="soil; carbon", scraped_at=None)
    item = _project_to_item(r)
    assert item.coordinator_pic == "999991722" and item.organisations[0].pic == "999991722"
    assert "soil; carbon" in item.body_txt                                             # the Keywords section is no longer empty


# --- B: the VAT -> PIC pairing and /funding/partners -------------------------------------------- #

def test_the_pairing_takes_the_dominant_pic_and_normalises_as_the_api_does():
    roi = importlib.import_module("scripts.refresh_org_identities")
    # A VAT number goes to the PIC holding 90% of its memberships (CSIC: 2,523 of 2,524), else to none.
    assert "(n >= 0.9 * projects) AS clear" in roi.PAIRS and "WHERE rk = 1" in roi.PAIRS
    assert "FROM agg WHERE clear" in roi.UPSERT and "agg.clear" in roi.STALE
    assert "upper(regexp_replace(o->>'vat', '[^A-Za-z0-9]', '', 'g'))" in roi.PAIRS


def _partners(**params):
    db = _Db()
    r = _client(db).get("/api/v2/funding/partners", params=params)
    return r, db.calls[-1] if db.calls else (None, None)


def test_partners_need_a_subject_or_a_name_and_known_values():
    assert _partners()[0].status_code == 400
    assert _partners(q="soil", role="boss")[0].status_code == 400
    assert _partners(q="soil", source="tweets")[0].status_code == 400


def test_partners_match_subjects_not_names_and_keep_people_out():
    r, (sql, params) = _partners(q="soil health", role="coordinator", country="GR")
    assert r.status_code == 200, r.text
    assert "websearch_to_tsquery('english', :q)" in sql and "coalesce(c.subject, '')" in sql
    assert "e.search_vector" not in sql                                                # the FTS vector holds names too
    assert "IS DISTINCT FROM 'Private Persons'" in sql and params["cc"] == "EL"
    assert "LEFT JOIN funding_org_identities m" in sql


def test_partner_filters_that_one_source_cannot_answer_drop_that_source():
    _, (sql, _) = _partners(q="ai", dg="CNECT")
    assert "jsonb_array_elements(pr.organisations)" not in sql and "c.dg ILIKE :dg" in sql   # payments only
    # The first SELECT of a UNION names its columns: payments alone answered 500 until they were named.
    for col in ("'payment' AS kind", "AS ref", "AS pic", "AS vat", "AS name", "AS country", "AS role", "AS amount_eur"):
        assert col in sql, col
    _, (sql, _) = _partners(q="ai", activity_type="REC")
    assert "fts_commitments c" not in sql and "activity_type = :at" in sql                 # projects only


def test_a_partner_item_links_each_activity_and_its_portal_profile():
    from api.v2.funding import partners
    r = SimpleNamespace(key="pic:999991722", pic="999991722", vat="ESQ2818002D", name="CSIC", short_name="CSIC", country="ES",
                        city="MADRID", activity_type="REC", is_sme=False, projects=1, coordinated=1, payments=1, contracts=0, awards=0,
                        eu_contribution=10.0, amount_eur=400000, last_day=date(2025, 1, 1), created=None, changed=None,
                        matches=[{"kind": "project", "id": "101112434", "title": "Soil", "role": "coordinator", "programme": "HORIZON",
                                  "date": "2025-01-01", "eu_contribution": 10.0, "amount_eur": None},
                                 {"kind": "payment", "id": "7", "title": "Soil study", "role": "coordinator", "programme": "Horizon Europe",
                                  "date": None, "eu_contribution": None, "amount_eur": 400000}])
    item = partners._item(r, "https://h")
    assert item.public_url.endswith("/org-details/999991722")
    assert [m.self for m in item.matches] == ["https://h/api/v2/funding/ft-funded-projects/101112434",
                                              "https://h/api/v2/funding/eu-funding-recipients/7"]


def test_a_partner_id_reaches_its_own_records():
    db = _Db()
    c = _client(db)
    assert c.get("/api/v2/funding/partners/pic:999991722").status_code == 404           # nothing held in the stand-in
    sql, params = db.calls[-1]
    assert params["key"] == "pic:999991722" and "organisations @> CAST(:key_contains AS jsonb)" in sql
    assert "FROM funding_org_identities WHERE pic = :key_val" in sql
    c.get("/api/v2/funding/partners/vat:es q2818002d")
    assert db.calls[-1][1]["key"] == "vat:ESQ2818002D"                                 # not paired in the stand-in

    class _Paired(_Db):
        def execute(self, stmt, params=None):
            if "FROM funding_org_identities WHERE vat_key" in str(stmt):
                return SimpleNamespace(scalar=lambda: "999991722")
            return super().execute(stmt, params)
    paired = _Paired()
    _client(paired).get("/api/v2/funding/partners/vat:ESQ2818002D")
    assert paired.calls[-1][1]["key"] == "pic:999991722"                               # a paired VAT answers as its PIC
    assert c.get("/api/v2/funding/partners/bogus").status_code == 404


# --- the jobs run where the data is read ---------------------------------------------------------- #

def test_the_jobs_run_after_the_data_they_read(monkeypatch):
    import asyncio
    from api import cron
    order = []

    async def fake_runner(key, script, args, timeout=None):
        order.append(key)
        return {"status": "success"}

    monkeypatch.setattr(cron, "_run_script_async", fake_runner)
    monkeypatch.setattr(cron, "_record_tier_results", lambda *a, **k: None)
    monkeypatch.setattr(cron, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr("services.sync.freshness.record_run", lambda *a, **k: None)
    asyncio.run(cron._run_commission_heavy_bg())
    assert order.index("fts_commitments") > order.index("commission_funding_recipient")
    assert "org_identities" in cron._WEEKLY_TIER_RECORDED
