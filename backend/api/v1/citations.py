"""
/api/v1/verify-citation/{ref}  +  /api/v1/citations/verify?q=...

Verifies a single CELEX, COM, or OEIL reference resolves to a real EU document.
Sprint 1a (April 2026) — Sprint 1c uniform-datapoint refresh (11 May 2026):
every response now carries the 5 mandatory Brubru v1 datapoints alongside the
verification result:

  public_url       — citizen-facing EUR-Lex URL
  body_text        — plain-text body (Cellar XHTML stripped)
  body_html        — HTML body (Cellar XHTML manifestation, EN)
  creation_date    — when this CELEX first entered Brubru's eu_laws corpus
  document_date    — the document's adoption or publication date

Reuses backend/services/citation_verifier.py for the HEAD-existence check and
caches body+dates alongside in citation_verifications (TTL: 30d ok / 24h broken
/ 1h unknown), so most calls are sub-millisecond.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, date as _date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from services.citation_verifier import verify_one

from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verify-citation", tags=["v1-citations"])
citations_router = APIRouter(prefix="/citations", tags=["v1-citations"])


class VerifyCitationItem(BaseModel):
    ref: str = Field(..., description="Canonical reference (CELEX form for COM input)")
    kind: str = Field(..., description="celex | com_as_celex | oeil | unknown")
    status: str = Field(..., description="ok | broken | unknown")
    # Two distinct URLs, intentionally:
    public_url: Optional[str] = Field(
        None,
        description=(
            "Citizen-facing EUR-Lex page for the document — the link humans "
            "share. Pattern: https://eur-lex.europa.eu/legal-content/EN/TXT/"
            "?uri=CELEX:{celex}. Always populated for CELEX/COM refs."
        ),
    )
    resolved_url: Optional[str] = Field(
        None,
        description=(
            "Cellar manifestation URL the verifier hit — typically "
            "cellar/<UUID>/DOC_1, suitable for machine consumption. Distinct "
            "from public_url; partners should use public_url for display and "
            "resolved_url for downstream pipelines that consume the document."
        ),
    )
    http_status: Optional[int] = None
    latency_ms: Optional[int] = Field(None, description="Network latency on the verifying call (null on cache hit)")
    original_form: Optional[str] = Field(None, description="The form the caller passed in")
    from_cache: bool = False
    # The 5 mandatory Brubru v1 datapoints
    body_text: Optional[str] = Field(
        None,
        description="Plain-text body of the document (Cellar XHTML stripped to text). Null when document is metadata-only or body fetch failed.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML body of the document (Cellar XHTML manifestation, EN). Null when XHTML manifestation is unavailable.",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When this CELEX first entered Brubru's eu_laws corpus (our scrape date). Null when CELEX is not in the corpus.",
    )
    document_date: Optional[_date] = Field(
        None,
        description="The document's adoption or publication date (from eu_laws). Null when CELEX is not in the corpus.",
    )


class VerifyCitationResponse(BaseModel):
    data: VerifyCitationItem


# ─────────────────────── Enrichment helpers ──────────────────────────────


_CELLAR_URL_TEMPLATE = "https://publications.europa.eu/resource/celex/{celex}"
_EURLEX_URL_TEMPLATE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
_BODY_FETCH_TIMEOUT_S = 45  # AI Act XHTML is 1.26 MB — 20s wasn't enough on Railway
_BODY_MIN_LEN = 500


def _strip_html_to_text(html: str) -> str:
    text_ = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>",
                   " ", html, flags=re.DOTALL | re.IGNORECASE)
    text_ = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", text_, flags=re.IGNORECASE)
    text_ = re.sub(r"<br\s*/?>", "\n", text_, flags=re.IGNORECASE)
    text_ = re.sub(r"<[^>]+>", " ", text_)
    text_ = (text_.replace("&nbsp;", " ").replace("&amp;", "&")
                 .replace("&lt;", "<").replace("&gt;", ">")
                 .replace("&quot;", '"').replace("&#39;", "'"))
    text_ = re.sub(r"[ \t]+", " ", text_)
    text_ = re.sub(r"\n[ \t]*\n+", "\n\n", text_)
    return text_.strip()


async def _fetch_cellar_xhtml(celex: str) -> Optional[str]:
    """Fetch Cellar XHTML manifestation in English. Returns HTML or None.

    Cellar returns 303 → http://publications.europa.eu/resource/cellar/<UUID>/DOC_1
    aiohttp follows the redirect with allow_redirects=True.

    Two retry conditions:
      - HTTP 202 (Accepted): Cellar is generating the manifestation server-side.
        Retry after 1.5s + exponential backoff, up to 3 attempts.
      - HTTP 503 (Service Unavailable): same retry pattern.

    AI Act XHTML is 1.26 MB; Railway nodes can be slower than local to
    download — hence the 45s timeout.
    """
    import aiohttp
    url = _CELLAR_URL_TEMPLATE.format(celex=celex)
    max_attempts = 4
    backoff = 1.5  # seconds, doubles each retry

    for attempt in range(1, max_attempts + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=_BODY_FETCH_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    headers={
                        "Accept": "application/xhtml+xml",
                        "Accept-Language": "en",
                        "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
                    },
                    allow_redirects=True,
                ) as resp:
                    # Retryable: Cellar still generating, or transient outage
                    if resp.status in (202, 503):
                        if attempt < max_attempts:
                            logger.info(
                                "[citations] Cellar XHTML for %s returned %s on attempt %d/%d — retrying in %.1fs",
                                celex, resp.status, attempt, max_attempts, backoff,
                            )
                            await asyncio.sleep(backoff)
                            backoff *= 2
                            continue
                        logger.warning(
                            "[citations] Cellar XHTML for %s gave up after %d attempts on status %s",
                            celex, max_attempts, resp.status,
                        )
                        return None

                    if resp.status != 200:
                        logger.warning("[citations] Cellar XHTML for %s returned status %s",
                                       celex, resp.status)
                        return None
                    ctype = (resp.headers.get("Content-Type") or "").lower()
                    if "xhtml" not in ctype and "html" not in ctype:
                        logger.warning("[citations] Cellar XHTML for %s wrong content-type: %s",
                                       celex, ctype)
                        return None
                    body = await resp.text()
                    if len(body) < _BODY_MIN_LEN:
                        logger.warning("[citations] Cellar XHTML for %s body too small (%d bytes)",
                                       celex, len(body))
                        return None
                    logger.info("[citations] Cellar XHTML for %s fetched (%d bytes, attempt %d)",
                                celex, len(body), attempt)
                    return body
        except asyncio.TimeoutError:
            logger.warning("[citations] Cellar XHTML timeout (>%ds) for %s on attempt %d",
                           _BODY_FETCH_TIMEOUT_S, celex, attempt)
            return None
        except Exception as exc:
            logger.warning("[citations] Cellar XHTML fetch failed for %s: %s: %s (attempt %d)",
                           celex, type(exc).__name__, exc, attempt)
            return None
    return None


def _lookup_eu_laws_dates(db: Session, celex: str) -> tuple[Optional[datetime], Optional[_date]]:
    """Look up creation_date (created_at) + document_date (date) from eu_laws."""
    try:
        row = db.execute(
            text("SELECT created_at, date FROM eu_laws WHERE celex = :c LIMIT 1"),
            {"c": celex},
        ).first()
        if row:
            return row[0], row[1]
    except Exception as exc:
        logger.debug("[citations] eu_laws lookup failed for %s: %s", celex, exc)
    return None, None


def _read_cached_enrichment(db: Session, ref: str) -> Optional[dict]:
    """Read body + dates from the verifier cache. Returns None if not present
    OR if the body has never been fetched (so we can backfill it inline)."""
    try:
        row = db.execute(
            text("""
                SELECT public_url, body_text, body_html, body_fetched_at,
                       creation_date, document_date
                  FROM citation_verifications
                 WHERE ref = :r
                 LIMIT 1
            """),
            {"r": ref},
        ).first()
        if not row:
            return None
        return {
            "public_url": row[0],
            "body_text": row[1],
            "body_html": row[2],
            "body_fetched_at": row[3],
            "creation_date": row[4],
            "document_date": row[5],
        }
    except Exception as exc:
        logger.debug("[citations] enrichment cache read failed for %s: %s", ref, exc)
        return None


def _write_enrichment_cache(
    db: Session,
    ref: str,
    public_url: Optional[str],
    body_text: Optional[str],
    body_html: Optional[str],
    creation_date: Optional[datetime],
    document_date: Optional[_date],
) -> None:
    """Update the row written by services.citation_verifier with body + dates."""
    try:
        db.execute(
            text("""
                UPDATE citation_verifications
                   SET public_url     = COALESCE(:public_url, public_url),
                       body_text      = COALESCE(:body_text, body_text),
                       body_html      = COALESCE(:body_html, body_html),
                       body_fetched_at = CASE WHEN :body_text IS NOT NULL OR :body_html IS NOT NULL
                                              THEN NOW() ELSE body_fetched_at END,
                       creation_date  = COALESCE(:creation_date, creation_date),
                       document_date  = COALESCE(:document_date, document_date)
                 WHERE ref = :ref
            """),
            {
                "ref": ref,
                "public_url": public_url,
                "body_text": body_text,
                "body_html": body_html,
                "creation_date": creation_date,
                "document_date": document_date,
            },
        )
        db.commit()
    except Exception as exc:
        logger.warning("[citations] enrichment cache write failed for %s: %s", ref, exc)
        try:
            db.rollback()
        except Exception:
            pass


async def _enrich(
    db: Session,
    ref: str,
    kind: str,
    status: str,
) -> dict:
    """Compute the 5 mandatory v1 datapoints for a citation. Reads cache when
    available, falls back to Cellar XHTML fetch + eu_laws lookup."""
    out = {
        "public_url": None,
        "body_text": None,
        "body_html": None,
        "creation_date": None,
        "document_date": None,
    }
    if status != "ok":
        return out

    # public_url is always derivable for CELEX-form refs (incl. com_as_celex)
    celex_form = ref if kind in ("celex", "com_as_celex") else None
    if celex_form and re.match(r"^[0-9]{5}[A-Z]{1,2}[0-9]{4}(\([0-9]+\))?$", celex_form):
        out["public_url"] = _EURLEX_URL_TEMPLATE.format(celex=celex_form)

    # Date lookup
    if celex_form:
        creation, doc_date = _lookup_eu_laws_dates(db, celex_form)
        out["creation_date"] = creation
        out["document_date"] = doc_date

    # Cache read for body
    cached = _read_cached_enrichment(db, ref)
    has_cached_body = bool(cached and cached.get("body_text") and cached.get("body_fetched_at"))

    if has_cached_body:
        out["body_text"] = cached["body_text"]
        out["body_html"] = cached["body_html"]
        # cached.public_url overrides our derived one only if non-null
        if cached.get("public_url"):
            out["public_url"] = cached["public_url"]
        if cached.get("creation_date"):
            out["creation_date"] = cached["creation_date"]
        if cached.get("document_date"):
            out["document_date"] = cached["document_date"]
        return out

    # Body fetch path — only for CELEX-form (Cellar doesn't serve OEIL bodies)
    if celex_form:
        xhtml = await _fetch_cellar_xhtml(celex_form)
        if xhtml:
            out["body_html"] = xhtml
            out["body_text"] = _strip_html_to_text(xhtml)

    # Persist enrichment for next call
    _write_enrichment_cache(
        db, ref,
        public_url=out["public_url"],
        body_text=out["body_text"],
        body_html=out["body_html"],
        creation_date=out["creation_date"],
        document_date=out["document_date"],
    )
    return out


# ─────────────────────── Handlers ────────────────────────────────────────


_OPENAPI_DESC = (
    "**What it does:** given any EU legal reference, tells you whether it "
    "points at a real document on EUR-Lex / OEIL, and returns the canonical "
    "URLs plus the document's body and dates.\n\n"
    "**When to use it:** ground your own AI's citations, validate a regulatory "
    "feed, or detect hallucinated CELEX numbers before showing them to your "
    "users. The body fields let you skip a separate fetch for downstream "
    "processing.\n\n"
    "**Accepted forms:**\n"
    "- CELEX — `32024R1689` (AI Act)\n"
    "- COM reference — `COM(2021) 206` (auto-converted to CELEX)\n"
    "- OEIL procedure — `2021/0106(COD)`\n\n"
    "**Try it:** `GET /api/v1/verify-citation/32016R0679` → returns "
    "`status=ok`, `public_url=https://eur-lex.europa.eu/legal-content/EN/"
    "TXT/?uri=CELEX:32016R0679`, the full GDPR text in `body_text` + "
    "`body_html`, plus `creation_date` (when we ingested it) and "
    "`document_date` (27 April 2016).\n\n"
    "**Two URL fields:**\n"
    "- `public_url` — the citizen-facing EUR-Lex page (humans share this)\n"
    "- `resolved_url` — the Cellar manifestation `cellar/<UUID>/DOC_1` URL "
    "the verifier hit (machines consume this)\n\n"
    "**Body fetch:** populated on first call from Cellar XHTML (English "
    "manifestation), cached alongside the verification result. Subsequent "
    "calls are sub-millisecond from cache.\n\n"
    "**Cache:** 30 days on success, 24h on broken refs, 1h on transient "
    "errors."
)


@router.get(
    "/{ref:path}",
    response_model=VerifyCitationResponse,
    summary="Verify a CELEX, COM or OEIL reference + return the document's body and dates",
    description=_OPENAPI_DESC,
)
async def verify_citation(
    request: Request,
    ref: str = Path(..., description="The reference to verify (URL-encoded if it contains spaces or parentheses)"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> VerifyCitationResponse:
    if not ref or len(ref) > 128:
        raise HTTPException(
            status_code=422,
            detail={"error": "ref must be 1-128 characters", "reason_code": "invalid_ref"},
        )

    result = await verify_one(ref, db=db)
    enrichment = await _enrich(db, result.ref, result.kind, result.status)

    return VerifyCitationResponse(
        data=VerifyCitationItem(
            ref=result.ref,
            kind=result.kind,
            status=result.status,
            public_url=enrichment["public_url"],
            resolved_url=result.resolved_url,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            original_form=result.original_form or ref,
            from_cache=result.from_cache,
            body_text=enrichment["body_text"],
            body_html=enrichment["body_html"],
            creation_date=enrichment["creation_date"],
            document_date=enrichment["document_date"],
        )
    )


@citations_router.get(
    "/verify",
    response_model=VerifyCitationResponse,
    summary="Verify a citation by query string + return the document's body and dates",
    description=(
        "Same as `/verify-citation/{ref}` (and returns the same 13-field "
        "envelope including body + dates) but accepts the reference as a "
        "`?q=` query parameter, which is friendlier for refs that include "
        "slashes or parentheses (CELEX, COM, OEIL). Cached identically."
    ),
)
async def verify_citation_q(
    request: Request,
    q: str = Query(..., min_length=1, max_length=128, description="The reference to verify (CELEX, COM, OEIL)"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> VerifyCitationResponse:
    result = await verify_one(q, db=db)
    enrichment = await _enrich(db, result.ref, result.kind, result.status)

    return VerifyCitationResponse(
        data=VerifyCitationItem(
            ref=result.ref,
            kind=result.kind,
            status=result.status,
            public_url=enrichment["public_url"],
            resolved_url=result.resolved_url,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            original_form=result.original_form or q,
            from_cache=result.from_cache,
            body_text=enrichment["body_text"],
            body_html=enrichment["body_html"],
            creation_date=enrichment["creation_date"],
            document_date=enrichment["document_date"],
        )
    )
