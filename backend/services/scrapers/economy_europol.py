"""
Europol — EU Agency for Law Enforcement Cooperation (api_socjust.md). /api/v2/europol.

europol.europa.eu is a Drupal site whose newsroom and detail bodies are loaded
client-side (the plain requests path returns an empty shell), so Europol is fed
through Playwright on the local refresh. The rendered /media-press/newsroom
listing exposes one <article> per item with a title link to
/media-press/newsroom/<...> and a "DD Mon YYYY" date in its <time> element; each
detail page is then rendered for the body. The crime-area, specialist-centre and
flagship-report pages (SOCTA, IOCTA) are substantial reference content,
snapshotted as topics.

Source map (verified 25 Jun 2026):
  - news  : /media-press/newsroom        (rendered listing -> per-item detail)
  - topic : crime-areas + specialist centres + flagship reports

Playwright-only, so the refresh runs locally, not on the Railway cron. Reads from
economy_items (body row seeded by migration 155); 5 mandatory datapoints.
Scope: read:economy. No LLM is used.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, extract_html

_BASE = "https://www.europol.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

NEWS_LISTING = "/media-press/newsroom"
_NEWS_HREF = re.compile(r"^/media-press/newsroom/[a-z0-9-]+/[a-z0-9-]{8,}")

_TOPIC_PATHS = [
    "/about-europol/operational-and-analysis-centre",
    "/about-europol/european-serious-and-organised-crime-centre-esocc",
    "/about-europol/european-cybercrime-centre-ec3",
    "/about-europol/european-counter-terrorism-centre-ectc",
    "/about-europol/european-financial-and-economic-crime-centre-efecc",
    "/how-we-work/operations",
    "/how-we-work/sirius-project",
    "/how-we-work/innovation-lab",
    "/how-we-work/europol-analysis-projects",
    "/crime-areas-and-statistics/empact",
    "/crime-areas/child-sexual-exploitation",
    "/crime-areas/corruption",
    "/crime-areas/criminal-finances-and-money-laundering",
    "/crime-areas/currency-counterfeiting",
    "/crime-areas/cyber-attacks",
    "/crime-areas/trade-in-illicit-drugs",
    "/publications-events/main-reports/socta-report",
    "/publications-events/main-reports/iocta-report",
]

_MONTH_IDX = {}
for _i, _full in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1):
    _MONTH_IDX[_full] = _i
    _MONTH_IDX[_full[:3]] = _i
_DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})")


def _text_date(s: str) -> datetime | None:
    m = _DMY.search(s or "")
    if not m:
        return None
    mo = _MONTH_IDX.get(m.group(2).lower())
    if not mo:
        return None
    try:
        return datetime(int(m.group(3)), mo, int(m.group(1)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _title_from(soup: BeautifulSoup, path: str) -> str:
    h1 = soup.select_one("main h1, article h1, h1")
    if h1:
        t = clean(h1.get_text(" ", strip=True))
        if t and len(t) > 3 and "can't find" not in t.lower():
            return t[:300]
    if soup.title and soup.title.get_text(strip=True):
        return clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])[:300]
    return path.rsplit("/", 1)[-1].replace("-", " ").title()[:300]


async def _ingest_news_async(*, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        try:
            await page.goto(_BASE + NEWS_LISTING, wait_until="networkidle", timeout=55000)
            await page.wait_for_timeout(2500)
            listing = await page.content()
        except Exception:
            await b.close()
            return items
        soup = BeautifulSoup(listing, "html.parser")
        rows: dict[str, tuple[str, datetime | None]] = {}
        for art in soup.select("article"):
            a = art.select_one('a[href*="/media-press/newsroom/"]')
            if not a or not a.get("href"):
                continue
            href = a["href"]
            if not _NEWS_HREF.match(href):
                continue
            title = clean(a.get_text(" ", strip=True))
            if not title or len(title) < 10:
                continue
            t = art.select_one("time")
            doc_dt = _text_date(t.get_text(" ", strip=True) if t else "")
            rows.setdefault(href, (title, doc_dt))
        for href, (title, doc_dt) in rows.items():
            url = _BASE + href
            body_txt = body_html = None
            if fetch_bodies:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(1200)
                    dhtml = await page.content()
                    ds = BeautifulSoup(dhtml, "html.parser")
                    h1 = ds.select_one("main h1, article h1, h1")
                    if h1 and "can't find" not in h1.get_text().lower():
                        title = clean(h1.get_text(" ", strip=True))[:300] or title
                    body_txt, body_html = extract_html(dhtml)
                    if doc_dt is None:
                        doc_dt = _text_date(ds.get_text(" ", strip=True))
                except Exception:
                    pass
            items.append(Item(body_code="europol", item_type="news", title=title[:300],
                              public_url=url, document_date=doc_dt, creation_date=now,
                              source_kind="html", guid=url,
                              body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


async def _ingest_topics_async(*, fetch_bodies: bool) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(900)
            except Exception:
                continue
            if resp is None or resp.status != 200:
                continue
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            title = _title_from(soup, path)
            if "can't find" in title.lower():
                continue
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(body_code="europol", item_type="topic", title=title,
                              public_url=url, creation_date=now, source_kind="html",
                              guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def ingest_europol_news(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_ingest_news_async(fetch_bodies=fetch_bodies))


def ingest_europol_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return asyncio.run(_ingest_topics_async(fetch_bodies=fetch_bodies))
