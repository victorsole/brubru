"""Access2Markets — /api/v2/commission/access2markets.

DG TRADE's Access2Markets reference data: partner/EU countries, the Combined
Nomenclature (CN) product tree, and a data-freshness probe. Live pass-through,
ported from v1 via delegation.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from models.user import User
from api.v1._body import body_threshold_param
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1 import specialised_a2m as _v1
from api.v1.specialised_a2m import CountryItem, ProductItem, FreshnessInfo

router = APIRouter(prefix="/access2markets")


@router.get(
    "/countries",
    response_model=PaginatedResponse[CountryItem],
    tags=["v2-commission"],
    summary="Access2Markets countries (EU Member States + trade partners)",
    description="""**What it does**
Returns the countries Access2Markets covers — EU Member States and trade partners — with ISO codes and an EU-MS flag.

**When to use it**
To resolve a country to its Access2Markets identifier before looking up tariffs / product rules.

**Input**
`eu_ms_only` (default false), `limit` (max 500), `page`.

**Try it**
```
GET /api/v2/commission/access2markets/countries?eu_ms_only=true
```

**You get back**
A paginated list of countries with ISO codes and the EU-MS flag.

**Data freshness**
Live pass-through from the Access2Markets API.""",
)
async def list_a2m_countries(
    request: Request,
    eu_ms_only: bool = Query(False),
    limit: int = Query(250, ge=1, le=500),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CountryItem]:
    return await _v1.list_countries(
        request=request, eu_ms_only=eu_ms_only, limit=limit, page=page,
        body_threshold=body_threshold, user=user)


@router.get(
    "/products",
    response_model=PaginatedResponse[ProductItem],
    tags=["v2-commission"],
    summary="Access2Markets Combined Nomenclature (CN) products",
    description="""**What it does**
Returns the Combined Nomenclature (CN) product tree used by Access2Markets — the goods classification underpinning EU tariffs and trade rules.

**When to use it**
To find the CN code for a product before querying tariffs / rules of origin. Filter by `q` (description substring) and `level` (CN tree depth).

**Input**
`q`, `level` (2-10), `limit` (max 500), `page`.

**Try it**
```
GET /api/v2/commission/access2markets/products?q=wine&level=4
```

**You get back**
A paginated list of CN nodes with code, description, level and parent code.

**Data freshness**
Live pass-through from the Access2Markets nomenclature API.""",
)
async def list_a2m_products(
    request: Request,
    q: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=2, le=10),
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[ProductItem]:
    return await _v1.list_products(
        request=request, q=q, level=level, limit=limit, page=page,
        body_threshold=body_threshold, user=user)


@router.get(
    "/last-update",
    response_model=FreshnessInfo,
    tags=["v2-commission"],
    summary="Access2Markets data freshness — timestamp of the last upstream refresh",
    description="""**What it does**
Returns the timestamp of the last upstream refresh of the Access2Markets data.

**When to use it**
A cheap freshness probe before relying on the country / product data.

**Try it**
```
GET /api/v2/commission/access2markets/last-update
```

**You get back**
A `FreshnessInfo` with the last-update timestamp.

**Data freshness**
Live pass-through.""",
)
async def a2m_last_update(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
) -> FreshnessInfo:
    return await _v1.last_update(request=request, user=user)
