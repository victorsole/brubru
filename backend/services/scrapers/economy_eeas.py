"""
EEAS — European External Action Service (api_eeas.md). /api/v2/eeas.

The EEAS Drupal site (eeas.europa.eu) sits behind a JS / bot wall: a plain
requests.get returns a 202 challenge page with no content, so EVERY fetch here
goes through Playwright headless Chromium (project rule: use Playwright when
hitting walls). The filter-page listings lazy-load their cards on scroll and
carry the date as DD.MM.YYYY / "DD Month YYYY" text (press, publications,
tenders) or a <time datetime> (events); a content card is an <a> in <main>
pointing at an /eeas/ or /delegations/ slug with a date nearby — requiring a
date cleanly excludes the navigation chrome.

Source map (verified 24 Jun 2026):
  - news        : /filter-page/press-material_en?f[0]=press_site:EEAS
                  (press releases, statements, speeches/remarks, op-eds)
  - publication : /filter-page/publications_en   (documents, research, reports)
  - event       : /filter-page/events_en         (agendas)
  - tender      : /eeas/tenders_en?f[0]=tender_status:ongoing  (calls + grants)
  - topic       : curated thematic / geographic reference pages (snapshots)

People are NOT ingested here: the 352 EEAS officials live in the EU Who-is-Who
(publications.europa.eu SPARQL) and are served by /api/v2/who-is-who/officials.

Resources read from economy_items (body row in migration 144). 5 mandatory
datapoints. Scope: read:economy. Playwright-only, so the refresh runs locally,
not on the Railway cron (Chromium is not installed there) — same constraint as
FRA / EUIPO / EASA. No LLM is used anywhere.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean, extract_html

_BASE = "https://www.eeas.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Lazy-loading listings: (path, scroll passes).
_LISTINGS = {
    "news":        "/filter-page/press-material_en?f%5B0%5D=press_site%3AEEAS",
    "publication": "/filter-page/publications_en",
    "event":       "/filter-page/events_en",
    "tender":      "/eeas/tenders_en?f%5B0%5D=tender_status%3Aongoing",
}

# Curated static reference pages from api_eeas.md (the # EEAS section + research).
# These are pages, not feeds, so they are snapshotted as item_type='topic'.
_TOPIC_PATHS = [
    "/eeas/about-european-external-action-service_en",
    "/eeas/creation-european-external-action-service_en",
    "/eeas/structure-and-organisation_en",
    "/eeas/high-representative-vice-president_en",
    "/eeas/eu-special-representatives_en",
    "/eeas/consular-protection-eu-citizens_en",
    "/eeas/missions-and-operations_en",
    "/eeas/africa-and-eu_en",
    "/eeas/central-asia_en",
    "/eeas/eastern-europe_en",
    "/eeas/latin-america-and-caribbean_en",
    "/eeas/middle-east-and-north-africa-mena_en",
    "/eeas/north-america-canada-and-united-states_en",
    "/eeas/western-balkans_en",
    "/eeas/western-europe_en",
    "/eeas/eastern-partnership_en",
    "/eeas/european-neighbourhood-policy_en",
    "/eeas/eu-peace-security-and-defence_en",
    "/eeas/crisis-response_en",
    "/eeas/green-transition-diplomacy_en",
    "/eeas/multilateral-relations_en",
    "/eeas/migration-mobility-forced-displacement_en",
    "/eeas/humanitarian-emergency-response_en",
    "/eeas/international-cooperation-partnerships_en",
    "/eeas/public-diplomacy_en",
    "/eeas/global-gateway_en",
    "/eeas/digital-diplomacy_en",
    "/eeas/economic-relations-trade-and-sustainability_en",
    "/eeas/european-union-sanctions_en",
    "/eeas/annual-reports_en",
]

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# JS that pulls every dated content card out of the rendered listing.
_EXTRACT_JS = r"""() => {
  const re = /\/(eeas|delegations)\//i;
  const seen = new Set(); const out = [];
  for (const a of document.querySelectorAll('main a[href]')) {
    const href = a.getAttribute('href') || '';
    if (!re.test(href)) continue;
    const title = a.textContent.trim();
    if (title.length < 12) continue;
    let card = a, ds = null;
    for (let i = 0; i < 5 && card; i++) {
      card = card.parentElement; if (!card) break;
      const tm = card.querySelector('time[datetime]');
      if (tm) { ds = tm.getAttribute('datetime'); break; }
      const m = card.textContent.match(/\d{1,2}\.\d{1,2}\.\d{4}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4}/);
      if (m) { ds = m[0]; break; }
    }
    if (!ds) continue;
    if (seen.has(href)) continue; seen.add(href);
    out.push({href, title, date: ds});
  }
  return out;
}"""


def _abs(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return _BASE + href
    return href


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    # ISO with optional time/zone
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None
    # DD.MM.YYYY
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError:
            return None
    # DD Month YYYY
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)
    if m:
        d = int(m.group(1)); mo = _MONTHS.get(m.group(2).lower()); y = int(m.group(3))
        if mo:
            try:
                return datetime(y, mo, d, tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


async def _render(page, url: str, *, scrolls: int = 0, settle_ms: int = 2500) -> str | None:
    try:
        await page.goto(url, wait_until="networkidle", timeout=55000)
        await page.wait_for_timeout(settle_ms)
        for _ in range(scrolls):
            await page.mouse.wheel(0, 5000)
            await page.wait_for_timeout(1100)
        return await page.content()
    except Exception:
        return None


async def _scrape_listing(item_type: str, path: str, *, fetch_bodies: bool,
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
        rows = await page.evaluate(_EXTRACT_JS)
        seen: set[str] = set()
        for r in rows:
            url = _abs(r["href"])
            if url in seen:
                continue
            seen.add(url)
            items.append(Item(
                body_code="eeas", item_type=item_type, title=clean(r["title"])[:300],
                public_url=url, document_date=_parse_date(r.get("date")),
                creation_date=now, source_kind="html", guid=url))
        if fetch_bodies:
            for it in items[:body_cap]:
                html = await _render(page, it.public_url, settle_ms=800)
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
              const m = (document.querySelector('main')||document.body).textContent
                          .match(/\d{1,2}\.\d{1,2}\.\d{4}/);
              return {title: h1 ? h1.textContent.trim() : document.title, date: m ? m[0] : null};
            }""")
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            title = clean(meta.get("title") or path.rsplit("/", 1)[-1])[:300]
            items.append(Item(
                body_code="eeas", item_type="topic", title=title, public_url=url,
                document_date=_parse_date(meta.get("date")), creation_date=now,
                source_kind="html", guid=url, body_txt=body_txt, body_html=body_html))
        await b.close()
    return items


def _run(coro):
    return asyncio.run(coro)


def ingest_eeas_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("news", _LISTINGS["news"],
                                fetch_bodies=fetch_bodies, scrolls=10, body_cap=80))


def ingest_eeas_publications(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("publication", _LISTINGS["publication"],
                                fetch_bodies=fetch_bodies, scrolls=10, body_cap=80))


def ingest_eeas_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("event", _LISTINGS["event"],
                                fetch_bodies=fetch_bodies, scrolls=8, body_cap=80))


def ingest_eeas_tenders(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("tender", _LISTINGS["tender"],
                                fetch_bodies=fetch_bodies, scrolls=8, body_cap=60))


def ingest_eeas_topics(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_topics(fetch_bodies=fetch_bodies))
