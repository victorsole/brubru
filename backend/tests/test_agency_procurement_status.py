"""EU bodies' own procurement items carry a status, a deadline and a reference (26 Oct 2026).

Most writers had the status and the deadline in hand and wrote them only into the text, so on 26
Oct 388 tenders, grants and calls had no status and none a deadline, nothing could close them, and
17 lists did not serve the fields at all. The rule is services/funding/agency_status.py; the phrases
below are the stored pages' own (EEAS delegations, HaDEA, the F&T programme calls).
"""
import asyncio
import importlib
import io
import pathlib
import sys
import types
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from services.funding import agency_status as ag  # noqa: E402

TODAY = date(2026, 10, 26)
D = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731


def test_the_dates_win_over_the_word():
    assert ag.from_source("Open", D(2026, 8, 31), TODAY) == "closed"         # an "Open" left behind
    assert ag.from_source("Upcoming", D(2026, 10, 15), TODAY) == "closed"
    assert ag.from_source("Open", D(2026, 10, 26), TODAY) == "open"          # the deadline day counts
    assert ag.from_source("Upcoming", D(2027, 2, 17), TODAY) == "forthcoming"
    assert ag.from_source("closed", D(2027, 1, 1), TODAY) == "closed"
    assert ag.from_source("Low-value contract", D(2027, 1, 1), TODAY) == "open"   # a kind, not a word
    assert ag.from_source("Ongoing", None, TODAY) == "open"
    assert ag.from_source(None, None, TODAY) is None and ag.from_source("unknown", None, TODAY) is None


@pytest.mark.parametrize("text,expected", [
    ("Deadline to express interest (inscription): 30 October 2026 at 17h30 (Timor-Leste local time)", D(2026, 10, 30)),
    ("Deadline for expressions of interest: 31 October 2026, 16:00 (Cambodian local time)", D(2026, 10, 31)),
    ("deadline to express your interest (to the email below): 29/10/2026 at 24h00 Indicative date for "
     "launching the invitation to tender: 10/11/2026", D(2026, 10, 29)),
    ("Deadline to express your interest (inscription): 3rd November 2026 Sending of invitation", D(2026, 11, 3)),
    ("The deadline for submitting expressions of interest is 2 nd November 2026 at 23:00", D(2026, 11, 2)),
    ("Deadline to express interest: 14 th October 2026 Email to address", D(2026, 10, 14)),
    ("Deadline for expressions of interest: 30.06.2026 (12:00 Rome time)", D(2026, 6, 30)),
    ("Details Status Open Publication date 3 March 2026 Opening date 3 March 2026 Deadline model "
     "Single-stage Deadline date 15 September 2026", D(2026, 9, 15)),
])
def test_a_labelled_deadline_is_read_whatever_its_format(text, expected):
    assert ag.deadline_in_text(text) == (expected, False)


def test_an_unlabelled_date_is_no_deadline_and_a_closed_one_is_closed():
    assert ag.deadline_in_text("Publication date 23 July 2026. Contract signed 4 May 2026.") == (None, False)
    assert ag.deadline_in_text("Once the deadline for inscription (expression of interest) is closed, "
                               "you will be added to the list") == (None, True)


def test_a_page_gives_its_labelled_facts():
    word, ref, deadline = ag.page_facts(
        "Details Status Upcoming Reference HADEA/2026/OP/0020 Publication date 23 July 2026 "
        "Deadline date 15 October 2026, 17:00 (CEST) Programme EU4Health")
    assert (word, ref, deadline) == ("Upcoming", "HADEA/2026/OP/0020", D(2026, 10, 15))
    assert ag.page_facts("s Details Status Upcoming Reference HORIZON-HLTH-2027-02-DISEASE-01-two-stage "
                         "Publication date 8 October 2026")[1] == "HORIZON-HLTH-2027-02-DISEASE-01-two-stage"
    assert ag.page_facts("Tender status Closed Launch date 10 Aug 2026 Deadline 24 Sep 2026")[0] == "Closed"


# --- the writers ------------------------------------------------------------------------------ #

