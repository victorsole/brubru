"""A call's or tender's deadline is never stored as its date (20 Oct 2026).

Read on /api/v2/funding: expert lists open until 2029 sorted to the top of /funding/all as if
published in 2029. agency_procurement._build stored the deadline when a listing printed no
publication date (EUAA, Eurojust, EUDA, ETF, ERA); EEAS tender cards and HaDEA tender cards
print their deadline where a news card prints its date; FTS rows took a project start in 2028;
funded projects their 2027 start date. Victor's rule (ECDC, 30 Sep): the publication date, else
NULL, never the deadline.
"""
import importlib
import io
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

ec = importlib.import_module("services.scrapers.economy_common")
ap = importlib.import_module("services.scrapers.agency_procurement")
NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def test_a_listing_without_a_publication_date_stores_none_not_the_deadline():
    it = ap._build(body_code="euaa", item_type="eoi_call", title="Call for Expressions of Interest",
                   url="https://euaa.europa.eu/procurements/cei", reference="EUAA/MLA/2024/CEI/0023",
                   status="Open", deadline=datetime(2029, 12, 19, tzinfo=timezone.utc), now=NOW,
                   source_kind="euaa_procurement")
    assert it.document_date is None
    assert "2029-12-19" in it.body_txt          # the deadline is still said, in the body


def test_the_euaa_page_names_its_publication_date():
    page = ("<main><h1>Call for Expressions of Interest (CEI)</h1><p>Reference: EUAA/MLA/2024/CEI/0023</p>"
            "<p>Dispatched: 19/12/2024 Published on the EUAA website: 20/12/2024</p>"
            "<p>Validity CEI until: 19/12/2029</p><p>Deadline: 19 December 2029</p></main>")
    d, carrier = ec.extract_item_date(page, today=NOW)
    assert d.date() == date(2024, 12, 20) and carrier == "published_on_website_label"


def _card(meta: str) -> str:
    return (f'<div class="ecl-content-item"><div class="ecl-content-block__title">'
            f'<a href="/calls/x_en">A call</a></div><div>{meta}</div></div>')


def test_an_ecl_call_card_is_dated_by_its_opening_date_and_a_tender_card_not_at_all():
    call = _card('Call status: Open Opening date <time datetime="2026-11-25T12:00:00Z">25 November 2026</time>'
                 ' Deadline date 2 February 2027')
    tender = _card('Call status: Ongoing Deadline date <time datetime="2026-12-08T11:00:00Z">8 December 2026</time>')
    news = _card('<time datetime="2026-10-14T12:00:00Z">14 October 2026</time> News')
    dates = [ec._parse_ecl_cards(h, "https://hadea.ec.europa.eu")[0][2] for h in (call, tender, news)]
    assert dates[0].date() == date(2026, 11, 25)     # a forthcoming call opens in the future: its date
    assert dates[1] is None                           # a deadline is not a publication date
    assert dates[2].date() == date(2026, 10, 14)      # other cards unchanged


def test_listing_only_agencies_read_each_items_page(monkeypatch):
    items = [ap._build(body_code="eurojust", item_type="tender", title="Provision of ICT services",
                       url=f"https://www.eurojust.europa.eu/procurement/p{n}", reference=f"EJ/{n}",
                       status="Open", deadline=datetime(2026, 11, 4, tzinfo=timezone.utc), now=NOW,
                       source_kind="eurojust_procurement") for n in range(3)]
    pages = {
        items[0].public_url: ("Provision of ICT services ... Publication Date 18/09/2026 " * 10, "<p>page</p>", "html",
                              datetime(2026, 9, 17, 22, tzinfo=timezone.utc), "time_datetime"),
        items[1].public_url: (None, None, "known", None, None),          # stored complete: untouched
        items[2].public_url: (None, None, "unreachable", None, None),
    }
    monkeypatch.setattr(ec, "fetch_detail_dated", lambda url: pages[url])
    out = ap._from_item_pages(items)
    assert out[0].document_date.date() == date(2026, 9, 17) and len(out[0].body_txt) > 300
    assert out[1].document_date is None and out[2].document_date is None
    assert "Deadline: 2026-11-04" in out[2].body_txt


def test_a_funded_project_is_dated_by_its_publication_never_a_future_start():
    fc = importlib.import_module("api.v1.funding_tenders_collections")
    today = datetime.now(timezone.utc)
    r = SimpleNamespace(published_at=datetime(2026, 3, 18), start_date=date(2027, 10, 1))
    assert fc._project_date(r) == date(2026, 3, 18)
    r = SimpleNamespace(published_at=None, start_date=(today - timedelta(days=40)).date())
    assert fc._project_date(r) == (today - timedelta(days=40)).date()
    r = SimpleNamespace(published_at=None, start_date=(today + timedelta(days=400)).date())
    assert fc._project_date(r) is None


def test_an_fts_row_starting_in_the_future_keeps_its_start_in_the_body(monkeypatch):
    from openpyxl import Workbook
    cf = importlib.import_module("services.scrapers.commission_funding")
    wb = Workbook(); ws = wb.active
    ws.append(["Name of beneficiary", "Commitment total amount", "Programme name", "Project start date", "Beneficiary country"])
    ws.append(["MESSETURM PROPCO", 31678, "DA/JU/EUI", "2028-04-01", "Luxembourg"])
    ws.append(["UNIVERSITA DI ROMA", 1000, "Horizon Europe", "2025-01-01", "Italy"])
    buf = io.BytesIO(); wb.save(buf)
    monkeypatch.setattr(cf.requests, "get", lambda *a, **k: SimpleNamespace(content=buf.getvalue()))
    items = {i.title: i for i in cf.ingest_eu_funding_recipients(year=2025)}
    future, past = items["MESSETURM PROPCO"], items["UNIVERSITA DI ROMA"]
    assert future.document_date is None and "Project start: 2028-04-01" in future.body_txt
    assert past.document_date.date() == date(2025, 1, 1)
