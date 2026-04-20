"""
/api/v1/consultations/* — EC Have Your Say consultation feedback.

Reference endpoint for the Data Provider API. Wraps the existing
HaveYourSayFeedbackClient and returns data in the canonical
PaginatedResponse envelope.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
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
        "Live stakeholder feedback submitted to the EC Have Your Say portal, by the "
        "integer initiative ID. Returns both summary aggregates (totals per country, "
        "per stakeholder type) and the paginated items. Upstream is cached for 6 hours."
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
