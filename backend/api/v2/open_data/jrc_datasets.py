"""JRC data catalogue — /api/v2/open-data/jrc-datasets.

The Joint Research Centre data catalogue. Ported from v1 via delegation;
v1 already carries the 5 datapoints.
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
from api.v1 import specialised_jrc as _v1
from api.v1.specialised_jrc import JrcDatasetItem, JrcDatasetDetail

router = APIRouter(prefix="/jrc-datasets")


@router.get(
    "",
    response_model=PaginatedResponse[JrcDatasetItem],
    tags=["v2-open-data"],
    summary="JRC data catalogue — Joint Research Centre datasets",
    description="""**What it does**
Returns datasets from the Joint Research Centre (JRC) data catalogue — the Commission's in-house science service: environmental, energy, agricultural, economic and scientific datasets.

**When to use it**
To find authoritative EU scientific datasets by topic. Filter by `q` (free text) and `keyword`.

**Input**
`q`, `keyword`, `limit` (max 200), `page`.

**Try it**
```
GET /api/v2/open-data/jrc-datasets?q=emissions
```

**You get back**
A paginated list of datasets; each carries title, description, publisher, keywords, modified date, plus the 5 datapoints (`public_url` = the JRC dataset page; full body on the detail endpoint).

**Data freshness**
Synced from the JRC data catalogue.""",
)
async def list_jrc_datasets(
    request: Request,
    q: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[JrcDatasetItem]:
    return await _v1.list_datasets(
        request=request, q=q, keyword=keyword, limit=limit, page=page,
        body_threshold=body_threshold, user=user, db=db)


@router.get(
    "/{uuid}",
    response_model=JrcDatasetDetail,
    tags=["v2-open-data"],
    summary="Look up one JRC dataset by its UUID (full metadata + distributions)",
    description="""**What it does**
Fetches one JRC dataset in full by its UUID — full metadata plus its distributions (download links).

**Input**
`uuid` — the JRC dataset UUID from the list endpoint.

**Try it**
```
GET /api/v2/open-data/jrc-datasets/{uuid}
```

**You get back**
A single `JrcDatasetDetail` with the full record + the 5 datapoints, or HTTP 404.

**Data freshness**
Synced from the JRC data catalogue.""",
)
async def get_jrc_dataset(
    request: Request,
    uuid: str = Path(..., description="JRC dataset UUID."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> JrcDatasetDetail:
    return await _v1.get_dataset(
        request=request, uuid=uuid, body_threshold=body_threshold, user=user, db=db)
