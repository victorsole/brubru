"""
Eurofound — European Foundation for the Improvement of Living and Working
Conditions (api_socjust.md). /api/v2/eurofound.

eurofound.europa.eu is a modern JS-rendered site: its news / publications LIST
pages have no server-side items, the on-site RSS feed 404s, and the plain
requests path is aggressively rate-limited (429). Its individual topic pages and
surveys-and-data pages ARE substantial reference content, so Eurofound is
delivered as page snapshots rendered through Playwright (real browser, paced):
  - topic       : /en/topic/<slug>            (policy topics)
  - publication : /en/surveys-and-data/<slug> (the flagship surveys + data tools)

Playwright-only, so the refresh runs locally, not on the Railway cron. Reads from
economy_items (body row already seeded); 5 mandatory datapoints. Scope:
read:economy. No LLM is used.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, extract_html

_BASE = "https://www.eurofound.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_TOPIC_PATHS = [
    "/en/topic/digitalisation", "/en/topic/minimum-wages", "/en/topic/minimum-wage",
    "/en/topic/gender-equality", "/en/topic/housing", "/en/topic/restructuring",
    "/en/topic/job-quality", "/en/topic/working-conditions",
    "/en/topic/quality-of-life", "/en/topic/industrial-relations",
    "/en/topic/labour-market-change", "/en/topic/working-time",
    "/en/topic/social-cohesion-and-convergence", "/en/topic/care",
]

_PUB_PATHS = [
    "/en/surveys-and-data/surveys/european-company-survey",
    "/en/surveys-and-data/surveys/european-quality-of-life-survey",
    "/en/surveys-and-data/surveys/european-working-conditions-survey",
    "/en/surveys-and-data/surveys/living-and-working-in-the-eu-e-survey",
    "/en/surveys-and-data/european-restructuring-monitor",
    "/en/surveys-and-data/eu-policywatch",
    "/en/surveys-and-data/convergence-monitoring-hub",
    "/en/surveys-and-data/minimum-wage-database",
    "/en/surveys-and-data/data-catalogue",
]


async def _snapshot_async(paths, item_type: str, *, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in paths:
            url = _BASE + path
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(900)
            except Exception:
                continue
            if resp is None or resp.status != 200:
                continue
            html = await page.content()
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.select_one("main h1, h1")
            if h1 and len(h1.get_text(strip=True)) > 3:
                title = clean(h1.get_text(" ", strip=True))
            elif soup.title and soup.title.get_text(strip=True):
                title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
            else:
                title = path.rsplit("/", 1)[-1].replace("-", " ").title()
            if not title:
                continue
            items.append(Item(body_code="eurofound", item_type=item_type, title=title[:300],
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_eurofound_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_snapshot_async(_TOPIC_PATHS, "topic", fetch_bodies=fetch_bodies))


def ingest_eurofound_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_snapshot_async(_PUB_PATHS, "publication", fetch_bodies=fetch_bodies))
