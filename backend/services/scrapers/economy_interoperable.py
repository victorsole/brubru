"""
EU Interoperable — the Interoperable Europe Portal (interoperable-europe.ec.europa.eu).
/api/v2/interoperable.

The portal (a Joinup/Drupal site) aggregates news, events and reusable solutions
ACROSS many thematic collections (OSOR, SEMIC, EU GovTech, EIF/Monitoring, Public
Sector Tech Watch, EUPL, CAMSS/EIRA, Digital-Ready Policymaking, Regulatory
Sandboxes, Guidelines, the Academy, Portal support). Item URLs encode their
collection: /collection/{collection}/news/{slug} and .../event/{slug}, so the
collection is parsed from public_url at query time (no extra column).

The listings lazy-load on scroll and are JS-rendered, so EVERY fetch goes through
Playwright headless Chromium (project rule: use Playwright at JS/bot walls). The
refresh runs locally, not on the Railway cron (Chromium is not installed there) —
same constraint as EEAS / FRA / EUIPO.

Source map (verified 30 Jun 2026):
  - news       : /news                (cross-collection news)
  - event      : /upcoming-events     (cross-collection upcoming events, DD/MM/YYYY)
  - solution   : /solutions           (reusable interoperability solutions)
  - collection : the portal nav's thematic-collection menu (one snapshot per hub)

No fabrication: every item is a real card on the rendered page; title, URL and
date come from the page itself, and the body is fetched from the item's OWN
detail page. Items with no usable title/URL are dropped, not invented.

Resources read from economy_items (body row in migration 196). 5 mandatory
datapoints (document_date is best-effort; the others always set). Scope:
read:economy. No LLM is used anywhere.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from services.scrapers.economy_common import Item, clean, extract_html

_BASE = "https://interoperable-europe.ec.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_LISTINGS = {
    "news":     "/news",
    "event":    "/upcoming-events",
    "solution": "/solutions",
}

# A content card is an <article> whose heading <a> points at a /news/, /event/
# or /solution/ slug, with a date nearby (DD/MM/YYYY or a <time datetime>).
# Requiring the slug pattern excludes the nav chrome and collection breadcrumbs.
_EXTRACT_JS = r"""() => {
  const out = []; const seen = new Set();
  for (const art of document.querySelectorAll('article')) {
    let a = null;
    for (const cand of art.querySelectorAll('a[href]')) {
      const h = cand.getAttribute('href') || '';
      if (/\/(news|event|solution)\//.test(h)) { a = cand; break; }
    }
    if (!a) continue;
    const href = a.getAttribute('href') || '';
    // The title lives in the card heading, not always in the link text.
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

# Thematic-collection menu: each entry is one hub. Names come from the rendered
# nav (the site's own labels), not from us.
_COLLECTIONS_JS = r"""() => {
  const out = []; const seen = new Set();
  for (const a of document.querySelectorAll('a[href*="/collection/"]')) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/\/collection\/([a-z0-9-]+)(\/?(\?|#|$))/i);
    if (!m) continue;
    const slug = m[1];
    const name = (a.textContent || '').trim();
    if (name.length < 3 || seen.has(slug)) continue;
    seen.add(slug);
    out.push({ slug, name });
  }
  return out;
}"""

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# The thematic hubs we surface in the collections directory (the genuine content
# collections, not portal-function pages). Verified on the portal nav 30 Jun 2026.
_DIRECTORY_SLUGS = [
    "open-source-observatory-osor", "semic-support-centre", "eugovtech",
    "public-sector-tech-watch", "iopeu-monitoring", "eupl",
    "european-interoperability-reference-architecture-eira",
    "digital-ready-policymaking", "interoperability-regulatory-sandboxes",
    "guidelines-sharing-interoperability-solutions", "interoperable-europe-academy",
    "portal-support",
]


def _abs(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return _BASE + href
    return href.split("#")[0]


def collection_key(url: str | None) -> str | None:
    """The collection slug encoded in an Interoperable Europe URL, or None."""
    if not url:
        return None
    m = re.search(r"/collection/([a-z0-9-]+)/", url, re.I)
    return m.group(1).lower() if m else None


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)  # ISO
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)  # DD/MM/YYYY
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", s)  # DD Month YYYY
            if not m:
                return None
            d = int(m.group(1)); mo = _MONTHS.get(m.group(2).lower()); y = int(m.group(3))
            if not mo:
                return None
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


async def _render(page, url: str, *, scrolls: int = 0, settle_ms: int = 2500) -> str | None:
    try:
        # Listings populate their cards via AJAX after first paint, so wait for
        # the network to settle (domcontentloaded fires too early -> empty page).
        try:
            await page.goto(url, wait_until="networkidle", timeout=55000)
        except Exception:
            await page.goto(url, wait_until="domcontentloaded", timeout=55000)
        await page.wait_for_timeout(settle_ms)
        for _ in range(scrolls):
            await page.mouse.wheel(0, 6000)
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
            # anti-hallucination: keep only real, on-site content URLs.
            if not url.startswith(_BASE) or url in seen:
                continue
            seen.add(url)
            ck = collection_key(url)
            items.append(Item(
                body_code="interoperable", item_type=item_type,
                title=clean(r["title"])[:300], public_url=url,
                document_date=_parse_date(r.get("date")), creation_date=now,
                source_kind="html", guid=url,
                extras={"collection": ck} if ck else {}))
        if fetch_bodies:
            for it in items[:body_cap]:
                html = await _render(page, it.public_url, settle_ms=900)
                if html:
                    it.body_txt, it.body_html = extract_html(html)
        await b.close()
    return items


async def _scrape_collections(*, fetch_bodies: bool) -> list[Item]:
    """One snapshot per thematic hub: title + standing description, fetched from
    the hub's own /collection/{slug} page. Names are the site's own."""
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    items: list[Item] = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        # the site's own labels for each hub, captured from the rendered nav
        if await _render(page, _BASE + "/", settle_ms=2500) is None:
            await b.close()
            return []
        nav = {c["slug"]: c["name"] for c in await page.evaluate(_COLLECTIONS_JS)}
        for slug in _DIRECTORY_SLUGS:
            url = f"{_BASE}/collection/{slug}"
            html = await _render(page, url, settle_ms=1500)
            if not html:
                continue
            meta = await page.evaluate(r"""() => {
              const h1 = document.querySelector('main h1, h1');
              return { title: h1 ? h1.textContent.trim() : null };
            }""")
            title = clean(meta.get("title") or nav.get(slug) or slug.replace("-", " "))[:300]
            body_txt, body_html = (extract_html(html) if fetch_bodies else (None, None))
            items.append(Item(
                body_code="interoperable", item_type="collection", title=title,
                public_url=url, document_date=None, creation_date=now,
                source_kind="html", guid=url, body_txt=body_txt, body_html=body_html,
                extras={"collection": slug}))
        await b.close()
    return items


def _run(coro):
    return asyncio.run(coro)


def ingest_interoperable_news(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("news", _LISTINGS["news"], fetch_bodies=fetch_bodies, scrolls=6, body_cap=40))


def ingest_interoperable_events(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("event", _LISTINGS["event"], fetch_bodies=fetch_bodies, scrolls=6, body_cap=40))


def ingest_interoperable_solutions(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_listing("solution", _LISTINGS["solution"], fetch_bodies=fetch_bodies, scrolls=6, body_cap=40))


def ingest_interoperable_collections(*, fetch_bodies: bool = True) -> list[Item]:
    return _run(_scrape_collections(fetch_bodies=fetch_bodies))
