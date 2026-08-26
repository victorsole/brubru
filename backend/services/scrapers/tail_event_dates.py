"""
Per-body event-date resolvers for the small "tail" of bodies whose event scrapers
captured the title + URL but not document_date (same class of miss as Cedefop, but
each site stores the date differently). Each resolver targets the EVENT date
specifically, not an arbitrary date in the page body (e.g. a publish stamp or a
year inside an anniversary title), so a wrong date is never written.

Used by scripts/backfill_event_dates.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")}
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_DMY = re.compile(r'\b(\d{1,2})\s+(' + "|".join(_MONTHS) + r')\s+(20\d{2})\b', re.I)
_ISO = re.compile(r'\b(20\d{2})-(\d{2})-(\d{2})\b')


def _from_dmy(text: str) -> datetime | None:
    m = _DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _from_iso(text: str) -> datetime | None:
    m = _ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _jsonld_start(soup) -> datetime | None:
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if o.get("startDate"):
                    return _from_iso(str(o["startDate"]))
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    return None


def _time_tag(soup, *, allow_any: bool) -> datetime | None:
    for t in soup.find_all("time"):
        dt = t.get("datetime")
        if not dt:
            continue
        if allow_any:
            d = _from_iso(dt) or _from_dmy(t.get_text(" ", strip=True))
            if d:
                return d
            continue
        ctx = " ".join(t.get("class", []))
        for anc in t.parents:
            ctx += " " + " ".join(anc.get("class", []) if hasattr(anc, "get") else [])
            if len(ctx) > 400:
                break
        if any(k in ctx.lower() for k in ("event", "when", "start", "daterange", "field-date", "date-display")):
            d = _from_iso(dt)
            if d:
                return d
    return None


def _resolve(url: str, *, selectors=(), allow_any_time: bool = False) -> datetime | None:
    try:
        r = requests.get(url, headers=_UA, timeout=30)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    d = _jsonld_start(soup)
    if d:
        return d
    for sel in selectors:
        for el in soup.select(sel):
            d = _from_dmy(el.get_text(" ", strip=True)) or _from_iso(el.get_text(" ", strip=True))
            if d:
                return d
    return _time_tag(soup, allow_any=allow_any_time)


# Per-body resolvers (verified against live samples 26 Jun 2026).
def eca_event_date(url):    return _resolve(url, allow_any_time=True)                       # <time datetime>
def eda_event_date(url):    return _resolve(url, selectors=[".event-dates", ".post-event-data"])
def sesar_event_date(url):  return _resolve(url, selectors=[".date-details .date", ".date-details"])
def euiss_event_date(url):  return _resolve(url)                                            # event-scoped <time>
def eige_event_date(url):   return _resolve(url)                                            # event-scoped <time>
def cinea_event_date(url):  return _resolve(url)                                            # JSON-LD startDate


# --- Comprehensive extractor + Playwright bulk path (JS-walled / 403 bodies) --- #

def extract_event_date(html: str) -> datetime | None:
    """All strategies in priority order: JSON-LD startDate, event-scoped <time>,
    any <time datetime>, then a DMY/ISO inside a date-labelled element."""
    soup = BeautifulSoup(html, "html.parser")
    return (_jsonld_start(soup)
            or _time_tag(soup, allow_any=False)
            or _time_tag(soup, allow_any=True)
            or _date_in_labelled_element(soup))


def _date_in_labelled_element(soup) -> datetime | None:
    for el in soup.find_all(True):
        cls = " ".join(el.get("class", [])).lower()
        idv = (el.get("id") or "").lower()
        if not any(k in cls + " " + idv for k in ("date", "when", "event-time", "schedule", "calendar")):
            continue
        txt = el.get_text(" ", strip=True)
        if len(txt) > 80:
            continue
        d = _from_dmy(txt) or _from_iso(txt)
        if d:
            return d
    return None


async def _pw_dates_async(urls, on_result, *, wait_ms=5000, pace=1.5):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(user_agent=_UA["User-Agent"])
        pg = await ctx.new_page()
        for url in urls:
            d = None
            try:
                await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                await pg.wait_for_timeout(wait_ms)
                d = extract_event_date(await pg.content())
            except Exception:
                pass
            on_result(url, d)
            await pg.wait_for_timeout(int(pace * 1000))
        await b.close()


def playwright_event_dates_bulk(urls, on_result) -> None:
    """One-browser bulk resolver for JS-rendered / 403 event pages."""
    import asyncio
    asyncio.run(_pw_dates_async(urls, on_result))
