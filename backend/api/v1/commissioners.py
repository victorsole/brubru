"""
/api/v1/commissioners — Commission College agendas (live).

Thin wrapper over CommissionerAgendaClient. Resolves name accent-insensitively,
scrapes the official Commission calendar, filters by date range.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commissioners", tags=["v1-commissioners"])


class AgendaItemOut(BaseModel):
    date: date
    title: str
    location: Optional[str] = None
    detail_url: Optional[str] = None


class CommissionerEnvelope(PaginatedResponse[AgendaItemOut]):
    commissioner_name: str
    commissioner_slug: str
    commissioner_portfolio: str
    commissioner_country: str
    bio_url: str


@router.get(
    "/{name}/agenda",
    response_model=CommissionerEnvelope,
    summary="Commissioner agenda (live, from commission.europa.eu)",
    description=(
        "Live calendar items for a Commission college member. Name resolution is "
        "accent-insensitive and accepts full name, surname, or known nickname (27 members)."
    ),
)
async def get_agenda(
    request: Request,
    name: str,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommissionerEnvelope:
    from services.api_clients.commissioner_agenda_client import (
        get_commissioner_agenda_client,
    )

    client = get_commissioner_agenda_client()
    try:
        profile, items = await client.fetch_agenda(name, date_from=date_from, date_to=date_to)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[v1] commissioner agenda fetch failed for {name}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "detail": "Upstream Commission calendar temporarily unavailable",
                "source": "commission.europa.eu",
            },
        )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "detail": "Commissioner not found",
                "resource": "commissioner",
                "id": name,
            },
        )

    total = len(items)
    start = (page - 1) * limit
    end = start + limit
    page_items = items[start:end]

    data = [
        AgendaItemOut(
            date=it.date,
            title=it.title,
            location=it.location or None,
            detail_url=it.detail_url or None,
        )
        for it in page_items
    ]

    envelope = build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=date_from,
        published_to=date_to,
    )
    return CommissionerEnvelope(
        **envelope.model_dump(),
        commissioner_name=profile.name,
        commissioner_slug=profile.slug,
        commissioner_portfolio=profile.portfolio,
        commissioner_country=profile.country,
        bio_url=profile.bio_url,
    )
