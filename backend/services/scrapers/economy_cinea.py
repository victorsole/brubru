"""
CINEA — European Climate, Infrastructure and Environment Executive Agency
(api_ec.md L3712-3756). /api/v2/cinea.

CINEA runs on the EU ECL stack (cinea.ec.europa.eu), server-rendered and reachable
with plain requests. Source map (verified 25 Jun 2026):
  - news   : /news-events/news_en    — ECL .ecl-content-item cards with <time
             datetime>; ?page=N paginated. Detail = HTML.
  - events : /news-events/events_en  — same ECL card layout, with event dates.
  - topic  : curated about / programme / funding / Green Assist landing pages.

CINEA's executive-agency role is to manage funding programmes (CEF Energy, Horizon
Europe energy, LIFE clean-energy transition, the Renewable Energy Financing
Mechanism) and the Green Assist advisory service. Reads from economy_items (body
row seeded by migration 157); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, snapshot_topics,
)

_BASE = "https://cinea.ec.europa.eu"

NEWS_PAGES = [f"{_BASE}/news-events/news_en"]
EVENT_PAGES = [f"{_BASE}/news-events/events_en"]

_TOPIC_PATHS = [
    "/about-us_en",
    "/about-us/mission-structure-and-objectives_en",
    "/about-us/key-documents_en",
    "/about-us/key-documents/work-programme_en",
    "/about-us/transparency_en",
    "/programmes_en",
    "/programmes/connecting-europe-facility/energy-infrastructure-connecting-europe-facility-0_en",
    "/programmes/horizon-europe/energy-supply-horizon-europe_en",
    "/programmes/renewable-energy-financing-mechanism_en",
    "/programmes/life/clean-energy-transition_en",
    "/programmes/communication-and-raising-eu-visibility_en",
    "/funding-opportunities_en",
    "/funding-opportunities/calls-proposals_en",
    "/funding-opportunities/calls-tenders_en",
    "/funding-opportunities/find-your-funding-programme-0_en",
    "/green-assist-green-advisory-service-sustainable-investments-support_en",
    "/green-assist-project-advisory_en",
    "/beneficiaries-corner_en",
    "/beneficiaries-corner/projects_en",
]


def ingest_cinea_news(**kw) -> list[Item]:
    return scrape_ecl_listing("cinea", "news", NEWS_PAGES, _BASE, **kw)


def ingest_cinea_events(**kw) -> list[Item]:
    return scrape_ecl_listing("cinea", "event", EVENT_PAGES, _BASE, **kw)


def ingest_cinea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cinea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
