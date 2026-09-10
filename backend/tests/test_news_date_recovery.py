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
