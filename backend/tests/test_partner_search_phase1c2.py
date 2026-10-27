"""Phase 1 C2 of the funding standard: the F&T Portal's Partner Search, organisations only.

Every organisation, text and identifier here is made up (the repository is public).
"""
import importlib
import pathlib
import sys
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402
from services.scrapers import ft_partner_search as fps  # noqa: E402


# --- the texts ----------------------------------------------------------------------------------------- #
def test_contacts_are_removed_and_figures_kept():
    text = ("We build sensors. Contact: jane.example@mail.test or +32 2 555 01 01, 00 34 91 555 01 01, "
            "Tel.: 06 1234 5678, ORCID 0000-0002-1825-0097, https://www.linkedin.com/in/jane-example-123 .")
    out = fps.redact(text)
    for gone in ("jane.example@", "555 01 01", "1234 5678", "1825-0097", "linkedin.com/in"):
        assert gone not in out, gone
    kept = "Budget EUR 3 500 000 for 2021-2027, topic HORIZON-CL5-2024-D4-02-05, ISO 9001:2015, version 2.0, 15 PhDs."
    assert fps.redact(kept) == kept
    assert fps.redact(None) is None and fps.redact("") == ""


# --- reading the index ----------------------------------------------------------------------------------- #
def _ps(labels=None):
    ps = fps.PartnerSearch.__new__(fps.PartnerSearch)
    ps._labels = labels or {"country": {"20000001": "Spain", "20000002": "Kosovo * UN resolution"},
                            "organisationType": {"31000001": "Small or medium-size enterprise"}}
    return ps


def test_an_announcement_is_read_with_its_codes_as_labels():
    md = {"announcementId": ["900001"], "pic": ["900000001"], "name": ["EXAMPLE  SENSORS\nSL"], "country": ["20000001"],
          "organisationType": ["31000001"], "expertise": ["Expertise_request"], "topics": ["HORIZON-CL4-2026-01-01"],
          "title": ["An example topic"], "requestedDate": ["2026-10-20T00:00:00.000+0000"],
          "announcementSummary": ["x" * 500], "es_SortDate": ["2026-10-20T09:00:00.000+0200"]}
    a = _ps().announcement(md)
    assert (a["announcement_id"], a["pic"], a["organisation_name"], a["country"]) == ("900001", "900000001", "EXAMPLE SENSORS SL", "ES")
    assert (a["organisation_type"], a["expertise"], a["topic_id"], a["requested_date"]) == (
        "Small or medium-size enterprise", "request", "HORIZON-CL4-2026-01-01", "2026-10-20")
    assert a["summary_cut"] is True and a["indexed_at"].startswith("2026-10-20T09:00:00")
    assert a["public_url"].endswith("/org-details/900000001")
    # A label carrying the EU's footnote mark; a type the index already writes as a label.
    b = _ps().announcement(dict(md, country=["20000002"], organisationType=["Research Organisation"],
                                expertise=["Expertise_offer"], announcementSummary=["short"]))
    assert (b["country"], b["organisation_type"], b["expertise"], b["summary_cut"]) == ("XK", "Research Organisation", "offer", False)
    assert _ps().announcement(dict(md, pic=[])) is None and _ps().announcement(dict(md, announcementId=["NA"])) is None
    # Cut at 500 counting the blanks the index kept at the end.
    c = _ps().announcement(dict(md, announcementSummary=["y" * 480 + "\t" * 20]))
    assert c["summary_cut"] is True and c["summary"] == "y" * 480


def test_only_organisations_are_asked_for():
    assert {"terms": {"announcementType": ["ORGANISATION"]}} in fps._ORG_ANNOUNCEMENTS
    assert {"terms": {"type": ["ANNOUNCEMENT"]}} in fps._ORG_ANNOUNCEMENTS
    assert {"terms": {"type": ["ORGANISATION"]}} in fps._PROFILES
    assert "PERSON" not in repr(fps._ORG_ANNOUNCEMENTS + fps._PROFILES)
    p = _ps().profile({"pic": ["900000001"], "name": ["Example Sensors SL"], "hasPartnerSearch": ["true"],
                       "noOfProjects": ["0"], "noOfPartnerSearch": ["3"], "country": ["20000001"], "topics": ["T-1"]})
    assert (p["pic"], p["projects"], p["portal_announcements"], p["country"]) == ("900000001", 0, 3, "ES")
    assert _ps().profile({"pic": ["900000002"], "hasPartnerSearch": ["false"]}) is None


