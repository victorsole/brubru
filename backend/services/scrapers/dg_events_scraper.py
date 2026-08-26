"""
European Commission DG / agency events scraper (My EU Calendar source).

Parses the EC "What's on" Drupal component (ECL `ecl-content-item` with an
`ecl-date-block`) shared across ~30 DG + executive-agency `/events_en` pages, plus
best-effort handling for Eurostat, data.europa.eu and the transparency SPAs.

NO LLM / NO Anthropic. DG subdomains render to a normal browser-UA fetch (no WAF,
per docs/api/eu_commission_data_access.md); SPA pages fall back to the Playwright
WAF fetcher. Source registry: dg_events_sources.py.
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import date
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")
_TAG = re.compile(r"<[^>]+>")

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"]) if m}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})

# One event card.
_ARTICLE = re.compile(r'<article\s+class="ecl-content-item.*?</article>', re.S)
_DAY = re.compile(r'ecl-date-block__day"[^>]*>\s*(\d{1,2})\s*<', re.S)
_MONTH = re.compile(r'ecl-date-block__month"[^>]*title="([^"]+)"', re.S)
_MONTH_TXT = re.compile(r'ecl-date-block__month"[^>]*>\s*([A-Za-z]{3,})\s*<', re.S)
_YEAR = re.compile(r'ecl-date-block__year"[^>]*>\s*(\d{4})\s*<', re.S)
_TITLE = re.compile(r'ecl-content-block__title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_META = re.compile(r'ecl-content-block__primary-meta-item">\s*([^<]+?)\s*<', re.S)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", s or ""))).strip()


def _event_type(meta: Optional[str], is_agency: bool) -> str:
    m = (meta or "").lower()
    if "workshop" in m:
        return "workshop"
    if "webinar" in m:
        return "webinar"
    if "training" in m:
        return "training"
    if "round" in m:
        return "roundtable"
    if any(k in m for k in ("conference", "summit", "forum", "high-level", "signature")):
        return "conference"
    return "agency_event" if is_agency else "conference"


def _slug_id(href: str) -> str:
    path = urlparse(href).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or path


def fetch_html(url: str, kind: str) -> str:
    """Browser-UA HTTP for DG pages; Playwright WAF fallback for SPA/empty."""
    spa = kind in ("agenda", "lobby", "expert_group", "college_calendar")
    if not spa:
        try:
            import httpx
            r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": _UA})
            if r.status_code == 200 and len(r.text) > 1500:
                return r.text
            logger.info(f"[DG-EVENTS] {url} -> HTTP {r.status_code} len {len(r.text)}; trying WAF browser")
        except Exception as e:
            logger.info(f"[DG-EVENTS] httpx failed for {url}: {e}; trying WAF browser")
    # SPA or HTTP failure -> Playwright
    try:
        from services.scrapers.waf_browser_fetcher import fetch_one
        res = fetch_one(url, expand_accordions=False, strip_chrome=False)
        return res.html or ""
    except Exception as e:
        logger.warning(f"[DG-EVENTS] WAF browser failed for {url}: {e}")
        return ""


def parse_oe_events(html: str, base_url: str, *, is_agency: bool) -> List[Dict]:
    """Parse the ECL 'What's on' event cards into normalised event dicts."""
    out: List[Dict] = []
    seen: set = set()
    for m in _ARTICLE.finditer(html or ""):
        block = m.group(0)
        tm = _TITLE.search(block)
        if not tm:
            continue
        href, title = tm.group(1), _clean(tm.group(2))
        if not title:
            continue
        day = _DAY.search(block)
        year = _YEAR.search(block)
        mon = _MONTH.search(block) or _MONTH_TXT.search(block)
        start = None
        if day and year and mon:
            mi = _MONTHS.get(mon.group(1).strip().lower())
            if mi:
                try:
                    start = date(int(year.group(1)), mi, int(day.group(1)))
                except ValueError:
                    start = None
        if not start:
            continue  # no usable date -> not a calendar event
        full_url = urljoin(base_url, href)
        ext = _slug_id(href)
        if ext in seen:
            continue
        seen.add(ext)
        meta = _META.search(block)
        out.append({
            "title": title[:480],
            "start_date": start,
            "all_day": True,
            "source_url": full_url,
            "external_id": ext,
            "event_type": _event_type(meta.group(1) if meta else None, is_agency),
        })
    return out


def scrape_source(src: Dict) -> List[Dict]:
    """Fetch + parse one registry source into event dicts (with institution/dg tags)."""
    kind = src.get("kind")
    # Meeting registers / already-covered agendas are not public-event feeds.
    if kind in ("agenda", "lobby", "expert_group"):
        logger.info(f"[DG-EVENTS] skip {kind} (not a public-event feed / already covered): {src['url']}")
        return []

    html = fetch_html(src["url"], kind)
    if not html:
        logger.warning(f"[DG-EVENTS] no HTML for {src['url']}")
        return []

    is_agency = bool(src.get("agency"))
    # oe_event, eurostat, dataeuropa, college_calendar all use the ECL card markup
    # to varying degrees; try the oe_event parser (it no-ops cleanly if absent).
    events = parse_oe_events(html, src["url"], is_agency=is_agency)

    dg = src.get("dg")
    agency = src.get("agency")
    src_key = dg or agency or "EC"
    for e in events:
        e["institution"] = src.get("institution", "COMMISSION")
        e["commission_dg"] = dg
        e["source"] = f"dg_events:{src_key}"
        if agency:
            e["organiser"] = agency
    if not events:
        logger.info(f"[DG-EVENTS] 0 events parsed from {src['url']} (kind={kind})")
    return events
