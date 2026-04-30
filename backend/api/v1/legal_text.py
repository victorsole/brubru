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

from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legal-text", tags=["v1-legal-text"])


class RecitalArticleMapResponse(BaseModel):
    celex: str
    map: dict = Field(..., description="Article -> [{recital_number, score, snippet}, ...] (top-3)")


class DefinedTermsResponse(BaseModel):
    celex: str
    terms: dict = Field(..., description="Term -> {term, definition, article, point}")


class ResolveRefsRequest(BaseModel):
    text: str
    annotate_html: bool = False


class ResolveAliasesRequest(BaseModel):
    text: str = Field(..., description="Plain text. Detects GDPR/DSA/AI Act/etc. by name.")


@router.get(
    "/{celex}/recital-article-map",
    response_model=RecitalArticleMapResponse,
    summary="Recital-to-article mapping (TF-IDF cosine, top-3 per article)",
)
def recital_article_map(
    celex: str,
    force_recompute: bool = Query(False),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> RecitalArticleMapResponse:
    from services.parsers.recital_article_store import get_or_compute_map

    # Defensive: catch ALL exceptions, including ones in service layer that
    # bubble up despite the inner try (e.g. import errors, missing DB columns
    # on production). Convert to clean 503 instead of an unhandled 500.
    try:
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
)
def defined_terms(
    celex: str,
    force_recompute: bool = Query(False),
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
    return DefinedTermsResponse(celex=celex, terms=mapping)


@router.post(
    "/resolve-references",
    summary="Resolve inline EU legal citations in plain text (READ-ONLY)",
    description=(
        "**This endpoint is idempotent and does NOT modify any server-side data.** "
        "It is POST because the request body carries free text that may exceed URL length limits. "
        "Given plain text containing EU legal citations (e.g. 'Article 7 of Regulation (EU) 2024/1234'), "
        "returns a structured list of matched CELEX identifiers with EUR-Lex URLs. "
        "Pass annotate_html=true to receive an HTML-annotated version instead."
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
        "**This endpoint is idempotent and does NOT modify any server-side data.** "
        "POST because the body carries free text. Scans the input for 680+ known human names "
        "of EU laws (GDPR, DSA, AI Act, CBAM, Solvency II, CRR, ...) and returns a list of "
        "matches with their CELEX identifiers and canonical titles."
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
