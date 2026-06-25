"""
ERA — European Union Agency for Railways (api_socjust.md). /api/v2/era.

ERA runs a Drupal site (era.europa.eu) built on the EU Bootstrap Component
Library: every list item is an article.card with a heading link (a.card-title /
a.bcl-heading) and a date that is either a <time datetime> (news) or a
"DD Month YYYY" / "Month YYYY" string in the card text (events, library). Plain
requests work (no WAF). Source map (verified 25 Jun 2026):
  - news        : /events-news/news_en
  - publication : /library/documents-regulations/{era-recommendations_en,
                  opinions-and-technical-advices, era-work-programmes-activity-reports}
  - event       : /events-training/events-training

Reads from economy_items (body row already seeded); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, norm_url, http_get, fetch_detail, extract_html, _iso_dt

_BASE = "https://www.era.europa.eu"

NEWS_PAGES = [f"{_BASE}/events-news/news_en"]
PUB_PAGES = [f"{_BASE}/library/documents-regulations/era-recommendations_en",
             f"{_BASE}/library/documents-regulations/opinions-and-technical-advices",
             f"{_BASE}/library/documents-regulations/era-work-programmes-activity-reports"]
EVENT_PAGES = [f"{_BASE}/events-training/events-training"]

# Curated thematic / reference pages (api_socjust.md): ERA's regulatory domains.
# Snapshotted as item_type='topic'.
_TOPIC_PATHS = [
    "/agency/about-us",
    "/domains/applicants",
    "/domains/technical-specifications-interoperability_en",
    "/domains/infrastructure/european-rail-traffic-management-system-ertms_en",
    "/domains/safety-management",
    "/domains/accident-incident",
    "/domains/operation/transport-dangerous-goods_en",
    "/domains/rail-environment",
    "/domains/cybersecurity-railways",
    "/domains/era-academy",
    "/domains/trains/route-compatibility-check-rcc_en",
    "/domains/trains/certification-entities-charge-maintenance_en",
    "/domains/operation/train-drivers_en",
    "/domains/conformity-assessment_en",
    "/activities/national-rules_en",
]

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_DMY = re.compile(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_MY = re.compile(r"\b([A-Z][a-z]+)\s+(\d{4})\b")


def _text_date(s: str) -> datetime | None:
    m = _DMY.search(s)
    if m:
        d = int(m.group(1)); mo = _MONTHS.get(m.group(2).lower()); y = int(m.group(3))
        if mo:
            try:
                return datetime(y, mo, d, tzinfo=timezone.utc)
            except ValueError:
                return None
    m = _MY.search(s)
    if m:
        mo = _MONTHS.get(m.group(1).lower()); y = int(m.group(2))
        if mo:
            return datetime(y, mo, 1, tzinfo=timezone.utc)
    return None


def _parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for card in soup.select("article.card"):
        link = card.select_one("a.card-title, a.bcl-heading, .card-title a[href], "
                                "h4 a[href], h3 a[href], h2 a[href]")
        if not link:
            for a in card.select("a[href]"):
                href = a.get("href") or ""
                if len(a.get_text(strip=True)) >= 12 and (
                        "/content/" in href or "/library/" in href or href.endswith(".pdf")):
                    link = a
                    break
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
        doc_dt = _iso_dt(tm.get("datetime")) if tm else _text_date(card.get_text(" ", strip=True))
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
            items.append(Item(body_code="era", item_type=item_type, title=title,
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_era_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("news", NEWS_PAGES, fetch_bodies=fetch_bodies)


def ingest_era_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("publication", PUB_PAGES, fetch_bodies=fetch_bodies)


def ingest_era_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _scrape("event", EVENT_PAGES, fetch_bodies=fetch_bodies)


def ingest_era_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 3:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rsplit("/", 1)[-1].replace("_en", "").replace("-", " ").title()
        if not title:
            continue
        items.append(Item(body_code="era", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
