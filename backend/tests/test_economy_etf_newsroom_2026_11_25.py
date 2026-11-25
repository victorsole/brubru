"""ETF moved its newsroom to /en/media-centre/newsroom/ around 20 Nov 2026 (old addresses
301 to the same slug there); the scraper, still reading /news-and-events/, parsed 0 items
for three runs. The listing and link prefix now follow the new path."""
from pathlib import Path

from services.scrapers import economy_etf as etf

FIXTURE = Path(__file__).parent / "fixtures" / "etf" / "newsroom_2026_11_25.html"


def test_listing_points_at_the_media_centre():
    assert etf.NEWS_PAGES[0][0].endswith("/en/media-centre/newsroom")
    assert etf.EVENT_PAGES[0][0].endswith("/en/media-centre/events")


def test_newsroom_cards_parse_with_titles_and_dates():
    items = etf._parse(FIXTURE.read_text(encoding="utf-8"), etf.NEWS_PAGES[0][1])
    assert len(items) == 4
    url, title, when = items[0]
    assert url.startswith("https://www.etf.europa.eu/en/media-centre/newsroom/")
    assert len(title) >= 10
    assert when is not None
