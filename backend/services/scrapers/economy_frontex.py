"""
Frontex — European Border and Coast Guard Agency (api_socjust.md). /api/v2/frontex.

frontex.europa.eu is server-rendered and reachable with plain requests (no WAF on
the news path): the /media-centre/news/news-release/ listing exposes one <article>
per item, with the title in an <h3><a> linking to the news-release detail and the
date in <span class="date"> as an ISO YYYY-MM-DD string. The about, careers and
transparency pages are substantial reference content, snapshotted as topics.

Source map (verified 25 Jun 2026):
  - news  : /media-centre/news/news-release/
  - topic : about-frontex + standing-corps + transparency pages

Reads from economy_items (body row seeded by migration 156); 5 mandatory
datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, extract_html)

_BASE = "https://www.frontex.europa.eu"

NEWS_LISTING = "/media-centre/news/news-release/"
_NEWS_HREF = re.compile(r"^/media-centre/news/news-release/[a-z0-9-]+")
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

_TOPIC_PATHS = [
    "/about-frontex/who-we-are/tasks-mission/",
    "/about-frontex/management-board/",
    "/about-frontex/procurement/procurement/",
    "/about-frontex/grants/",
    "/careers/standing-corps/about/",
    "/careers/standing-corps/training/",
    "/careers/standing-corps/profiles/",
    "/transparency/accountability/",
    "/transparency/data-protection/",
    "/transparency/public-access-to-documents/public-access-to-documents/",
]


def _iso_date(s: str) -> datetime | None:
    m = _ISO.search(s or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def ingest_frontex_news(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    r = http_get(_BASE + NEWS_LISTING)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    seen: set[str] = set()
    for art in soup.select("article"):
        link = None
        for a in art.select("h3 a[href], a[href]"):
            if _NEWS_HREF.match(a.get("href", "")) and len(a.get_text(strip=True)) >= 10:
                link = a
                break
        if not link:
            continue
        href = link["href"]
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        seen.add(url)
        title = clean(link.get_text(" ", strip=True))
        d = art.select_one("span.date")
        doc_dt = _iso_date(d.get_text(strip=True) if d else "") or _iso_date(art.get_text(" ", strip=True))
        items.append(Item(body_code="frontex", item_type="news", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="html", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind == "pdf":
                it.source_kind = "pdf"
    return items


def ingest_frontex_topics(*, fetch_bodies: bool = True) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        title = ""
        if soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        _generic = {"frontex", "news", "home", "general information", "about", ""}
        if title.lower() in _generic:
            slug = path.rstrip("/").rsplit("/", 1)[-1]
            # Carry the parent segment for context where the leaf is generic.
            parent = path.rstrip("/").rsplit("/", 2)[-2] if "/" in path.rstrip("/")[1:] else ""
            label = slug.replace("-", " ").title()
            if slug in ("about", "procurement") and parent and parent != slug:
                label = f"{parent.replace('-', ' ').title()}: {label}"
            title = label
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code="frontex", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items
