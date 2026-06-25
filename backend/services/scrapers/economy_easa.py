"""
EASA — European Union Aviation Safety Agency (api_socjust.md). /api/v2/easa.

EASA runs a server-rendered Drupal site (easa.europa.eu). Listing pages pair a
heading link (h2/h3 a) with a <time datetime> per card; the scraper anchors on
each <time> and climbs to the nearest heading-link container (the ENISA pattern).
Plain requests work (no WAF). Source map (verified 25 Jun 2026):
  - news        : /newsroom-and-events/news + /press-releases
  - publication : /document-library/research-reports
  - event       : /newsroom-and-events/events/current-and-upcoming-events

Reads from economy_items (body row already seeded); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, extract_html, _iso_dt,
)

_BASE = "https://www.easa.europa.eu"

NEWS_PAGES = [f"{_BASE}/en/newsroom-and-events/news",
              f"{_BASE}/en/newsroom-and-events/press-releases"]
PUB_PAGES = [f"{_BASE}/en/document-library/research-reports"]
EVENT_PAGES = [f"{_BASE}/en/newsroom-and-events/events/current-and-upcoming-events"]

# Curated thematic / reference pages (api_socjust.md): the regulatory domains and
# the "EASA Light" topic hub. Snapshotted as item_type='topic'.
_TOPIC_PATHS = [
    "/en/domains/aerodromes", "/en/domains/air-operations",
    "/en/domains/air-traffic-management", "/en/domains/aircraft-products",
    "/en/domains/aircrew-and-medical", "/en/domains/civil-drones",
    "/en/domains/cyber-security", "/en/domains/environment",
    "/en/domains/general-aviation", "/en/domains/international-cooperation",
    "/en/domains/safety-management", "/en/domains/research-innovation",
    "/en/domains/rotorcraft-vtol",
    "/en/light/topics/easa-and-you", "/en/light/topics/drones",
    "/en/light/topics/urban-air-mobility", "/en/light/topics/sustainability",
    "/en/light/topics/research-and-innovation", "/en/light/topics/international",
]


def _parse(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for t in main.select("time[datetime]"):
        node = t
        link = None
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            link = node.select_one("h3 a[href], h2 a[href]")
            if link:
                break
        if not link or not link.get("href"):
            continue
        href = link["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        seen.add(url)
        title = clean(link.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        doc_dt = _iso_dt(t.get("datetime"))
        desc = node.select_one(".content, .description, .summary, p")
        summary = clean(desc.get_text(" ", strip=True)[:1000]) if desc else None
        out.append((url, title, doc_dt, summary))
    return out


def _scrape(item_type: str, listing_urls, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        r = http_get(listing)
        if r is None:
            continue
        for url, title, doc_dt, summary in _parse(r.text):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="easa", item_type=item_type, title=title,
                              public_url=url, summary=summary, document_date=doc_dt,
                              creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_easa_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_easa_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("publication", PUB_PAGES, fetch_bodies=fetch_bodies)


def ingest_easa_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies)


def _snapshot_topics(base: str, paths, body_code: str, *, fetch_bodies: bool) -> list[Item]:
    """Snapshot a curated list of thematic / reference pages as item_type='topic'.
    Each page's H1 is the title and its main content is the body."""
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in paths:
        url = base + path
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        title = clean(h1.get_text(" ", strip=True)) if h1 else path.rsplit("/", 1)[-1].replace("-", " ")
        if not title:
            continue
        items.append(Item(body_code=body_code, item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items


def ingest_easa_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return _snapshot_topics(_BASE, _TOPIC_PATHS, "easa", fetch_bodies=fetch_bodies)