def test_the_facet_service_answers_every_facet_and_only_the_asked_one_is_kept():
    ps = _ps()
    ps._labels = {}
    answer = {"facets": [{"name": "topics", "values": [{"rawValue": "HORIZON-X", "value": "HORIZON-X"}]},
                         {"name": "country", "values": [{"rawValue": "20000001", "value": "Spain"}]}]}
    ps._post = lambda url, parts: answer
    ps._facet = "f"
    assert ps.labels("country") == {"20000001": "Spain"}


def test_a_dropped_connection_is_tried_again(monkeypatch):
    import requests
    calls = []

    class _Session:
        def post(self, url, data, headers, timeout):
            calls.append(url)
            if len(calls) < 3:
                raise requests.ConnectionError("Remote end closed connection without response")
            return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"ok": 1})
    monkeypatch.setattr(fps.time, "sleep", lambda s: None)
    ps = _ps()
    ps.session, ps.sleep = _Session(), 0
    assert ps._post("u", {}) == {"ok": 1} and len(calls) == 3

    class _Down(_Session):
        def post(self, url, data, headers, timeout):
            raise requests.ConnectionError("down")
    ps.session = _Down()
    try:
        ps._post("u", {})
        raise AssertionError("a connection down four times must raise")
    except requests.ConnectionError:
        pass

def test_a_range_above_the_cap_is_split_until_each_part_fits():
    ps = _ps()
    counts = {(date(2026, 1, 1), date(2027, 1, 1)): 25_000, (date(2026, 1, 1), date(2026, 7, 2)): 12_000,
              (date(2026, 7, 2), date(2027, 1, 1)): 13_000}
    ps.total = lambda must: next((n for (a, b), n in counts.items() if must[-1] == fps._requested(a, b)), 4_000)
    parts = ps.slices(date(2026, 1, 1), date(2027, 1, 1))
    assert all(n <= fps.CAP for _, _, n in parts) and len(parts) == 4
    assert parts[0][0] == date(2026, 1, 1) and parts[-1][1] == date(2027, 1, 1)
    assert all(parts[i][1] == parts[i + 1][0] for i in range(len(parts) - 1))      # no gap, no overlap


def test_a_range_read_short_is_marked_incomplete():
    ps = _ps()
    ps.slices = lambda a, b: [(a, b, 3)]
    md = {"announcementId": ["1"], "pic": ["9"], "requestedDate": ["2026-10-20T00:00:00.000+0000"]}
    ps._pages = lambda must, fields: iter([{"total": 3, "results": [{"metadata": md}, {"metadata": dict(md, announcementId=["2"])}]}])
    rows, n, complete = ps.announcements(date(2026, 10, 1), date(2026, 11, 1))
    assert (len(rows), n, complete) == (2, 3, False)


def test_profiles_are_complete_only_when_every_country_gave_its_count():
    ps = _ps()
    md = lambda pic: {"metadata": {"pic": [pic], "hasPartnerSearch": ["true"], "country": ["20000001"]}}  # noqa: E731
    pages = {"20000001": [{"total": 2, "results": [md("1"), md("2")]}], "20000002": [{"total": 1, "results": [md("3")]}]}
    ps._pages = lambda must, fields: iter(pages[must[-1]["terms"]["country"][0]])
    ps.total = lambda must: 3                    # counted before the read
    rows, n, complete = ps.profiles()
    assert (len(rows), n, complete) == (3, 3, True)
    ps.total = lambda must: 2                    # a profile added during the read is not a gap
    assert ps.profiles()[2] is True
    pages["20000002"] = [{"total": 2, "results": [md("3")]}]                  # a country short of its count
    assert ps.profiles()[2] is False
    pages["20000002"] = [{"total": 1, "results": [md("3")]}]
    ps.total = lambda must: 4                    # a profile in no country
    assert ps.profiles()[2] is False

