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


class CommissionerProfileOut(BaseModel):
    """Profile-only view of a College member. Returned by `/commissioners` (list)
    and `/commissioners/{slug}` (detail). The agenda lives at a separate path."""
    slug: str
    name: str
    portfolio: str
    country: str
    bio_url: str
    agenda_url: Optional[str] = None              # Filtered unified-calendar URL when leader_id resolved
    agenda_pdf_url: Optional[str] = None          # Reserved — most don't publish a PDF
    unified_calendar_url: str = (
        "https://commission.europa.eu/about/organisation/college-commissioners/"
        "calendar-items-president-and-commissioners_en"
    )
    type: str = "commissioner"


def _build_profile_out(profile) -> CommissionerProfileOut:
    leader_id = getattr(profile, "leader_id", None)
    agenda_url = None
    if leader_id:
        agenda_url = (
            "https://commission.europa.eu/about/organisation/college-commissioners/"
            "calendar-items-president-and-commissioners_en"
            "?f%5B0%5D=commissioner_dynamic_commissioner_dynamic%3A"
            f"http%3A//publications.europa.eu/resource/authority/political-leader/{leader_id}"
        )
    return CommissionerProfileOut(
        slug=profile.slug,
        name=profile.name,
        portfolio=profile.portfolio,
        country=profile.country,
        bio_url=profile.bio_url,
        agenda_url=agenda_url,
    )


@router.get(
    "/{slug}",
    response_model=CommissionerProfileOut,
    summary="Commissioner profile (no agenda — see /agenda for events)",
    description=(
        "Profile-only view of one Commission college member. Same shape as the "
        "rows returned by GET /commissioners. To get the events / meetings for "
        "this commissioner, call GET /commissioners/{slug}/agenda."
    ),
)
async def get_profile(
    request: Request,
    slug: str,
    user: User = Depends(api_user_with_rate_limit),
) -> CommissionerProfileOut:
    from services.api_clients.commissioner_agenda_client import (
        get_commissioner_agenda_client,
    )

    client = get_commissioner_agenda_client()
    profile = client.resolve(slug)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "detail": "Commissioner not found",
                "resource": "commissioner",
                "id": slug,
            },
        )
    return _build_profile_out(profile)


@router.get(
    "/{name}/agenda",
    response_model=PaginatedResponse[AgendaItemOut],
    summary="Commissioner agenda — events only (no profile fields)",
    description=(
        "Live calendar items for a Commission college member. Name resolution is "
        "accent-insensitive and accepts full name, slug, or known nickname (27 members). "
        "Returns ONLY the agenda data envelope — for the profile, call "
        "GET /commissioners/{slug}."
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
) -> PaginatedResponse[AgendaItemOut]:
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

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=date_from,
        published_to=date_to,
    )
