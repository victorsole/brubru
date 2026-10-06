"""Economy ingestors skip items already stored complete (6 Oct 2026).

SRB, Parliament and EUDA failed every economy run on the 600s timeout because each run
re-fetched everything it listed. The upsert never shortens a stored body, so a known
item needs no fetch; a new, incomplete or recent one always gets one.
"""
from datetime import datetime, timedelta, timezone

import pytest

from services.scrapers import economy_common as ec

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=90)


@pytest.fixture(autouse=True)
def _registry():
    ec._KNOWN.clear()
    ec.set_known("srb", "publication", [
        ("https://srb/a.pdf", "A", OLD, 5000, "a"),
        ("https://srb/short.pdf", "S", OLD, 40, "s"),
        ("https://srb/recent.pdf", "R", NOW - timedelta(days=3), 5000, "r"),
        ("https://srb/undated.pdf", "U", None, 5000, "u"),
        ("https://srb/untitled.pdf", None, OLD, 5000, "t"),
    ])
    yield
    ec._KNOWN.clear()


@pytest.mark.parametrize("url, kwargs, expected", [
    ("https://srb/new.pdf", {}, True),                    # never seen
    ("https://srb/a.pdf", {}, False),                     # stored complete, old
    ("https://srb/short.pdf", {}, True),                  # body too short
    ("https://srb/short.pdf", {"want_body": False}, False),
    ("https://srb/recent.pdf", {}, True),                 # publishers correct recent items
    ("https://srb/undated.pdf", {}, True),                # a date is still owed
    ("https://srb/undated.pdf", {"want_date": False}, False),
    ("https://srb/untitled.pdf", {}, True),
])
def test_needs_fetch(url, kwargs, expected):
    assert ec.needs_fetch("srb", "publication", url, now=NOW, **kwargs) is expected


def test_outside_the_sync_nothing_is_skipped():
    ec._KNOWN.clear()
    assert ec.needs_fetch("srb", "publication", "https://srb/a.pdf", now=NOW)


def test_srb_publications_fetch_only_what_is_missing(monkeypatch):
    from services.scrapers import economy_srb as srb

    class Page:
        text = "<html></html>"
    monkeypatch.setattr(srb, "_get", lambda url: Page() if url.endswith("documents") else None)
    monkeypatch.setattr(srb, "_parse_register_rows", lambda html: [
        ("https://srb/a.pdf", "A", OLD), ("https://srb/new.pdf", "N", NOW)])
    monkeypatch.setattr(srb.time, "sleep", lambda s: None)
    fetched = []
    monkeypatch.setattr(srb, "_fetch_detail_spaced",
                        lambda url: fetched.append(url) or ("text " * 100, "<p>x</p>", "pdf"))
    items = srb.ingest_srb_publications(max_pages=1)
    assert fetched == ["https://srb/new.pdf"]
    assert {i.public_url for i in items} == {"https://srb/a.pdf", "https://srb/new.pdf"}
    assert next(i for i in items if i.public_url == "https://srb/a.pdf").body_txt is None


def _walked_years(monkeypatch, stored: bool, **kw):
    from services.scrapers import ep_supporting_analyses as sa
    if stored:
        ec.set_known("parliament", "supporting_analysis", [("https://ep/x", "X", OLD, 900, "x")])
    years = []
    monkeypatch.setattr(sa, "walk_year", lambda s, y: years.append(y) or iter(()))
    sa.ingest_supporting_analyses(**kw)
    return years


def test_supporting_analyses_walk_two_years_once_stored(monkeypatch):
    years = _walked_years(monkeypatch, stored=True)
    this_year = datetime.now(timezone.utc).year
    assert this_year in years and len(years) in (2, 3)  # 3 only in January
    assert all(1992 <= y <= this_year for y in years)


def test_supporting_analyses_walk_everything_on_first_fill(monkeypatch):
    years = _walked_years(monkeypatch, stored=False)
    assert years[-1] == 1992 and len(years) == datetime.now(timezone.utc).year - 1991


def test_an_explicit_backfill_still_walks_every_year(monkeypatch):
    years = _walked_years(monkeypatch, stored=True, first_year=2020)
    assert years[-1] == 2020 and len(years) == datetime.now(timezone.utc).year - 2019