# --- the loader ------------------------------------------------------------------------------------------ #
def test_each_day_reads_the_recent_days_and_a_seventh_of_the_months():
    sync = importlib.import_module("sync_ft_partner_search")
    today = date(2026, 10, 27)
    recent = today.toordinal() - sync.RECENT_DAYS
    covered = set()
    for d in range(sync.ROTATION):
        ranges = sync.ranges_for(date.fromordinal(today.toordinal() + d), False)
        assert ranges[-1] == (date.fromordinal(recent + d), date.fromordinal(today.toordinal() + d + 1))
        covered |= {a for a, _ in ranges[:-1]}
    assert covered == {a for a, _ in sync.months(sync.FIRST_DAY, date.fromordinal(recent))}     # every month in a week
    assert sync.ranges_for(today, True) == [(sync.FIRST_DAY, date(2026, 10, 28))]
    assert sync.ranges_for(today, False, since=date(2026, 10, 1)) == [(date(2026, 10, 1), date(2026, 10, 28))]


def test_a_row_is_written_only_when_the_source_changed_it():
    sync = importlib.import_module("sync_ft_partner_search")
    assert "ON CONFLICT (announcement_id) DO UPDATE SET" in sync.UPSERT_ANNOUNCEMENTS
    assert "WHERE t.pic IS DISTINCT FROM EXCLUDED.pic OR" in sync.UPSERT_ANNOUNCEMENTS
    assert all(f"t.{c} IS DISTINCT FROM EXCLUDED.{c}" in sync.UPSERT_ANNOUNCEMENTS for c in sync.ANNOUNCEMENT_COLUMNS)
    assert all(f"t.{c} IS DISTINCT FROM EXCLUDED.{c}" in sync.UPSERT_ORGS for c in sync.ORG_COLUMNS)


class _Conn:
    def __init__(self, held=1):
        self.sql, self.commits, self.held = [], 0, held

    def cursor(self):
        conn = self

        class _Cur:
            rowcount = 0

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                conn.sql.append((" ".join(sql.split()), params))

            def fetchone(self):
                return (conn.held,)
        return _Cur()

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def _run(monkeypatch, *, profiles, ranges, argv=("--apply",), held=1):
    sync = importlib.import_module("sync_ft_partner_search")
    conn, written = _Conn(held), []

    class _PS:
        def __init__(self, session, sleep):
            pass

        def profiles(self):
            return profiles

        def announcement_slices(self, a, b):
            rows, count, complete = ranges[(a, b)]
            yield a, b, count, rows, complete
    monkeypatch.setattr(sync, "PartnerSearch", _PS)
    monkeypatch.setattr(sync, "get_env", lambda k: "postgresql://x")
    monkeypatch.setattr(sync.psycopg2, "connect", lambda url: conn)
    monkeypatch.setattr(sync.psycopg2.extras, "execute_values", lambda cur, sql, rows, page_size: written.append((sql, rows)))
    monkeypatch.setattr(sync, "ranges_for", lambda today, full, since, until: list(ranges))
    return sync.main(list(argv)), conn, written


def _ann(aid, day="2026-10-20"):
    return {"announcement_id": aid, "pic": "9", "organisation_name": "Example SL", "country": "ES",
            "organisation_type": "Other", "expertise": "offer", "topic_id": "T-1", "topic_ids": ["T-1"],
            "topic_title": "A topic", "summary": "text", "summary_cut": False, "requested_date": day,
            "indexed_at": None, "public_url": "https://example.test/9"}


