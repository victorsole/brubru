"""
EACEA — European Education and Culture Executive Agency (api_ec.md L3758-3804).
/api/v2/eacea.

EACEA runs on the EU ECL stack (www.eacea.ec.europa.eu), server-rendered and
reachable with plain requests. Source map (verified 25 Jun 2026):
  - news         : /news-events/news_en    — ECL .ecl-content-item cards with <time>.
  - events       : /news-events/events_en  — same ECL layout (EACEA is grants-led,
                   so the events feed is sparse).
  - publications : /about-eacea/document-register/annual-activity-reports-and-work-
                   programmes_en — the document register holds the annual work
                   programmes / activity reports as year-labelled PDFs. (The generic
                   /publications-0_en page is a client-side search widget with no
                   server-side items, and the agency's research outputs live on the
                   EU Publications Office, so the document register is the on-site
                   publications source.) Bodies extracted from the PDFs.
  - topic        : curated about / grants / scholarships landing pages.

EACEA manages Erasmus+, Creative Europe, the European Solidarity Corps, CERV and
Erasmus Mundus. Reads from economy_items (body row seeded by migration 158); 5
mandatory datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, http_get, fetch_detail, scrape_ecl_listing, snapshot_topics,
)

_BASE = "https://www.eacea.ec.europa.eu"

NEWS_PAGES = [f"{_BASE}/news-events/news_en"]
EVENT_PAGES = [f"{_BASE}/news-events/events_en"]
PUB_REGISTER = f"{_BASE}/about-eacea/document-register/annual-activity-reports-and-work-programmes_en"
_YEAR = re.compile(r"\b(19|20)\d{2}\b")

_TOPIC_PATHS = [
    "/about-eacea_en",
    "/about-eacea/eacea-platforms_en",
    "/about-eacea/transparency_en",
    "/about-eacea/data-protection_en",
    "/about-eacea/eacea-language-policy_en",
    "/about-eacea/document-register_en",
    "/grants_en",
    "/grants/how-get-grant_en",
    "/grants/2021-2027_en",
    "/grants/managing-your-grant_en",
    "/scholarships_en",
    "/scholarships/erasmus-mundus-catalogue_en",
    "/scholarships/intra-africa-scholarships-0_en",
    "/procurement_en",
    "/eacea-programme-budget-2021-2027_en",
]


def ingest_eacea_news(**kw) -> list[Item]:
    return scrape_ecl_listing("eacea", "news", NEWS_PAGES, _BASE, **kw)


def ingest_eacea_events(**kw) -> list[Item]:
    return scrape_ecl_listing("eacea", "event", EVENT_PAGES, _BASE, **kw)


def ingest_eacea_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    r = http_get(PUB_REGISTER)
    if r is None:
        return items
    main = BeautifulSoup(r.text, "html.parser").select_one("main") or BeautifulSoup(r.text, "html.parser")
    for a in main.select("a[href]"):
        href = a.get("href", "")
        if ".pdf" not in href.lower():
            continue
        url = norm_url(href if href.startswith("http") else _BASE + href)
        if url in seen:
            continue
        seen.add(url)
        label = clean(a.get_text(" ", strip=True))
        ym = _YEAR.search(label) or _YEAR.search(href)
        year = ym.group(0) if ym else None
        # The register page lists the annual work programmes / activity reports by
        # year; build a descriptive title rather than leaving the bare year text.
        if label and not _YEAR.fullmatch(label):
            title = label if "eacea" in label.lower() else f"EACEA {label}"
        elif year:
            title = f"EACEA Annual Work Programme {year}"
        else:
            title = "EACEA document register publication"
        doc_dt = datetime(int(year), 1, 1, tzinfo=timezone.utc) if year else None
        items.append(Item(body_code="eacea", item_type="publication", title=title[:300],
                          public_url=url, document_date=doc_dt, creation_date=now,
                          source_kind="pdf", guid=url))
    if fetch_bodies:
        for it in items:
            body_txt, body_html, kind = fetch_detail(it.public_url)
            it.body_txt, it.body_html = body_txt, body_html
            if kind in ("pdf", "html"):
                it.source_kind = kind
    return items


def ingest_eacea_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return snapshot_topics("eacea", _BASE, _TOPIC_PATHS, fetch_bodies=fetch_bodies)
