"""
EU Transparency Register domain — /api/v2/transparency-register/*.

The interest representatives (lobbyists, NGOs, trade unions, think tanks, law
firms, churches, ...) who declare lobbying activity towards the Commission and
the European Parliament. Ported from v1 via the v1-delegation pattern; the v1
handlers already carry the 5 datapoints, so this is pure delegation with the
folder path + example URLs rehomed to /api/v2/transparency-register/*.
Tag v2-transparency-register → grouped in the "Transparency Register" Postman folder.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._body import body_threshold_param
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1 import specialised_transparency_register as _v1
from api.v1.specialised_transparency_register import TrListItem, TrDetail, CategoryCount

router = APIRouter(prefix="/transparency-register")


@router.get(
    "",
    response_model=PaginatedResponse[TrListItem],
    tags=["v2-transparency-register"],
    summary="EU Transparency Register — lobbyists / interest representatives",
    description="""**What it does**
Returns organisations in the EU Transparency Register — the interest representatives (lobbyists, NGOs, trade unions, professional associations, think tanks, law firms, churches) who declare lobbying towards the Commission and the European Parliament (~17k active orgs from the daily public XML).

**When to use it**
Lead generation, competitive intelligence and CRM enrichment — find who lobbies in your policy area, with what budget and how many EP-accredited passes. Filter by `country`, `category`, `interest`, `q`, `min_fte`, `min_costs`, `ep_accredited_only`.

**Input**
`country`, `category`, `interest`, `q`, `min_fte`, `min_costs`, `ep_accredited_only`, `limit` (max 200), `page`.

**Try it**
```
GET /api/v2/transparency-register?country=BE&min_costs=1000000
GET /api/v2/transparency-register?interest=digital&ep_accredited_only=true
```

**You get back**
A paginated envelope; each org carries name, acronym, country, registration category, declared interests, FTE, lobbying costs, EP passes, plus the 5 datapoints (`public_url` = its register page; `body_txt`/`body_html` null on the list — fetch `/{code}`).

**Data freshness**
Refreshed daily from the Transparency Register public XML.""",
)
async def list_transparency_register(
    request: Request,
    country: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    interest: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    min_fte: Optional[float] = Query(None),
    min_costs: Optional[float] = Query(None),
    ep_accredited_only: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TrListItem]:
    return await _v1.list_tr(
        request=request, country=country, category=category, interest=interest, q=q,
        min_fte=min_fte, min_costs=min_costs, ep_accredited_only=ep_accredited_only,
        limit=limit, page=page, body_threshold=body_threshold, user=user, db=db)


@router.get(
    "/categories",
    response_model=list[CategoryCount],
    tags=["v2-transparency-register"],
    summary="Registration-category breakdown with EP-pass and costs aggregates",
    description="""**What it does**
Returns the breakdown of registered organisations by registration category, with the count, total declared lobbying costs and number of EP accreditation passes per category.

**When to use it**
A one-call overview of the lobbying landscape — which categories (in-house, consultancies, NGOs, think tanks, ...) dominate by number, spend and Parliament access.

**Input**
No parameters.

**Try it**
```
GET /api/v2/transparency-register/categories
```

**You get back**
A list of category records, each with the category name, organisation count, aggregate costs and EP-pass count.

**Data freshness**
Refreshed daily from the Transparency Register public XML.""",
)
async def transparency_register_categories(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[CategoryCount]:
    return await _v1.list_categories(request=request, user=user, db=db)


@router.get(
    "/{code}",
    response_model=TrDetail,
    tags=["v2-transparency-register"],
    summary="Single organisation in the Transparency Register (full record + body)",
    description="""**What it does**
Returns one registered organisation in full by its Transparency Register identification code — all declared fields plus the composed body and the 5 datapoints.

**Input**
`code` — the Transparency Register identification code, e.g. `880143435725-46`.

**Try it**
```
GET /api/v2/transparency-register/880143435725-46
```

**You get back**
A single `TrDetail` with the full record + the 5 datapoints, or HTTP 404.

**Data freshness**
Refreshed daily from the Transparency Register public XML.""",
)
async def get_transparency_register(
    request: Request,
    code: str = Path(..., description="Transparency Register identification code, e.g. 880143435725-46."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TrDetail:
    return await _v1.get_tr(request=request, code=code, body_threshold=body_threshold, user=user, db=db)
