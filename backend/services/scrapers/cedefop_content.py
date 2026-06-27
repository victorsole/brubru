"""Cedefop — news, events, publications (generic EU-agency listing walker) + topics."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from services.scrapers.economy_common import Item, clean, http_get, extract_html
from services.scrapers.eu_agency_listing import walk

_BASE = "https://www.cedefop.europa.eu"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_EVENT_NAV = {"/en/events", "/en/events/upcoming-events", "/en/events/past-events"}

# Curated about / theme / tool landing pages, snapshotted as topics.
_TOPIC_PATHS = [
    "/en/about-cedefop/who-we-are",
    "/en/about-cedefop/what-we-do",
    "/en/themes/skills-labour-market",
    "/en/themes/vet-knowledge-centre",
    "/en/themes/delivering-vet-qualifications",
    "/en/themes/statistics",
    "/en/tools/european-skills-index",
    "/en/tools/european-vet-policy-dashboard",
    "/en/tools/skills-forecast",
    "/en/tools/skills-intelligence",
    "/en/tools/matching-skills",
    "/en/tools/european-skills-jobs-survey",
    "/en/tools/apprenticeship-schemes",
    "/en/tools/validation-non-formal-informal-learning",
    "/en/tools/mobility-scoreboard",
    "/en/tools/vet-glossary",
    "/en/tools/key-indicators-on-vet",
    "/en/tools/skills-online-vacancies",
]


def ingest_cedefop_topics(*, fetch_bodies: bool = True, **_) -> list[Item]:
    items: list[Item] = []
    now = datetime.now(timezone.utc)
    for path in _TOPIC_PATHS:
        url = _BASE + path
        r = http_get(url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.select_one("main h1, h1")
        if h1 and len(h1.get_text(strip=True)) > 2:
            title = clean(h1.get_text(" ", strip=True))
        elif soup.title and soup.title.get_text(strip=True):
            title = clean(soup.title.get_text(strip=True).split(" | ")[0].split(" - ")[0])
        else:
            title = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        body_txt, body_html = (extract_html(r.text) if fetch_bodies else (None, None))
        items.append(Item(body_code="cedefop", item_type="topic", title=title[:300],
                          public_url=url, creation_date=now, source_kind="html",
                          guid=url, body_txt=body_txt, body_html=body_html))
    return items


def ingest_cedefop_news(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/en/news", "cedefop", "news", "/en/news/", "cedefop_drupal")


def _event_start_date(card) -> datetime | None:
    """Cedefop renders the start date as <span class="day">29</span>
    <span class="month">JUN</span> <span class="year">2026</span> inside
    .field-ced-event-date .date.start (no machine-readable <time datetime>)."""
    start = card.select_one(".field-ced-event-date .date.start") or card.select_one(".date.start")
    if not start:
        return None
    day = start.select_one(".day")
    month = start.select_one(".month")
    year = start.select_one(".year")
    if not (day and month and year):
        return None
    mon = _MONTHS.get(month.get_text(strip=True).upper()[:3])
    try:
        d, y = int(day.get_text(strip=True)), int(year.get_text(strip=True))
    except ValueError:
        return None
    if not mon:
        return None
    try:
        return datetime(y, mon, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_event_cards(html: str, out: dict[str, Item], now) -> int:
    """Parse one events listing page card-by-card. div.group-content wraps exactly
    one event link + one date field, so each event is paired with its own start
    date (zip-by-index would misalign on the leading nav link)."""
    new = 0
    for card in BeautifulSoup(html, "html.parser").select("div.group-content"):
        link = next((a for a in card.select('a[href*="/en/events/"]')
                     if a.get_text(strip=True)
                     and a.get("href", "").rstrip("/") not in _EVENT_NAV
                     and a.get("href", "").rstrip("/").startswith("/en/events/")), None)
        if not link:
            continue
        href = link.get("href", "")
        url = href if href.startswith("http") else _BASE + href
        if url in out:
            continue
        title = clean(link.get_text(" ", strip=True))
        if len(title) < 6:
            continue
        dt = _event_start_date(card)
        lines = [l for l in [title, f"Date: {dt.date()}" if dt else ""] if l]
        out[url] = Item(
            body_code="cedefop", item_type="event", title=title[:120],
            public_url=url, summary=title[:200],
            body_txt=clean("\n".join(lines)),
            body_html=clean("<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"),
            document_date=dt, creation_date=now, source_kind="cedefop_drupal", guid=url)
        new += 1
    return new


def ingest_cedefop_events(*, fetch_bodies: bool = True, **_) -> list[Item]:
    # Cedefop walls the ?page= pager behind a bot challenge, so only the first
    # (no-param) page of each listing is fetchable; it carries the nearest
    # upcoming + most-recent past events, each correctly dated. The deeper history
    # is held in the DB and date-backfilled from detail pages by
    # scripts/backfill_event_dates.py.
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    now = datetime.now(timezone.utc)
    out: dict[str, Item] = {}
    for path in ("/en/events", "/en/events/past-events"):
        try:
            r = s.get(f"{_BASE}{path}", timeout=40)
        except requests.RequestException:
            continue
        if r.status_code == 200 and "/challenge" not in r.url:
            _parse_event_cards(r.text, out, now)
        time.sleep(0.3)
    return list(out.values())


async def _cedefop_dates_async(urls, on_result, *, pace: float = 4.0,
                               cooldown: float = 300.0) -> None:
    """Resolve event start dates through a single persistent headless-Chromium
    context. Cedefop rate-limits bursts behind a /challenge interstitial that
    only clears after an IP-wide cooldown (minutes), so per-row retries are
    pointless while throttled: instead, on a challenge we pause the WHOLE grind
    for `cooldown` seconds (letting the limit fully reset) and re-fetch the same
    row, never skipping it. Slow base pace keeps us under the threshold.
    on_result(url, date|None) is called per resolved row for incremental commit."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA)
        pg = await ctx.new_page()
        for url in urls:
            dt = None
            for attempt in range(6):
                try:
                    await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await pg.wait_for_timeout(3000)
                    html = await pg.content()
                except Exception:
                    break
                if "/challenge" not in pg.url:
                    dt = _event_start_date(BeautifulSoup(html, "html.parser"))
                    break
                await pg.wait_for_timeout(int(cooldown * 1000))  # ride out the IP cooldown
            on_result(url, dt)
            await pg.wait_for_timeout(int(pace * 1000))
        await b.close()


def cedefop_event_dates_bulk(urls, on_result) -> None:
    """Sync wrapper: resolve many Cedefop event dates in one browser session."""
    import asyncio
    asyncio.run(_cedefop_dates_async(urls, on_result))


def cedefop_event_date(url: str, *, retries: int = 3) -> datetime | None:
    """Fetch one Cedefop event detail page and return its start date (for the
    date backfill of rows ingested before the date parser existed). Cedefop trips
    a bot challenge under load, so a challenged response backs off and retries
    rather than silently giving up on the date."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": _UA}, timeout=40)
        except requests.RequestException:
            return None
        if r.status_code == 200 and "/challenge" not in r.url:
            return _event_start_date(BeautifulSoup(r.text, "html.parser"))
        if "/challenge" in r.url and attempt < retries - 1:
            time.sleep(10 * (attempt + 1))  # 10s, 20s — let the challenge cool off
            continue
        return None
    return None


def ingest_cedefop_publications(*, fetch_bodies: bool = True, **_) -> list[Item]:
    return walk(_BASE, "/en/publications", "cedefop", "publication", "/en/publications/",
                "cedefop_drupal")
