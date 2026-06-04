"""
On-demand recital + article counter for the Comparator.

When `eu_laws.extra_metadata.recital_article_map` is empty for a CELEX, fall
back to fetching + parsing the act through Brubru's existing
`EurlexFetcher` + `EurlexParser` pipeline (hits Cellar / EUR-Lex web). Hard
timeout of 12 seconds so a slow upstream never hangs Comparator compute.

Once we get a count, we cache it back into `eu_laws.extra_metadata.structure_counts`
so subsequent computes are instant. Subsequent (re)compute calls read the
cache without hitting Cellar.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.parsers.eurlex_parser import EurlexParser


_TIMEOUT_SECONDS = 25.0


def _cellar_url(celex: str) -> str:
    """Cellar (Publications Office) endpoint. Adopted acts return XHTML directly;
    Commission proposals return HTTP 300 with a multi-choice listing of PDFs.
    Per CLAUDE.md (26 April 2026): requires BOTH `Accept: application/xhtml+xml`
    AND `Accept-Language: en`."""
    return f"https://publications.europa.eu/resource/celex/{celex}"


def _eurlex_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


_PDF_CHOICE_PATTERN = re.compile(
    r'href="(http://publications\.europa\.eu/resource/cellar/[^"]+/DOC_\d+)"',
)


async def _try_cellar_xhtml(client: httpx.AsyncClient, celex: str) -> Optional[Tuple[int, int]]:
    """Adopted-act path: Cellar serves the XHTML body directly."""
    headers = {"Accept": "application/xhtml+xml", "Accept-Language": "en"}
    try:
        resp = await client.get(_cellar_url(celex), headers=headers)
    except Exception:
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    try:
        doc = EurlexParser().parse_html(resp.text)
    except Exception:
        return None
    recitals = doc.recitals or []
    articles = doc.articles or []
    if not recitals and not articles:
        return None
    return (len(recitals), len(articles))


async def _try_cellar_pdf(client: httpx.AsyncClient, celex: str) -> Optional[Tuple[int, int]]:
    """Proposal path: Cellar returns 300 with a multi-choice listing of PDFs.
    We grab DOC_1 (the act body, not the annex) and parse with pypdf.

    Counting strategy: Cellar PDFs use sequential `Article N` headings and
    `(N)` recital markers. We take the MAX numbered occurrence as the count
    (conservative for both since both are sequentially numbered in EU acts).
    """
    headers = {"Accept": "application/pdf", "Accept-Language": "en"}
    try:
        resp = await client.get(_cellar_url(celex), headers=headers)
    except Exception:
        return None
    if resp.status_code != 300 or not resp.text:
        return None
    pdf_urls = _PDF_CHOICE_PATTERN.findall(resp.text)
    if not pdf_urls:
        return None
    # DOC_1 is the act body; DOC_2+ are annexes. Pick DOC_1.
    pdf_urls.sort()  # alphabetical = DOC_1 first
    pdf_url = pdf_urls[0]
    try:
        pdf_resp = await client.get(pdf_url)
    except Exception:
        return None
    if pdf_resp.status_code != 200 or not pdf_resp.content:
        return None
    return _count_in_pdf_bytes(pdf_resp.content)


def _count_sequential(numbers) -> int:
    """Robust count for sequentially-numbered EU legal elements.

    EU acts number recitals/articles 1..N. Raw detection over-counts: a
    cross-reference like "Article 13" in the body, or an annex, adds duplicate
    or out-of-order numbers. Taking the longest contiguous run starting at 1
    ignores both duplicates and spurious high numbers; falls back to max(ints)
    if there's no run from 1.
    """
    ints = sorted({int(n) for n in numbers if str(n).isdigit()})
    if not ints:
        return 0
    run = 0
    for expected, value in enumerate(ints, start=1):
        if value == expected:
            run = value
        else:
            break
    return run or max(ints)


def _count_in_pdf_bytes(data: bytes) -> Optional[Tuple[int, int]]:
    """Extract recital + article counts from a PDF body."""
    try:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        full_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return None
    if not full_text:
        return None
    article_nums = re.findall(r'(?:^|\n)\s*Article\s+(\d+)\b', full_text)
    recital_nums = re.findall(r'(?:^|\n)\s*\((\d+)\)\s', full_text)
    article_count = _count_sequential(article_nums)
    recital_count = _count_sequential(recital_nums)
    if article_count == 0 and recital_count == 0:
        return None
    return (recital_count, article_count)


async def _fetch_async(celex: str) -> Optional[Tuple[int, int]]:
    """Two-step fetch: try Cellar XHTML (adopted acts), fall back to Cellar PDF
    (proposals). Both paths return (recital_count, article_count) or None."""
    headers = {
        "User-Agent": "Brubru/1.0 (EU Policy Assistant; +https://brubru.beresol.eu)",
    }
    async with httpx.AsyncClient(
        timeout=_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
    ) as client:
        result = await _try_cellar_xhtml(client, celex)
        if result is not None:
            return result
        return await _try_cellar_pdf(client, celex)


def _fetch_via_waf_browser(celex: str) -> Optional[Tuple[int, int]]:
    """Final fallback: render the EUR-Lex HTML through the Playwright WAF browser
    and count recitals/articles with EurlexParser.

    httpx Cellar paths only serve XHTML for adopted acts; Commission proposals
    (PC/JC/DC) are PDF-only and frequently fail to parse cleanly. The rendered
    EUR-Lex HTML, however, is clean — this is the same source the Amendator uses.
    """
    try:
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
        from services.parsers.eurlex_parser import EurlexParser
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"
        with WafBrowserFetcher() as fetcher:
            html = fetcher.fetch(url, expand_accordions=False).html or ""
        if not html:
            return None
        parsed = EurlexParser().parse_html(html)
        # Count by longest contiguous run from 1, not len() — EurlexParser
        # mis-detects in-body cross-references ("Article 13") as extra articles.
        recital_count = _count_sequential([r.number for r in parsed.recitals])
        article_count = _count_sequential([a.number for a in parsed.articles])
        if recital_count == 0 and article_count == 0:
            return None
        return (recital_count, article_count)
    except Exception:
        return None


def fetch_structure_counts(celex: str) -> Optional[Tuple[int, int]]:
    """Synchronous wrapper with hard timeout. Returns None on timeout/failure.

    Safe to call from sync FastAPI endpoints; uses a fresh event loop so we
    don't collide with any caller-managed loop. Order: Cellar XHTML (adopted) ->
    Cellar PDF (proposals) -> WAF-browser EUR-Lex HTML (clean proposal fallback).
    """
    if not celex:
        return None
    try:
        result = asyncio.run(asyncio.wait_for(_fetch_async(celex), timeout=_TIMEOUT_SECONDS))
    except (asyncio.TimeoutError, RuntimeError):
        result = None
    except Exception:
        result = None
    if result is not None:
        return result
    # Cellar paths failed (typical for Commission proposals) — try the clean
    # rendered HTML via the WAF browser.
    return _fetch_via_waf_browser(celex)


def cache_structure_counts(db: Session, celex: str, counts: Tuple[int, int]) -> None:
    """Persist counts into eu_laws.extra_metadata.structure_counts so future
    Comparator computes for this CELEX skip the slow path."""
    if not celex or counts is None:
        return
    recital_count, article_count = counts
    payload: Dict[str, Any] = {
        "recital_count": recital_count,
        "article_count": article_count,
        "source": "comparator_structure_extractor",
    }
    try:
        db.execute(
            text(
                """
                UPDATE eu_laws
                SET extra_metadata = COALESCE(extra_metadata, '{}'::jsonb)
                                    || jsonb_build_object('structure_counts', CAST(:p AS JSONB))
                WHERE celex = :celex
                """
            ),
            {"celex": celex, "p": json.dumps(payload)},
        )
        db.commit()
    except Exception:
        db.rollback()


def read_cached_counts(db: Session, celex: str) -> Optional[Tuple[int, int]]:
    """Return cached (recital, article) tuple if present in eu_laws."""
    row = db.execute(
        text(
            """
            SELECT extra_metadata->'structure_counts' AS sc
            FROM eu_laws
            WHERE celex = :celex
            LIMIT 1
            """
        ),
        {"celex": celex},
    ).fetchone()
    if not row or not row[0]:
        return None
    sc = row[0]
    if not isinstance(sc, dict):
        return None
    rc = sc.get("recital_count")
    ac = sc.get("article_count")
    if isinstance(rc, int) and isinstance(ac, int):
        return (rc, ac)
    return None
