"""
/api/v1/consultations/* — EC Have Your Say consultation feedback.

Reference endpoint for the Data Provider API. Wraps the existing
HaveYourSayFeedbackClient and returns data in the canonical
PaginatedResponse envelope.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.public_consultation import PublicConsultation
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consultations", tags=["v1-consultations"])


def _normalise_date(raw) -> Optional[str]:
    """Normalise upstream HYS date to ISO-8601 'YYYY-MM-DDTHH:MM:SSZ'.

    Upstream ranges from 'YYYY/MM/DD HH:MM:SS' to 'YYYY-MM-DD' to datetime objects.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%dT%H:%M:%SZ")
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("/", "-")
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", s)
    if m:
        return f"{m.group(1)}T{m.group(2)}Z"
    m = re.match(r"(\d{4}-\d{2}-\d{2})$", s)
    if m:
        return f"{m.group(1)}T00:00:00Z"
    return s


class FeedbackItem(BaseModel):
    feedback_id: Optional[str] = None
    date: Optional[str] = None  # upstream format varies; pass through as string
    user_type: Optional[str] = None
    organisation: Optional[str] = None
    author_name: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    company_size: Optional[str] = None
    transparency_register_number: Optional[str] = None
    text: Optional[str] = None
    attachments: list = Field(default_factory=list)
    public_url: Optional[str] = None


class FeedbackAggregates(BaseModel):
    """Summary aggregates exposed alongside the items list."""

    consultation_id: Optional[str] = None
    initiative_id: str
    publication_id: int
    title: Optional[str] = None
    portal_url: Optional[str] = None
    feedback_url: Optional[str] = None
    summary_total: int
    by_user_type: dict = Field(default_factory=dict)
    by_country: dict = Field(default_factory=dict)


class FeedbackEnvelope(PaginatedResponse[FeedbackItem]):
    """Response envelope + aggregates. Partners get analytics + detail in one call."""

    aggregates: FeedbackAggregates


@router.get(
    "/by-initiative/{initiative_id}/feedback",
    response_model=FeedbackEnvelope,
    summary="Stakeholder feedback on a Have Your Say initiative (live, paginated)",
    description=(
        "**What it does:** returns the live stakeholder feedback submitted to the EC "
        "Have Your Say portal for one initiative, plus summary aggregates (totals per "
        "country, per stakeholder type) in the same payload.\n\n"
        "**How to obtain an `initiative_id`:** call `/api/v1/consultations` (LIST) and "
        "grab the `initiative_id` field. This sub-route requires the **numeric** form "
        "(initiatives that accept feedback always have one — slug-style call-for-evidence "
        "IDs return 422).\n\n"
        "**Try it:** `GET /api/v1/consultations/by-initiative/13693/feedback?limit=10` "
        "(Cooking appliances energy labelling).\n\n"
        "**Cache:** upstream HYS portal cached for 6 hours."
    ),
)
async def get_feedback_by_initiative(
    request: Request,
    initiative_id: int,
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    country: Optional[str] = Query(None, min_length=3, max_length=3),
    user_type: Optional[str] = Query(None),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FeedbackEnvelope:
    from services.api_clients.have_your_say_feedback_client import (
        get_have_your_say_feedback_client,
    )

    consultation = (
        db.query(PublicConsultation)
        .filter(PublicConsultation.initiative_id == str(initiative_id))
        .first()
    )

    client = get_have_your_say_feedback_client()
    try:
        # Fetch more than we strictly need for the page so the client cache warms
        # but still cap at 100. Pagination here is intentionally bounded.
        items = await client.fetch_feedback(
            initiative_id,
            limit=limit,
            country=country,
            user_type=user_type,
        )
        summary = await client.get_summary_counts(initiative_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[v1] HYS feedback fetch failed for initiative {initiative_id}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "detail": "Upstream EU Have Your Say portal temporarily unavailable",
                "source": "have-your-say",
            },
        )

    total = int(summary.get("total", 0))

    data = [
        FeedbackItem(
            feedback_id=str(it.feedback_id) if it.feedback_id is not None else None,
            date=_normalise_date(it.date),
            user_type=it.user_type,
            organisation=it.organisation,
            author_name=it.author_name,
            country=it.country,
            language=it.language,
            company_size=it.company_size,
            transparency_register_number=it.transparency_register_number,
            text=it.short_text,
            attachments=it.attachments,
            public_url=it.public_url,
        )
        for it in items
    ]

    envelope = build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        detail_level="Full",
    )
    # Surface rate-limit headers for successful responses
    return FeedbackEnvelope(
        **envelope.model_dump(),
        aggregates=FeedbackAggregates(
            consultation_id=str(consultation.id) if consultation else None,
            initiative_id=str(initiative_id),
            publication_id=initiative_id,
            title=consultation.title if consultation else None,
            portal_url=consultation.portal_url if consultation else None,
            feedback_url=getattr(consultation, "feedback_url", None) if consultation else None,
            summary_total=total,
            by_user_type=summary.get("by_user_type", {}),
            by_country=summary.get("by_country", {}),
        ),
    )


# ============================================================================
# Consultations LIST endpoint (W1 P0 — Thursday brief 1.9)
# ============================================================================


