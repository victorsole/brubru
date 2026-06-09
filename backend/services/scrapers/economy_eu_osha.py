"""
EU-OSHA — European Agency for Safety and Health at Work (api_health.md).
/api/v2/eu-osha.

EU-OSHA runs a Drupal site (osha.europa.eu). Each listing item pairs a heading
link with a <time datetime> in a per-section container (node--type-highlight for
news, .publications-right-column for publications, .right-column for events).
The scraper anchors on each <time datetime> and climbs to the heading link, which
handles all three layouts. Source map (verified):
  - news         : /en/highlights — ?page=N paginated. Detail = HTML.
  - publications : /en/publications.
  - events       : /en/oshevents.

No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt,
)

_BASE = "https://osha.europa.eu"
_SOURCES = {
    "news": f"{_BASE}/en/highlights",
    "publication": f"{_BASE}/en/publications",
    "event": f"{_BASE}/en/oshevents",
}


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for t in soup.select("time[datetime]"):
        node, link = t, None
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            cand = node.select_one("h2 a[href], h3 a[href], h4 a[href]")
            if cand and cand.get_text(strip=True) and "/en/" in cand["href"]:
                link = cand
                break
        if not link:
            continue
        url = norm_url(link["href"] if link["href"].startswith("http") else _BASE + link["href"])
        if url in seen:
            continue
        seen.add(url)
        title = clean(link.get_text(" ", strip=True))
        if not title:
            continue
        out.append((url, title, _iso_dt(t.get("datetime"))))
    return out


def _scrape(item_type: str, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    listing = _SOURCES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        url = listing if page == 0 else f"{listing}?page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse(r.text)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="eu_osha", item_type=item_type, title=title,
                              public_url=u, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=u))
        if new == 0:
            break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eu_osha_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eu_osha_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("publication", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eu_osha_events(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("event", fetch_bodies=fetch_bodies, max_pages=max_pages)
