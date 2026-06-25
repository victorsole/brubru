"""
Circular Bio-based Europe JU — CBE (api_euratom_ju.md). /api/v2/cbe.

cbe.europa.eu is an OpenEuropa Drupal site, server-rendered, plain requests. The
news page lists article nodes with a title link to /news/<slug> and a <time
datetime>; the publications page lists document nodes with PDF links. Source map
(verified 25 Jun 2026):
  - news        : /news
  - publication : /publications
  - topic       : organisation, mission, governance, bioeconomy, projects, funding.

The CBE JU funds research and innovation in competitive circular bio-based
industries in Europe (succeeding the BBI JU). Reads from economy_items (body row
seeded by migration 184); 5 mandatory datapoints. Scope: read:economy. No LLM.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.cbe.europa.eu"
NEWS_PAGE = f"{_BASE}/news"
PUB_PAGE = f"{_BASE}/publications"

_TOPIC_PATHS = [
    "/organisation", "/mission-and-objectives", "/governance",
    "/our-team-and-values", "/about-bioeconomy", "/why-joint-undertaking",
    "/cbe-ju-supporting-eu-policies-through-bio-based-solutions", "/projects",
    "/achievements", "/open-calls-proposals", "/how-apply-funding",
    "/reference-documents",
]


def _scrape(url: str, item_type: str, prefer_pdf: bool, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for art in soup.select("article"):
        link = None
        if prefer_pdf:
            link = art.select_one('a[href$=".pdf"], a[href*=".pdf"]')
        link = link or art.select_one('h2 a[href], h3 a[href], .node__title a[href], a[href]')
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if "?f%5b" in href.lower() or href.startswith("#") or href.rstrip("/").endswith(("/news", "/publications")):
            continue
        te = art.select_one("h2 a, h3 a, .node__title")
        title = clean(te.get_text(" ", strip=True)) if te else clean(link.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        u = norm_url(href if href.startswith("http") else _BASE + href)
        if u in seen:
            continue
        seen.add(u)
        t = art.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        items.append(Item(body_code="cbe", item_type=item_type, title=title[:300],
                          public_url=u, document_date=doc_dt, creation_date=now,
                          source_kind="pdf" if ".pdf" in u.lower() else "html", guid=u))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_cbe_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, "news", False, fetch_bodies=fetch_bodies)


def ingest_cbe_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(PUB_PAGE, "publication", True, fetch_bodies=fetch_bodies)


def ingest_cbe_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cbe", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
