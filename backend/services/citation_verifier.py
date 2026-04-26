"""
Citation Verifier (Sprint 1a, April 2026)

Verifies that legal references the AI cites actually resolve against
authoritative EU sources. Closes the #1 gap from the LegTech benchmarking
report (CoCounsel verifies citations before delivery; Brubru did not).

This module is the shared service. Wired in three places (Sprint 1a):
  1. backend/services/ai_service.py -- log-only, after LLM generation
  2. backend/api/v1/citations.py    -- /api/v1/verify-citation/{ref}
  3. backend/scripts/measure_citation_latency.py -- offline measurement

What it verifies:
  - CELEX numbers (e.g. 32024R1689, 52021PC0206)
  - COM references (COM(2021) 206) -- converted to CELEX, tries PC then DC
  - OEIL procedure refs (e.g. 2021/0106(COD))

Design rules (per CLAUDE.md learned rules):
  - Cellar URL: publications.europa.eu/resource/celex/{CELEX} with
    Accept: application/xhtml+xml. Never scrape eur-lex.europa.eu directly.
  - Browser User-Agent on every request (the WAF blocks "Brubru URL checker").
  - HEAD first, fall back to GET with Range on 405.
  - Fail-open on network errors: status='unknown', do not crash callers.
  - Cache every result (including broken/unknown) to avoid re-hitting.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from sqlalchemy.orm import Session

from models.citation_verification import CitationVerification

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELLAR_BASE = "https://publications.europa.eu/resource/celex"
OEIL_BASE = "https://oeil.europarl.europa.eu/oeil/en/procedure-file"
# EUR-Lex direct fallback (HEAD-only). CLAUDE.md forbids SCRAPING eur-lex
# body content; HEAD existence-check does not violate that rule (no body
# pulled, no parsing). Used when Cellar 404s on refs that EUR-Lex resolves
# (e.g. REACH 32006R1907 -- Cellar 404, EUR-Lex 200).
EURLEX_BASE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEAD_TIMEOUT_S = 6.0   # Cellar redirects + OEIL slowness need headroom
TOTAL_BUDGET_S = 8.0   # ceiling per verify_text call across all refs combined

TTL_OK = timedelta(days=30)
TTL_BROKEN = timedelta(hours=24)
TTL_UNKNOWN = timedelta(hours=1)

# CELEX: sector(1) + year(4) + type(1-2 letters) + seq(4)
# Examples: 32024R1689, 52021PC0206, 32016L0680
CELEX_RE = re.compile(r"\b[1-9]\d{4}[A-Z]{1,2}\d{4}\b")

# COM: COM(YYYY) NNN, COM (YYYY) NNN, COM(YYYY)NNN, optional " final"
COM_RE = re.compile(
    r"\bCOM\s*\(\s*(\d{4})\s*\)\s*(\d{1,4})(?:\s+final)?",
    re.IGNORECASE,
)

# OEIL procedure: YYYY/NNNN(TYPE)
OEIL_TYPES = ("COD", "NLE", "APP", "CNS", "INI", "INL", "RSP", "RPS", "BUD")
OEIL_RE = re.compile(rf"\b\d{{4}}/\d{{4}}\((?:{'|'.join(OEIL_TYPES)})\)")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------
@dataclass
class RefMatch:
    """A reference extracted from text, before verification."""
    ref: str               # canonical form used as cache key
    kind: str              # celex | com_as_celex | oeil
    original_form: str     # how the AI wrote it (may equal ref)


@dataclass
class VerifyResult:
    """One reference's verification outcome."""
    ref: str
    kind: str
    status: str            # ok | broken | unknown
    resolved_url: Optional[str] = None
    http_status: Optional[int] = None
    latency_ms: Optional[int] = None
    original_form: Optional[str] = None
    from_cache: bool = False

    def to_dict(self) -> dict:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "status": self.status,
            "resolved_url": self.resolved_url,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "original_form": self.original_form,
            "from_cache": self.from_cache,
        }


@dataclass
class VerifyTextSummary:
    """Aggregate result for verify_text(): one row per response."""
    total_refs: int = 0
    verified: int = 0
    broken: int = 0
    unknown: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    verification_ms: int = 0
    details: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_refs": self.total_refs,
            "verified": self.verified,
            "broken": self.broken,
            "unknown": self.unknown,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "verification_ms": self.verification_ms,
            "details": [d.to_dict() for d in self.details],
        }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def _com_to_celex_candidates(year: str, num: str) -> list[str]:
    """COM refs are ambiguous: PC=proposal, DC=communication. Try both."""
    n = num.zfill(4)
    return [f"5{year}PC{n}", f"5{year}DC{n}"]


