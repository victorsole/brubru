"""
eu-LISA — EU Agency for the Operational Management of Large-Scale IT Systems
(api_market.md). /api/v2/eu-lisa.

eu-LISA runs a clean Drupal site (eulisa.europa.eu). Each listing item is an
article.node--type-{news|event|publication} with a heading link and a
<time datetime>. Source map (verified):
  - news         : /news-and-events?ts=&tp=77 — node--type-news; ?page=N paginated.
  - events       : /news-and-events?ts=&tp=78 — node--type-event.
  - publications : /our-publications — node--type-publication (detail page links
                   to the PDF). Detail = HTML.

No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.eulisa.europa.eu"

# Curated about + activities landing pages, snapshotted as topics. The individual
# large-scale-IT-system sub-pages are tried too; snapshot_topics drops any 404s.
_TOPIC_PATHS = [
    "/about-us/who-we-are",
    "/about-us/organisation",
    "/about-us/access-to-documents",
    "/activities/large-scale-it-systems",
    "/activities/large-scale-it-systems/sis",
    "/activities/large-scale-it-systems/eurodac",
    "/activities/large-scale-it-systems/vis",
    "/activities/large-scale-it-systems/ees",
    "/activities/large-scale-it-systems/etias",
    "/activities/interoperability",
    "/activities/data-protection",
    "/activities/security",
    "/activities/research-and-development",
    "/activities/training",
    "/activities/carriers",
    "/activities/empact",
    "/activities/pilot-projects",
]


def ingest_eulisa_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eu_lisa", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)

_SOURCES = {
    "news": (f"{_BASE}/news-and-events?ts=&tp=77", ".node--type-news"),
    "event": (f"{_BASE}/news-and-events?ts=&tp=78", ".node--type-event"),
    "publication": (f"{_BASE}/our-publications", ".node--type-publication"),
}


def _parse(html: str, node_sel: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for node in main.select(node_sel):
        a = node.select_one("h2 a[href], h3 a[href], h4 a[href]") or node.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        t = node.select_one("time[datetime]")
        doc_dt = _iso_dt(t.get("datetime")) if t else None
        out.append((url, title, doc_dt))
    return out


def _scrape(item_type: str, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    listing, node_sel = _SOURCES[item_type]
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in range(max_pages):
        sep = "&" if "?" in listing else "?"
        url = listing if page == 0 else f"{listing}{sep}page={page}"
        r = http_get(url)
        if r is None:
            break
        rows = _parse(r.text, node_sel)
        new = 0
        for u, title, doc_dt in rows:
            if u in seen:
                continue
            seen.add(u)
            new += 1
            items.append(Item(body_code="eu_lisa", item_type=item_type, title=title,
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


def ingest_eulisa_news(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("news", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eulisa_events(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("event", fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eulisa_publications(*, fetch_bodies: bool = True, max_pages: int = 6) -> list[Item]:
    return _scrape("publication", fetch_bodies=fetch_bodies, max_pages=max_pages)
