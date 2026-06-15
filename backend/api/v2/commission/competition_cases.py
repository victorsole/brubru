"""DG COMP competition cases — /api/v2/commission/competition-cases.

Live pass-through to the Commission's competition case search (state aid SA.*,
antitrust AT.*, merger M.*). Ported from v1 via delegation; v1 already carries
the 5 datapoints. Sits next to /commission/state-aid + /commission/dma-cases.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request

from models.user import User
from api.v1._body import body_threshold_param
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1 import specialised_competition as _v1
from api.v1.specialised_competition import CompetitionCaseItem

router = APIRouter(prefix="/competition-cases")


@router.get(
    "",
    response_model=PaginatedResponse[CompetitionCaseItem],
    tags=["v2-commission"],
    summary="DG COMP competition cases (state aid, antitrust, merger) — live pass-through",
    description="""**What it does**
Searches the European Commission's competition case register live — state aid (`SA.*`), antitrust (`AT.*`) and merger (`M.*`) cases handled by DG Competition.

**When to use it**
To monitor competition enforcement across all three instruments in one query. For the curated state-aid feed see `/api/v2/commission/state-aid`; for Digital Markets Act cases see `/api/v2/commission/dma-cases`.

**Input**
- `q` — Lucene query (default `*` = all).
- `case_instrument` — `SA` | `M` | `AT`.
- `limit` (max 200), `page`.

**Try it**
```
GET /api/v2/commission/competition-cases?case_instrument=SA&q=energy
GET /api/v2/commission/competition-cases?q=*&limit=20
```

**You get back**
A paginated envelope; each case carries the case number, title, instrument, parties, decision date and links, plus the 5 datapoints (`public_url` = the case page).

**Data freshness**
Live pass-through — queried against the Commission case search at request time.""",
)
async def list_competition_cases(
    request: Request,
    q: str = Query("*", description="Lucene query, default '*' = all."),
    case_instrument: Optional[str] = Query(None, regex="^(SA|M|AT)$"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CompetitionCaseItem]:
    return await _v1.list_cases(
        request=request, q=q, case_instrument=case_instrument, limit=limit, page=page,
        body_threshold=body_threshold, user=user)


@router.get(
    "/{case_number}",
    response_model=CompetitionCaseItem,
    tags=["v2-commission"],
    summary="Look up one DG COMP competition case by its case number (e.g. SA.105841)",
    description="""**What it does**
Fetches one competition case in full by its case number.

**Input**
`case_number` — e.g. `SA.105841` or `M.10999`.

**Try it**
```
GET /api/v2/commission/competition-cases/SA.105841
```

**You get back**
A single `CompetitionCaseItem` with the full record + the 5 datapoints, or HTTP 404.

**Data freshness**
Live pass-through.""",
)
async def get_competition_case(
    request: Request,
    case_number: str = Path(..., description="Case number, e.g. SA.105841 or M.10999."),
    user: User = Depends(api_user_with_rate_limit),
) -> CompetitionCaseItem:
    return await _v1.get_case(request=request, case_number=case_number, user=user)
