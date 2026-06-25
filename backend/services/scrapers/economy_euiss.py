"""
EUISS — European Union Institute for Security Studies (api_defence.md). /api/v2/euiss.

iss.europa.eu is a Drupal site, server-rendered and reachable with plain requests.
Listings render as article.teaser (node--view-mode-teaser) blocks with a title link
and a <time datetime>. Source map (verified 25 Jun 2026):
  - news        : /activities/news
  - publication : /publications (+ briefs, chaillot-papers, commentary, analysis,
                  books) — the EUISS research output.
  - event       : /activities/events
  - topic       : about, the thematic topics, the regions and the projects.

The EUISS is the EU's foreign-and-security-policy think tank. Reads from
economy_items (body row seeded by migration 175); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.iss.europa.eu"

NEWS_PAGES = [f"{_BASE}/activities/news"]
PUB_PAGES = [f"{_BASE}/publications", f"{_BASE}/publications/briefs",
             f"{_BASE}/publications/chaillot-papers", f"{_BASE}/publications/analysis",
             f"{_BASE}/publications/commentary"]
EVENT_PAGES = [f"{_BASE}/activities/events"]

_TOPIC_PATHS = [
    "/about-us",
    "/topics/eu-foreign-policy",
    "/topics/global-governance",
    "/topics/security-and-defence",
    "/topics/transnational-challenges",
    "/topics/strategic-foresight",
    "/regions/africa",
    "/regions/asia",
    "/regions/russia-and-eastern-neighbours",
    "/regions/mena",
    "/regions/the-americas",
    "/regions/western-balkans",
    "/projects/eu-cyber-direct",
    "/projects/countering-foreign-interference",
    "/projects/chipdiplo",
    "/projects/scope",
]


def _parse_teasers(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tz in soup.select("article.teaser, .node--view-mode-teaser, .teaser"):
        a = tz.select_one(".teaser-content a[href], h2 a[href], h3 a[href], .field--name-title a[href], a[href]")
        if not a or not a.get("href"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 10:
            continue
        t = tz.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        out.append((norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"]),
                    title, doc_dt))
    return out


def _scrape(pages, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in pages:
        r = http_get(page)
        if r is None:
            continue
        for purl, title, doc_dt in _parse_teasers(r.text):
            if purl in seen:
                continue
            seen.add(purl)
            items.append(Item(body_code="euiss", item_type=item_type, title=title[:300],
                              public_url=purl, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=purl))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_euiss_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGES, "news", fetch_bodies=fetch_bodies)


def ingest_euiss_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(PUB_PAGES, "publication", fetch_bodies=fetch_bodies)


def ingest_euiss_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(EVENT_PAGES, "event", fetch_bodies=fetch_bodies)


def ingest_euiss_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("euiss", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
