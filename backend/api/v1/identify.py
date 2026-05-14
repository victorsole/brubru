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
    summary="Recognise any single EU identifier — legal IDs, case-law IDs, DOIs, ISBNs, OJ refs",
    description="""**What it does**
Hand it any EU standard identifier and get back its recognised type, the canonical EU URL where the resource lives, the Brubru v1 endpoint (where one exists), and a deep-link to the EU Vocabularies ShowVoc browser. Single entry point that ties together every identifier-shape regex in Brubru so chat / partner integrations / Tenderator can all use one unified resolver. Supports: CELEX legal IDs, ECLI case-law IDs, ELI URIs, ISBN, ISSN, DOI, Official Journal references, Publications Office catalogue numbers, EU authority URIs, EuroVoc URIs.

**When to use it**
When you have an identifier of unknown type and want one call that says "this is an X, here's where to find it". Common pattern in chat: user pastes an identifier, you call this, get back the canonical URL + Brubru endpoint, and you know how to follow up.

**Input**
- `q` — the identifier string (any of the supported types).

**Try it**
```
GET /api/v1/identify?q=32016R0679
GET /api/v1/identify?q=ECLI:EU:C:2014:317
GET /api/v1/identify?q=10.1016/j.foo.2024.123
```

**You get back**
An `IdentifyResult` with `kind` (the recognised type), `value` (normalised identifier), `canonical_url` (where the resource lives officially), `brubru_url` (the matching v1 endpoint if any), `showvoc_url` (EU Vocabularies deep-link), `parts` (per-type structured breakdown). HTTP 422 with `reason_code: unknown_identifier` if no type matches.

**Data freshness**
Live pass-through (pure pattern recognition + URL composition; no upstream HTTP call needed).""",
)
async def identify_one(
    request: Request,
    q: str = Query(..., min_length=1, description="Identifier string", example="32016R0679"),
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
    summary="Scan free text and extract every embedded EU identifier — list of recognised matches",
    description="""**What it does**
Scans any free-text string and returns every embedded EU standard identifier it can recognise — CELEX legal IDs, ECLI case-law IDs, ELI URIs, ISBN, ISSN, DOI, OJ refs, catalogue numbers. Each match comes back as a fully-resolved `IdentifyResult` (same shape as `/identify`).

**When to use it**
When you have a chunk of free text (a news article, an email, a chat message) and you want every identifier in it extracted + resolved in one call. Typical use: bulk-import a partner's brief, extract all CELEX numbers, fetch their metadata. The order of returned matches reflects the order of appearance in the input text.

**Input**
- `text` — the free-text string to scan (min 2 chars).

**Try it**
```
GET /api/v1/identify/scan?text=See%20Regulation%20(EU)%202016/679%20and%20Directive%202002/58/EC.
```

**You get back**
A `PaginatedResponse[IdentifyResult]` envelope. Each item is one match with the same fields as the `/identify` response.

**Data freshness**
Live pass-through (pure pattern recognition; no upstream HTTP call).""",
)
async def identify_scan(
    request: Request,
    text: str = Query(..., min_length=2, description="Free text to scan", example="See Regulation (EU) 2016/679 and Directive 2002/58/EC."),
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