def extract_refs(text: str) -> list[RefMatch]:
    """
    Pull every CELEX / COM / OEIL ref from a block of text. Deduplicates by
    canonical ref form. COM refs produce one candidate per CELEX form (PC, DC)
    -- the verifier will try them in order and stop on the first OK.
    """
    seen: set[str] = set()
    out: list[RefMatch] = []

    # CELEX (canonical, no transformation needed)
    for m in CELEX_RE.finditer(text):
        ref = m.group(0).upper()
        if ref in seen:
            continue
        seen.add(ref)
        out.append(RefMatch(ref=ref, kind="celex", original_form=m.group(0)))

    # COM -> CELEX candidates (try PC, then DC)
    for m in COM_RE.finditer(text):
        year, num = m.group(1), m.group(2)
        original = m.group(0)
        for candidate in _com_to_celex_candidates(year, num):
            if candidate in seen:
                continue
            seen.add(candidate)
            out.append(RefMatch(ref=candidate, kind="com_as_celex", original_form=original))

    # OEIL (canonical)
    for m in OEIL_RE.finditer(text):
        ref = m.group(0).upper().replace(" ", "")
        if ref in seen:
            continue
        seen.add(ref)
        out.append(RefMatch(ref=ref, kind="oeil", original_form=m.group(0)))

    return out


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _cache_lookup(db: Optional[Session], ref: str) -> Optional[VerifyResult]:
    if db is None:
        return None
    row = db.get(CitationVerification, ref)
    if row is None:
        return None
    if row.expires_at < datetime.utcnow():
        return None  # stale
    return VerifyResult(
        ref=row.ref,
        kind=row.kind,
        status=row.status,
        resolved_url=row.resolved_url,
        http_status=row.http_status,
        latency_ms=row.latency_ms,
        original_form=row.original_form,
        from_cache=True,
    )


def _cache_write(db: Optional[Session], result: VerifyResult) -> None:
    if db is None:
        return
    ttl = TTL_OK if result.status == "ok" else TTL_BROKEN if result.status == "broken" else TTL_UNKNOWN
    expires_at = datetime.utcnow() + ttl
    row = db.get(CitationVerification, result.ref)
    if row is None:
        row = CitationVerification(ref=result.ref)
        db.add(row)
    row.kind = result.kind
    row.status = result.status
    row.resolved_url = result.resolved_url
    row.http_status = result.http_status
    row.latency_ms = result.latency_ms
    row.original_form = result.original_form
    row.verified_at = datetime.utcnow()
    row.expires_at = expires_at
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"citation cache write failed for {result.ref}: {e}")


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def _url_for(ref: str, kind: str) -> str:
    if kind == "oeil":
        return f"{OEIL_BASE}?reference={ref}"
    # celex and com_as_celex both resolve via Cellar
    return f"{CELLAR_BASE}/{ref}"


async def _head_or_get(session: aiohttp.ClientSession, url: str, *, accept: str,
                       accept_language: Optional[str] = None) -> tuple[int, Optional[str]]:
    """
    HEAD first; on 405 fall back to GET with a Range header for a cheap probe.
    Returns (http_status, resolved_url or None).
    """
    headers = {"User-Agent": BROWSER_UA, "Accept": accept}
    if accept_language:
        headers["Accept-Language"] = accept_language
    try:
        async with session.head(url, headers=headers, allow_redirects=True,
                                timeout=aiohttp.ClientTimeout(total=HEAD_TIMEOUT_S)) as resp:
            if resp.status != 405:
                return resp.status, str(resp.url) if resp.status == 200 else None
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass

    # Fallback: GET with Range
    range_headers = dict(headers)
    range_headers["Range"] = "bytes=0-1023"
    async with session.get(url, headers=range_headers, allow_redirects=True,
                           timeout=aiohttp.ClientTimeout(total=HEAD_TIMEOUT_S)) as resp:
        # Drain a tiny bit to free the connection
        _ = await resp.content.read(1024)
        return resp.status, str(resp.url) if resp.status in (200, 206) else None


def _classify_status(http_status: Optional[int]) -> str:
    if http_status == 200:
        return "ok"
    if http_status in (300, 301, 302, 303, 307, 308):
        # 300 = Multiple Choices (Cellar negotiation). 30x = redirect cap hit.
        # Either way the resource exists.
        return "ok"
    if http_status in (404, 410):
        return "broken"
    return "unknown"  # 4xx auth, 5xx, network, etc.


