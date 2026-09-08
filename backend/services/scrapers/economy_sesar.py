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

NEWS_FEED = f"{_BASE}/rss.xml"


def news_dates() -> dict:
    """{canonical news URL -> publication datetime} from SESAR's own RSS feed.

    Why the feed (measured 8 September 2026)
    ----------------------------------------
    Neither the item page nor the listing states a date. The 83KB item pages carry
    none of six date carriers (no <time datetime>, no article:published_time, no
    JSON-LD datePublished, no parseable visible date), and walking five levels of
    ancestor from each listing link finds nothing either. So every SESAR news row
    was written undated (23 rows).
    
    `/rss.xml` publishes an RFC-822 <pubDate> per item, which IS the publisher's own
    statement of that item's date. That makes it a legitimate source, unlike a
    sitemap <lastmod> (a modification date) or the ingest time.

    Two link forms appear in the feed: `/news/<slug>` matching what the scraper
    collects, and `/node/<id>` (the raw node route). A node link is resolved by
    reading its page's <link rel="canonical">, which is the site's own mapping to
    the alias, so the date lands on the right row rather than on a guess.

    The feed holds only the most recent ~10 items, so historical rows stay undated.
    Returning a partial map is correct; inventing the rest is not.
    """
    import email.utils
    out: dict = {}
    r = http_get(NEWS_FEED)
    if r is None:
        return out
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
    except Exception:  # noqa: BLE001
        return out
    for it in root.findall(".//item"):
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        if not link or not pub:
            continue
        try:
            dt = email.utils.parsedate_to_datetime(pub)
        except Exception:  # noqa: BLE001
            continue
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if "/news/" not in link:
            # /node/<id> -> follow it and take the canonical alias the site declares.
            nr = http_get(link)
            if nr is None:
                continue
            m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                          nr.text, re.I) or re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', nr.text, re.I)
            if not m:
                continue
            link = m.group(1)
            if "/news/" not in link:
                continue
        out[norm_url(link)] = dt
    return out


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
    items = _scrape(NEWS_PAGE, r"/news/[a-z0-9-]{6,}", "news", fetch_bodies=fetch_bodies)
    # Neither the item page nor the listing carries a date, so take it from SESAR's
    # own RSS <pubDate>. Only the ~10 most recent items are in the feed; anything
    # older keeps document_date None rather than acquiring a made-up one.
    dates = news_dates()
    for it in items:
        if it.document_date is None:
            it.document_date = dates.get(it.public_url)
    return items


def ingest_sesar_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(DOCS_PAGE, r"/node/\d+", "publication", fetch_bodies=fetch_bodies)


def ingest_sesar_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(EVENTS_PAGE, r"/node/\d+", "event", fetch_bodies=fetch_bodies)


def ingest_sesar_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("sesar", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
