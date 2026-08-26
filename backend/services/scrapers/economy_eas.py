"""
EAS / EUSA — European School of Administration (api_ec.md L4074-4080). /api/v2/eas.

The European School of Administration is a small interinstitutional training body
with no standalone website: its public presence is a Commission department page,
and its corporate documents (annual activity reports, management plans) are
published on the Commission strategy-documents pages filtered by the EAS corporate
body. Those filtered listings are client-rendered, so publications are read through
Playwright; the department and leadership pages are plain HTML. Source map
(verified 25 Jun 2026):
  - publication : commission.europa.eu strategy-documents (annual activity reports +
                  management plans) filtered by corporate-body/EAS — ECL content
                  items with a <time datetime> and a title link.
  - topic       : the Commission department page + the EUSA leadership pages.

Reads from economy_items (body row seeded by migration 164); 5 mandatory
datapoints. Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import (
    Item, clean, norm_url, _iso_dt, snapshot_topics,
)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

_EAS_AUTHOR = ("?f%5B0%5D=oe_publication_authors%3Askos_concept%7Chttp%3A//"
               "publications.europa.eu/resource/authority/corporate-body/EAS")
_PUB_PAGES = [
    "https://commission.europa.eu/strategy-and-policy/strategy-documents/"
    "annual-activity-reports_en" + _EAS_AUTHOR,
    "https://commission.europa.eu/strategy-and-policy/strategy-documents/"
    "management-plans_en" + _EAS_AUTHOR,
]

_TOPIC_URLS = [
    "https://commission.europa.eu/about/departments-and-executive-agencies/"
    "european-school-administration_en",
    "https://commission.europa.eu/persons/anna-mitelman_en",
    "https://commission.europa.eu/persons/christiane-keutgens_en",
]


async def _scrape_pubs_async(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for listing in _PUB_PAGES:
            try:
                await page.goto(listing, wait_until="networkidle", timeout=55000)
                await page.wait_for_timeout(2500)
            except Exception:
                continue
            soup = BeautifulSoup(await page.content(), "html.parser")
            for art in soup.select("article.ecl-content-item, .ecl-content-item"):
                link = None
                for a in art.select("a[href]"):
                    if len(a.get_text(strip=True)) >= 10:
                        link = a
                        break
                if not link or not link.get("href"):
                    continue
                href = link["href"]
                url = norm_url(href if href.startswith("http") else "https://commission.europa.eu" + href)
                if url in seen:
                    continue
                seen.add(url)
                title = clean(link.get_text(" ", strip=True))
                t = art.select_one("time[datetime]")
                doc_dt = _iso_dt(t["datetime"]) if t and t.get("datetime") else None
                items.append(Item(body_code="eas", item_type="publication", title=title[:300],
                                  public_url=url, document_date=doc_dt, creation_date=now,
                                  source_kind="html", guid=url))
        await b.close()
    return items


def ingest_eas_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    import asyncio
    return asyncio.run(_scrape_pubs_async(fetch_bodies=fetch_bodies))


def ingest_eas_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # Full URLs (not a single base), so pass base="" and absolute paths.
    return snapshot_topics("eas", "", _TOPIC_URLS, fetch_bodies=fetch_bodies)
