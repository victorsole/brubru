"""
ESDC — European Security and Defence College (api_defence.md). /api/v2/esdc.

esdc.europa.eu is a Drupal/ECL site, server-rendered and reachable with plain
requests; it exposes a news RSS feed. Source map (verified 25 Jun 2026):
  - news  : /node/2/rss_en — the ESDC news RSS feed (20 items with dates).
  - topic : about-us, the network, training-and-education and the training
            configurations (climate, cyber, doctoral school, military Erasmus, ...).

The ESDC is the EU's network college that trains civilian and military personnel
for CSDP missions and operations. Reads from economy_items (body row seeded by
migration 178); 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from services.scrapers.economy_common import Item, snapshot_topics
from services.scrapers.economy_ecb import ingest_feeds

_BASE = "https://www.esdc.europa.eu"
NEWS_FEEDS = [f"{_BASE}/node/2/rss_en"]

_TOPIC_PATHS = [
    "/about-us-0_en",
    "/about-us-0/mission_en",
    "/about-us-0/history_en",
    "/about-us-0/structure_en",
    "/about-us-0/network_en",
    "/training-and-education_en",
    "/training-and-education/course-catalogue-and-curricula_en",
    "/training-and-education/how-join-network_en",
    "/configurations_en",
    "/configurations/climate-change-environment-security-and-defence_en",
    "/configurations/missions-and-operations-training_en",
    "/configurations/eabcyber_en",
    "/configurations/doctoral-school_en",
    "/configurations/military-erasmus_en",
    "/configurations/eumssf_en",
    "/configurations/war-colleges-initiative_en",
    "/faq_en",
]


def ingest_esdc_news(**kw) -> list[Item]:
    return ingest_feeds("esdc", "news", NEWS_FEEDS, **kw)


def ingest_esdc_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("esdc", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
