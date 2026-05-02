"""
/api/v1/verify-citation/{ref}

Reuses backend/services/citation_verifier.py. Returns the canonical verify
result for a single CELEX, COM, or OEIL ref. Cached at the DB layer (TTL: 30
days OK / 24h broken / 1h unknown), so most calls are sub-millisecond.

Sprint 1a (April 2026) of the LegTech benchmarking integration. Used by the
v1 API as a paid feature for partners (GovClipping etc.) and reused
internally by Chat post-processing for citation grounding.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from services.citation_verifier import verify_one

from ._deps import api_user_with_rate_limit

# Two prefixes share the same handlers: /verify-citation/{ref} (legacy, kept for
# back-compat with anyone who built against the original path) and /citations
# (matches what the public docs and Postman advertise).
router = APIRouter(prefix="/verify-citation", tags=["v1-citations"])
citations_router = APIRouter(prefix="/citations", tags=["v1-citations"])


class VerifyCitationItem(BaseModel):
    ref: str = Field(..., description="Canonical reference (CELEX form for COM input)")
    kind: str = Field(..., description="celex | com_as_celex | oeil | unknown")
    status: str = Field(..., description="ok | broken | unknown")
    resolved_url: Optional[str] = Field(None, description="Authoritative URL when status=ok")
    http_status: Optional[int] = None
    latency_ms: Optional[int] = Field(None, description="Network latency on the verifying call (null on cache hit)")
    original_form: Optional[str] = Field(None, description="The form the caller passed in")
    from_cache: bool = False


class VerifyCitationResponse(BaseModel):
    data: VerifyCitationItem


@router.get(
    "/{ref:path}",
    response_model=VerifyCitationResponse,
    summary="Verify a CELEX, COM or OEIL reference resolves to a real EU document",
    description=(
        "**What it does:** given any EU legal reference, tells you whether it points "
        "at a real document on EUR-Lex / OEIL, and returns the canonical URL.\n\n"
        "**When to use it:** ground your own AI's citations, validate a regulatory "
        "feed, or detect hallucinated CELEX numbers before showing them to your users.\n\n"
        "**Accepted forms:**\n"
        "- CELEX — `32024R1689` (AI Act)\n"
        "- COM reference — `COM(2021) 206` (auto-converted to CELEX)\n"
        "- OEIL procedure — `2021/0106(COD)`\n\n"
        "**Try it:** `GET /api/v1/verify-citation/32016R0679` → returns `status=ok`, "
        "`resolved_url=https://eur-lex.europa.eu/eli/reg/2016/679/oj`.\n\n"
        "**Cache:** 30 days on success, 24h on broken refs, 1h on transient errors. "
        "Most calls are sub-millisecond from cache."
    ),
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
            detail={
                "error": "ref must be 1-128 characters",
                "reason_code": "invalid_ref",
            },
        )

    result = await verify_one(ref, db=db)

    return VerifyCitationResponse(
        data=VerifyCitationItem(
            ref=result.ref,
            kind=result.kind,
            status=result.status,
            resolved_url=result.resolved_url,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            original_form=result.original_form or ref,
            from_cache=result.from_cache,
        )
    )


@citations_router.get(
    "/verify",
    response_model=VerifyCitationResponse,
    summary="Verify a citation by query string (alias of /verify-citation/{ref})",
    description=(
        "Same as `/verify-citation/{ref}` but accepts the reference as a `?q=` "
        "query parameter, which is friendlier for refs that include slashes "
        "or parentheses (CELEX, COM, OEIL). Cached identically."
    ),
)
async def verify_citation_q(
    request: Request,
    q: str = Query(..., min_length=1, max_length=128, description="The reference to verify (CELEX, COM, OEIL)"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> VerifyCitationResponse:
    result = await verify_one(q, db=db)
    return VerifyCitationResponse(
        data=VerifyCitationItem(
            ref=result.ref,
            kind=result.kind,
            status=result.status,
            resolved_url=result.resolved_url,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            original_form=result.original_form or q,
            from_cache=result.from_cache,
        )
    )