def test_build_fills_the_columns_and_shows_the_derived_word():
    from services.scrapers import agency_procurement as ap
    now = D(2026, 10, 26)
    past = ap._build(body_code="euda", item_type="tender", title="T", url="https://x/1", reference="EUDA/2026/OP/0003",
                     status="Open", deadline=D(2026, 6, 1), now=now, source_kind="euda_procurement")
    assert past.extras == {"tender_reference": "EUDA/2026/OP/0003", "status": "closed", "deadline": D(2026, 6, 1)}
    assert "Status: closed" in past.body_txt and "Open" not in past.summary
    era = ap._build(body_code="era", item_type="tender", title="T", url="https://x/2", reference="a-url-slug",
                    status="Open", deadline=D(2026, 12, 31), now=now, source_kind="era_procurement",
                    published_reference=False)
    assert era.extras["tender_reference"] is None and era.extras["status"] == "open"
    unlabelled = ap._build(body_code="etf", item_type="tender", title="T", url="https://x/3", status="",
                           deadline=None, now=now, source_kind="etf_procurement")
    assert unlabelled.extras["status"] is None


def test_the_listings_we_labelled_open_send_no_word(monkeypatch):
    from services.scrapers import agency_procurement as ap
    seen = {}
    monkeypatch.setattr(ap, "_fetch", lambda url: "")
    monkeypatch.setattr(ap, "_from_item_pages", lambda items, fetch_bodies=True: items)
    monkeypatch.setattr(ap, "parse_field_cards", lambda *a, **kw: seen.setdefault("etf", kw["status"]) and [])
    monkeypatch.setattr(ap, "parse_positional_table",
                        lambda *a, **kw: seen.setdefault(kw["body_code"], kw["status"]) and [])
    ap.ingest_etf_tenders(fetch_bodies=False)
    ap.ingest_euaa_calls(fetch_bodies=False)
    ap.ingest_euda_tenders(fetch_bodies=False)
    assert seen == {"etf": "", "euaa": "", "euda": ""}


def test_the_programme_calls_write_the_columns(monkeypatch):
    mod = importlib.import_module("ingest_ft_programme_calls")
    conflict = " ".join(mod.UPSERT_SQL.split("ON CONFLICT", 1)[1].split())
    for col in ("tender_reference", "status", "deadline"):
        assert f"{col} = COALESCE(EXCLUDED.{col}, economy_items.{col})" in conflict
    pages = iter([{"results": [{"raw": 1}]}])
    monkeypatch.setattr(mod, "fetch_sedia_page", lambda *a, **kw: next(pages, None))
    monkeypatch.setattr(mod, "normalise_row", lambda r: {
        "topic_id": "JUST-2027-JTRA", "title": "Judicial training", "status": "forthcoming",
        "deadline": datetime(2027, 3, 4), "published_at": None, "record_type": "1"})
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    written = []
    cur = SimpleNamespace(execute=lambda sql, p: written.append(p))
    assert mod.ingest_programme(cur, "justice", apply=True) == 1
    p = written[0]
    assert (p["tender_reference"], p["status"], p["deadline"]) == ("JUST-2027-JTRA", "forthcoming", datetime(2027, 3, 4))


def test_an_ecl_page_fills_the_columns(monkeypatch):
    from services.scrapers import economy_common as ec
    monkeypatch.setattr(ec, "http_get", lambda url: SimpleNamespace(text="<html/>"))
    cards = iter([[("https://hadea.ec.europa.eu/t/1", "A tender", None, None)], []])
    monkeypatch.setattr(ec, "_parse_ecl_cards", lambda html, base: next(cards))
    page = ("Details Status Upcoming Reference HADEA/2099/OP/0001 Publication date 23 July 2026 "
            "Deadline date 15 October 2099, 17:00 (CEST)")
    monkeypatch.setattr(ec, "fetch_detail_dated", lambda url: (page, "<p/>", "html", None, None))
    [it] = ec.scrape_ecl_listing("hadea", "tender", ["https://hadea.ec.europa.eu/t"], "https://hadea.ec.europa.eu")
    assert it.extras == {"tender_reference": "HADEA/2099/OP/0001", "deadline": D(2099, 10, 15), "status": "forthcoming"}


