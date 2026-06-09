"""
AMLA — Anti-Money Laundering Authority (api_econ.md L673-691).
/api/v2/eu-financial-institutions/amla.

AMLA runs on the EU ECL stack (amla.europa.eu). Source map (verified):
  - news         : /node/19/rss_en (Drupal RSS feed, dated) -> detail HTML.
  - publications : /resources/document-library_en — ECL .ecl-file cards
                   (title + date + /document/download/<uuid> PDF), ?page=N paginated.
  - events       : /policy/public-hearings_en — ECL .ecl-content-item cards with
                   an .ecl-date-block; plus speaking engagements where present.

No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, scrape_ecl_file_listing,
)
from services.scrapers.economy_ecb import ingest_feeds

_BASE = "https://www.amla.europa.eu"

AMLA_NEWS_FEEDS = [f"{_BASE}/node/19/rss_en"]
AMLA_PUB_PAGES = [f"{_BASE}/resources/document-library_en"]
AMLA_EVENT_PAGES = [
    f"{_BASE}/policy/public-hearings_en",
    f"{_BASE}/news-media/speaking-engagements_en",
]


def ingest_amla_news(**kw) -> list[Item]:
    return ingest_feeds("amla", "news", AMLA_NEWS_FEEDS, **kw)


def ingest_amla_publications(**kw) -> list[Item]:
    return scrape_ecl_file_listing("amla", "publication", AMLA_PUB_PAGES, _BASE, **kw)


def ingest_amla_events(**kw) -> list[Item]:
    return scrape_ecl_listing("amla", "event", AMLA_EVENT_PAGES, _BASE, **kw)
