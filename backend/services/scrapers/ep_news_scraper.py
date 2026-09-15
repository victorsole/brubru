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

# The PRESS ROOM does not use `es_document`. It renders `ep-m_product` article
# cards: <div class="ep_title"><a href=".../press-room/<ID>/<slug>"> ... <span
# class="ep_name">Title</span>. parse_ep() only knew the committee/delegation
# markup, so the press-room source returned 0 items on EVERY run since it was
# added: eu_news_items held 407 EP rows, all tagged with a committee source_key
# and not one with source_key 'EP'. Every release a committee page does not
# carry (plenary openings, press briefings, "EP Today", the President's office,
# antenna offices) was never ingested, which read as "EP news stops at 11 Sep"
# on 15 Sep 2026 while the press room had published three releases since.
_PRODUCT_CARD = re.compile(
    r'<article[^>]*ep-m_product[^>]*>(.*?)</article>', re.S)
_CARD_LINK = re.compile(
    r'class="ep_title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_CARD_SUMMARY = re.compile(r'class="ep-a_text"[^>]*>(.*?)</div>', re.S)
# The card's own publication time. Preferred over the ID date, which is when the
# document was CREATED: "EP TODAY | Tuesday 15 September" carries ID 20260910IPR47441
# but datePublished 2026-09-15. Committee pages show the ID date, so a card date is
# marked date_source='published' and the sync lets it override an ID date, never
# the reverse (otherwise the two sources flip the stored date on every run).
_CARD_PUBLISHED = re.compile(r'itemprop="datePublished"\s+datetime="(\d{4})-(\d{2})-(\d{2})')
# A press-room URL with its slug: .../press-room/20260914IPR47510/european-...
# The committee pages link the SAME release as .../press-room/20260914IPR47510/
# (no slug). Both must reduce to one identity or every release a committee page
# also lists is stored twice under two entry_keys.
_PRESS_ID_URL = re.compile(
    r'^(https?://www\.europarl\.europa\.eu/news/[a-z]{2}/press-room/\d{8}[A-Z]{2,5}\d+)(?:/.*)?$')


def canonical_ep_url(url: str) -> str:
    """Strip the slug from a press-room URL so both EP markups share one identity."""
    m = _PRESS_ID_URL.match(url or "")
    return (m.group(1) + "/") if m else url


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
    matches = [(m.group(1), m.group(2), None, None) for m in _ITEM.finditer(html or "")]
    for card in _PRODUCT_CARD.finditer(html or ""):
        lm = _CARD_LINK.search(card.group(1))
        if not lm:
            continue
        sm = _CARD_SUMMARY.search(card.group(1))
        pm = _CARD_PUBLISHED.search(card.group(1))
        published = None
        if pm:
            try:
                published = date(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)))
            except ValueError:
                published = None
        matches.append((lm.group(1), lm.group(2), _clean(sm.group(1)) if sm else None, published))
    for href, title_html, summary, published in matches:
        title = _clean(title_html)
        if not title or "/press-room/contacts/" in href or "press-officers" in href:
            continue
        url = canonical_ep_url(href if href.startswith("http") else EP_BASE + href)
        key = _canon_url(url)
        if key in seen:
            continue
        seen.add(key)
        nd = published
        dm = None if nd else _DATE.search(url)
        if dm:
            try:
                nd = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except ValueError:
                nd = None
        out.append({
            "title": title[:480], "summary": (summary or None), "news_date": nd,
            "image_url": None, "source_url": url, "external_id": _slug_id(url),
            "item_type": "press",
            "date_source": "published" if published else ("id" if nd else None),
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
