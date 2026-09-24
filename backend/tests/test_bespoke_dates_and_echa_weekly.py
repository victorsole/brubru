"""ECHA went 37 days without a news item, and it was not ECHA being quiet (24 Sep 2026).

Checked at the source: ECHA's news ALERTS really did stop on 17 August (its alerts
archive's newest entry is that day), because the live stream moved to the weekly, which
it publishes every Tuesday and which we were not reading at all. The feed therefore
showed a 37-day-old agency that had published the day before.

The weekly's date is in its URL with the month spelled out
(`.../echa-weekly-23-september-2026`), and `date_re` only read numeric groups, so every
weekly would have arrived undated and the write guard would have refused the lot. Two
things are tested here: the date reader, and the listing whose link text is only a day
("23 September") needing its title built rather than guessed from the URL slug.

No network.
"""
from __future__ import annotations

import re
from datetime import date

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

from services.scrapers.bespoke_news_scraper import (  # noqa: E402
    BESPOKE_SOURCES,
    _date_from_url,
    parse_bespoke,
)

ECHA_WEEKLY = next(c for c in BESPOKE_SOURCES if c.get("source_key") == "ECHA_WEEKLY")
BASE = "https://echa.europa.eu/view-article/-/journal_content/title/"


# --------------------------------------------------------------------------- the date reader
@pytest.mark.parametrize("pattern,url,expected", [
    # what every numeric source here uses, unchanged
    (r"/press-releases/(\d{4})/(\d{2})/(\d{2})/",
     "https://www.consilium.europa.eu/en/press/press-releases/2026/09/23/thing/", date(2026, 9, 23)),
    # ECHA: day first, month spelled out, year last
    (ECHA_WEEKLY["date_re"], BASE + "echa-weekly-23-september-2026", date(2026, 9, 23)),
    (ECHA_WEEKLY["date_re"], BASE + "echa-weekly-1-july-2026", date(2026, 7, 1)),
    (ECHA_WEEKLY["date_re"], BASE + "echa-weekly-09-march-2026", date(2026, 3, 9)),
])
def test_a_url_that_names_a_day_is_read_whatever_the_order(pattern, url, expected):
    assert _date_from_url(re.compile(pattern), url) == expected


@pytest.mark.parametrize("pattern,url", [
    # A year or a month alone is NOT a publication date: reading one as the 1st put 57
    # FRA rows on 1 January and 50 CJEU rows on 1 April (15 Sep 2026).
    (r"/news/(\d{4})/", "https://fra.europa.eu/en/news/2026/some-story"),
    (r"/pdf/(\d{4})-(\d{2})/", "https://curia.europa.eu/pdf/2026-04/cp260051en.pdf"),
    # an impossible day must not become a date
    (ECHA_WEEKLY["date_re"], BASE + "echa-weekly-31-february-2026"),
    # a month that is not a month
    (ECHA_WEEKLY["date_re"], BASE + "echa-weekly-12-smarch-2026"),
])
def test_what_is_not_a_day_stays_undated(pattern, url):
    assert _date_from_url(re.compile(pattern), url) is None


def test_no_pattern_at_all_is_not_an_error():
    assert _date_from_url(None, BASE + "echa-weekly-23-september-2026") is None


# --------------------------------------------------------------------------- the listing
ARCHIVE_HTML = """
<html><body>
  <div class="archive">
    <h3>September</h3>
    <a href="/view-article/-/journal_content/title/echa-weekly-23-september-2026">23 September</a>
    <a href="/view-article/-/journal_content/title/echa-weekly-16-september-2026">16 September</a>
    <h3>August</h3>
    <a href="/view-article/-/journal_content/title/echa-weekly-26-august-2026">26 August</a>
    <a href="/news-and-events/e-news-archive">e-news archive</a>
    <a href="/news">News</a>
  </div>
</body></html>
"""


def test_the_weekly_listing_yields_dated_items_with_a_real_title():
    items = parse_bespoke(ARCHIVE_HTML, ECHA_WEEKLY)
    assert [i["news_date"] for i in items] == [date(2026, 9, 23), date(2026, 9, 16), date(2026, 8, 26)]
    # Without the template the title is the URL slug: "Echa weekly 23 september 2026".
    assert [i["title"] for i in items] == [
        "ECHA Weekly, 23 September 2026",
        "ECHA Weekly, 16 September 2026",
        "ECHA Weekly, 26 August 2026",
    ]
    assert {i["item_type"] for i in items} == {"news"}
    assert {i["source_key"] for i in items} == {"ECHA_WEEKLY"}


def test_the_listing_page_itself_is_not_an_item():
    """The archive link and the news hub both sit in the page and are not weeklies."""
    urls = {i["source_url"] for i in parse_bespoke(ARCHIVE_HTML, ECHA_WEEKLY)}
    assert not any(u.endswith("/e-news-archive") or u.endswith("/news") for u in urls)


def test_the_weekly_is_a_type_the_news_feed_actually_serves():
    """/api/v2/news serves eu_news_items rows of these types only. A 'newsletter' or
    'publication' row would be stored and still invisible, which is how a source can be
    fixed and still look silent."""
    from api.v2.news import _EU_NEWS_SOURCE_TYPES

    assert ECHA_WEEKLY["type"] in _EU_NEWS_SOURCE_TYPES


def test_the_news_alerts_source_is_still_there():
    """ECHA publishes alerts rarely now, but when it does they are the real news."""
    alerts = [c for c in BESPOKE_SOURCES
              if c["institution"] == "ECHA" and c.get("source_key") != "ECHA_WEEKLY"]
    assert len(alerts) == 1 and alerts[0]["url"].endswith("/news")


# --------------------------------------------------------------------------- machine tokens
# CPVO's image links carry alt="field_file_image_title_text" -- the Drupal FIELD NAME, not
# a description. At 27 characters it passed the length check and was stored as the title of
# a news item (found 24 Sep 2026 while auditing six "stale" agencies).
from services.scrapers.bespoke_news_scraper import _is_machine_token, _resolve_title_with_source  # noqa: E402


@pytest.mark.parametrize("value", [
    "field_file_image_title_text",
    "field_image_alt_text",
    "news-and-events-listing",
])
def test_a_machine_token_is_not_a_headline(value):
    assert _is_machine_token(value)


@pytest.mark.parametrize("value", [
    "Official Publications 4.2026",
    "EU-Australia trade deal signed",
    "CPVO and Dutch Board launch a harmonised form",
    "field_image",                     # two parts only: could be a real word pair
])
def test_a_real_title_is_not_mistaken_for_one(value):
    assert not _is_machine_token(value)


def test_the_alt_placeholder_never_becomes_the_title():
    """Falls through to the slug, which is a poor title but a TRUE one."""
    title, source = _resolve_title_with_source(
        attrs='href="/en/news-and-events/news/official-publications-42026"',
        inner='<img src="x.png" alt="field_file_image_title_text">',
        path="/en/news-and-events/news/official-publications-42026",
    )
    assert source == "slug" and "field_" not in (title or "")
