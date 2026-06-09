"""
BEREC — Body of European Regulators for Electronic Communications
(api_market.md). /api/v2/berec.

BEREC runs a Drupal site (berec.europa.eu). Listings are server-rendered for the
first page; deeper pages are JS-only, so the scraper takes the first page of
each category listing and stops when a page returns nothing new. Source map
(verified):
  - news         : /en/news/latest-news + /en/news/press-releases — .news-teaser-article
                   cards (heading link + .teaser-date "25 May 2026"). Detail = HTML.
  - publications : /en/news/publications — .publication-article.news-teaser-article cards.
  - events       : /en/events — article[about] with .event-top-title link and an
                   .event-formatted-date ("09 June 2026" / "10-11 September 2026").

No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date,
)

_BASE = "https://www.berec.europa.eu"

NEWS_PAGES = [f"{_BASE}/en/news/latest-news", f"{_BASE}/en/news/press-releases"]
PUB_PAGES = [f"{_BASE}/en/news/publications"]
EVENT_PAGES = [f"{_BASE}/en/events"]


def _parse(html: str, item_type: str):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    out = []
    if item_type == "event":
        cards = main.select("article[about]")
    else:
        cards = main.select(".news-teaser-article")
    for c in cards:
        if item_type == "event":
            a = c.select_one(".event-top-title a") or c.find("a", href=True)
            de = c.select_one(".event-formatted-date")
        else:
            a = c.select_one("h2 a, h3 a, h4 a") or c.find("a", href=True)
            de = c.select_one(".teaser-date")
        href = (a["href"] if a and a.get("href") else c.get("about"))
        if not href:
            continue
        url = norm_url(href if href.startswith("http") else _BASE + href)
        title = clean(a.get_text(" ", strip=True)) if a else None
        if not title:
            continue
        doc_dt = parse_listing_date(de.get_text(" ", strip=True)) if de else None
        out.append((url, title, doc_dt))
    return out


def _scrape(item_type: str, listing_urls, *, fetch_bodies: bool, max_pages: int) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for listing in listing_urls:
        for page in range(max_pages):
            sep = "&" if "?" in listing else "?"
            url = listing if page == 0 else f"{listing}{sep}page={page}"
            r = http_get(url)
            if r is None:
                break
            rows = _parse(r.text, item_type)
            new = 0
            for u, title, doc_dt in rows:
                if u in seen:
                    continue
                seen.add(u)
                new += 1
                items.append(Item(body_code="berec", item_type=item_type, title=title,
                                  public_url=u, document_date=doc_dt, creation_date=now,
                                  source_kind="html", guid=u))
            if new == 0:          # BEREC's deeper pages are JS-only; stop when dry
                break
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_berec_news(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_berec_publications(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("publication", PUB_PAGES, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_berec_events(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies, max_pages=max_pages)
