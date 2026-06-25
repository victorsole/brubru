"""
Clean Aviation JU (api_euratom_ju.md). /api/v2/clean-aviation.

clean-aviation.eu is a Drupal faceted-search site, server-rendered, plain requests.
The news-events page lists content as .card teaser nodes (title link to a clean
slug; the ?f[...] links are facet filters and are skipped). Source map (verified
25 Jun 2026):
  - news  : /news-events — .card teaser nodes.
  - topic : about, members, calls and research-and-innovation pages.

The Clean Aviation JU funds research into low-emission and climate-neutral
aircraft technologies. Reads from economy_items (body row seeded by migration 183);
5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.clean-aviation.eu"
NEWS_PAGE = f"{_BASE}/news-events"

_TOPIC_PATHS = [
    "/about-us",
    "/about-us/who-we-are",
    "/about-us/governance",
    "/discover-our-members",
    "/clean-aviation-calls",
    "/clean-aviation-calls/call-for-proposals",
    "/research-and-innovation/clean-aviation",
    "/research-and-innovation/clean-aviation/clean-aviation-projects",
    "/research-and-innovation/clean-aviation/our-energy-efficiency-and-emission-reduction",
    "/about-us/reference-documents",
    "/success-stories",
]


def ingest_aviation_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NEWS_PAGE)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select(".card"):
        a = card.select_one(".node__title a[href], h2 a[href], h3 a[href], a[href]")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        if "?f%5b" in href.lower() or "?f[" in href.lower() or href.startswith("#"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 12:
            continue
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        seen.add(url)
        t = card.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        items.append(Item(body_code="aviation", item_type="news", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_aviation_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("aviation", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
