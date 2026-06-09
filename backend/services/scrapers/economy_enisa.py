"""
ENISA — European Union Agency for Cybersecurity (api_market.md).
/api/v2/enisa.

ENISA runs a custom Drupal site (enisa.europa.eu). Listing items pair a heading
link with a <time datetime>, in different container classes per section
(.featured-content for news, .item-card for publications). The scraper anchors
on each <time datetime> and climbs to the nearest heading-link container — that
handles both layouts. Source map (verified):
  - news         : /news — ~14 recent items (single server-rendered page). Detail = HTML.
  - publications : /publications — ~13 recent items (single server-rendered page).

ENISA's events listing is JS-rendered with no server-side dates, so only news +
publications are surfaced. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt,
)

_BASE = "https://www.enisa.europa.eu"

NEWS_PAGES = [f"{_BASE}/news"]
PUB_PAGES = [f"{_BASE}/publications"]


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
        if not title:
            continue
        doc_dt = _iso_dt(t.get("datetime"))
        desc = node.select_one(".content, .description, .summary")
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
            items.append(Item(body_code="enisa", item_type=item_type, title=title,
                              public_url=url, summary=summary, document_date=doc_dt,
                              creation_date=now, source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_enisa_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_enisa_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("publication", PUB_PAGES, fetch_bodies=fetch_bodies)
