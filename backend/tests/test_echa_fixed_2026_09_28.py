"""ECHA end to end (28 Sep 2026): dates, the new news page, the retry, the ledger.

Before: every ECHA news item since 17 Aug was refused as undated (the date sits in
<dd class="NewsDate">DD/MM/YYYY</dd> and nothing read it; the article pages carry
none), the economy scraper read an archive ECHA stopped updating and reported
success on 0 new rows, the weekly archive answered Railway with a challenge on 8 runs
in 3 days, and Terraqui's ledger called a normal five-week news gap STALE."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

import services.scrapers.bespoke_news_scraper as b
from services.scrapers.echa_news import _parse_news

CARD = """<div class="TRow"><dl><dt><a href="/-/szilvia-deim-appointed-chair-of-echas-management-board">
Szilvia Deim appointed chair of ECHA's Management Board</a></dt><dd class="NewsDate">24/09/2026</dd>
<dd><p>The Management Board has elected its Hungarian member.</p></dd></dl></div>
<div class="TRow"><dl><dt><a href="/-/echa-convenes-first-collaborative-platform-on-alternatives">
ECHA convenes first Collaborative Platform on Alternatives to Animal Testing meeting</a></dt>
<dd class="NewsDate">17/06/2026 | REACH | CLP | BPR</dd></dl></div>"""


def _cfg():
    return [c for c in b.BESPOKE_SOURCES if c.get("institution") == "ECHA" and "e-news" not in c["url"]][0]


def test_bespoke_reads_the_news_date_class_day_first():
    got = {i["title"][:20]: i["news_date"] for i in b.parse_bespoke(CARD, _cfg())}
    assert got["Szilvia Deim appoint"] == date(2026, 9, 24)
    assert got["ECHA convenes first "] == date(2026, 6, 17)       # with regulation tags after it


def test_numeric_date_outside_a_date_class_is_not_read():
    card = BeautifulSoup('<div><a href="/-/x">Title here long</a><span>09/10/2026</span></div>', "html.parser")
    assert b._card_class_numeric_date(card) is None


def test_two_different_dates_in_date_classes_are_refused():
    card = BeautifulSoup('<div><dd class="NewsDate">24/09/2026</dd><span class="date">01/10/2026</span></div>',
                         "html.parser")
    assert b._card_class_numeric_date(card) is None


def test_economy_parser_reads_the_news_page():
    items = _parse_news(CARD, datetime.now(timezone.utc))
    assert [i.document_date.date() for i in items] == [date(2026, 9, 24), date(2026, 6, 17)]
    assert items[0].public_url.endswith("/-/szilvia-deim-appointed-chair-of-echas-management-board")


def test_one_retry_after_a_challenge_then_success():
    class Res:
        def __init__(self, html, status):
            self.html, self.nav_status = html, status
    calls = []

    class Fetcher:
        def fetch(self, url, **k):
            calls.append(url)
            return Res("<html>challenge</html>", 403) if len(calls) == 1 else Res(CARD, 200)
    import time
    orig = time.sleep
    time.sleep = lambda s: None
    try:
        items = b.scrape_bespoke(dict(_cfg(), rss=None), Fetcher())
    finally:
        time.sleep = orig
    assert len(calls) == 2 and len(items) == 2


def test_ledger_reads_news_and_weekly_at_a_weekly_cadence():
    p = Path(__file__).resolve().parents[1] / "data" / "client_sources" / "terraqui_dpp_tex.json"
    d = json.loads(p.read_text())
    src = d["sources"] if isinstance(d, dict) else d
    echa = [s for s in src if s["key"] == "echa"][0]
    assert "eu_news_items" in echa["sql"] and "economy_items" in echa["sql"]
    assert echa["stale_after_days"] == 10