def test_an_eeas_tender_takes_its_page_deadline(monkeypatch):
    from services.scrapers import economy_eeas as ee

    class _Page:
        async def evaluate(self, js):
            return [{"href": "/delegations/x/call_en", "title": "Supply of generators", "date": "2026-10-29"}]

    class _Browser:
        async def new_context(self, **kw): return SimpleNamespace(new_page=self._page)
        async def _page(self): return _Page()
        async def close(self): pass

    class _PW:
        async def __aenter__(self):
            async def launch(**kw): return _Browser()
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        async def __aexit__(self, *a): return False

    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", SimpleNamespace(async_playwright=_PW))

    async def _render(page, url, **kw): return "<html/>"
    monkeypatch.setattr(ee, "_render", _render)
    monkeypatch.setattr(ee, "extract_html", lambda html: (
        "Supply of generators. Deadline for submission of tenders: 27/11/2099.", "<p/>"))
    monkeypatch.setattr(ee, "extract_item_date", lambda html: (None, None))
    [it] = asyncio.run(ee._scrape_listing("tender", "/x", fetch_bodies=True, scrolls=0, body_cap=5))
    assert it.extras == {"tender_reference": None, "deadline": D(2099, 11, 27), "status": "open"}
    assert it.document_date is None          # the card's date is not taken as a publication date


# --- the routes and the daily pass ------------------------------------------------------------ #

def test_every_procurement_list_serves_the_three_fields():
    from main import app
    without = []
    for r in app.routes:
        ep = getattr(r, "endpoint", None)
        if not ep or not getattr(ep, "__closure__", None) or r.path.endswith("}") or "/documents" in r.path:
            continue
        cv = dict(zip(ep.__code__.co_freevars, (c.cell_contents for c in ep.__closure__)))
        if cv.get("item_type") in ag.ITEM_TYPES and "body_code" in cv and not cv.get("procurement"):
            without.append(r.path)
    assert without == []


def test_the_daily_pass_closes_what_has_passed():
    calls = []

    class _Db:
        def __init__(self, n): self.n = n
        def execute(self, stmt, params=None):
            calls.append((str(stmt), params))
            return SimpleNamespace(scalar=lambda: self.n)
        def commit(self): calls.append(("COMMIT", None))

    assert ag.close_passed(_Db(0), apply=True) == 0 and not any(s.startswith("UPDATE") for s, _ in calls)
    assert ag.close_passed(_Db(3), apply=True) == 3
    upd = [(s, p) for s, p in calls if s.startswith("UPDATE")]
    assert len(upd) == 1 and "deadline::date < CURRENT_DATE" in upd[0][0]
    assert upd[0][1]["types"] == list(ag.ITEM_TYPES)


