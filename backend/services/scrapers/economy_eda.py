"""
EDA — European Defence Agency (api_defence.md). /api/v2/eda.

eda.europa.eu is server-rendered with a custom card layout (.eda-card), reachable
with plain requests. Source map (verified 25 Jun 2026):
  - news        : /news-and-events/news      — .eda-card (.eda-card-title + a +
                  a <time> with an M/D/YYYY date).
  - publication : /publications-and-data/publications
  - event       : /news-and-events/events
  - topic       : the what-we-do and who-we-are pages.

The EDA supports Member States in developing defence capabilities, defence
research and the EU defence initiatives. Reads from economy_items (body row seeded
by migration 176); 5 mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://eda.europa.eu"

NEWS_PAGE = f"{_BASE}/news-and-events/news"
PUB_PAGE = f"{_BASE}/publications-and-data/publications"
EVENTS_PAGE = f"{_BASE}/news-and-events/events"

_MDY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

_TOPIC_PATHS = [
    "/what-we-do",
    "/what-we-do/EU-defence-initiatives",
    "/what-we-do/capability-development",
    "/what-we-do/research-technology",
    "/what-we-do/industry-engagement",
    "/what-we-do/eu-policies",
    "/what-we-do/training-exercises",
    "/what-we-do/enablers",
    "/what-we-do/support-to-operations",
    "/who-we-are",
    "/who-we-are/Missionandfunctions",
    "/who-we-are/history",
    "/publications-and-data/defence-data",
]


def _mdy(s: str) -> datetime | None:
    m = _MDY.search(s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_cards(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".eda-card"):
        te = card.select_one(".eda-card-title")
        a = card.select_one(".eda-card-title a[href]") or card.select_one("a[href]")
        if not a or not a.get("href"):
            continue
        title = clean(te.get_text(" ", strip=True)) if te else clean(a.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        href = a["href"]
        if href.startswith("http"):
            url = href
        else:
            url = _BASE + "/" + href.lstrip("/")
        t = card.select_one("time")
        doc_dt = _mdy(t.get("datetime") or t.get_text(" ", strip=True)) if t else None
        out.append((norm_url(url), title, doc_dt))
    return out


def _scrape(url: str, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    for purl, title, doc_dt in _parse_cards(r.text):
        if purl in seen:
            continue
        seen.add(purl)
        items.append(Item(body_code="eda", item_type=item_type, title=title[:300],
                          public_url=purl, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=purl))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_eda_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, "news", fetch_bodies=fetch_bodies)


def ingest_eda_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(PUB_PAGE, "publication", fetch_bodies=fetch_bodies)


def ingest_eda_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(EVENTS_PAGE, "event", fetch_bodies=fetch_bodies)


def ingest_eda_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eda", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