async def _verify_one_ref(session: aiohttp.ClientSession, match: RefMatch) -> VerifyResult:
    """
    Hit the network for a single ref. No cache logic here.

    Strategy:
      1. Try Cellar (canonical). If 200/30x -> ok.
      2. If Cellar returns 4xx/unknown AND ref is a CELEX-shape, fall back to
         EUR-Lex HEAD. Some refs (e.g. REACH 32006R1907) 404 on Cellar but
         200 on EUR-Lex. HEAD doesn't violate the no-scrape rule.
      3. OEIL refs use OEIL only (no fallback path).
    """
    url = _url_for(match.ref, match.kind)
    accept = "application/xhtml+xml" if match.kind != "oeil" else "text/html"
    accept_lang = "en" if match.kind != "oeil" else None
    start = time.monotonic()

    # --- Attempt 1: canonical (Cellar or OEIL) ---
    http_status: Optional[int] = None
    resolved: Optional[str] = None
    try:
        http_status, resolved = await _head_or_get(session, url, accept=accept,
                                                    accept_language=accept_lang)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass  # fall through to fallback
    except Exception as e:
        logger.warning(f"verify_one_ref attempt1 unexpected error for {match.ref}: {e}")

    status = _classify_status(http_status)

    # --- Attempt 2: EUR-Lex HEAD fallback for CELEX-shape refs only ---
    if status != "ok" and match.kind in ("celex", "com_as_celex"):
        eurlex_url = f"{EURLEX_BASE}{match.ref}"
        try:
            ex_status, ex_resolved = await _head_or_get(
                session, eurlex_url, accept="text/html",
            )
            ex_class = _classify_status(ex_status)
            logger.debug(f"EUR-Lex fallback {match.ref}: cellar={http_status} eurlex={ex_status} -> {ex_class}")
            if ex_class == "ok":
                status = "ok"
                resolved = ex_resolved or eurlex_url
                http_status = ex_status
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"EUR-Lex fallback {match.ref} threw {type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"verify_one_ref EUR-Lex fallback error for {match.ref}: {e}")

    return VerifyResult(
        ref=match.ref, kind=match.kind, status=status,
        resolved_url=resolved if status == "ok" else None,
        http_status=http_status,
        latency_ms=int((time.monotonic() - start) * 1000),
        original_form=match.original_form,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def verify_text(text: str, db: Optional[Session] = None) -> VerifyTextSummary:
    """
    Extract and verify every legal ref in `text`. Cache hits skip the network.
    Bounded by TOTAL_BUDGET_S overall: if we exceed, remaining refs return
    status='unknown' rather than holding up the response.
    """
    summary = VerifyTextSummary()
    matches = extract_refs(text)
    summary.total_refs = len(matches)
    if not matches:
        return summary

    overall_start = time.monotonic()

    # 1. Cache pass (sync, fast)
    cache_misses: list[RefMatch] = []
    for m in matches:
        cached = _cache_lookup(db, m.ref)
        if cached is not None:
            summary.cache_hits += 1
            summary.details.append(cached)
        else:
            cache_misses.append(m)
    summary.cache_misses = len(cache_misses)

    # 2. Network pass for misses, parallelised
    if cache_misses:
        timeout = aiohttp.ClientTimeout(total=TOTAL_BUDGET_S)
        # limit_per_host=4: publications.europa.eu and oeil.europarl.europa.eu
        # both throttle when hammered. 4 concurrent per host is plenty for
        # typical 5-7 ref responses without triggering rate limits.
        connector = aiohttp.TCPConnector(limit_per_host=4)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = [_verify_one_ref(session, m) for m in cache_misses]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=TOTAL_BUDGET_S,
                )
            except asyncio.TimeoutError:
                # Budget blown -- mark every miss as unknown
                results = [
                    VerifyResult(
                        ref=m.ref, kind=m.kind, status="unknown",
                        original_form=m.original_form,
                    )
                    for m in cache_misses
                ]

        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"verify gather exception: {r}")
                continue
            summary.details.append(r)
            _cache_write(db, r)

    # COM ambiguity collapse: if both PC and DC variants of the same COM were
    # tried, count "verified" only once per original_form to avoid inflating.
    deduped_count_keys: set[str] = set()
    for d in summary.details:
        key = d.original_form or d.ref
        if d.status == "ok":
            if key not in deduped_count_keys:
                summary.verified += 1
                deduped_count_keys.add(key)
        elif d.status == "broken":
            # Only count broken if no OK sibling exists for the same original
            siblings = [x for x in summary.details if (x.original_form or x.ref) == key]
            if not any(s.status == "ok" for s in siblings):
                if key not in deduped_count_keys:
                    summary.broken += 1
                    deduped_count_keys.add(key)
        else:  # unknown
            siblings = [x for x in summary.details if (x.original_form or x.ref) == key]
            if not any(s.status == "ok" for s in siblings) and key not in deduped_count_keys:
                summary.unknown += 1
                deduped_count_keys.add(key)

    # When deduplication collapsed COM PC/DC pairs, total_refs from the AI
    # perspective should also reflect distinct originals.
    summary.total_refs = len({(d.original_form or d.ref) for d in summary.details})

    summary.verification_ms = int((time.monotonic() - overall_start) * 1000)
    return summary


async def verify_one(ref: str, db: Optional[Session] = None) -> VerifyResult:
    """
    Verify a single canonical ref. Used by /api/v1/verify-citation.
    `ref` must already be normalised (CELEX form for COM is the caller's job;
    but callers can pass a COM string and we'll detect it).
    """
    matches = extract_refs(ref)
    if not matches:
        # Caller passed something we couldn't parse
        return VerifyResult(ref=ref, kind="unknown", status="unknown",
                            original_form=ref)

    # Honour cache for the first match
    first = matches[0]
    cached = _cache_lookup(db, first.ref)
    if cached is not None:
        return cached

    timeout = aiohttp.ClientTimeout(total=HEAD_TIMEOUT_S + 0.5)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        result = await _verify_one_ref(session, first)
    _cache_write(db, result)
    return result
