"""
Legislative Train source — /api/v2/legislative/legislative-train/*.

Backend: Brubru's legislative_carriages mirror of the EP Legislative Train
Schedule — files tracked against von der Leyen II priorities, with monthly
status timelines. Same underlying table as the OEIL source, but presented
train-style: priority + committee + status filters and a status timeline.

Native v2 (PROPOSED). Reuses the v1 procedures URL/enum helpers so link and
status formatting stay identical to the OEIL surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.legislative_train import LegislativeCarriage
from models.user import User

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1.procedures import _enum_str, _law_tracker_url, _oeil_url

router = APIRouter(prefix="/legislative-train", tags=["v2-legislative-train"])


class TrainCarriage(BaseModel):
    id: str
    title: Optional[str] = None
    oeil_procedure_ref: Optional[str] = None
    current_status: Optional[str] = None
    is_blocked: bool = False
    days_in_current_status: Optional[int] = None
    lead_committee: Optional[str] = None
    ec_priority_ids: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    expected_completion: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    status_history: list = Field(default_factory=list)
    oeil_key_events: list = Field(default_factory=list)
    law_tracker_url: Optional[str] = None
    public_url: Optional[str] = None


def _coerce_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _to_train(r: LegislativeCarriage, *, with_timeline: bool = False) -> TrainCarriage:
    return TrainCarriage(
        id=str(r.id),
        title=r.title,
        oeil_procedure_ref=r.oeil_procedure_ref,
        current_status=_enum_str(r.current_status),
        is_blocked=bool(r.is_blocked),
        days_in_current_status=r.days_in_current_status,
        lead_committee=r.lead_committee,
        ec_priority_ids=list(r.ec_priority_ids or []),
        policy_areas=list(r.policy_areas or []),
        expected_completion=r.expected_completion,
        last_updated=r.last_updated,
        status_history=_coerce_list(r.status_history) if with_timeline else [],
        oeil_key_events=_coerce_list(getattr(r, "oeil_key_events", None)) if with_timeline else [],
        law_tracker_url=_law_tracker_url(r.oeil_procedure_ref),
        public_url=_oeil_url(r.oeil_procedure_ref),
    )


@router.get(
    "/carriages",
    response_model=PaginatedResponse[TrainCarriage],
    summary="Legislative Train carriages — files by von der Leyen II priority / committee / status",
    description="""**What it does**
Lists the legislative files tracked on the EP Legislative Train Schedule, filterable by Commission priority, lead committee, and current status. Each carriage carries its priority tags, lead committee, current status, and expected completion.

**When to use it**
To monitor a Commission priority's pipeline ("everything under the Clean Industrial Deal"), or a committee's active files, train-style.

**Input**
- `priority` — Commission priority tag (matched against `ec_priority_ids`).
- `committee` — lead committee code (e.g. `ENVI`).
- `status` — current carriage status.
- `limit` (1-100, default 50), `page`.

**Try it**
```
GET /api/v2/legislative/legislative-train/carriages?committee=ENVI
```

**You get back**
A `PaginatedResponse[TrainCarriage]` (id, title, oeil_procedure_ref, current_status, lead_committee, ec_priority_ids, expected_completion, law_tracker_url).

**Data freshness**
Synced every 6 hours (hot tier) from OEIL; priority mapping refreshed with the Legislative Train schedule.""",
)
async def list_carriages(
    request: Request,
    priority: Optional[str] = Query(None, description="Commission priority tag (matched against ec_priority_ids)"),
    committee: Optional[str] = Query(None, description="Lead committee code (e.g. ENVI)"),
    status: Optional[str] = Query(None, description="Current carriage status"),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TrainCarriage]:
    query = db.query(LegislativeCarriage)
    filters = []
    if committee:
        filters.append(func.upper(LegislativeCarriage.lead_committee) == committee.upper())
    if status:
        filters.append(
            func.lower(func.cast(LegislativeCarriage.current_status, String)) == status.lower()
        )
    if priority:
        # ec_priority_ids may be ARRAY or JSON — cast to text and substring-match
        # so the filter is type-agnostic.
        filters.append(func.cast(LegislativeCarriage.ec_priority_ids, String).ilike(f"%{priority}%"))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(LegislativeCarriage.last_updated.desc().nullslast(), LegislativeCarriage.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    data = [_to_train(r) for r in rows]
    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        op_core_title="Legislative Train carriages",
        op_core_type="Legislative procedure",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/carriages/{carriage_id:path}",
    response_model=TrainCarriage,
    summary="One Legislative Train carriage + its monthly status timeline",
    description="""**What it does**
Returns one carriage with its full status history / timeline — the train view of a single legislative file.

**When to use it**
To show a file's journey across the Legislative Train (status changes over time) in one call.

**Input**
- `carriage_id` (path) — Brubru's internal carriage id (from the list endpoint) or the OEIL procedure reference.

**Try it**
```
GET /api/v2/legislative/legislative-train/carriages/123
```

**You get back**
A `TrainCarriage` including `status_history[]` and `oeil_key_events[]`. HTTP 404 (`reason_code: not_found`) if no carriage matches.

**Data freshness**
Synced every 6 hours (hot tier) from OEIL.""",
)
async def get_carriage(
    carriage_id: str = Path(..., description="Internal carriage id or OEIL procedure reference"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TrainCarriage:
    r = None
    # Try internal id (numeric/uuid), then OEIL ref.
    try:
        r = (
            db.query(LegislativeCarriage)
            .filter(func.cast(LegislativeCarriage.id, String) == carriage_id)
            .first()
        )
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        r = None
    if r is None:
        r = (
            db.query(LegislativeCarriage)
            .filter(LegislativeCarriage.oeil_procedure_ref == carriage_id)
            .first()
        )
    if r is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Carriage {carriage_id} not found", "reason_code": "not_found", "resource": "carriage", "id": carriage_id},
        )
    return _to_train(r, with_timeline=True)
