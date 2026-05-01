"""
/api/v1/procedures — EU legislative procedures (legislative_carriages).

Each carriage represents one file moving through the ordinary legislative
procedure (Commission proposal -> EP/Council -> adoption). Filters by OEIL
procedure reference, status, committee, last-update date range.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    # Aggregated procedure tracker on law-tracker.europa.eu — combines OEIL,
    # EUR-Lex and Commission events on a single page. Pattern:
    # https://law-tracker.europa.eu/procedure/{YYYY}_{NNN}?lang=en
    law_tracker_url: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None


def _law_tracker_url(oeil_ref: Optional[str]) -> Optional[str]:
    """Map an OEIL procedure reference (e.g. '2025/0420(COD)') to the
    law-tracker.europa.eu URL ('2025_420'). Strips leading zeros from the
    sequential number to match the tracker's slug format. Returns None when
    we can't parse the ref."""
    if not oeil_ref:
        return None
    import re
    m = re.match(r"^\s*(\d{4})/0*(\d+)(?:\([A-Z]+\))?\s*$", oeil_ref)
    if not m:
        return None
    year, seq = m.group(1), m.group(2)
    return f"https://law-tracker.europa.eu/procedure/{year}_{seq}?lang=en"


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
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
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
    # Add id as secondary sort to keep pagination deterministic when many rows
    # share last_updated (or it's NULL) — without it page=2 could return rows
    # already on page=1.
    rows = (
        query.order_by(
            LegislativeCarriage.last_updated.desc().nullslast(),
            LegislativeCarriage.id.asc(),
        )
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
            law_tracker_url=_law_tracker_url(r.oeil_procedure_ref),
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


# ============================================================================
# Procedure DETAIL endpoint (W1 P0 — Thursday brief 1.6 / Jordi P0.3)
# ============================================================================


class ProcedureDetail(BaseModel):
    id: str
    file_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    oeil_procedure_ref: Optional[str] = None

    current_status: Optional[str] = None
    is_blocked: bool = False
    days_in_current_status: Optional[int] = None
    text_type: Optional[str] = None

    # Committees + rapporteurs
    lead_committee: Optional[str] = None
    opinion_committees: list = Field(default_factory=list)
    committees: list = Field(default_factory=list)
    rapporteur_mep_id: Optional[str] = None

    # Cross-references
    celex_numbers: list = Field(default_factory=list)
    eprs_briefing_ids: list = Field(default_factory=list)
    eprs_matched_briefings: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    related_themes: list = Field(default_factory=list)
    spotlight_tags: list = Field(default_factory=list)
    ec_priority_ids: list = Field(default_factory=list)

    # Timeline & history
    timeline: list = Field(default_factory=list)
    status_history: list = Field(default_factory=list)
    oeil_timeline: list = Field(default_factory=list)
    oeil_key_events: list = Field(default_factory=list)
    eurlex_documents: list = Field(default_factory=list)

    # AI enrichment
    ai_summary: Optional[str] = None
    ai_entities: list = Field(default_factory=list)
    ai_policy_classifications: list = Field(default_factory=list)

    # Links
    legal_text_url: Optional[str] = None
    url: Optional[str] = None
    # https://law-tracker.europa.eu/procedure/{YYYY}_{N}?lang=en
    law_tracker_url: Optional[str] = None

    # Temporal
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    expected_completion: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    enrichment_quality: Optional[str] = None


def _coerce_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _enum_str(v) -> Optional[str]:
    """Render enums as their string value, not as 'EnumClass.MEMBER'."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


def _carriage_to_detail(r: LegislativeCarriage) -> ProcedureDetail:
    return ProcedureDetail(
        id=str(r.id),
        file_id=r.file_id,
        title=r.title,
        description=r.description,
        oeil_procedure_ref=r.oeil_procedure_ref,
        current_status=_enum_str(r.current_status),
        is_blocked=bool(r.is_blocked),
        days_in_current_status=r.days_in_current_status,
        text_type=_enum_str(r.text_type),
        lead_committee=r.lead_committee,
        opinion_committees=list(r.opinion_committees or []),
        committees=list(r.committees or []),
        rapporteur_mep_id=r.rapporteur_mep_id,
        celex_numbers=list(r.celex_numbers or []),
        eprs_briefing_ids=list(r.eprs_briefing_ids or []),
        eprs_matched_briefings=_coerce_list(r.eprs_matched_briefings),
        policy_areas=list(r.policy_areas or []),
        related_themes=list(r.related_themes or []),
        spotlight_tags=list(r.spotlight_tags or []),
        ec_priority_ids=list(r.ec_priority_ids or []),
        timeline=_coerce_list(r.timeline),
        status_history=_coerce_list(r.status_history),
        oeil_timeline=_coerce_list(r.oeil_timeline),
        oeil_key_events=_coerce_list(r.oeil_key_events),
        eurlex_documents=_coerce_list(r.eurlex_documents),
        ai_summary=r.ai_summary,
        ai_entities=_coerce_list(r.ai_entities),
        ai_policy_classifications=_coerce_list(r.ai_policy_classifications),
        legal_text_url=r.legal_text_url,
        url=r.url,
        law_tracker_url=_law_tracker_url(r.oeil_procedure_ref),
        first_seen=r.first_seen,
        last_updated=r.last_updated,
        expected_completion=r.expected_completion,
        enriched_at=r.enriched_at,
        enrichment_quality=r.enrichment_quality,
    )


@router.get(
    "/{reference:path}",
    response_model=ProcedureDetail,
    summary="Full procedure detail by OEIL reference or file_id",
    description=(
        "Returns the complete legislative carriage including OEIL timeline, key events, "
        "rapporteurs, committees, EPRS-matched briefings, EUR-Lex documents, and AI "
        "enrichment. Accepts either the OEIL procedure_ref (e.g. '2021/0106(COD)') "
        "or the internal file_id."
    ),
)
async def get_procedure_detail(
    reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ProcedureDetail:
    # Try OEIL procedure_ref first (most common partner usage), then file_id
    r = (
        db.query(LegislativeCarriage)
        .filter(LegislativeCarriage.oeil_procedure_ref == reference)
        .first()
    )
    if not r:
        r = (
            db.query(LegislativeCarriage)
            .filter(LegislativeCarriage.file_id == reference)
            .first()
        )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Procedure {reference} not found (tried oeil_procedure_ref and file_id)",
                "reason_code": "not_found",
                "resource": "procedure",
                "id": reference,
            },
        )
    return _carriage_to_detail(r)
