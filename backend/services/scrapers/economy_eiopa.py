"""
EIOPA — European Insurance and Occupational Pensions Authority
(/api/v2/eu-financial-institutions/eiopa).

Verified source map (URL-verification pass, api_econ.md L416-470): no RSS, but
every listing is a server-rendered EU ECL (.ecl-content-item) view with a
<time datetime> ISO date, paginated. Reuses the generic scrape_ecl_listing.

  - news         : news + interviews-contributions + feature-articles + speeches
  - publications : the document library
  - events       : the events listing

No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import scrape_ecl_listing, Item

_BASE = "https://www.eiopa.europa.eu"

EIOPA_NEWS = [
    f"{_BASE}/media/news_en",
    f"{_BASE}/media/interviews-contributions_en",
    f"{_BASE}/media/feature-articles_en",
    f"{_BASE}/media/speeches-presentations_en",
]
EIOPA_PUBLICATIONS = [f"{_BASE}/document-library_en"]
EIOPA_EVENTS = [f"{_BASE}/media/events_en"]


def ingest_eiopa_news(**kw) -> list[Item]:
    return scrape_ecl_listing("eiopa", "news", EIOPA_NEWS, _BASE, **kw)


def ingest_eiopa_publications(**kw) -> list[Item]:
    return scrape_ecl_listing("eiopa", "publication", EIOPA_PUBLICATIONS, _BASE, **kw)


def ingest_eiopa_events(**kw) -> list[Item]:
    return scrape_ecl_listing("eiopa", "event", EIOPA_EVENTS, _BASE, **kw)
