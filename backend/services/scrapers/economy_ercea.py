"""
ERCEA — European Research Council Executive Agency (api_ec.md L3880-3931).
/api/v2/ercea.

ERCEA's public face is the European Research Council site (erc.europa.eu), a Drupal
build that is NOT on the standard ec.europa.eu ECL stack: it uses its own theme.
Server-rendered, plain requests. Source map (verified 25 Jun 2026):
  - news         : /news-events/news    — <article> with an h2/h3 title link to
                   /news-events/news/<slug> and a <time datetime> (ISO). Detail=HTML.
  - events       : /news-events/events  — <article about="/news-events/events/<slug>">
                   with the title in an h2 and a "DD Month YYYY" date in the card.
  - publications : /news-events/erc-publications — .views-row publication cards with
                   a .document-title, a .publication-date <time> and a PDF link.
                   Bodies extracted from the PDFs.
  - topic        : curated about-erc / apply-grant / project pages.

ERCEA runs the European Research Council's frontier-research grants (Starting,
Consolidator, Advanced, Proof of Concept, Synergy). Reads from economy_items (body
row seeded by migration 161); 5 mandatory datapoints. Scope: read:economy.
No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://erc.europa.eu"

NEWS_PAGES = [f"{_BASE}/news-events/news"]
EVENT_PAGES = [f"{_BASE}/news-events/events"]
PUB_PAGES = [f"{_BASE}/news-events/erc-publications"]

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")

_TOPIC_PATHS = [
    "/about-erc",
    "/about-erc/erc-glance",
    "/about-erc/erc-president-scientific-council",
    "/about-erc/thematic-working-groups",
    "/about-erc/standing-committees",
    "/about-erc/erc-executive-agency-ercea",
    "/about-erc/erc-legal-basis",
    "/apply-grant",
    "/apply-grant/starting-grants",
    "/apply-grant/consolidator-grants",
    "/apply-grant/advanced-grants",
    "/apply-grant/proof-concept",
    "/apply-grant/synergy-grants",
    "/manage-your-project",
    "/projects-statistics",
]


def _iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _text_dmy(s: str) -> datetime | None:
    m = _DMY.search(s or "")
    if not m:
        return None
    mo = _MONTHS.get(m.group(2).lower())
    if not mo:
        return None
    try:
        return datetime(int(m.group(3)), mo, int(m.group(1)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _norm(href: str) -> str:
    return norm_url(href if href.startswith("http") else _BASE + href)


def ingest_ercea_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(NEWS_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for art in soup.select('article[about*="/news-events/news/"]'):
        url = _norm(art.get("about", ""))
        if not url or url in seen:
            continue
        h = art.select_one(".field--name-title, h2, h3")
        title = clean(h.get_text(" ", strip=True)) if h else ""
        if not title or len(title) < 6:
            continue
        seen.add(url)
        t = art.select_one("time[datetime]")
        doc_dt = _iso(t["datetime"]) if t else _text_dmy(art.get_text(" ", strip=True))
        items.append(Item(body_code="ercea", item_type="news", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            bt, bh, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = bt, bh
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_ercea_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(EVENT_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for art in soup.select('article[about*="/news-events/events/"]'):
        url = _norm(art.get("about", ""))
        if not url or url in seen:
            continue
        h = art.select_one("h2, .field--name-title, h3")
        title = clean(h.get_text(" ", strip=True)) if h else ""
        if not title or len(title) < 6:
            continue
        seen.add(url)
        doc_dt = _text_dmy(art.get_text(" ", strip=True))
        items.append(Item(body_code="ercea", item_type="event", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            bt, bh, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = bt, bh
    return items


def ingest_ercea_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(PUB_PAGES[0])
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for row in soup.select(".views-row"):
        pdf = row.select_one('a[href*=".pdf"]')
        if not pdf or not pdf.get("href"):
            continue
        url = _norm(pdf["href"])
        if url in seen:
            continue
        seen.add(url)
        te = row.select_one(".document-title")
        title = clean(te.get_text(" ", strip=True)) if te else clean(pdf.get_text(" ", strip=True))
        if not title:
            title = url.rsplit("/", 1)[-1]
        tm = row.select_one(".publication-date time[datetime], time[datetime]")
        doc_dt = _iso(tm["datetime"]) if tm else None
        items.append(Item(body_code="ercea", item_type="publication", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="pdf", guid=url))
    if fetch_bodies:
        for it in items:
            bt, bh, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = bt, bh
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_ercea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("ercea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
