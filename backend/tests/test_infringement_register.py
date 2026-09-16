"""The Commission's infringement register behind /api/v2/commission/infringements (16 Sep 2026).

Before: the path served 169 Commission press releases, 166 of them undated, last ingested
7 May 2026. Now: every decision in the Commission's register since 1987 (62,610 on
16 Sep 2026), grouped into 25,658 cases, plus the 'Implementing EU law' statistics.

Three layers are tested:
  * the sync's transforms and its reconciliation guards (no network, no DB);
  * the statistics validation, which exists because the source answers a bad
    parameter with a series of zeros instead of an error (no network);
  * the routes against the stored register, including one INDEPENDENT check: the
    open cases per Member State must equal the Commission dashboard's own count.
"""
import pathlib
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import sync_infringement_register as sync  # noqa: E402
from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402
from services.infringements import implementing_eu_law as iel  # noqa: E402

B = "/api/v2/commission/infringements"

REF = {
    "memberState": {"Spain": "ES", "Greece": "EL", "United Kingdom": "UK"},
    "dg": {"Environment": "ENV"},
    "decisionType": {"Formal notice Art. 258 TFEU": "FN258", "Referral to Court Art. 258 TFEU": "RTC258",
                     "Closing of the case": "CLOSING_OF_THE_CASE"},
    "decisionCategory": {"FN258": "LFN", "RTC258": "RTC", "CLOSING_OF_THE_CASE": "CLOSURES"},
}


def _raw(**over):
    raw = {"infringementNumber": "INFR(2020)2001", "memberState": "Spain", "leadDg": "Environment",
           "caseType": "Bad application", "title": "Urban  waste water\nDirective", "activeInfringementCase": "Yes",
           "nonCommunicationCase": "No", "decisionDate": "2/07/2021", "decisionType": "Formal notice Art. 258 TFEU",
           "pressRelease": None, "pressReleaseURL": None, "memo": None, "memoURL": None,
           "normalCuriaReference": None, "normalCuriaReferenceURL": None, "policyAreas": ["Water", "Water"]}
    raw.update(over)
    return raw


# --------------------------------------------------------------------------- sync transforms
def test_a_register_record_is_normalised():
    d = sync.transform(_raw(), REF)
    assert d["decision_date"] == date(2021, 7, 2)            # D/MM/YYYY, day-first
    assert (d["member_state"], d["lead_dg_code"], d["decision_category"]) == ("ES", "ENV", "LFN")
    assert d["title"] == "Urban waste water Directive"
    assert (d["active_case"], d["non_communication"]) == (True, False)
    assert d["policy_areas"] == ["Water"]
    assert (d["public_url_kind"], d["body_source"]) == ("register_search", "composed:register")
    assert "INFR(2020)2001" in d["body_txt"] and "Spain" in d["body_txt"] and d["body_html"].startswith("<article>")


def test_public_url_prefers_the_items_own_page():
    press = sync.transform(_raw(pressReleaseURL="https://ec.europa.eu/commission/presscorner/detail/EN/IP_21_1",
                                memoURL="https://ec.europa.eu/m", normalCuriaReferenceURL="http://curia.europa.eu/juris/liste.jsf?num=C-1/21"), REF)
    assert press["public_url_kind"] == "press_release"
    court = sync.transform(_raw(normalCuriaReference="C-1/21", normalCuriaReferenceURL="http://curia.europa.eu/juris/liste.jsf?num=C-1/21"), REF)
    assert (court["public_url_kind"], court["public_url"]) == ("court_case", "https://curia.europa.eu/juris/liste.jsf?num=C-1/21")


def test_a_case_takes_its_state_from_its_latest_decision():
    ds = [sync.transform(_raw(decisionDate="2/07/2021", activeInfringementCase="No"), REF),
          sync.transform(_raw(decisionDate="9/02/2023", decisionType="Referral to Court Art. 258 TFEU",
                              normalCuriaReference="C-9/23", normalCuriaReferenceURL="http://curia.europa.eu/x",
                              activeInfringementCase="Yes"), REF),
          sync.transform(_raw(infringementNumber="INFR(2019)0001", decisionType="Closing of the case"), REF)]
    cases = {c["infringement_number"]: c for c in sync.build_cases(ds)}
    c = cases["INFR(2020)2001"]
    assert (c["decision_count"], c["first_decision_date"], c["latest_decision_date"]) == (2, date(2021, 7, 2), date(2023, 2, 9))
    assert (c["latest_decision_category"], c["active_case"], c["court_cases"]) == ("RTC", True, ["C-9/23"])
    assert c["public_url_kind"] == "court_case"
    assert "2021-07-02: Formal notice" in c["body_txt"] and "2023-02-09: Referral to Court" in c["body_txt"]


