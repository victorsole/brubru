"""
CdT — Translation Centre for the Bodies of the European Union (cdt.europa.eu).
/api/v2/cdt.

CdT runs a Drupal site, server-rendered and reachable with plain requests. Source
map (verified 25 Jun 2026):
  - news  : /en/news — .card blocks with an h5.card-title, a <time datetime> and a
            stretched-link to /en/news/<slug>. Detail = HTML.
  - topic : curated services, about and cooperation pages. The page h1 is a fixed
            banner ("Translation Centre For the Bodies of the EU") on every page, so
            titles are read from <title> (snapshot_topics prefer_title=True).

CdT provides translation, terminology, audiovisual and language services to the EU
agencies and bodies, and runs IATE, the EU's shared terminology database. Reads from
economy_items (body row seeded by migration 165); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://cdt.europa.eu"
NEWS_PAGES = [f"{_BASE}/en/news"]

_TOPIC_PATHS = [
    "/en/discover-our-range-services",
    "/en/services/translation-services",
    "/en/services/terminology-services",
    "/en/services/audiovisual-language-services",
    "/en/services/other-services",
    "/en/iate",
    "/en/our-story",
    "/en/our-cooperation-clients",
    "/en/interinstitutional-cooperation",
    "/en/eu-agencies-network",
    "/en/external-language-service-providers",
    "/en/documentation",
    "/en/procurement",
    "/en/interested-working-us",
]


def ingest_cdt_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NEWS_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select(".card"):
        a = card.select_one('a[href*="/en/news/"]')
        if not a or not a.get("href"):
            continue
        url = norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"])
        if url in seen:
            continue
        seen.add(url)
        te = card.select_one("h5.card-title, .card-title")
        title = clean(te.get_text(" ", strip=True)) if te else clean(a.get_text(" ", strip=True))
        if not title or title.lower() == "read more":
            continue
        t = card.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        items.append(Item(body_code="cdt", item_type="news", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_cdt_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cdt", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies,
                           prefer_title=True)
