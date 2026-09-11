"""Date recovery for the two news stores (10 September 2026).

Guards three defects found on 10 September, each of which had produced a
confident wrong reading before it was found:

  1. A page that RENDERS its date client-side reads as `no_carrier` on the
     static HTML. The ECA serves 157KB with no <time>, no meta, no JSON-LD and
     no date class; the rendered page opens with
     `<time class="date" datetime="09/09/2026">`. Sixteen rows, including the
     REPowerEU special report, were written off as undatable.
  2. EIT publishes its date in `<div class="date-place">`, which fails the
     generic "class ends in -date" shape test.
  3. Both publish DD/MM/YYYY, which is silently wrong if read as MM/DD.
"""
import pathlib
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.scrapers.economy_common import (  # noqa: E402
    extract_item_date, _PUBLICATION_DATE_CLASSES, _NON_PUBLICATION_DATE_CLASSES,
)
from scripts.backfill_news_document_dates import _TABLES  # noqa: E402
from scripts.backfill_news_document_dates import _STORED_BODIES  # noqa: E402
from services.scrapers.economy_common import extract_brussels_dateline  # noqa: E402


@pytest.mark.parametrize("html,expected,carrier", [
    # ECA, as rendered. DD/MM proven across 5 pages: first field ranged 6-19,
    # second never exceeded 12, and news-2024-12-19-fraud-warning's slug agrees
    # with its own datetime attribute.
    ('<time class="date" datetime="19/12/2024">', "2024-12-19", "time_datetime"),
    ('<time class="date" datetime="09/09/2026">', "2026-09-09", "time_datetime"),
    ('<time class="date" datetime="07/07/2026">', "2026-07-07", "time_datetime"),
    # EIT byline element.
    ('<div class="metadata"><div class="date-place">17/12/2025</div></div>',
     "2025-12-17", "date_class"),
    # ISO still works.
    ('<time datetime="2026-07-01T00:00:00Z"></time>', "2026-07-01", "time_datetime"),
])
def test_carriers_parse_the_publisher_date(html, expected, carrier):
    dt, got = extract_item_date(html)
    assert dt is not None, f"no date extracted from {html!r}"
    assert dt.date().isoformat() == expected
    assert got == carrier


@pytest.mark.parametrize("cls", ["event-date", "deadline-date", "expiry-date",
                                 "start-date", "closing-date", "updated-date"])
def test_non_publication_date_classes_are_still_refused(cls):
    """The allowlist must not have re-opened the door the blocklist guards.

    An event or deadline date is often in the past and would be stored as a
    publication date with nothing looking wrong.
    """
    dt, _ = extract_item_date(f'<div class="{cls}">17/12/2025</div>')
    assert dt is None, f"{cls} was accepted as a publication date"


def test_publication_class_allowlist_stays_an_allowlist():
    """Relaxing the shape test to startswith('date') would re-admit every class
    the blocklist exists to exclude, so the widening is enumerated."""
    assert isinstance(_PUBLICATION_DATE_CLASSES, tuple)
    assert "date-place" in _PUBLICATION_DATE_CLASSES
    for bad in _NON_PUBLICATION_DATE_CLASSES:
        assert bad not in _PUBLICATION_DATE_CLASSES


def test_future_and_ancient_dates_are_refused():
    """A future publication date is not a publication date: a scraped deadline
    once set the corpus freshness anchor to 2031."""
    assert extract_item_date('<time datetime="2031-01-01T00:00:00Z"></time>')[0] is None
    assert extract_item_date('<time datetime="1889-01-01T00:00:00Z"></time>')[0] is None


def test_both_news_stores_are_profiled():
    assert set(_TABLES) == {"economy_items", "eu_news_items"}
    for name, p in _TABLES.items():
        for key in ("table", "pk", "date_col", "url_col", "body_col",
                    "text_col", "order_col", "where_extra"):
            assert p.get(key), f"{name} profile is missing {key}"


