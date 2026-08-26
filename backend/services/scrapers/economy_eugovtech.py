"""
EC GovTech — the EU GovTech collection on the Interoperable Europe Portal
(interoperable-europe.ec.europa.eu/collection/eugovtech). /api/v2/eugovtech.

EU GovTech is a dedicated sub-portal (a collection within Interoperable Europe)
covering govtech for the public sector: news, events, reusable solutions, the
Knowledge Centre (reports & policy briefs), the GovTech Atlas (initiatives &
startups) and GovTech4All public-sector challenges. It is promoted to its own
folder because its own listings carry the full history (36+ news/events) that
the cross-collection /api/v2/interoperable feeds only sample.

Source map (verified 30 Jun 2026, all under /collection/eugovtech/):
  - news        : /news-events              (the /news/ items; incl. GovTech4All challenges)
  - event       : /news-events              (the /event/ items)
  - solution    : /solutions                (reusable solutions)
  - publication : /knowledge-centre         (GovTech reports & policy briefs; /document/ items)
  - topic       : the hub pages (Welcome, GovTech Atlas, GovTech4All) as snapshots

JS-rendered + lazy-loaded, so every fetch goes through Playwright (project rule).
No fabrication: titles/URLs/dates/bodies come from the live pages; off-site URLs
are dropped. Reuses the Interoperable Europe helpers. Reads economy_items (body
row in migration 197). 5 mandatory datapoints. Scope: read:economy. Local refresh.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean, extract_html
from services.scrapers.economy_interoperable import (_BASE, _UA, _abs, _parse_date,
                                                     _parse_item_date, _render)

_BODY = "eugovtech"
_COLLECTION = "/collection/eugovtech"

# item_type for each URL "kind" segment.
_KIND_TO_TYPE = {"news": "news", "event": "event", "solution": "solution", "document": "publication"}

# Hub pages snapshotted as topics (the named sub-collections of EU GovTech).
_TOPIC_PATHS = [
    "/collection/eugovtech/welcome-eu-govtech",
    "/collection/eugovtech/govtech-atlas-explore-initiatives-and-startups",
    "/collection/eugovtech/govtech4all-20-public-sector-challenges",
    "/collection/eugovtech/knowledge-centre",
]

# Extract dated content cards whose link points at one of the allowed kinds.
_EXTRACT_JS = r"""(kinds) => {
  const re = new RegExp('/(' + kinds.join('|') + ')/', 'i');
  const out = []; const seen = new Set();
  for (const art of document.querySelectorAll('article')) {
    let a = null;
    for (const cand of art.querySelectorAll('a[href]')) {
      const h = cand.getAttribute('href') || '';
      if (re.test(h) && h.indexOf('/collection/eugovtech/') !== -1) { a = cand; break; }
    }
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    const head = art.querySelector('h1,h2,h3,h4,[class*="title"]');
    let title = (head ? head.textContent : '').trim();
    if (!title) title = (a.textContent || '').trim();
    if (!title) title = (a.getAttribute('title') || a.getAttribute('aria-label') || '').trim();
    if (title.length < 6) continue;
    if (seen.has(href)) continue; seen.add(href);
    const tm = art.querySelector('time[datetime]');
    let date = tm ? tm.getAttribute('datetime') : null;
    if (!date) { const m = (art.textContent || '').match(/\d{1,2}\/\d{1,2}\/\d{4}/); date = m ? m[0] : null; }
    out.push({ href, title, date });
  }
  return out;
}"""

import re as _re


def _kind(url: str) -> str | None:
    m = _re.search(r"/collection/eugovtech/(news|event|solution|document)/", url, _re.I)
    return m.group(1).lower() if m else None


async def _scrape_listing(path: str, kinds: list[str], *, fetch_bodies: bool,
                          scrolls: int, body_cap: int) -> list[Item]:
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        if await _render(page, _BASE + path, scrolls=scrolls) is None:
            await b.close()
            return []
        rows = await page.evaluate(_EXTRACT_JS, kinds)
        seen: set[str] = set()
        for r in rows:
            url = _abs(r["href"])
            if not url.startswith(_BASE) or url in seen:
                continue
            kind = _kind(url)
            if kind is None:
                continue
            seen.add(url)
            items.append(Item(
                body_code=_BODY, item_type=_KIND_TO_TYPE[kind],
                title=clean(r["title"])[:300], public_url=url,
                document_date=_parse_item_date(r.get("date"), _KIND_TO_TYPE[kind],
                                               title=clean(r["title"])), creation_date=now,
                source_kind="html", guid=url))
        if fetch_bodies:
            for it in items[:body_cap]:
                html = await _render(page, it.public_url, settle_ms=900)
                if html:
                    it.body_txt, it.body_html = extract_html(html)
        await b.close()
    return items


async def _scrape_topics(*, fetch_bodies: bool) -> list[Item]:
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for path in _TOPIC_PATHS:
            url = _BASE + path
            html = await _render(page, url, settle_ms=1500)
            if not html:
                continue
            meta = await page.evaluate(r"""() => {
              const h1 = document.querySelector('main h1, h1');
              return { title: h1 ? h1.textContent.trim() : document.title };
            }""")
            title = clean(meta.get("title") or path.rsplit("/", 1)[-1].replace("-", " "))[:300]
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(
                body_code=_BODY, item_type="topic", title=title, public_url=url,
                document_date=None, creation_date=now, source_kind="html",
                guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def _run(coro):
    return asyncio.run(coro)


def ingest_eugovtech_news(*, fetch_bodies: bool = True) -> list[Item]:
    # news + events share the news-events listing; keep only the /news/ items.
    return [it for it in _run(_scrape_listing(
        "/collection/eugovtech/news-events", ["news"], fetch_bodies=fetch_bodies,
        scrolls=8, body_cap=60)) if it.item_type == "news"]


def ingest_eugovtech_events(*, fetch_bodies: bool = True) -> list[Item]:
    return [it for it in _run(_scrape_listing(
        "/collection/eugovtech/news-events", ["event"], fetch_bodies=fetch_bodies,
        scrolls=8, body_cap=60)) if it.item_type == "event"]


def ingest_eugovtech_solutions(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("/collection/eugovtech/solutions", ["solution"],
                                fetch_bodies=fetch_bodies, scrolls=6, body_cap=40))


def ingest_eugovtech_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("/collection/eugovtech/knowledge-centre", ["document"],
                                fetch_bodies=fetch_bodies, scrolls=6, body_cap=40))


def ingest_eugovtech_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_topics(fetch_bodies=fetch_bodies))
