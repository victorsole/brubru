"""
EISMEA — European Innovation Council and SMEs Executive Agency
(api_ec.md L3838-3878). /api/v2/eismea.

EISMEA runs on the EU ECL stack (eismea.ec.europa.eu), server-rendered and
reachable with plain requests. Source map (verified 25 Jun 2026):
  - news         : /news_en                              — ECL .ecl-content-item.
  - events       : /events_en                            — same ECL layout (sparse).
  - publications : /documents_en                         — ECL .ecl-file document
                   library (work programmes, annual reports, accounts); PDFs.
  - call         : /funding-opportunities/calls-proposals_en — open calls for
                   proposals, ECL .ecl-content-item cards.
  - topic        : curated about / programme / funding landing pages.

(The /funding-opportunities/calls-tenders_en page lists no current tenders, so no
tenders resource is exposed.)

EISMEA manages the European Innovation Council, European Innovation Ecosystems, the
Single Market Programme and the Interregional Innovation Investments (I3)
instrument. Reads from economy_items (body row seeded by migration 160); 5
mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import (
    Item, scrape_ecl_listing, scrape_ecl_file_listing, snapshot_topics,
)

_BASE = "https://eismea.ec.europa.eu"

NEWS_PAGES = [f"{_BASE}/news_en"]
EVENT_PAGES = [f"{_BASE}/events_en"]
PUB_PAGES = [f"{_BASE}/documents_en"]
CALL_PAGES = [f"{_BASE}/funding-opportunities/calls-proposals_en"]

_TOPIC_PATHS = [
    "/about-eismea_en",
    "/programmes_en",
    "/programmes/european-innovation-council_en",
    "/programmes/european-innovation-ecosystems_en",
    "/programmes/single-market-programme_en",
    "/programmes/interregional-innovation-investments-i3-instrument_en",
    "/funding-opportunities_en",
    "/easme-documents_en",
]


def ingest_eismea_news(**kw) -> list[Item]:
    return scrape_ecl_listing("eismea", "news", NEWS_PAGES, _BASE, **kw)


def ingest_eismea_events(**kw) -> list[Item]:
    return scrape_ecl_listing("eismea", "event", EVENT_PAGES, _BASE, **kw)


def ingest_eismea_publications(**kw) -> list[Item]:
    return scrape_ecl_file_listing("eismea", "publication", PUB_PAGES, _BASE, **kw)


def ingest_eismea_calls(**kw) -> list[Item]:
    return scrape_ecl_listing("eismea", "call", CALL_PAGES, _BASE, **kw)


def ingest_eismea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eismea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
