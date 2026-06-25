"""
HaDEA — European Health and Digital Executive Agency (api_ec.md L3806-3836).
/api/v2/hadea.

HaDEA runs on the EU ECL stack (hadea.ec.europa.eu), server-rendered and reachable
with plain requests. Source map (verified 25 Jun 2026):
  - news    : /news_en             — ECL .ecl-content-item cards with <time>.
  - events  : /events_en           — same ECL layout.
  - call    : /calls-proposals_en  — open calls for proposals (funding), ECL cards.
  - tender  : /calls-tenders_en     — procurement calls for tenders, ECL cards.
  - topic   : curated about / programme landing pages.

HaDEA manages EU funding programmes in health and digital: EU4Health, the Single
Market Programme (food), Horizon Europe health/digital clusters, the Connecting
Europe Facility (digital) and the Digital Europe Programme. Reads from economy_items
(body row seeded by migration 159); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, snapshot_topics,
)

_BASE = "https://hadea.ec.europa.eu"

NEWS_PAGES = [f"{_BASE}/news_en"]
EVENT_PAGES = [f"{_BASE}/events_en"]
CALL_PAGES = [f"{_BASE}/calls-proposals_en"]
TENDER_PAGES = [f"{_BASE}/calls-tenders_en"]

_TOPIC_PATHS = [
    "/about_en",
    "/about/legal-base-and-key-documents_en",
    "/about/programmes-funding_en",
    "/about/our-staff-our-agency_en",
    "/programmes_en",
    "/programmes/eu4health_en",
    "/programmes/single-market-programme-food_en",
    "/programmes/horizon-europe_en",
    "/programmes/connecting-europe-facility_en",
    "/programmes/digital-europe-programme_en",
]


def ingest_hadea_news(*, fetch_bodies: bool = True, max_pages: int = 1, **_) -> list[Item]:
    # The news listing server-renders ~100 items per page; one page is a deep
    # enough archive and keeps the nightly body-fetch load bounded.
    return scrape_ecl_listing("hadea", "news", NEWS_PAGES, _BASE,
                              fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_hadea_events(**kw) -> list[Item]:
    return scrape_ecl_listing("hadea", "event", EVENT_PAGES, _BASE, **kw)


def ingest_hadea_calls(**kw) -> list[Item]:
    return scrape_ecl_listing("hadea", "call", CALL_PAGES, _BASE, **kw)


def ingest_hadea_tenders(**kw) -> list[Item]:
    return scrape_ecl_listing("hadea", "tender", TENDER_PAGES, _BASE, **kw)


def ingest_hadea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("hadea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
