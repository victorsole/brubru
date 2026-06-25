"""
EDPB — European Data Protection Board (api_market.md L507-533). /api/v2/edpb.

edpb.europa.eu is a Drupal site, server-rendered and reachable with plain requests.
Source map (verified 25 Jun 2026):
  - news                : /news_en — .node-article-card (.node-article-card__title +
                          a[href*="/news/"] + <time datetime>).
  - document            : /documents_en — .document-card blocks (the EDPB's adopted
                          opinions, guidelines, recommendations and decisions). Title
                          from the "Read more about <title>" link.
  - public_consultation : /public-consultations_en — .node-public-consultation-card.
  - topic               : about, the GDPR topic pages and the registers.

The EDPB ensures consistent GDPR application across the EU; it adopts guidelines,
opinions and binding decisions and coordinates the national data-protection
authorities. Reads from economy_items (body row seeded by migration 173); 5
mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, _iso_dt, snapshot_topics,
)

_BASE = "https://www.edpb.europa.eu"

NEWS_PAGE = f"{_BASE}/news_en"
DOCS_PAGE = f"{_BASE}/documents_en"
CONSULT_PAGE = f"{_BASE}/public-consultations_en"

_READ_MORE = re.compile(r"^Read more about\s+", re.I)
_HAVE_SAY = re.compile(r"^Have your say!?\s*", re.I)

_TOPIC_PATHS = [
    "/about-edpb_en",
    "/sme_en",
    "/topics_en",
    "/topics/key-gdpr-concepts_en",
    "/topics/accountability-and-compliance-tools_en",
    "/topics/cooperation-enforcement_en",
    "/topics/ai-and-technology_en",
    "/topics/international-transfers-and-international-cooperation_en",
    "/topics/security-data-breaches_en",
    "/topics/police-justice_en",
    "/topics/specific-domains_en",
    "/registers_en",
    "/registers/register-of-final-one-stop-shop-decisions_en",
]


def _abs(href: str) -> str:
    return norm_url(href if href.startswith("http") else _BASE + href)


def _scrape_cards(url: str, card_sel: str, title_sel: str, link_substr: str,
                  item_type: str, *, fetch_bodies: bool, strip=None) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select(card_sel):
        te = card.select_one(title_sel)
        link = card.select_one(f'a[href*="{link_substr}"]') or card.select_one("a[href]")
        if not link or not link.get("href"):
            continue
        title = clean(te.get_text(" ", strip=True)) if te else clean(link.get_text(" ", strip=True))
        if strip:
            title = clean(strip.sub("", title))
        if not title or len(title) < 8:
            continue
        purl = _abs(link["href"])
        if purl in seen:
            continue
        seen.add(purl)
        t = card.select_one("time[datetime]")
        doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
        items.append(Item(body_code="edpb", item_type=item_type, title=title[:300],
                          public_url=purl, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=purl))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_edpb_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_cards(NEWS_PAGE, ".node-article-card", ".node-article-card__title, h3",
                         "/news/", "news", fetch_bodies=fetch_bodies)


def ingest_edpb_documents(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_cards(DOCS_PAGE, ".document-card", ".document-card__title, h3",
                         "/our-work-tools/", "document", fetch_bodies=fetch_bodies,
                         strip=_READ_MORE)


def ingest_edpb_public_consultations(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_cards(CONSULT_PAGE, ".node-public-consultation-card",
                         ".node-public-consultation-card__title, h3",
                         "/public-consultations/", "public_consultation",
                         fetch_bodies=fetch_bodies, strip=_HAVE_SAY)


def ingest_edpb_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("edpb", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
