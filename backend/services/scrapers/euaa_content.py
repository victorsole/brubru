"""EUAA — news, publications (generic EU-agency listing walker) + topics."""
from __future__ import annotations

from services.scrapers.economy_common import Item, snapshot_topics
from services.scrapers.eu_agency_listing import walk

_BASE = "https://www.euaa.europa.eu"

# Curated about + asylum-knowledge + operations landing pages, as topics.
_TOPIC_PATHS = [
    "/about-us/who-we-are",
    "/about-us/what-we-do",
    "/about-us/governance-and-internal-control",
    "/about-us/legal-basis",
    "/about-us/management-board",
    "/asylum-knowledge",
    "/asylum-knowledge/asylum-report",
    "/asylum-knowledge/country-guidance",
    "/asylum-knowledge/courts-and-tribunals",
    "/asylum-knowledge/data-analysis-and-research",
    "/asylum-knowledge/dublin-procedure",
    "/asylum-knowledge/information-and-analysis-developments-asylum",
    "/asylum-knowledge/medcoi-medical-country-origin-information",
    "/asylum-knowledge/monitoring-ceas",
    "/asylum-knowledge/reception",
    "/asylum-knowledge/vulnerability",
    "/country-origin-information",
    "/operations",
    "/operations/country-operations",
    "/operations/operational-assistance",
    "/operations/resettlement",
    "/complaints-mechanism",
    "/euaa-fundamental-rights-officer",
]


def ingest_euaa_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("euaa", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)


def ingest_euaa_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/news-events/press-releases", "euaa", "news", "/news-events/", "euaa_drupal")


def ingest_euaa_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/publications", "euaa", "publication", "/publications/", "euaa_drupal")
