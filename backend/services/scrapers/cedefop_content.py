"""Cedefop — news, events, publications (generic EU-agency listing walker)."""
from __future__ import annotations

from services.scrapers.economy_common import Item
from services.scrapers.eu_agency_listing import walk

_BASE = "https://www.cedefop.europa.eu"


def ingest_cedefop_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/en/news", "cedefop", "news", "/en/news/", "cedefop_drupal")


def ingest_cedefop_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    upcoming = walk(_BASE, "/en/events", "cedefop", "event", "/en/events/", "cedefop_drupal")
    past = walk(_BASE, "/en/events/past-events", "cedefop", "event", "/en/events/", "cedefop_drupal")
    seen = {i.guid for i in upcoming}
    return upcoming + [i for i in past if i.guid not in seen]


def ingest_cedefop_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/en/publications", "cedefop", "publication", "/en/publications/",
                "cedefop_drupal")
