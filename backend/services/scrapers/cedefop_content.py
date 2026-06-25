"""Cedefop — news, events, publications (generic EU-agency listing walker) + topics."""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, http_get, extract_html
from services.scrapers.eu_agency_listing import walk

_BASE = "https://www.cedefop.europa.eu"

# Curated about / theme / tool landing pages, snapshotted as topics.
_TOPIC_PATHS = [
    "/en/about-cedefop/who-we-are",
    "/en/about-cedefop/what-we-do",
    "/en/themes/skills-labour-market",
    "/en/themes/vet-knowledge-centre",
    "/en/themes/delivering-vet-qualifications",
    "/en/themes/statistics",
    "/en/tools/european-skills-index",
    "/en/tools/european-vet-policy-dashboard",
    "/en/tools/skills-forecast",
    "/en/tools/skills-intelligence",
    "/en/tools/matching-skills",
    "/en/tools/european-skills-jobs-survey",
    "/en/tools/apprenticeship-schemes",
    "/en/tools/validation-non-formal-informal-learning",
    "/en/tools/mobility-scoreboard",
    "/en/tools/vet-glossary",
    "/en/tools/key-indicators-on-vet",
    "/en/tools/skills-online-vacancies",
]


def ingest_cedefop_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 2:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code="cedefop", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items


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
