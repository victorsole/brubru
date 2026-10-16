"""EPSO's selection site lists news as Drupal views rows, not ECL cards (16 Oct 2026)."""
from datetime import date

from services.scrapers.dg_news_scraper import parse_ecl_news, parse_views_rows
from services.scrapers import dg_news_sources

PAGE = """
<main>
<div class="list-group-item views-row"><div class="views-field views-field-changed">
<span class="views-label views-label-changed">Last updated: </span><span class="field-content">
<time datetime="2026-10-14T17:39:00+02:00" title="14/10/2026 - 17:39">14/10/2026 - 17:39</time></span></div>
<span class="views-field views-field-title"><h2 class="field-content">
<a href="/en/news/clarification-education-requirement/20909" hreflang="en">Clarification of education requirement</a></h2></span>
<div class="views-field views-field-body"><div class="field-content"><p>In the Notice of <strong>Competition</strong> point 3.3.1.</p></div></div></div>
<div class="list-group-item views-row"><div class="views-field views-field-changed">
<span class="field-content"><time datetime="2026-10-13T10:00:00+02:00">13/10/2026</time></span></div>
<span class="views-field views-field-title"><h2 class="field-content">
<a href="/en/news/ad5-testing/20908">AD5 Graduates Competition: Testing</a></h2></span></div>
</main>
"""


def test_views_rows_are_parsed_with_dates_and_absolute_urls():
    items = parse_views_rows(PAGE, "https://selection.eu-careers.europa.eu/en/news", "news")
    assert [i["title"] for i in items] == ["Clarification of education requirement", "AD5 Graduates Competition: Testing"]
    assert items[0]["news_date"] == date(2026, 10, 14)
    assert items[1]["news_date"] == date(2026, 10, 13)
    assert items[0]["source_url"] == "https://selection.eu-careers.europa.eu/en/news/clarification-education-requirement/20909"
    assert items[0]["summary"].startswith("In the Notice of Competition")
    assert items[1]["summary"] is None


def test_the_ecl_parser_cannot_read_this_page():
    # The defect this parser fixes: the default parser returned nothing for EPSO.
    assert parse_ecl_news(PAGE, "https://selection.eu-careers.europa.eu/en/news", "news") == []


def test_epso_source_points_at_the_selection_site_with_the_views_parser():
    srcs = [s for v in vars(dg_news_sources).values() if isinstance(v, list)
            for s in v if isinstance(s, dict) and s.get("agency") == "EPSO"]
    assert len(srcs) == 1
    assert srcs[0]["url"] == "https://selection.eu-careers.europa.eu/en/news"
    assert srcs[0]["kind"] == "views"
