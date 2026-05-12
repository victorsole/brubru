"""
oeil_body_scraper — fetch + clean the OEIL procedure-file page body.

Produces two strings per procedure:
- html_body : section1..6 of the OEIL page, lightly cleaned (links kept,
              chrome stripped). Wrapped in <article>.
- text_body : plain-text rendering of html_body (whitespace collapsed,
              section headings preserved with newlines).

Used by:
- scripts/backfill_oeil_body.py (initial backfill + cron refresh)
- backend/api/v1/committees.py (preferred source for body_txt / body_html
  when present; falls back to description + key_events composition).

Cellar-style retry on 202/503 is unnecessary — OEIL serves these pages
synchronously. We do retry on transient 5xx once.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

OEIL_BASE = "https://oeil.europarl.europa.eu/oeil/en/procedure-file"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Brubru-OEIL-scraper/1.0"
)

# Sections to extract. OEIL uses <div id="sectionN" class="erpl-product-content
# oeil-spy-section …"> for each major card. We keep 1-6 (the substantive
# content); section 7+ are link bars we don't need.
SECTION_IDS = ["section1", "section2", "section3", "section4", "section5", "section6"]


@dataclass
class OeilBody:
    html_body: str
    text_body: str


def _strip_attrs(tag: Tag) -> None:
    """Strip noisy attributes everywhere — keep only structural ones."""
    keep = {"href", "src", "alt", "id"}
    for el in tag.find_all(True):
        attrs = {k: v for k, v in el.attrs.items() if k in keep}
        # Drop in-page anchors that point to OEIL navigation only
        if el.name == "a" and isinstance(attrs.get("href"), str) and attrs["href"].startswith("#"):
            attrs.pop("href", None)
        el.attrs = attrs


def _remove_junk(soup: BeautifulSoup) -> None:
    """Drop tooltip popups, anchor-target spans, hidden helpers."""
    for cls in ["sr-only", "popover", "tooltip", "es_links-list", "fa", "fas", "far"]:
        for el in soup.select(f".{cls}"):
            el.decompose()
    # Drop empty divs / spans
    for el in soup.find_all(["div", "span"]):
        if not el.get_text(strip=True) and not el.find(["a", "img"]):
            el.decompose()


def _absolutise_links(soup: BeautifulSoup) -> None:
    """Convert relative href / src to absolute (https://oeil…) so partners
    can follow them outside OEIL's frame."""
    base = "https://oeil.europarl.europa.eu"
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            a["href"] = base + href
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("/"):
            img["src"] = base + src


def parse_body(html: str) -> Optional[OeilBody]:
    """Return cleaned (html_body, text_body) or None if the page doesn't
    contain any of the expected section anchors."""
    soup = BeautifulSoup(html, "html.parser")
    sections: List[Tag] = []
    for sid in SECTION_IDS:
        div = soup.find("div", id=sid)
        if div:
            sections.append(div)
    if not sections:
        return None

    # Build a fresh BeautifulSoup with just the extracted sections so the
    # rest of the page (header, footer, JS) is dropped.
    out_soup = BeautifulSoup("<article></article>", "html.parser")
    article = out_soup.article
    for sec in sections:
        article.append(sec)
    _remove_junk(out_soup)
    _strip_attrs(out_soup)
    _absolutise_links(out_soup)

    html_body = str(out_soup)
    # Plain text — preserve section breaks via newlines around headings/list items
    for el in out_soup.find_all(["h1", "h2", "h3", "h4", "li", "p", "tr"]):
        el.append("\n")
    text = out_soup.get_text(separator=" ")
    # Collapse whitespace but preserve newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return OeilBody(html_body=html_body, text_body=text)


async def fetch_one(oeil_ref: str, client: httpx.AsyncClient) -> Optional[OeilBody]:
    """Fetch + parse a single OEIL procedure-file page. Returns None on any
    error so the caller can skip and move on."""
    url = f"{OEIL_BASE}?reference={oeil_ref}"
    try:
        r = await client.get(url, timeout=30.0)
        if r.status_code in (502, 503, 504):
            await asyncio.sleep(2.0)
            r = await client.get(url, timeout=30.0)
        if r.status_code != 200:
            logger.warning("[oeil-body] %s HTTP %s", oeil_ref, r.status_code)
            return None
        return parse_body(r.text)
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("[oeil-body] %s fetch error: %s", oeil_ref, exc)
        return None


async def fetch_many(oeil_refs: List[str], concurrency: int = 4) -> dict:
    """Fetch a batch with bounded concurrency. Returns {oeil_ref: OeilBody|None}."""
    out: dict = {}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        follow_redirects=True,
    ) as client:
        async def _go(ref: str) -> None:
            async with sem:
                out[ref] = await fetch_one(ref, client)
        await asyncio.gather(*(_go(r) for r in oeil_refs))
    return out
