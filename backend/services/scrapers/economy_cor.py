"""
CoR — European Committee of the Regions (api_eesc_cor_ombud.md). /api/v2/cor.

The CoR site (cor.europa.eu) is server-rendered with a custom component library:
listings are article.c-card blocks (.c-card__title a + <time datetime>). Plain
requests. Source map (verified 25 Jun 2026):
  - news    : /en/news/all-news-and-press-releases — c-card news + press releases.
  - opinion : /en/our-work/opinions — the CoR's adopted opinions.
  - topic   : about, members, the six commissions, the 2025-2030 priorities and the
              studies/networks/working-groups pages.

The CoR is the EU's assembly of regional and local representatives; it issues
opinions on EU legislation with a territorial impact. Reads from economy_items
(body row seeded by migration 170); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.cor.europa.eu"

NEWS_PAGE = f"{_BASE}/en/news/all-news-and-press-releases"
OPINIONS_PAGE = f"{_BASE}/en/our-work/opinions"

_COMMISSIONS = ["civex", "coter", "econ", "enve", "nat", "sedec"]
_TOPIC_PATHS = [
    "/en/about",
    "/en/about/President",
    "/en/members",
    "/en/members/political-groups-cor",
    "/en/members/national-delegations",
    "/en/our-work",
    "/en/our-work/priorities-2025-2030",
    "/en/our-work/priorities-2025-2030/cohesion",
    "/en/our-work/priorities-2025-2030/resilience",
    "/en/our-work/priorities-2025-2030/proximity",
    "/en/our-work/commissions",
    "/en/our-work/studies-publications",
    "/en/our-work/cooperations-and-networks",
    "/en/our-work/working-groups",
    "/en/plenaries-events",
] + [f"/en/our-work/commissions/{c}" for c in _COMMISSIONS]


def _parse_cards(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select("article.c-card, .c-card"):
        a = card.select_one(".c-card__title a[href], h3 a[href], h2 a[href]")
        if not a or not a.get("href"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 12:
            continue
        t = card.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        out.append((norm_url(a["href"] if a["href"].startswith("http") else _BASE + a["href"]),
                    title, doc_dt))
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
        items.append(Item(body_code="cor", item_type=item_type, title=title[:300],
                          public_url=purl, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=purl))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_cor_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(NEWS_PAGE, "news", fetch_bodies=fetch_bodies)


def ingest_cor_opinions(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape(OPINIONS_PAGE, "opinion", fetch_bodies=fetch_bodies)


def ingest_cor_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("cor", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
