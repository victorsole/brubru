"""
European Parliament news scraper (MEUB "News").

EP committee/delegation/press-room pages are JS-rendered (a plain fetch returns
only a shell), and they use EP's own `es_document` markup (NOT the EC ECL
component, NOT RSS). So this renders with Playwright and parses the EP
search-results items. The publication date is encoded in the press-release ID
(e.g. .../press-room/20260513IPR43316/ -> 2026-05-13).

Covers: the general press room + all 25 committees (press-releases) + all
delegations (communiques). institution='EP', source_key = committee/delegation
code. NO LLM / NO Anthropic.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Dict, List

from services.scrapers.dg_news_scraper import _clean, _canon_url, _slug_id

logger = logging.getLogger(__name__)

EP_BASE = "https://www.europarl.europa.eu"

COMMITTEES = ["AFET", "DROI", "SEDE", "DEVE", "INTA", "BUDG", "CONT", "ECON", "FISC",
              "EMPL", "ENVI", "SANT", "ITRE", "IMCO", "TRAN", "REGI", "AGRI", "PECH",
              "CULT", "JURI", "LIBE", "AFCO", "FEMM", "PETI", "EUDS"]
DELEGATIONS = ["d-af", "d-al", "d-br", "d-by", "d-ca", "d-cl", "d-cn", "d-il", "d-in",
               "d-iq", "d-ir", "d-jp", "d-md", "d-me", "d-mk", "d-mx", "d-rs", "d-ru",
               "d-tr", "d-ua", "d-uk", "d-us", "d-za"]

_ITEM = re.compile(r'es_document-title[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DATE = re.compile(r'/(\d{4})(\d{2})(\d{2})[A-Z]{2,5}\d+')


def ep_sources() -> List[Dict]:
    """Every EP news surface: press room + committees + delegations."""
    out = [{"url": f"{EP_BASE}/news/en/press-room", "source_key": "EP", "label": "Press room"}]
    for c in COMMITTEES:
        out.append({"url": f"{EP_BASE}/committees/en/{c.lower()}/home/press-releases",
                    "source_key": c, "label": f"Committee {c}"})
    for d in DELEGATIONS:
        out.append({"url": f"{EP_BASE}/delegations/en/{d}/documents/communiques",
                    "source_key": d.upper().replace("-", "_"), "label": f"Delegation {d}"})
    return out


def parse_ep(html: str) -> List[Dict]:
    """Parse EP `es_document` search-results items into normalised dicts."""
    out: List[Dict] = []
    seen: set = set()
    for m in _ITEM.finditer(html or ""):
        href, title_html = m.group(1), m.group(2)
        title = _clean(title_html)
        if not title or "/press-room/contacts/" in href or "press-officers" in href:
            continue
        url = href if href.startswith("http") else EP_BASE + href
        key = _canon_url(url)
        if key in seen:
            continue
        seen.add(key)
        nd = None
        dm = _DATE.search(url)
        if dm:
            try:
                nd = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except ValueError:
                nd = None
        out.append({
            "title": title[:480], "summary": None, "news_date": nd,
            "image_url": None, "source_url": url, "external_id": _slug_id(url),
            "item_type": "press",
        })
    return out


def scrape_ep_source(src: Dict, fetcher) -> List[Dict]:
    """Render one EP source (Playwright) + parse + tag institution=EP."""
    try:
        res = fetcher.fetch(src["url"], expand_accordions=False, strip_chrome=False)
    except Exception as e:
        logger.warning(f"[EP-NEWS] fetch failed {src['url']}: {e}")
        return []
    items = parse_ep(res.html or "")
    for it in items:
        it["institution"] = "EP"
        it["commission_dg"] = None
        it["source_key"] = src["source_key"]
        it["entry_key"] = _canon_url(it["source_url"])
    if not items:
        logger.info(f"[EP-NEWS] 0 items from {src['url']}")
    return items
