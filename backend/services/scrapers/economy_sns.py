"""
Smart Networks and Services JU — SNS (api_euratom_ju.md). /api/v2/sns.

smart-networks.europa.eu is a WordPress site, server-rendered, plain requests. Its
publications are titled PDF links; the about, governance and funding pages are plain
content. (The news listing mixes real articles with menu pages, so it is not exposed
as a clean resource.) Source map (verified 25 Jun 2026):
  - publication : /sns-publications/ + the SNS journals — titled PDF links.
  - topic       : missions, governance, team, procurement, calls and reference pages.

The SNS JU funds research and innovation in 5G/6G smart networks and services under
Horizon Europe. Reads from economy_items (body row seeded by migration 190); 5
mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_BASE = "https://smart-networks.europa.eu"
PUB_PAGES = [f"{_BASE}/sns-publications/", f"{_BASE}/sns-journal-2025/",
             f"{_BASE}/sns-journal-2024/", f"{_BASE}/relevant-external-publications/"]

_TOPIC_PATHS = [
    "/missions-and-objectives/", "/gouvernance/", "/our-team/", "/procurement/",
    "/integrity-internal-control-and-anti-fraud/", "/current-call-for-proposals/",
    "/open-calls-from-sns-projects/", "/proposing-a-project/",
    "/interactive-map-of-sns-projects/", "/sns-ju-projects-key-achievements-2025/",
    "/reference-documents/",
]


def _title_from_filename(url: str) -> str:
    stem = url.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = re.sub(r"[ _-]?v?\d+(\.\d+)*$", "", stem.replace("_", " ").replace("-", " "))
    stem = re.sub(r"\s+", " ", stem).strip()
    return clean(stem[:1].upper() + stem[1:]) if stem else ""


def ingest_sns_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    for page in PUB_PAGES:
        r = http_get(page)
        if r is None:
            continue
        main = BeautifulSoup(r.text, "html.parser").select_one("main") or BeautifulSoup(r.text, "html.parser")
        for a in main.select('a[href*=".pdf"]'):
            href = a.get("href", "")
            if ".pdf" not in href.lower():
                continue
            u = norm_url(href if href.startswith("http") else _BASE + href)
            if u in seen:
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title or len(title) < 8 or re.match(r"^(read more|download|click)", title, re.I):
                title = _title_from_filename(u)
            if not title or len(title) < 6:
                continue
            seen.add(u)
            items.append(Item(body_code="sns", item_type="publication", title=title[:300],
                              public_url=u, creation_date=now, source_kind="pdf", guid=u))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_sns_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("sns", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