def test_deletions_only_where_the_read_was_complete(monkeypatch):
    org = {"pic": "9", "name": "Example SL", "city": None, "country": "ES", "organisation_type": "Other",
           "projects": 0, "portal_announcements": 1, "topics": [], "public_url": "u"}
    r1, r2 = (date(2026, 9, 1), date(2026, 10, 1)), (date(2026, 10, 13), date(2026, 10, 28))
    code, conn, written = _run(monkeypatch, profiles=([org], 1, True),
                               ranges={r1: ([_ann("1", "2026-09-05")], 1, True), r2: ([_ann("2")], 2, False)})
    assert code == 0
    deletes = [p for s, p in conn.sql if s.startswith("DELETE FROM ft_partner_search_announcements")]
    assert deletes == [(r1[0], r1[1], ["1"])]                     # the incomplete range deletes nothing
    assert [p for s, p in conn.sql if s.startswith("DELETE FROM ft_partner_search_orgs")] == [(["9"],)]
    rows = [r for s, batch in written if "ft_partner_search_announcements" in s for r in batch]
    assert sorted(r[0] for r in rows) == ["1", "2"] and all(r[-2] for r in rows)      # body_txt composed
    # Each slice is written as soon as it is read, before the next is asked for.
    assert [len(batch) for s, batch in written if "ft_partner_search_announcements" in s] == [1, 1]
    # Profiles read incompletely: no organisation is deleted.
    code, conn, _ = _run(monkeypatch, profiles=([org], 2, False), ranges={r1: ([_ann("1")], 1, True)})
    assert not [s for s, p in conn.sql if s.startswith("DELETE FROM ft_partner_search_orgs")]


def test_a_sample_or_a_dry_run_deletes_nothing(monkeypatch):
    org = {"pic": "9", "name": "Example SL", "city": None, "country": "ES", "organisation_type": "Other",
           "projects": 0, "portal_announcements": 1, "topics": [], "public_url": "u"}
    r1 = (date(2026, 9, 1), date(2026, 10, 1))
    code, conn, written = _run(monkeypatch, profiles=([org], 1, True),
                               ranges={r1: ([_ann("1", "2026-09-05"), _ann("2", "2026-09-06")], 2, True)},
                               argv=("--apply", "--limit", "1"))
    assert code == 0 and not [s for s, p in conn.sql if s.startswith("DELETE")]
    assert [len(batch) for s, batch in written if "ft_partner_search_announcements" in s] == [1]
    code, conn, written = _run(monkeypatch, profiles=([org], 1, True), ranges={r1: ([_ann("1", "2026-09-05")], 1, True)},
                               argv=())
    assert code == 0 and conn.sql == [] and written == []

def test_a_run_that_finds_no_profile_fails_and_touches_nothing(monkeypatch):
    rng = (date(2026, 10, 1), date(2026, 10, 2))
    code, conn, written = _run(monkeypatch, profiles=([], 0, True), ranges={rng: ([_ann("1", "2026-10-01")], 1, True)})
    assert code == 1 and conn.sql == [] and written == []


def test_an_index_that_lists_far_fewer_than_held_deletes_nothing(monkeypatch, capsys):
    org = {"pic": "9", "name": "Example SL", "city": None, "country": "ES", "organisation_type": "Other",
           "projects": 0, "portal_announcements": 1, "topics": [], "public_url": "u"}
    rng = (date(2026, 9, 1), date(2026, 10, 1))
    code, conn, _ = _run(monkeypatch, profiles=([org], 1, True), ranges={rng: ([_ann("1", "2026-09-05")], 1, True)}, held=500)
    assert code == 0 and not [s for s, p in conn.sql if s.startswith("DELETE FROM ft_partner_search_announcements")]
    assert "deletions held back" in capsys.readouterr().out
    # An empty listing deletes nothing either.
    code, conn, _ = _run(monkeypatch, profiles=([org], 1, True), ranges={rng: ([], 0, True)}, held=500)
    assert not [s for s, p in conn.sql if s.startswith("DELETE FROM ft_partner_search_announcements")]