def test_profile_columns_exist_in_the_database():
    """A profile naming a column that does not exist fails at query time and the
    surface prints '-', which reads as 'nobody used it'. 359 feed subscriptions
    were invisible that way until this morning."""
    import os
    from dotenv import load_dotenv
    load_dotenv(str(BACKEND / ".env"))
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set in this environment")
    from sqlalchemy import create_engine, text
    conn = create_engine(os.environ["DATABASE_URL"]).connect()
    try:
        for name, p in _TABLES.items():
            cols = {r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t"), {"t": p["table"]})}
            assert cols, f"table {p['table']} does not exist"
            for key in ("pk", "date_col", "url_col", "body_col", "text_col", "order_col"):
                assert p[key] in cols, f"{name}.{key} = {p[key]!r} is not a column of {p['table']}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# EDPS / EDPB press-release datelines (11 September 2026)
#
# All 20 EDPS press releases were undated -- the whole type, frozen since the
# August 2026 migration made ingest_edps_press_releases intentionally empty. It was
# first written off as unrecoverable. It was not: every release prints its date as
# `Brussels, <day> <Month> <year>`, but PDF extraction splits the glyphs, and the
# dates at the TOP of each release are the event, not the publication. Every
# expected value below was checked against the raw PDF text and, for the joint
# releases, against the EDPB's own page.
# ---------------------------------------------------------------------------
_EDPS_PDF = "https://www.edps.europa.eu/system/files/{}/release.pdf"


@pytest.mark.parametrize("text,folder,expected,provenance", [
    # Biotech Act joint release: the day is split "1 2"; a contiguous scan read 2 March.
    ("safeguards Brussels, 1 2 March 2026 \u2013 The European", "2026-03",
     "2026-03-12", "brussels_dateline"),
    # US-EU security screenings: token AND year split; the opening line says 17 September.
    ("PRESS RELEASE EDPS/2025/09 Brusse ls, 18 September 202 5 2 Background", "2025-09",
     "2025-09-18", "brussels_dateline"),
    # Entry/Exit System: opens "entered into operation on 12 October" (the event).
    ("entered into operation on 12 October 2025 ... Brusse ls, 24 October 2025 2 Ba",
     "2025-10", "2025-10-24", "brussels_dateline"),
    # UN Cybercrime Convention: opens "On 4 September 2025, the EDPS issued an Opinion".
    ("On 4 September 2025, the EDPS issued an Opinion ... Brusse ls, 9 September 2025 2",
     "2025-09", "2025-09-09", "brussels_dateline"),
    # NIS2 joint release: EDPB page metadata says 19 May; the document says 19 March.
    ("protecting individuals' personal data Brussels, 1 9 March 2026 \u2013", "2026-03",
     "2026-03-19", "brussels_dateline"),
    # AI Act joint release: yearless; EDPB's page confirms 21 January 2026.
    ("safeguards Brussels, 21 January - The European Data Protection Board", "2026-01",
     "2026-01-21", "brussels_dateline_day_folder_year"),
])
def test_edps_dateline_reads_the_release_date_not_the_opening_date(text, folder, expected, provenance):
    dt, got = extract_brussels_dateline(text, _EDPS_PDF.format(folder))
    assert dt is not None, f"no date from {text!r}"
    assert dt.date().isoformat() == expected
    assert got == provenance


@pytest.mark.parametrize("text,url,provenance", [
    # Two different datelines: the document is ambiguous.
    ("Brussels, 3 March 2026 ... Brussels, 9 March 2026", _EDPS_PDF.format("2026-03"),
     "brussels_dateline_multi"),
    # A dateline outside its upload month: a fused digit or wrong year is refused.
    ("Brussels, 28 February 2026 \u2013", _EDPS_PDF.format("2026-03"),
     "brussels_dateline_folder_mismatch"),
    # Yearless "28 December" uploaded in January would otherwise be stored a year out.
    ("Brussels, 28 December - The EDPB", _EDPS_PDF.format("2026-01"),
     "brussels_dateline_yearless_month_mismatch"),
    # Yearless with no upload folder to anchor a year.
    ("Brussels, 21 January - The EDPB", "https://example.invalid/no-folder.pdf",
     "brussels_dateline_yearless_unanchored"),
    # The EDPS boilerplate mentions Brussels without a date.
    ("the EDPS, based in Brussels and Luxembourg, supervises", _EDPS_PDF.format("2026-03"),
     "none"),
    ("Brussels, 12 March 2099 \u2013", _EDPS_PDF.format("2099-03"),
     "brussels_dateline_out_of_bounds"),
])
def test_edps_dateline_refuses_rather_than_guesses(text, url, provenance):
    dt, got = extract_brussels_dateline(text, url)
    assert dt is None, f"accepted {dt} from {text!r}"
    assert got == provenance


def test_backfill_routes_edps_to_the_dateline_resolver():
    """The press-release ingestor returns [] on purpose, so the stored PDF text is
    the only place these dates will ever be read from."""
    assert _STORED_BODIES["edps"] is extract_brussels_dateline

