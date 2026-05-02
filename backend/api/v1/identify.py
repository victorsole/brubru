"""
/api/v1/identify — unified standard-identifier dispatch.

Phase 13 of docs/applications/euvoc.md. Hand it ANY identifier string
(CELEX / ECLI / ELI / ISBN / ISSN / DOI / OJ / catalogue number / URI)
and it returns the recognised type, the canonical EU URL, the matching
Brubru v1 endpoint (where one exists), and a ShowVoc deep-link.

Single entry point that ties Phases 1-12 together — chat / partner
integrations / Tenderator can all use this without re-implementing
identifier-shape regex.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from models.user import User
from services.api_clients.showvoc_client import deep_link as showvoc_deep_link
from services.identifiers.standard_identifier_resolver import (
    parse_all,
    recognise,
)

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identify", tags=["v1-identify"])


class IdentifyResult(BaseModel):
    kind: str
    value: str
    canonical_url: Optional[str] = None
    brubru_url: Optional[str] = None
    showvoc_url: Optional[str] = None
    parts: Optional[dict] = None


@router.get(
    "",
    response_model=IdentifyResult,
    summary="Recognise a single standard identifier",
    description=(
        "Hand it any EU standard identifier (CELEX, ECLI, ELI URI, ISBN, "
        "ISSN, DOI, OJ ref, catalogue number, authority URI, EuroVoc URI) "
        "and get back its type, canonical EU URL, Brubru endpoint, and "
        "ShowVoc deep-link. Per OP Standards v4.0.0 §2."
    ),
)
async def identify_one(
    request: Request,
    q: str = Query(..., min_length=1, description="Identifier string"),
    user: User = Depends(api_user_with_rate_limit),
) -> IdentifyResult:
    match = recognise(q)
    if match is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Could not recognise {q!r} as any known EU identifier type",
                "reason_code": "unknown_identifier",
            },
        )
    sv = showvoc_deep_link(match.canonical_url or match.value)
    return IdentifyResult(
        kind=match.kind.value,
        value=match.value,
        canonical_url=match.canonical_url,
        brubru_url=match.brubru_url,
        showvoc_url=sv,
        parts=match.parts,
    )


@router.get(
    "/scan",
    response_model=PaginatedResponse[IdentifyResult],
    summary="Find every embedded identifier in a longer string",
    description=(
        "Scans free text for every embedded EU identifier and returns "
        "the list. Useful for chat / partner integrations that ingest a "
        "paragraph mixing CELEX + ECLI + DOI + ISSN."
    ),
)
async def identify_scan(
    request: Request,
    text: str = Query(..., min_length=2, description="Free text to scan"),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[IdentifyResult]:
    matches = parse_all(text)
    items = [
        IdentifyResult(
            kind=m.kind.value,
            value=m.value,
            canonical_url=m.canonical_url,
            brubru_url=m.brubru_url,
            showvoc_url=showvoc_deep_link(m.canonical_url or m.value),
            parts=m.parts,
        )
        for m in matches
    ]
    return build_envelope(
        items=items,
        total=len(items),
        page=1,
        limit=max(1, len(items)),
        op_core_title="Standard-identifier scan",
        op_core_type="EU identifiers",
        op_core_identifier=str(request.url),
        coverage_complete=True,
    )
