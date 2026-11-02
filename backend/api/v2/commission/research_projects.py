"""GET /api/v2/commission/research-projects: a view of the funded projects since 2 Nov 2026.

Until then the route served its own copy of Horizon Europe from CORDIS, in economy_items, written by a second
ingester: 23,954 projects, every one also in ft_funded_projects, in a third shape without consortium (register
O50; funding standard §4: one dataset, one table, one writer). It now reads ft_funded_projects, the list
/api/v2/funding/ft-funded-projects serves, limited to what the CORDIS Horizon Europe dump holds. The route keeps
answering until the date set for legacy routes, with its old filters and defaults; an old numeric id still opens
its project. The rows in economy_items stay, frozen, as the map from those ids.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1 import funding_tenders_collections as _v1
from api.v1._body import body_threshold_param
from api.v1._change_window import SYNC_ORDERS, validate_window
from api.v1._date_bounds import UpperBoundDatetime
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.funding_tenders_collections import FtFundedProjectItem
from core.database import get_db
from models.user import User
from ..funding._standard import without_bodies

router = APIRouter()

# The programmes of the CORDIS Horizon Europe dump: its 23,954 projects were these two codes on 2 Nov 2026.
_HORIZON_DUMP = ("HORIZON", "EURATOM2027")
_ORDERS = ("recent", "oldest", "title")
# The old ids were economy_items' keys (up to about 11 million); a CORDIS grant number has 9 digits.
_LOWEST_GRANT_NUMBER = 100_000_000

_DESC = """**Deprecated view (2 Nov 2026).** The Horizon Europe and Euratom projects of `/api/v2/funding/ft-funded-projects`, the list to use for anything new.

**What it does**
Lists EU-funded research projects from CORDIS: title, objective, consortium, EU contribution, total cost, topic, status, start and end dates, each linking to its CORDIS page. Until 2 Nov 2026 this route served its own copy of the same projects.

**When to use it**
Only to keep an existing integration working. `/api/v2/funding/ft-funded-projects` serves these projects and every other programme, with more filters.

**Input**
`q` (words in the title, objective and keywords), `since`, `until` (the document date), `created_from`, `created_to`, `updated_from`, `updated_to`, `order` (recent | oldest | title | updated_asc | updated_desc | created_asc | created_desc), `page`, `limit`, `include_body`.

**Try it**
```
GET /api/v2/commission/research-projects?q=fungus
GET /api/v2/commission/research-projects?updated_from=2026-10-01&order=updated_asc
```

**You get back**
What `/api/v2/funding/ft-funded-projects` returns: `id`, `project_id`, `title`, `status`, `public_url`, `body_txt`, `body_html`, `document_date`, `creation_date`, `updated_date` and the project's fields. An item's `id` is the project's own key, no longer a number from the old copy.

**Data freshness**
As `/api/v2/funding/ft-funded-projects`: read every Sunday from CORDIS."""


@router.get("/research-projects", response_model=PaginatedResponse[FtFundedProjectItem], tags=["v2-commission"],
            deprecated=True, summary="EU research projects (Horizon Europe): a view of the funded projects", description=_DESC)
async def list_research_projects(
    request: Request,
    q: Optional[str] = Query(None, description="Words in the title, objective and keywords."),
    since: Optional[date] = Query(None, description="The document date on or after (YYYY-MM-DD). `from` is accepted as an alias."),
    until: Optional[date] = Query(None, description="The document date on or before (YYYY-MM-DD). `to` is accepted as an alias."),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Content last changed on or after (ISO date or datetime, UTC)."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Content last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | title | updated_asc | updated_desc | created_asc | created_desc."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_body: bool = Query(False, description="Return `body_txt` and `body_html` on every item."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    page_ = await _v1.funded_projects_page(
        request=request, framework_programme=None, coordinator_country=None, type_of_action=None, status=None, q=q,
        organisation=None, role=None, participant_country=None, topic=None, keyword=None, start_from=None, end_to=None,
        updated_from=window["updated_from"], updated_to=window["updated_to"], limit=limit, page=page,
        body_threshold=body_threshold, user=user, db=db, created_from=window["created_from"],
        created_to=window["created_to"], published_from=since or from_, published_to=until or to, order=order,
        programme_codes=_HORIZON_DUMP)
    return without_bodies(page_, include_body)


@router.get("/research-projects/{item_id}", response_model=FtFundedProjectItem, tags=["v2-commission"], deprecated=True,
            summary="One EU research project: a view of the funded project",
            description="""**Deprecated view (2 Nov 2026).** The project as `/api/v2/funding/ft-funded-projects/{project_id}` serves it.

**What it does**
Fetches one project by its grant number, its `id`, or the number this route used before 2 Nov 2026.

**When to use it**
Only to keep an existing integration working; use `/api/v2/funding/ft-funded-projects/{project_id}` for anything new.

**Input**
- `item_id` (path): a grant number (e.g. `101300652`), a project `id`, or an old id.

**Try it**
```
GET /api/v2/commission/research-projects/101300652
```

**You get back**
A single project, or 404.""")
async def get_research_project(
    item_id: str = Path(..., description="A grant number, a project id or an old id of this route."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
):
    project_id = item_id
    if item_id.isdigit() and int(item_id) < _LOWEST_GRANT_NUMBER:
        project_id = db.execute(text("SELECT guid FROM economy_items WHERE id = :i AND body_code = 'commission' "
                                     "AND item_type = 'research_project'"), {"i": int(item_id)}).scalar()
        if not project_id:
            raise HTTPException(status_code=404, detail=f"No research project with id {item_id}")
    return await _v1.get_funded_project(project_id=project_id, body_threshold=body_threshold, user=user, db=db)