class ConsultationItem(BaseModel):
    id: str
    initiative_id: str
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    consultation_type: Optional[str] = None
    status: Optional[str] = None
    dg_responsible: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    feedback_count: int = 0
    portal_url: Optional[str] = None
    feedback_url: Optional[str] = None
    com_references: list = Field(default_factory=list)
    celex_numbers: list = Field(default_factory=list)
    last_updated: Optional[datetime] = None


@router.get(
    "",
    response_model=PaginatedResponse[ConsultationItem],
    summary="List EC Have Your Say consultations / initiatives",
    description=(
        "Searchable, paginated list of EC public consultations, calls for evidence, "
        "and Have Your Say initiatives. For per-initiative stakeholder feedback, use "
        "/by-initiative/{id}/feedback."
    ),
)
async def list_consultations(
    request: Request,
    q: Optional[str] = Query(None, description="Substring match on title + description"),
    status: Optional[str] = Query(None, description="open | upcoming | closed | outcome_published | withdrawn"),
    consultation_type: Optional[str] = Query(None, description="public_consultation | call_for_evidence | feedback | roadmap | initiative"),
    dg_responsible: Optional[str] = Query(None, description="DG code, e.g. CNECT, JUST"),
    policy_area: Optional[str] = Query(None, description="Single policy area tag"),
    published_from: Optional[date] = Query(None, description="start_date >= value"),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None, description="Alias of published_to. 422 if both differ."),
    updated_from: Optional[datetime] = Query(None, description="last_updated >= value. Returns rows ordered by last_updated desc when set."),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to. 422 if both differ."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ConsultationItem]:
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if published_from and published_to and published_from > published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Invalid date range: published_from={published_from} is after published_to={published_to}.",
            "reason_code": "invalid_date_range",
        })
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    query = db.query(PublicConsultation)
    filters = []
    if status:
        filters.append(PublicConsultation.status == status.lower())
    if consultation_type:
        filters.append(PublicConsultation.consultation_type == consultation_type.lower())
    if dg_responsible:
        filters.append(PublicConsultation.dg_responsible == dg_responsible.upper())
    if policy_area:
        filters.append(PublicConsultation.policy_areas.any(policy_area))
    if published_from:
        filters.append(PublicConsultation.start_date >= published_from)
    if published_to:
        filters.append(PublicConsultation.start_date <= published_to)
    if updated_from:
        filters.append(PublicConsultation.last_updated >= updated_from)
    if updated_to:
        filters.append(PublicConsultation.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(PublicConsultation.title.ilike(like), PublicConsultation.description.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = PublicConsultation.last_updated.desc().nullslast()
    else:
        order_col = PublicConsultation.start_date.desc().nullslast()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    data = [
        ConsultationItem(
            id=str(r.id),
            initiative_id=r.initiative_id,
            title=r.title,
            short_title=r.short_title,
            description=r.description,
            consultation_type=r.consultation_type.value if hasattr(r.consultation_type, "value") else (str(r.consultation_type) if r.consultation_type else None),
            status=r.status.value if hasattr(r.status, "value") else (str(r.status) if r.status else None),
            dg_responsible=r.dg_responsible,
            policy_areas=list(r.policy_areas or []),
            start_date=r.start_date,
            end_date=r.end_date,
            feedback_count=int(r.feedback_count or 0),
            portal_url=r.portal_url,
            feedback_url=r.feedback_url,
            com_references=list(r.com_references or []),
            celex_numbers=list(r.celex_numbers or []),
            last_updated=r.last_updated,
        )
        for r in rows
    ]

    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/{initiative_id}",
    response_model=ConsultationItem,
    summary="Single consultation detail by initiative_id",
    description=(
        "**What it does:** returns a single Have Your Say consultation / call for "
        "evidence by its `initiative_id`.\n\n"
        "**How to obtain an `initiative_id`:** call `/api/v1/consultations` (LIST) and "
        "grab the `initiative_id` field. This route accepts BOTH numeric IDs "
        "(e.g. `13693`) and slug IDs (e.g. `eu-aviation-aeronautics-strategy-2026`).\n\n"
        "**Try it:**\n"
        "- `GET /api/v1/consultations/13693` (Cooking appliances energy labelling)\n"
        "- `GET /api/v1/consultations/13687` (Solid-fuel local space heaters)\n"
        "- `GET /api/v1/consultations/eu-aviation-aeronautics-strategy-2026` (EU Aviation Strategy)"
    ),
)
async def get_consultation_detail(
    initiative_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ConsultationItem:
    r = db.query(PublicConsultation).filter(PublicConsultation.initiative_id == initiative_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Consultation initiative_id={initiative_id} not found",
            "reason_code": "not_found",
            "resource": "consultation",
            "id": initiative_id,
        })
    return ConsultationItem(
        id=str(r.id),
        initiative_id=r.initiative_id,
        title=r.title,
        short_title=r.short_title,
        description=r.description,
        consultation_type=r.consultation_type.value if hasattr(r.consultation_type, "value") else (str(r.consultation_type) if r.consultation_type else None),
        status=r.status.value if hasattr(r.status, "value") else (str(r.status) if r.status else None),
        dg_responsible=r.dg_responsible,
        policy_areas=list(r.policy_areas or []),
        start_date=r.start_date,
        end_date=r.end_date,
        feedback_count=int(r.feedback_count or 0),
        portal_url=r.portal_url,
        feedback_url=r.feedback_url,
        com_references=list(r.com_references or []),
        celex_numbers=list(r.celex_numbers or []),
        last_updated=r.last_updated,
    )