# --- the routes ------------------------------------------------------------------------------------------- #
class _Db:
    def __init__(self, row=None):
        self.calls, self.row = [], row

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        rows = [self.row] if self.row else []
        return SimpleNamespace(scalar=lambda: len(rows), fetchall=lambda: rows, fetchone=lambda: self.row,
                               mappings=lambda: SimpleNamespace(all=lambda: []))


def _client(db):
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def _row(**kw):
    base = dict(announcement_id="900001", pic="900000001", organisation_name="Example Sensors SL", country="ES",
                organisation_type="Small or medium-size enterprise", expertise="request", topic_id="HORIZON-CL4-2026-01-01",
                topic_ids=["HORIZON-CL4-2026-01-01"], topic_title="An example topic", summary="We seek a partner.",
                summary_cut=False, requested_date=date(2026, 10, 20), public_url="https://example.test/org/900000001",
                first_seen=None, last_updated=None, city="Madrid", projects=0, topic_status="open", topic_deadline=None,
                body_txt="t", body_html="<p>t</p>")
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_announcement_list_filters_on_the_announcements_and_pages_before_joining():
    from api.v2.funding import partner_announcements as pa
    db = _Db(_row())
    r = _client(db).get("/api/v2/funding/partner-announcements", params={
        "q": "sensor", "topic": "HORIZON-CL4", "programme": "HORIZON", "status": "open", "expertise": "request",
        "organisation_type": "Small", "country": "GR", "without_eu_projects": "true", "since": "2026-01-01"})
    assert r.status_code == 200, r.text
    count_sql, params = db.calls[0]
    assert "FROM ft_partner_search_announcements s WHERE true" in count_sql and "JOIN" not in count_sql
    assert f"{pa._TSV} @@ websearch_to_tsquery('english', :q)" in count_sql
    assert "s.topic_id IN (SELECT topic_id FROM ft_calls_for_proposals WHERE status = :status AND is_test = false)" in count_sql
    assert "s.pic IN (SELECT pic FROM ft_partner_search_orgs WHERE projects = 0)" in count_sql
    assert (params["topic"], params["programme"], params["cc"], params["start"]) == ("HORIZON-CL4%", "%HORIZON%", "EL", date(2026, 1, 1))
    page_sql = db.calls[1][0]
    assert page_sql.strip().startswith("WITH page AS (SELECT s.announcement_id FROM ft_partner_search_announcements s WHERE true")
    assert "LEFT JOIN ft_calls_for_proposals t ON t.topic_id = s.topic_id" in page_sql
    item = r.json()["data"][0]
    assert (item["id"], item["item_type"], item["status"], item["expertise"]) == ("900001", "partner_announcement", "open", "request")
    org = item["organisations"][0]
    assert (org["role"], org["projects"], org["partner"].split("/partners/")[1]) == ("partner", 0, "pic:900000001")
    assert _client(_Db()).get("/api/v2/funding/partner-announcements", params={"expertise": "both"}).status_code == 400
    assert _client(_Db()).get("/api/v2/funding/partner-announcements", params={"status": "live"}).status_code == 400


def test_an_announcement_item_carries_its_body_and_a_missing_one_is_404():
    r = _client(_Db(_row())).get("/api/v2/funding/partner-announcements/900001")
    assert r.status_code == 200, r.text
    assert (r.json()["body_txt"], r.json()["document_date"]) == ("t", "2026-10-20")
    assert _client(_Db()).get("/api/v2/funding/partner-announcements/1").status_code == 404


