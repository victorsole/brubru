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


# --- the same rule for every ingestor, in the one function they all fetch through ----
# 13 Oct 2026: the skip above lived in three scrapers. The other 43 re-fetched every item
# they listed on every run and timed out whenever a source was slow: 10 of the 54 "Deploy
# Crashed" mails of 6-13 October. ESMA's publications stage ran past 16 minutes against a
# 10-minute limit; inside the scope it takes 13 seconds.

class _Resp:
    headers = {"content-type": "text/html"}
    text = "<html><body><main><p>" + ("A real article body. " * 40) + "</p></main></body></html>"
    content = b""


@pytest.fixture
def http(monkeypatch):
    asked = []
    monkeypatch.setattr(ec, "http_get", lambda url: asked.append(url) or _Resp())
    yield asked
    ec.clear_scope()


def _old_complete(url):
    return [(url, "A stored title", datetime.now(timezone.utc) - timedelta(days=90), 5000, url)]


def test_inside_a_sync_an_item_stored_complete_is_not_fetched(http):
    ec._KNOWN.clear()
    ec.set_scope("esma", "publication", lambda: _old_complete("https://esma/a.pdf"))
    assert ec.fetch_detail_dated("https://esma/a.pdf") == (None, None, "known", None, None)
    assert ec.fetch_detail("https://esma/a.pdf") == (None, None, "known")
    assert http == []
    # A new item on the same listing is fetched as before.
    body_txt, _html, kind, _dt, _carrier = ec.fetch_detail_dated("https://esma/new")
    assert kind == "html" and body_txt and http == ["https://esma/new"]


def test_outside_a_sync_every_item_is_fetched_as_before(http):
    ec._KNOWN.clear()
    ec.set_known("esma", "publication", _old_complete("https://esma/a.pdf"))
    assert ec._SCOPE is None
    assert ec.fetch_detail_dated("https://esma/a.pdf")[2] != "known"
    assert http == ["https://esma/a.pdf"]


def test_the_stored_rows_are_read_once_and_only_if_an_item_page_is_asked(http):
    ec._KNOWN.clear()
    reads = []
    ec.set_scope("esma", "publication", lambda: reads.append(1) or _old_complete("https://esma/a.pdf"))
    assert reads == []                      # a bulk dataset that reads no item page never pays
    ec.fetch_detail_dated("https://esma/a.pdf")
    ec.fetch_detail_dated("https://esma/b")
    ec.fetch_detail_dated("https://esma/a.pdf")
    assert reads == [1]


def test_stored_rows_that_cannot_be_read_mean_fetch_everything(http, capsys):
    ec._KNOWN.clear()

    def broken():
        raise RuntimeError("connection dropped")
    ec.set_scope("esma", "publication", broken)
    assert ec.fetch_detail_dated("https://esma/a.pdf")[2] != "known"
    assert http == ["https://esma/a.pdf"]
    assert "fetching every item" in capsys.readouterr().out


def test_one_scope_does_not_answer_for_another(http):
    ec._KNOWN.clear()
    ec.set_known("esma", "publication", _old_complete("https://esma/a.pdf"))
    ec.set_scope("esma", "news", lambda: [])
    assert ec.fetch_detail_dated("https://esma/a.pdf")[2] != "known"
    assert http == ["https://esma/a.pdf"]


def test_the_sync_sets_the_scope_for_the_ingestor_and_always_clears_it(monkeypatch):
    from scripts import sync_economy as se
    seen = {}

    def ingestor(fetch_bodies=True):
        seen["scope"] = ec._SCOPE[:2] if ec._SCOPE else None
        raise RuntimeError("the source is down")
    monkeypatch.setitem(se.INGESTORS, ("esma", "publication"), ingestor)
    with pytest.raises(RuntimeError):
        se._run_one(object(), "esma", "publication", fetch_bodies=True, legal_limit=1)
    assert seen["scope"] == ("esma", "publication")
    assert ec._SCOPE is None
    # An explicit full re-read, and a run that reads no bodies, set no scope.
    for kwargs in ({"refetch_all": True}, {"fetch_bodies": False}):
        seen.clear()
        with pytest.raises(RuntimeError):
            se._run_one(object(), "esma", "publication",
                        **{"fetch_bodies": True, "legal_limit": 1, **kwargs})
        assert seen["scope"] is None


def test_no_ingestor_reaches_an_item_page_around_the_shared_function():
    """Every item-page fetch goes through fetch_detail / fetch_detail_dated, or the skip
    above does not cover it. A scraper that needs its own pacing wraps one of them."""
    import pathlib
    import re
    scrapers = pathlib.Path(ec.__file__).parent
    src = (scrapers / "economy_common.py").read_text(encoding="utf-8")
    body = src[src.index("def fetch_detail(url"):src.index("def fetch_detail_dated(url")]
    assert "fetch_detail_dated(url)" in body          # the 3-value form is a wrapper of the other
    dated = src[src.index("def fetch_detail_dated(url"):]
    assert dated.index("stored_complete(url)") < dated.index("http_get(url)")
    users = [p.name for p in scrapers.glob("economy_*.py")
             if p.name != "economy_common.py" and re.search(r"\bfetch_detail(_dated)?\(", p.read_text(encoding="utf-8"))]
    assert len(users) >= 40, users
