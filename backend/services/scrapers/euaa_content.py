"""EUAA — news, publications (generic EU-agency listing walker)."""
from __future__ import annotations

from services.scrapers.economy_common import Item
from services.scrapers.eu_agency_listing import walk

_BASE = "https://www.euaa.europa.eu"


def ingest_euaa_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/news-events/press-releases", "euaa", "news", "/news-events/", "euaa_drupal")


def ingest_euaa_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/publications", "euaa", "publication", "/publications/", "euaa_drupal")