def test_the_tender_status_job_runs_the_pass(monkeypatch):
    mod = importlib.import_module("scripts.refresh_tender_status")
    monkeypatch.setattr(mod, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(mod, "refresh", lambda db, apply: {})
    monkeypatch.setattr(mod, "close_passed", lambda db, apply: 4)
    # and, since 28 Oct 2026, the TED notices in ft_calls_for_tenders from their TED row (O96)
    from collections import Counter
    monkeypatch.setattr(mod, "sync_ft_copies", lambda db, apply: Counter({("open", "closed"): 205}))
    out = io.StringIO()
    with redirect_stdout(out):
        assert mod.main(["--apply"]) == 0
    assert "4 EU body procurement item(s) past their deadline closed" in out.getvalue()
    assert "open -> closed: 205" in out.getvalue()
    assert "205 TED notice(s) in ft_calls_for_tenders set from the TED row" in out.getvalue()


# --- the backfill ----------------------------------------------------------------------------- #

def _stored(**kw):
    base = dict(body_code="euda", item_type="tender", source_kind="euda_procurement", guid=None,
                summary=None, body_txt="")
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_backfill_reads_what_each_row_holds():
    from scripts.backfill_agency_status import derive
    # the summary is rewritten every run, the body is not: the summary's deadline is the newer one
    r = _stored(guid="EUDA/2026/OP/0006", summary="EUDA/2026/OP/0006 · Open · 2026-12-02",
                body_txt="T\nReference: EUDA/2026/OP/0006\nStatus: Open\nDeadline: 2026-11-16")
    assert derive(r, TODAY)[:3] == ("open", D(2026, 12, 2), "EUDA/2026/OP/0006")
    # our own "Open" over a whole listing is not the body's word
    assert derive(_stored(body_code="etf", source_kind="etf_procurement", summary="Open",
                          body_txt="Expertise provision. Four framework contracts."), TODAY)[0] is None
    # an EEAS page's own "Status: Ongoing" does not hide its passed deadline
    eeas = _stored(body_code="eeas", source_kind="html", guid="https://www.eeas.europa.eu/x",
                   body_txt="Deadline for expressions of interest: 30.06.2026 (12:00 Rome time) "
                            "PRACTICAL INFORMATION OVERVIEW\nStatus: Ongoing")
    assert derive(eeas, TODAY)[:3] == ("closed", D(2026, 6, 30), None)
    # SEDIA's "unknown" is no status; the topic id is the reference
    sedia = _stored(body_code="just", item_type="grant", source_kind="sedia", guid="JUST-JCOO-NETW-2017",
                    summary="Justice Programme · unknown", body_txt="T\nStatus: unknown")
    assert derive(sedia, TODAY)[:3] == (None, None, "JUST-JCOO-NETW-2017")
    era = _stored(body_code="era", source_kind="era_procurement", guid="a-url-slug",
                  summary="a-url-slug · Open · 2026-12-31", body_txt="T\nReference: a-url-slug")
    assert derive(era, TODAY)[:3] == ("open", D(2026, 12, 31), None)


# --- one row per (body, reference) ------------------------------------------------------------ #

def _it(url, ref, body="hadea", itype="call"):
    return SimpleNamespace(body_code=body, item_type=itype, public_url=url, extras={"tender_reference": ref})


def test_a_reference_printed_on_several_pages_goes_to_none_of_them():
    sync = importlib.import_module("scripts.sync_economy")
    items = [_it("https://h/space-1", "HORIZON-CL4-2026-03"), _it("https://h/space-2", "HORIZON-CL4-2026-03"),
             _it("https://h/other", "HORIZON-CL4-2027-06"), _it("https://e/1", "HORIZON-CL4-2026-03", body="eismea")]
    sync._shared_references_to_none(items)
    assert [i.extras["tender_reference"] for i in items] == [None, None, "HORIZON-CL4-2027-06", "HORIZON-CL4-2026-03"]


def test_a_reference_another_row_holds_is_not_sent_again():
    sync = importlib.import_module("scripts.sync_economy")
    seen = {}

    class _Cur:
        def execute(self, sql, params=None): seen["params"] = params
        def fetchall(self): return [("hadea", "HADEA/2026/OP/0020", "tender", "https://h/notice")]

    items = [_it("https://h/call", "HADEA/2026/OP/0020", itype="tender"),
             _it("https://h/notice", "HADEA/2026/OP/0020", itype="tender"), _it("https://h/new", "HADEA/2026/OP/0099", itype="tender")]
    sync._drop_references_held_elsewhere(SimpleNamespace(cur=_Cur()), items)
    assert [i.extras["tender_reference"] for i in items] == [None, "HADEA/2026/OP/0020", "HADEA/2026/OP/0099"]
    assert set(seen["params"][0]) == {("hadea", "HADEA/2026/OP/0020"), ("hadea", "HADEA/2026/OP/0099")}


def test_the_sync_applies_both_rules_around_the_repoint():
    import inspect
    sync = importlib.import_module("scripts.sync_economy")
    src = inspect.getsource(sync._run_one)
    assert (src.index("_shared_references_to_none(") < src.index("_repoint_by_reference(")
            < src.index("_drop_references_held_elsewhere(") < src.index("rows = ["))
