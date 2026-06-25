"""
EFCA — European Fisheries Control Agency (api_socjust.md). /api/v2/efca.

EFCA runs a Drupal site (efca.europa.eu): the news listing is article cards with
an h2 heading link and a <time datetime>. Plain requests work (no WAF). Only the
news listing is cleanly dated, so news only. Source map (verified 25 Jun 2026):
  - news : /en/news/latest

Reads from economy_items (body row already seeded); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, _iso_dt

_BASE = "https://www.efca.europa.eu"

NEWS_PAGES = [f"{_BASE}/en/news/latest"]


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for card in soup.select("article"):
        link = card.select_one("h2 a[href], h3 a[href], a.card-title")
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
            items.append(Item(body_code="efca", item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_efca_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)
