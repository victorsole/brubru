"""
/api/v1/procedures — EU legislative procedures (legislative_carriages).

Each carriage represents one file moving through the ordinary legislative
procedure (Commission proposal -> EP/Council -> adoption). Filters by OEIL
procedure reference, status, committee, last-update date range.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.legislative_train import LegislativeCarriage
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/procedures", tags=["v1-procedures"])


class ProcedureItem(BaseModel):
    id: str
    file_id: Optional[str] = None
    title: Optional[str] = None
    oeil_procedure_ref: Optional[str] = None
    current_status: Optional[str] = None
    is_blocked: bool = False
    lead_committee: Optional[str] = None
    committees: list = Field(default_factory=list)
    rapporteur_mep_id: Optional[str] = None
    celex_numbers: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    legal_text_url: Optional[str] = None
    url: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None


@router.get(
    "",
    response_model=PaginatedResponse[ProcedureItem],
    summary="Search EU legislative procedures",
    description=(
        "1,200+ legislative files tracked from Commission proposal to adoption. "
        "Filters by OEIL reference, lead committee, status, and last-updated date range."
    ),
)
async def list_procedures(
    request: Request,
    q: Optional[str] = Query(None, description="Substring match on title"),
    reference: Optional[str] = Query(None, description="OEIL procedure reference (e.g. 2025/0726(COD))"),
    committee: Optional[str] = Query(None, description="Lead committee code (e.g. LIBE, ENVI)"),
    rapporteur_mep_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Carriage status"),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to (GovClipping-compatible)"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProcedureItem]:
    if updated_end and not updated_to:
        updated_to = updated_end
    query = db.query(LegislativeCarriage)
    filters = []
    if reference:
        filters.append(LegislativeCarriage.oeil_procedure_ref == reference)
    if committee:
        filters.append(func.upper(LegislativeCarriage.lead_committee) == committee.upper())
    if rapporteur_mep_id:
        filters.append(LegislativeCarriage.rapporteur_mep_id == rapporteur_mep_id)
    if status:
        filters.append(func.lower(func.cast(LegislativeCarriage.current_status, func.TEXT.type)) == status.lower())  # type: ignore[attr-defined]
    if updated_from:
        filters.append(LegislativeCarriage.last_updated >= updated_from)
    if updated_to:
        filters.append(LegislativeCarriage.last_updated <= updated_to)
    if q:
        filters.append(LegislativeCarriage.title.ilike(f"%{q}%"))

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(LegislativeCarriage.last_updated.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        ProcedureItem(
            id=str(r.id),
            file_id=r.file_id,
            title=r.title,
            oeil_procedure_ref=r.oeil_procedure_ref,
            current_status=str(r.current_status) if r.current_status is not None else None,
            is_blocked=bool(r.is_blocked),
            lead_committee=r.lead_committee,
            committees=list(r.committees or []),
            rapporteur_mep_id=r.rapporteur_mep_id,
            celex_numbers=list(r.celex_numbers or []),
            policy_areas=list(r.policy_areas or []),
            legal_text_url=r.legal_text_url,
            url=r.url,
            first_seen=r.first_seen,
            last_updated=r.last_updated,
        )
        for r in rows
    ]

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        updated_from=updated_from,
        updated_to=updated_to,
    )