def test_the_index_expression_is_the_one_the_queries_use():
    from api.v2.funding import partner_announcements as pa
    from api.v2.funding import partners
    sql = (BACKEND / "migrations" / "316_ft_partner_search.sql").read_text()
    expr = "to_tsvector('english', coalesce(topic_title, '') || ' ' || coalesce(summary, ''))"
    assert expr in sql
    assert pa._TSV == partners._ANNOUNCEMENT_TSV == expr.replace("topic_title", "s.topic_title").replace("(summary", "(s.summary")
    for table in ("ft_partner_search_orgs", "ft_partner_search_announcements"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"GRANT SELECT ON public.{table} TO anon, authenticated" in sql and f"GRANT ALL ON public.{table} TO service_role" in sql


def test_partners_take_the_announcements_by_their_pic():
    from api.v2.funding import partners
    db = _Db()
    r = _client(db).get("/api/v2/funding/partners", params={"q": "sensor", "topic": "HORIZON-CL4", "is_sme": "true",
                                                           "since": "2026-01-01"})
    assert r.status_code == 200, r.text
    sql = db.calls[-1][0]
    assert "'announcement' AS kind" in sql and "FROM ft_partner_search_announcements s LEFT JOIN ft_partner_search_orgs o" in sql
    assert f"{partners._ANNOUNCEMENT_TSV} @@ websearch_to_tsquery('english', :q)" in sql
    assert "s.topic_id ILIKE :topic_prefix" in sql and "s.requested_date >= :since" in sql
    assert f"(s.organisation_type = '{partners._SME_TYPE}') AS is_sme" in sql and "s.expertise AS role" in sql
    assert "count(DISTINCT ref) FILTER (WHERE kind = 'announcement') AS announcements" in sql
    # No department, no CORDIS activity type: dg or activity_type leaves the announcements out.
    for extra in ({"dg": "CNECT"}, {"activity_type": "REC"}):
        db = _Db()
        _client(db).get("/api/v2/funding/partners", params={"q": "ai", **extra})
        assert "ft_partner_search_announcements" not in db.calls[-1][0], extra
    db = _Db()
    _client(db).get("/api/v2/funding/partners/pic:900000001")
    assert "s.pic = :key_val" in db.calls[-1][0]
    # An announcement's partner is always pic:<PIC>: a vat: or name: key never reads them.
    for key in ("vat:ESB00000000", "name:es:example-sensors-sl"):
        db = _Db()
        _client(db).get(f"/api/v2/funding/partners/{key}")
        assert "ft_partner_search_announcements" not in db.calls[-1][0], key
    # A programme's name reaches the topics through its code.
    db = _Db()
    _client(db).get("/api/v2/funding/partners", params={"q": "ai", "programme": "Horizon Europe"})
    sql, params = db.calls[-1]
    assert "s.topic_id ILIKE ANY(CAST(:prog_topics AS text[]))" in sql and params["prog_topics"] == ["HORIZON-%"]
    db = _Db()
    _client(db).get("/api/v2/funding/partner-announcements", params={"programme": "Connecting Europe"})
    assert db.calls[0][1]["prog_topics"] == ["CEF-%"]
    db = _Db()
    _client(db).get("/api/v2/funding/partners", params={"q": "ai", "source": "announcements"})
    sql = db.calls[-1][0]
    assert "ft_partner_search_announcements" in sql and "ted_award_winners" not in sql and "FROM fts_commitments c" not in sql


def test_an_announcement_match_links_to_its_own_route():
    from api.v2.funding import partners
    r = SimpleNamespace(key="pic:9", name="Example SL", short_name=None, pic="9", vat=None, country="ES", city=None,
                        activity_type=None, is_sme=True, projects=0, coordinated=0, payments=0, contracts=0, awards=0,
                        announcements=1, eu_contribution=None, amount_eur=None, last_day=None, created=None, changed=None,
                        matches=[{"kind": "announcement", "id": "900001", "title": "A topic", "role": "request",
                                  "programme": "T-1", "date": "2026-10-20", "department": None, "eu_contribution": None,
                                  "amount_eur": None, "tender_value_eur": None}])
    item = partners._item(r, "https://api.test")
    assert item.matches[0].self == "https://api.test/api/v2/funding/partner-announcements/900001"
    assert item.announcements == 1 and "Matching Partner Search announcements: 1" in item.body_txt


def test_the_partner_search_runs_daily_and_is_recorded_by_the_tier():
    src = (BACKEND / "api" / "cron.py").read_text()
    assert '"partner_search", "scripts/sync_ft_partner_search.py", ["--apply"]' in src
    from api import cron
    assert "partner_search" in cron._DAILY_TIER_RECORDED
