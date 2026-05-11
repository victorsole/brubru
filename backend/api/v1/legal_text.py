"""
/api/v1/legal-text — Legal-Text Intelligence endpoints on the Data Provider API.

Wraps the recital-article linker, definition extractor, cross-reference resolver,
and law alias resolver that power Brubru's internal chatbot and Amendator.

Customers get the same primitives Brubru uses internally.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import DEFAULT_HAS_BODY_THRESHOLD, body_threshold_param
from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legal-text", tags=["v1-legal-text"])


class RecitalArticleMapResponse(BaseModel):
    celex: str
    map: dict = Field(..., description="Article -> [{recital_number, score, snippet}, ...] (top-3)")


class DefinedTermsResponse(BaseModel):
    celex: str
    terms: dict = Field(..., description="Term -> {term, definition, article, point}")
    # Body fields composed from the concatenated definitions, useful as a
    # standalone glossary view of the law. body_html is a semantic <dl> with
    # one <dt>/<dd> pair per term; body_text is a plain-text rendering.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None


def _compose_definitions_body(terms: dict, threshold: int = DEFAULT_HAS_BODY_THRESHOLD):
    """Compose body_html / body_text / has_body from the defined-terms dict.

    Builds:
      body_html — <dl><dt>{term}</dt><dd>{definition}</dd>…</dl>, optionally
                  grouped by article when articles vary.
      body_text — "term — definition" lines, blank-line separated.
    Honest empties: returns (None, None, False) when terms is empty.
    """
    from html import escape

    if not terms or not isinstance(terms, dict):
        return None, None, False

    # Iterate in insertion order (typically article order from the parser).
    dt_dd = []
    text_lines = []
    for key, entry in terms.items():
        if not isinstance(entry, dict):
            continue
        term = (entry.get("term") or key or "").strip()
        defn = (entry.get("definition") or "").strip()
        article = (entry.get("article") or "").strip()
        if not term or not defn:
            continue
        anchor = f" <small>({escape(article)})</small>" if article else ""
        dt_dd.append(f"<dt>{escape(term)}{anchor}</dt><dd>{escape(defn)}</dd>")
        text_lines.append(f"{term}{f' ({article})' if article else ''} — {defn}")

    if not dt_dd:
        return None, None, False

    body_html = f"<article><h2>Defined terms</h2><dl>{''.join(dt_dd)}</dl></article>"
    body_text = "\n\n".join(text_lines)
    has_body = len(body_text) >= threshold
    return body_html, body_text, has_body


class ResolveRefsRequest(BaseModel):
    text: str
    annotate_html: bool = False


class ResolveAliasesRequest(BaseModel):
    text: str = Field(..., description="Plain text. Detects GDPR/DSA/AI Act/etc. by name.")


@router.get(
    "/{celex}/recital-article-map",
    response_model=RecitalArticleMapResponse,
    summary="Recital-to-article mapping (TF-IDF cosine, top-3 per article)",
    description=(
        "**What it does:** for a given EU law (CELEX), returns a mapping of each article "
        "to its top-3 most semantically related recitals, computed via TF-IDF cosine similarity.\n\n"
        "**When to use it:** when interpreting a specific article and you need its "
        "explanatory recitals automatically — instead of skimming the full preamble.\n\n"
        "**Production cache state (2 May 2026):** 5 implementing acts cached "
        "(`32025D2208`, `32025R2149`, `32025R2158`, `32025R2226`). Backfill for the "
        "flagship laws (DSA, GDPR, AI Act, DORA) is queued behind CC-2(b) — the "
        "TF-IDF computation requires Formex XML which is not deployed on Railway "
        "for size reasons.\n\n"
        "**Try it:** `GET /api/v1/legal-text/32025R2149/recital-article-map` returns "
        "the live cached mapping.\n\n"
        "**Errors:** 404 with `reason_code=not_found` means the cache hasn't been "
        "computed yet for this CELEX — pass `?force_recompute=true` if running locally."
    ),
)
def recital_article_map(
    celex: str,
    force_recompute: bool = Query(False),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> RecitalArticleMapResponse:
    # Defensive: catch ALL exceptions, including the lazy import itself, so
    # any failure surfaces as a clean 503 instead of an unhandled 500.
    try:
        from services.parsers.recital_article_store import get_or_compute_map
        mapping = get_or_compute_map(db, celex, force_recompute=force_recompute)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"recital-article-map computation failed for {celex}: {exc}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": f"Unable to compute recital-article map for CELEX {celex}",
                "reason_code": "computation_unavailable",
                "source": "brubru-recital-linker",
                "exception": type(exc).__name__,
                "exception_message": str(exc)[:200],
            },
        )
    if mapping is None:
        # Either the law isn't in eu_laws or the LEG XML isn't available on
        # this deployment (Railway doesn't ship the LEG corpus by design).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"CELEX {celex} not available — recital map requires Formex XML which is not deployed to production",
                "reason_code": "not_found",
                "resource": "law",
                "id": celex,
                "hint": "Use /api/v1/laws/{celex}/text to get the full text via the EUR-Lex Cellar fallback",
            },
        )
    return RecitalArticleMapResponse(celex=celex, map=mapping)


@router.get(
    "/{celex}/defined-terms",
    response_model=DefinedTermsResponse,
    summary="Article 3/4-style definitions extracted from a law",
    description=(
        "**What it does:** extracts the formal Article 3 (or Article 4) definitions "
        "from an EU law — the terms the law itself defines authoritatively for its "
        "own scope.\n\n"
        "**When to use it:** when you need to know exactly how a law defines terms "
        "like 'very large online platform', 'AI system', 'personal data' — without "
        "reading the full text.\n\n"
        "**Try it:** `GET /api/v1/legal-text/32022R2065/defined-terms` returns 23 "
        "DSA definitions (~7.9 KB) including 'online platform', 'recipient of the "
        "service', 'illegal content', etc.\n\n"
        "**Production cache state (2 May 2026):** the DSA (`32022R2065`) is fully "
        "cached. Other flagship laws (GDPR, AI Act, DORA) compute on first request, "
        "but the underlying Formex XML isn't deployed to Railway — backfill happens "
        "as part of CC-2(b)."
    ),
)
def defined_terms(
    celex: str,
    force_recompute: bool = Query(False),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> DefinedTermsResponse:
    from services.parsers.definition_store import get_or_compute_map as _get_defs

    mapping = _get_defs(db, celex, force_recompute=force_recompute)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "detail": f"CELEX {celex} not available", "resource": "law", "id": celex},
        )
    body_html, body_text, has_body = _compose_definitions_body(mapping, threshold=body_threshold)
    return DefinedTermsResponse(
        celex=celex, terms=mapping,
        has_body=has_body, body_html=body_html, body_txt=body_text,
    )


@router.post(
    "/resolve-references",
    summary="Resolve inline EU legal citations in plain text (READ-ONLY)",
    description=(
        "**What it does:** scans a block of free text and extracts every embedded "
        "EU legal citation (e.g. 'Article 7 of Regulation (EU) 2024/1234'), returning "
        "a structured list with the matched CELEX identifier and canonical EUR-Lex URL. "
        "Pass `annotate_html=true` to receive the original text with each citation wrapped "
        "in an `<a href=...>` link instead.\n\n"
        "**When to use it:** auto-link EU citations in opinion pieces, briefings, AI-"
        "generated answers, or when converting Word documents into HTML.\n\n"
        "**Why POST:** request body carries free text that can exceed URL length limits. "
        "Idempotent — does NOT modify any server-side data.\n\n"
        "**Try it:** `POST /api/v1/legal-text/resolve-references` with body "
        "`{\"text\":\"Article 5 of Regulation (EU) 2022/2065 prohibits...\"}` → "
        "returns `{refs: [{celex:\"32022R2065\", url:\"https://eur-lex.europa.eu/...\"}]}`."
    ),
)
def resolve_references(
    payload: ResolveRefsRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    from services.parsers.cross_reference_resolver import (
        resolve_references_json,
        annotate_html,
    )

    if payload.annotate_html:
        return {"html": annotate_html(payload.text)}
    return {"refs": resolve_references_json(payload.text)}


@router.post(
    "/resolve-aliases",
    summary="Resolve human names (GDPR, DSA, AI Act, ...) to CELEX (READ-ONLY)",
    description=(
        "**What it does:** scans free text for known human names of EU laws — GDPR, "
        "DSA, AI Act, CBAM, DORA, Solvency II, CRR, MiFID II, and 680+ more aliases — "
        "and returns each match with its CELEX identifier, canonical title, and the "
        "character offset where it was matched.\n\n"
        "**When to use it:** when your users type 'GDPR' but you need `32016R0679` to "
        "feed into other Brubru endpoints. Or to extract every law referenced in a "
        "policy paper.\n\n"
        "**Why POST:** body carries free text. Idempotent — does NOT modify server data.\n\n"
        "**Try it:** `POST /api/v1/legal-text/resolve-aliases` with body "
        "`{\"text\":\"Comparing GDPR and the AI Act on automated decisions\"}` → "
        "returns `{aliases: [{alias:\"GDPR\", celex:\"32016R0679\"}, "
        "{alias:\"AI Act\", celex:\"32024R1689\"}]}`."
    ),
)
def resolve_aliases(
    payload: ResolveAliasesRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    from services.parsers.law_alias_resolver import find_alias_matches

    matches = find_alias_matches(payload.text)
    return {
        "aliases": [
            {
                "raw": m.raw,
                "alias": m.alias,
                "celex": m.celex,
                "full_title": m.full_title,
                "start": m.start,
                "end": m.end,
            }
            for m in matches
        ]
    }
