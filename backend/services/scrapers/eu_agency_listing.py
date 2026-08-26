"""Generic listing scraper for the server-rendered EU agency sites
(api_socjust.md: Cedefop, ERA, Eurofound, EUAA, ...).

These are mostly Drupal/EU-theme sites whose news / events / publications
listings are server-rendered and paginated with ?page=N (0-indexed). The card
markup differs per agency, but every item is an <a> whose href sits under a known
path prefix, with the title as the anchor text and the date in a nearby <time>
tag or a "DD Mon YYYY" string. This walker extracts items by that contract, so a
new agency is one thin wrapper: walk(base, path, body_code, item_type, link_substr).
"""
from __future__ import annotations

import html as _html
import re
import time
from datetime import datetime, timezone

import requests

from services.scrapers.economy_common import Item, clean

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}
_ISO = re.compile(r'datetime="(\d{4}-\d{2}-\d{2})')
_DMY = re.compile(r'(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})')
_HEADING = re.compile(r'<h[1-4][^>]*>(.*?)</h[1-4]>', re.S)
_GENERIC = {"read more", "read", "more", "details", "learn more", "view", "download", "see more"}


def _txt(x: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip())


def _date(window: str) -> datetime | None:
    m = _ISO.search(window)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    m = _DMY.search(_txt(window))
    if m:
        try:
            return datetime.strptime(m.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _parse_page(text: str, anchor: re.Pattern, base: str, path: str, body_code: str,
                item_type: str, source_kind: str, min_title: int, out: dict, now) -> int:
    new = 0
    for m in anchor.finditer(text):
        href, raw = m.group(1), m.group(2)
        title = _txt(raw)
        url = href if href.startswith("http") else base + href
        if url in out or url.rstrip("/") == f"{base}{path}".rstrip("/"):
            continue
        window = text[max(0, m.start() - 600): m.end() + 120]
        # "Read More"-style cards: the anchor text is generic, so take the
        # title from the nearest heading in the card window.
        if title.lower() in _GENERIC or len(title) < min_title:
            heads = [_txt(h) for h in _HEADING.findall(window)]
            heads = [h for h in heads if len(h) >= min_title and h.lower() not in _GENERIC]
            if heads:
                title = heads[-1]
        if len(title) < min_title:
            continue
        dt = _date(window)
        lines = [l for l in [title, f"Date: {dt.date()}" if dt else ""] if l]
        out[url] = Item(
            body_code=body_code, item_type=item_type, title=clean(title)[:120],
            public_url=url, summary=clean(title)[:200],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=dt, creation_date=now, source_kind=source_kind, guid=url)
        new += 1
    return new


def _anchor_re(link_substr: str) -> re.Pattern:
    return re.compile(
        r'<a\s+[^>]*href="(' + re.escape(link_substr) + r'[^"#?]*)"[^>]*>(.*?)</a>', re.S)


def walk(base: str, path: str, body_code: str, item_type: str, link_substr: str,
         source_kind: str, *, min_title: int = 12, max_pages: int = 200,
         page_param: str = "page", page_start: int = 0) -> list[Item]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    anchor = _anchor_re(link_substr)
    for page in range(page_start, page_start + max_pages):
        try:
            r = s.get(f"{base}{path}", params={page_param: page}, timeout=40)
        except requests.RequestException:
            break
        if r.status_code != 200:
            break
        if _parse_page(r.text, anchor, base, path, body_code, item_type, source_kind,
                       min_title, out, now) == 0:
            break
        time.sleep(0.2)
    return list(out.values())


async def walk_browser(base: str, path: str, body_code: str, item_type: str, link_substr: str,
                       source_kind: str, *, min_title: int = 12, max_pages: int = 250,
                       page_param: str = "page", page_start: int = 0,
                       settle_ms: int = 1800, on_page=None) -> list[Item]:
    """Playwright variant for sites behind a JS / proof-of-work wall (e.g. FRA's
    Anubis). Renders each ?page=N in a real browser, then reuses _parse_page.
    on_page(list[Item]) is called with each page's NEW items for incremental
    persistence (the walk is slow, so a resumable backfill upserts per page)."""
    from playwright.async_api import async_playwright
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    anchor = _anchor_re(link_substr)
    sep = "&" if "?" in path else "?"
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        page = await ctx.new_page()
        for n in range(page_start, page_start + max_pages):
            url = f"{base}{path}{sep}{page_param}={n}"
            try:
                await page.goto(url, wait_until="networkidle", timeout=55000)
                await page.wait_for_timeout(settle_ms)
            except Exception:
                break
            before = set(out)
            if _parse_page(await page.content(), anchor, base, path, body_code, item_type,
                           source_kind, min_title, out, now) == 0:
                break
            if on_page is not None:
                on_page([out[u] for u in out if u not in before])
        await b.close()
    return list(out.values())


def ingest_browser(base, path, body_code, item_type, link_substr, source_kind, **kw):
    """Sync wrapper around walk_browser for the sync_economy INGESTORS registry."""
    import asyncio
    return asyncio.run(walk_browser(base, path, body_code, item_type, link_substr,
                                    source_kind, **kw))
