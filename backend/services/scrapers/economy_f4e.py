"""
Fusion for Energy — F4E (api_euratom_ju.md). /api/v2/f4e.

fusionforenergy.europa.eu is a WordPress site, server-rendered, plain requests. Its
press releases and publications are listed as titled PDF links. Source map (verified
25 Jun 2026):
  - press_release : /press-releases/ — titled PDF links (multilingual; deduplicated
                    by title to one entry per release).
  - publication   : /publications/   — titled PDF links.
  - topic         : the about, fusion-explainer, ITER and governance pages.

F4E is the EU agency that manages Europe's contribution to ITER and the Broader
Approach fusion-energy projects. Reads from economy_items (body row seeded by
migration 188); 5 mandatory datapoints. Scope: read:economy. No LLM is used.

(The Governing Board "Meetings & Decisions" PDFs are a deeper follow-up: most are
untitled download links inside a meetings table rather than titled list items.)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, snapshot_topics,
)

_LANG_SUFFIX = re.compile(r"[ _-]+(EN|ES|FR|IT|DE)$", re.I)
_NOISE = re.compile(r"\b(press[ _-]?release|factsheet|fact[ _-]?sheet|final|v\d+|sin)\b", re.I)


def _title_from_filename(url: str) -> str:
    stem = url.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = stem.replace("_", " ").replace("-", " ")
    stem = _LANG_SUFFIX.sub("", stem)
    stem = _NOISE.sub("", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -_")
    return clean(stem[:1].upper() + stem[1:]) if stem else ""

_BASE = "https://fusionforenergy.europa.eu"
PRESS_PAGE = f"{_BASE}/press-releases/"
PUB_PAGE = f"{_BASE}/publications/"

_TOPIC_PATHS = [
    "/our-mission-values/", "/what-is-fusion/", "/merits-of-fusion-energy/",
    "/developing-fusion/", "/iter/", "/the-device/", "/iter-the-story-so-far/",
    "/discover-the-benefits-of-fusion-for-europe/", "/governance-committees/",
    "/governance-committees/governing-board/", "/get-involved/",
    "/key-reference-documents/",
]


def _scrape_pdfs(url: str, item_type: str, *, fetch_bodies: bool, en_only: bool) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(url)
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main") or soup
    for a in main.select('a[href*=".pdf"]'):
        href = a.get("href", "")
        if ".pdf" not in href.lower():
            continue
        fname = href.rsplit("/", 1)[-1]
        # press releases come in EN/ES/FR/IT; keep the EN copy (or the only copy)
        if en_only and re.search(r"[ _-](ES|FR|IT|DE)\.pdf$", fname, re.I):
            continue
        # title prefers the link text, else the filename
        title = clean(a.get_text(" ", strip=True))
        if not title or len(title) < 8 or title.upper() in ("EN", "ES", "FR", "IT", "DE"):
            title = _title_from_filename(href)
        if not title or len(title) < 6:
            continue
        u = norm_url(href if href.startswith("http") else _BASE + href)
        key = title.lower()
        if u in seen or key in seen:
            continue
        seen.add(u)
        seen.add(key)
        items.append(Item(body_code="f4e", item_type=item_type, title=title[:300],
                          public_url=u, creation_date=now, source_kind="pdf", guid=u))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_f4e_press_releases(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # Catalogue-style (the full PDF archive is ~150 items): title + the PDF link,
    # no per-document text fetch, to keep the nightly cron bounded.
    return _scrape_pdfs(PRESS_PAGE, "press_release", fetch_bodies=False, en_only=True)


def ingest_f4e_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return _scrape_pdfs(PUB_PAGE, "publication", fetch_bodies=False, en_only=False)


def ingest_f4e_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("f4e", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
