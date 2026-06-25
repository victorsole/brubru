"""
Chips JU (api_euratom_ju.md). /api/v2/chips.

chips-ju.europa.eu runs a Dynamics-style CMS, server-rendered, plain requests. News
and events are link lists to /NewsDetails?id=<guid> and /EventsDetails?id=<guid>.
Source map (verified 25 Jun 2026):
  - news  : /News    — a[href*="/NewsDetails?id="].
  - event : /Events/ — a[href*="/EventsDetails?id="].
  - topic : about, governance, MAWP, Chips for Europe, ECS, documents, publications.

The Chips JU funds research and innovation to strengthen Europe's semiconductor
ecosystem under the European Chips Act. Reads from economy_items (body row seeded by
migration 186); 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://www.chips-ju.europa.eu"
NEWS_PAGE = f"{_BASE}/News"
EVENTS_PAGE = f"{_BASE}/Events/"

_TOPIC_PATHS = [
    "/About-us", "/Governance-and-Members", "/MAWP", "/Chips-for-Europe", "/ECS",
    "/General-Documents", "/Publications", "/Operational-Procurement",
]


def _scrape(url: str, detail_substr: str, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select(f'a[href*="{detail_substr}"]'):
        href = a.get("href", "")
        if detail_substr not in href:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        u = norm_url(href if href.startswith("http") else _BASE + "/" + href.lstrip("/"))
        if u in seen:
            continue
        seen.add(u)
        items.append(Item(body_code="chips", item_type=item_type, title=title[:300],
                          public_url=u, creation_date=now, source_kind="html", guid=u))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
    return items


def ingest_chips_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, "/NewsDetails?id=", "news", fetch_bodies=fetch_bodies)


def ingest_chips_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(EVENTS_PAGE, "/EventsDetails?id=", "event", fetch_bodies=fetch_bodies)


def ingest_chips_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("chips", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