def test_the_sweep_refuses_a_window_that_would_not_fit_one_page(monkeypatch):
    monkeypatch.setattr(sync, "fetch_window", lambda client, f, t: {"totalRows": 5001 if f == "01/01/1900" else 1, "records": []})
    with pytest.raises(sync.RegisterError, match="pre-1990"):
        sync.fetch_register(None, today=date(2026, 9, 16))


def test_the_sweep_splits_a_large_year_into_months(monkeypatch):
    calls = []

    def fake(client, f, t):
        calls.append((f, t))
        if f == "01/01/2005" and t == "31/12/2005":
            return {"totalRows": 6000, "records": []}
        return {"totalRows": 1, "records": [{"w": f}]}
    monkeypatch.setattr(sync, "fetch_window", fake)
    records, _ = sync.fetch_register(None, today=date(2006, 3, 1))
    month_windows_2005 = [c for c in calls if c[0] and c[0].endswith("/2005") and c != ("01/01/2005", "31/12/2005")]
    assert ("01/02/2005", "28/02/2005") in calls and ("01/12/2005", "31/12/2005") in calls
    assert len(month_windows_2005) == 12
    assert len(records) == len(calls) - 2  # every window but the total probe and the split year returned one record


def test_a_failed_reconciliation_is_a_failure_not_a_partial_write(monkeypatch, capsys):
    class _Client:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(sync, "_client", lambda: _Client())
    monkeypatch.setattr(sync, "fetch_reference", lambda c: REF)
    monkeypatch.setattr(sync, "fetch_register", lambda c: ([_raw()], 2))
    monkeypatch.setattr(sync, "write", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not write")))
    monkeypatch.setattr(sys, "argv", ["sync", "--dry-run"])
    assert sync.main() == 1
    assert "reconciliation failed" in capsys.readouterr().out


# --------------------------------------------------------------------------- statistics validation
def test_member_state_codes_follow_the_commission():
    assert iel.normalise_member_state("gr") == "EL"
    with pytest.raises(ValueError):
        iel.normalise_member_state("XX")


def test_a_dataset_rejects_a_parameter_it_does_not_take():
    with pytest.raises(ValueError, match="does not accept member_state"):
        iel.fetch_dataset("active-cases-by-member-state", member_state="PL")


@pytest.mark.parametrize("kwargs", [{"day": date(2999, 1, 1)}, {"year": 1990, "month": 1}, {"end_year": 2025, "year_range": 99}])
def test_out_of_range_values_are_refused(kwargs):
    key = {"day": "active-cases-by-member-state", "year": "transposition-deficit-by-member-state",
           "end_year": "cases-opened-closed-active"}[next(iter(kwargs))]
    with pytest.raises(ValueError):
        iel.fetch_dataset(key, today=date(2026, 9, 16), **kwargs)


def test_the_upstream_call_uses_the_sources_own_formats(monkeypatch):
    seen = []
    monkeypatch.setattr(iel, "_get_json", lambda path: seen.append(path) or [{"name": "New", "data": [{"name": "2025", "y": 3}]}])
    monkeypatch.setattr(iel, "last_update", lambda section: date(2026, 9, 16))
    monkeypatch.setattr(iel, "policy_areas", lambda section: [{"id": "14", "code": "ENV", "title": "Environment"}])
    r = iel.fetch_dataset("cases-opened-closed-active", member_state="GR", case_type=["ncm", "BAD"],
                          policy_area=["env"], end_year=2025, year_range=3, today=date(2026, 9, 16))
    assert seen == ["/get-cases-opened-closed-active?end-year=2025&year-range=3&member-state=EL&case-type=NCM&case-type=BAD&policy-area=14"]
    assert r["parameters"] == {"end_year": 2025, "year_range": 3, "member_state": "EL", "case_type": ["NCM", "BAD"], "policy_area": ["ENV"]}
    assert r["rows"] == [{"series": "New", "label": "2025", "value": 3}]
    iel.fetch_dataset("active-cases-by-member-state", day=date(2026, 9, 1), today=date(2026, 9, 16))
    assert seen[-1] == "/get-repartition-infringements-cases-member-state?date=01-09-2026"
    iel.fetch_dataset("dialogues-by-member-state", year=2024, today=date(2026, 9, 16))
    assert seen[-1] == "/get-repartition-eu-pilot-cases-member-state?date=31-12-2024"


# --------------------------------------------------------------------------- routes and stored data
@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


def test_the_register_is_loaded_and_consistent(db):
    q = lambda sql: db.execute(text(sql)).scalar()
    decisions, cases = q("SELECT count(*) FROM infringement_decisions"), q("SELECT count(*) FROM infringement_cases")
    assert decisions > 60000 and cases > 25000, (decisions, cases)
    assert q("SELECT count(*) FROM infringement_decisions d WHERE NOT EXISTS "
             "(SELECT 1 FROM infringement_cases c WHERE c.infringement_number = d.infringement_number)") == 0
    assert q("SELECT count(*) FROM infringement_cases c WHERE decision_count <> "
             "(SELECT count(*) FROM infringement_decisions d WHERE d.infringement_number = c.infringement_number)") == 0
    for table in ("infringement_decisions", "infringement_cases"):
        assert q(f"SELECT count(*) FROM {table} WHERE public_url IS NULL OR body_txt IS NULL OR body_html IS NULL") == 0
    assert q("SELECT count(*) FROM infringement_decisions WHERE member_state IS NULL OR decision_category IS NULL") == 0


def test_open_cases_per_member_state_match_the_commissions_dashboard(db):
    """Independent source: the dashboard's own count. The register also lists open UK
    cases, which the dashboard leaves out."""
    import httpx
    try:
        rows = httpx.get(f"{iel.BASE}/get-repartition-infringements-cases-member-state?date={date.today():%d-%m-%Y}",
                         headers=iel._HEADERS, timeout=60).json()[0]["data"]
    except Exception as e:  # the dashboard being down is not our defect
        pytest.skip(f"dashboard unavailable: {type(e).__name__}")
    theirs = {r["name"]: r["y"] for r in rows}
    assert sum(theirs.values()) > 1000, "dashboard returned no figures: the instrument, not a pass"
    ours = dict(db.execute(text("SELECT member_state_name, count(*) FROM infringement_cases "
                                "WHERE active_case AND member_state <> 'UK' GROUP BY 1")).fetchall())
    assert ours == theirs


def test_the_case_list_carries_the_contract(client, db):
    j = client.get(B, params={"limit": 3}).json()
    assert j["total"] == db.execute(text("SELECT count(*) FROM infringement_cases")).scalar()
    for item in j["data"]:
        for key in ("public_url", "body_txt", "body_html", "document_date", "creation_date"):
            assert key in item
        assert item["body_txt"] is None and item["body_html"] is None      # bodies live on the detail
        assert item["document_date"] == item["latest_decision_date"]
        assert item["self"].endswith(f"{B}/{item['id']}")
    dates = [i["latest_decision_date"] for i in j["data"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.parametrize("params,column,value", [
    ({"member_state": "PL", "active": "true"}, "member_state", "PL"),
    ({"member_state": "GR"}, "member_state", "EL"),
    ({"case_type": "NCM"}, "case_type", "Non-communication"),
    ({"lead_dg": "env"}, "lead_dg_code", "ENV"),
])
def test_case_filters_match_the_table(client, db, params, column, value):
    j = client.get(B, params={**params, "limit": 5}).json()
    where = f"{column} = :v" + (" AND active_case" if params.get("active") == "true" else "")
    assert j["total"] == db.execute(text(f"SELECT count(*) FROM infringement_cases WHERE {where}"), {"v": value}).scalar()
    assert j["total"] > 0 and all(i[column] == value for i in j["data"])


@pytest.mark.parametrize("path,params", [
    (B, {"member_state": "XX"}), (B, {"case_type": "nope"}), (B, {"decision_from": "2026-07-01", "decision_to": "2026-06-01"}),
    (B, {"order": "sideways"}), (f"{B}/decisions", {"member_state": "XX"}),
    (f"{B}/statistics/active-cases-by-member-state", {"member_state": "PL"}),
    (f"{B}/statistics/transposition-deficit-by-member-state", {"month": 13}),
])
def test_bad_input_is_a_422_not_an_empty_result(client, path, params):
    r = client.get(path, params=params)
    assert r.status_code == 422, (path, params, r.status_code, r.text[:200])


def test_a_case_resolves_by_id_and_by_number_with_all_its_decisions(client, db):
    number, cid, count = db.execute(text("SELECT infringement_number, id, decision_count FROM infringement_cases "
                                         "WHERE decision_count >= 3 ORDER BY latest_decision_date DESC LIMIT 1")).one()
    by_number = client.get(f"{B}/{number.lower()}").json()
    by_id = client.get(f"{B}/{cid}").json()
    assert by_number == by_id
    assert by_number["body_txt"] and by_number["body_html"] and by_number["document_date"] == by_number["latest_decision_date"]
    assert len(by_number["decisions"]) == count
    assert [d["decision_date"] for d in by_number["decisions"]] == sorted(d["decision_date"] for d in by_number["decisions"])
    sub = client.get(f"{B}/{number}/decisions", params={"limit": 100}).json()
    assert sub["total"] == count


def test_a_decision_has_its_body_on_the_detail(client):
    lst = client.get(f"{B}/decisions", params={"with_press_release": "true", "limit": 1}).json()
    item = lst["data"][0]
    assert item["body_txt"] is None and item["public_url_kind"] == "press_release" and item["case_id"]
    detail = client.get(item["self"].split("testserver", 1)[1]).json()
    assert detail["id"] == item["id"] and detail["body_txt"] and item["infringement_number"] in detail["body_txt"]


@pytest.mark.parametrize("path", [f"{B}/INFR(1900)0000", f"{B}/decisions/999999999", f"{B}/statistics/nope", f"{B}/INFR(1900)0000/decisions"])
def test_unknown_items_are_404(client, path):
    assert client.get(path).status_code == 404


def test_the_statistics_catalogue_lists_every_dataset(client):
    j = client.get(f"{B}/statistics").json()
    assert {i["dataset"] for i in j["data"]} == set(iel.DATASETS)
    assert {i["section"] for i in j["data"]} == {"infringements", "transposition", "pre_infringement_dialogues"}
    assert client.get(f"{B}/statistics", params={"section": "transposition"}).json()["total"] == 6


def test_a_statistics_dataset_returns_figures_with_the_datapoints(client):
    r = client.get(f"{B}/statistics/cases-opened-closed-active", params={"member_state": "IT", "end_year": 2025, "year_range": 3})
    if r.status_code == 502:
        pytest.skip("dashboard unavailable")
    j = r.json()
    assert r.status_code == 200 and j["parameters"]["member_state"] == "IT"
    assert len(j["rows"]) == 9 and any(x["value"] for x in j["rows"]), "no figures: the instrument, not a pass"
    assert j["public_url"].endswith("/member-state-infringement-cases/en") and j["document_date"] and j["body_txt"]


def test_the_press_release_collection_still_answers(client):
    j = client.get(f"{B}/press-releases", params={"limit": 1}).json()
    assert j["total"] > 0 and "inf_reference" in j["data"][0]


def test_old_press_release_urls_under_this_path_redirect(client):
    """Until 16 Sep 2026 /infringements/{ref} served a press release. Those URLs keep working."""
    r = client.get(f"{B}/IP_26_838", follow_redirects=False)
    if r.status_code == 404:
        pytest.skip("press release IP_26_838 no longer stored")
    assert r.status_code == 308 and r.headers["location"] == f"{B}/press-releases/IP_26_838"
    assert client.get(f"{B}/IP_26_838").json()["inf_reference"] == "IP_26_838"


def test_a_sweep_that_would_delete_more_than_two_percent_refuses(monkeypatch):
    """A register answering with a fraction of its rows (an outage page, a changed API)
    must not wipe the table, even when the counts reconciled."""
    import scripts._specialised_helpers as helpers

    class _Cur:
        def __init__(self): self.last = None
        def fetchone(self): return self.last

    class _Db:
        def __init__(self):
            self.cur = _Cur(); self.deleted = False
        def execute(self, sql, params=None):
            if sql.startswith("SELECT count(*)") and "last_seen_at" in sql:
                self.cur.last = (500,)          # unseen in this sweep
            elif sql.startswith("SELECT count(*)"):
                self.cur.last = (1000,)         # held
            elif sql.startswith("DELETE"):
                self.deleted = True
        def commit(self): pass

    fake = _Db()
    monkeypatch.setattr(helpers, "ChunkedDb", lambda: fake)
    monkeypatch.setattr("psycopg2.extras.execute_values", lambda *a, **k: None)
    with pytest.raises(sync.RegisterError, match="refusing to delete"):
        sync.write([sync.transform(_raw(), REF)], sync.build_cases([sync.transform(_raw(), REF)]),
                   started=__import__("datetime").datetime.now())
    assert not fake.deleted


def test_the_statistics_cache_is_bounded(monkeypatch):
    class _R:
        status_code = 200
        def json(self): return []
    monkeypatch.setattr("httpx.get", lambda *a, **k: _R())
    monkeypatch.setattr(iel, "CACHE_MAX_ENTRIES", 5)
    iel._cache.clear()
    for i in range(12):
        iel._get_json(f"/x?{i}")
    assert len(iel._cache) <= 5 and "/x?11" in iel._cache
    iel._cache.clear()
