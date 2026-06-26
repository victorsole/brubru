"""
SESAR 3 JU (api_euratom_ju.md). /api/v2/sesar.

sesarju.eu is a Drupal site, server-rendered, plain requests. News items link to
/news/<slug>; events and documents are /node/<id> link lists. Source map (verified
25 Jun 2026):
  - news        : /news                     — /news/<slug> links.
  - publication : /search-content/documents — /node/<id> document links.
  - event       : /events                   — /node/<id> event links.
  - topic       : discover-sesar, approach and the thematic pages.

The SESAR 3 JU funds research and innovation to modernise European air-traffic
management (the digital European sky, U-space, smart ATM). Reads from economy_items
(body row seeded by migration 187); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://www.sesarju.eu"
NEWS_PAGE = f"{_BASE}/news"
DOCS_PAGE = f"{_BASE}/search-content/documents"
EVENTS_PAGE = f"{_BASE}/events"

_TOPIC_PATHS = [
    "/discover-sesar", "/approach", "/what-is-smart-atm", "/sustainability",
    "/MasterPlan2025", "/innovation-pipeline", "/approach/deployment",
    "/digitalisation", "/U-space", "/ai", "/virtual-centres", "/RTS", "/CNS",
    "/smartairports",
]


def _scrape(url: str, href_re: str, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    best: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup
    pat = re.compile(href_re)
    for a in main.select("a[href]"):
        href = a.get("href", "")
        if not pat.search(href) or "#" in href:
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 14:
            continue
        u = norm_url(href if href.startswith("http") else _BASE + href)
        # group by URL, keep the longest title (filters short location/meta links)
        if u not in best or len(title) > len(best[u]):
            best[u] = title
    for u, title in best.items():
        items.append(Item(body_code="sesar", item_type=item_type, title=title[:300],
                          public_url=u, creation_date=now, source_kind="html", guid=u))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_sesar_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, r"/news/[a-z0-9-]{6,}", "news", fetch_bodies=fetch_bodies)


def ingest_sesar_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(DOCS_PAGE, r"/node/\d+", "publication", fetch_bodies=fetch_bodies)


def ingest_sesar_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(EVENTS_PAGE, r"/node/\d+", "event", fetch_bodies=fetch_bodies)


def ingest_sesar_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("sesar", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
