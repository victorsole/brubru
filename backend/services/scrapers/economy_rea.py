"""
REA — European Research Executive Agency (api_ec.md L3933-3979). /api/v2/rea.

REA runs on the EU ECL stack (rea.ec.europa.eu), server-rendered and reachable with
plain requests. Source map (verified 25 Jun 2026):
  - news         : /news_en          — ECL .ecl-content-item cards with <time>.
  - events       : /events_en        — same ECL layout.
  - publications : /publications_en   — ECL .ecl-content-item listing (REA renders
                   its publications as content items, not a .ecl-file library).
  - topic        : curated about / funding-and-grants / guidance landing pages.

REA implements parts of Horizon Europe (clusters 2 and 3, the EU Soil Mission, the
Marie Sklodowska-Curie actions support) and the agricultural products promotion
programme. Reads from economy_items (body row seeded by migration 162); 5 mandatory
datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, snapshot_topics,
)

_BASE = "https://rea.ec.europa.eu"

NEWS_PAGES = [f"{_BASE}/news_en"]
EVENT_PAGES = [f"{_BASE}/events_en"]
PUB_PAGES = [f"{_BASE}/publications_en"]

_C2 = "/funding-and-grants/horizon-europe-cluster-2-culture-creativity-and-inclusive-society"
_C3 = "/funding-and-grants/horizon-europe-cluster-3-civil-security-society"

_TOPIC_PATHS = [
    "/about-rea_en",
    "/funding-and-grants_en",
    "/funding-and-grants/eu-mission-soil-deal-europe_en",
    f"{_C2}_en",
    f"{_C2}/democracy-and-governance_en",
    f"{_C2}/european-cultural-heritage-and-cultural-and-creative-industries_en",
    f"{_C2}/social-and-economic-transformations_en",
    f"{_C3}_en",
    f"{_C3}/disaster-resilient-society-europe_en",
    f"{_C3}/better-protect-eu-and-its-citizens-against-crime-and-terrorism_en",
    f"{_C3}/effective-management-eu-external-borders_en",
    f"{_C3}/resilient-infrastructures_en",
    "/funding-and-grants/promotion-agricultural-products-0_en",
    "/guidance_en",
    "/guidance/advice-applicants_en",
    "/guidance/advice-eu-projects_en",
    "/guidance/research-careers-eu_en",
    "/working-rea_en",
    "/transparency_en",
]


def ingest_rea_news(**kw) -> list[Item]:
    return scrape_ecl_listing("rea", "news", NEWS_PAGES, _BASE, **kw)


def ingest_rea_events(**kw) -> list[Item]:
    return scrape_ecl_listing("rea", "event", EVENT_PAGES, _BASE, **kw)


def ingest_rea_publications(**kw) -> list[Item]:
    return scrape_ecl_listing("rea", "publication", PUB_PAGES, _BASE, **kw)


def ingest_rea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("rea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
