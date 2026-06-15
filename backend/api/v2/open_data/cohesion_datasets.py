"""DG REGIO Cohesion Open Data — dataset catalogue — /api/v2/open-data/cohesion-datasets.

The catalogue of DG REGIO Cohesion Open Data Platform datasets (Socrata). This is
the dataset CATALOGUE, distinct from the per-fund finance endpoints under
/api/v2/funding/* which serve the actual allocation rows. Ported from v1 via
delegation; v1 already carries the 5 datapoints.
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
from api.v1 import specialised_cohesion as _v1
from api.v1.specialised_cohesion import CohesionListItem, CohesionDetail, CohesionCategoryCount

router = APIRouter(prefix="/cohesion-datasets")


@router.get(
    "",
    response_model=PaginatedResponse[CohesionListItem],
    tags=["v2-open-data"],
    summary="DG REGIO Cohesion Open Data datasets (the dataset catalogue)",
    description="""**What it does**
Returns the catalogue of DG REGIO Cohesion Open Data Platform datasets (Socrata). Each row is a *dataset*, not a data row — to fetch the actual tabular rows follow `api_endpoint` (Socrata REST) or `public_url` (HTML viewer). For per-fund allocation rows, use the dedicated endpoints under `/api/v2/funding/*` (erdf, esf-plus, ...).

**When to use it**
To discover which cohesion-policy datasets exist (finances, achievements, beneficiaries) and where to pull them.

**Input**
`category`, `tag`, `q`, `limit` (max 200), `page`.

**Try it**
```
GET /api/v2/open-data/cohesion-datasets?category=Finances
GET /api/v2/open-data/cohesion-datasets?q=ERDF
```

**You get back**
A paginated list of datasets; each carries title, category, tags, `api_endpoint`, plus the 5 datapoints (`public_url` = the Socrata viewer page).

**Data freshness**
Synced from the Cohesion Open Data Platform catalogue.""",
)
async def list_cohesion_datasets(
    request: Request,
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CohesionListItem]:
    return await _v1.list_cohesion(
        request=request, category=category, tag=tag, q=q, limit=limit, page=page,
        body_threshold=body_threshold, user=user, db=db)


@router.get(
    "/categories",
    response_model=list[CohesionCategoryCount],
    tags=["v2-open-data"],
    summary="Cohesion Open Data dataset counts by category — browseable index",
    description="""**What it does**
Returns the count of cohesion datasets per category — a quick browseable index of the catalogue.

**Input**
No parameters.

**Try it**
```
GET /api/v2/open-data/cohesion-datasets/categories
```

**You get back**
A list of category records with the dataset count per category.

**Data freshness**
Synced from the Cohesion Open Data Platform catalogue.""",
)
async def cohesion_dataset_categories(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[CohesionCategoryCount]:
    return await _v1.list_categories(request=request, user=user, db=db)


@router.get(
    "/{socrata_id}",
    response_model=CohesionDetail,
    tags=["v2-open-data"],
    summary="Look up one Cohesion Open Data dataset by its Socrata id (full schema + body)",
    description="""**What it does**
Fetches one cohesion dataset in full by its Socrata 4x4 id — full schema, the API endpoint and the composed body.

**Input**
`socrata_id` — the Socrata 4x4 id, e.g. `7twf-r3rc`.

**Try it**
```
GET /api/v2/open-data/cohesion-datasets/7twf-r3rc
```

**You get back**
A single `CohesionDetail` with the full record + the 5 datapoints, or HTTP 404.

**Data freshness**
Synced from the Cohesion Open Data Platform catalogue.""",
)
async def get_cohesion_dataset(
    request: Request,
    socrata_id: str = Path(..., description="Socrata 4x4 ID, e.g. 7twf-r3rc."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CohesionDetail:
    return await _v1.get_cohesion(
        request=request, socrata_id=socrata_id, body_threshold=body_threshold, user=user, db=db)
