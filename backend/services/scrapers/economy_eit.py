"""
EIT — European Institute of Innovation and Technology (api_market.md).
/api/v2/eit.

EIT runs a Drupal site (eit.europa.eu). Source map (verified):
  - news   : /news-events/news — .views-row cards (heading link; the date is
             dd/mm/yyyy in the row text, no <time>); ?page=N paginated. Detail = HTML.
  - events : /news-events/events — .views-row cards (heading link; a date range
             dd/mm/yyyy in the row text -> the start day). Detail = HTML.

EIT publishes no standalone documents listing, so only news + events. No LLM.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, parse_listing_date, snapshot_topics,
)

_BASE = "https://www.eit.europa.eu"

# Curated who-we-are + Innovation Community (KIC) landing pages, snapshotted as
# topics. snapshot_topics drops any path that 404s.
_TOPIC_PATHS = [
    "/who-we-are/eit-glance",
    "/community-activities",
    "/global-challenges",
    "/eit-ecosystem-map",
    "/our-communities",
    "/our-communities/eit-climate-kic",
    "/our-communities/28digital",
    "/our-communities/eit-food",
    "/our-communities/eit-innoenergy",
    "/our-communities/eit-rawmaterials",
    "/our-communities/eit-urban-mobility",
    "/our-communities/eit-water",
    "/eit-community/eit-culture-creativity",
    "/eit-community/eit-health",
    "/eit-community/eit-manufacturing",
]


def ingest_eit_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eit", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)

NEWS_PAGES = [f"{_BASE}/news-events/news"]
EVENT_PAGES = [f"{_BASE}/news-events/events"]


def _parse(html: str):
    main = BeautifulSoup(html, "html.parser").select_one("main") or BeautifulSoup(html, "html.parser")
    out = []
    for row in main.select(".views-row"):
        a = (row.select_one("h2 a[href], h3 a[href], h4 a[href], .field--name-title a[href]")
             or next((x for x in row.find_all("a", href=True) if x.get_text(strip=True)), None))
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        doc_dt = parse_listing_date(row.get_text(" ", strip=True))
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
            rows = _parse(r.text)
            new = 0
            for u, title, doc_dt in rows:
                if u in seen:
                    continue
                seen.add(u)
                new += 1
                items.append(Item(body_code="eit", item_type=item_type, title=title,
                                  public_url=u, document_date=doc_dt, creation_date=now,
                                  source_kind="html", guid=u))
            if new == 0:
                break
    if fetch_bodies:
        # EIT rate-limits bursts: space the detail fetches and retry transient
        # "unreachable" timeouts so bodies extract cleanly in one pass.
        for it in items:
            body_txt = body_html = None
            kind = "unreachable"
            for attempt in range(3):
                body_txt, body_html, kind = fetch_detail(it.public_url)
                if kind != "unreachable":
                    break
                time.sleep(2.0 * (attempt + 1))
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
            time.sleep(0.4)
    return items


def ingest_eit_news(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies, max_pages=max_pages)


def ingest_eit_events(*, fetch_bodies: bool = True, max_pages: int = 4) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies, max_pages=max_pages)
