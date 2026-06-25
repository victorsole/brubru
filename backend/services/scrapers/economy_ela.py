"""
ELA — European Labour Authority (api_socjust.md). /api/v2/ela.

ELA runs a Drupal site (ela.europa.eu) on the EU Bootstrap Component Library:
each list item is an article with a title link (a.standalone inside
.oe-sc-news__node-title) and a <time datetime>. Plain requests work (no WAF).
Source map (verified 25 Jun 2026):
  - news  : /en/news-events/news
  - event : /en/news-events/events

Reads from economy_items (body row in migration 152); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, _iso_dt

_BASE = "https://www.ela.europa.eu"

NEWS_PAGES = [f"{_BASE}/en/news-events/news"]
EVENT_PAGES = [f"{_BASE}/en/news-events/events"]

_LINK_SEL = ("a.standalone, a.card-title, .oe-sc-news__node-title a[href], "
             ".node-title a[href], h2 a[href], h3 a[href]")


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for card in soup.select("article"):
        link = card.select_one(_LINK_SEL)
        if not link or not link.get("href"):
            continue
        href = link["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        title = clean(link.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        seen.add(url)
        tm = card.select_one("time[datetime]")
        doc_dt = _iso_dt(tm.get("datetime")) if tm else None
        out.append((url, title, doc_dt))
    return out


def _scrape(item_type: str, listing_urls, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        r = http_get(listing)
        if r is None:
            continue
        for url, title, doc_dt in _parse(r.text):
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(body_code="ela", item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_ela_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_ela_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies)
