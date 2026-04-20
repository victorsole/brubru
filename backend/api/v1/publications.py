"""
/api/v1/publications — unified EU institutional publications feed.

Reads from `institutional_publications` table, populated by the generic
RSS ingester (`backend/services/ingestion/rss_ingestor.py`).

Partners get one endpoint that spans ~26 feeds today (growing). Filters by
institution, source, category, policy area, free-text search, and
publication-date range.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.institutional_publication import InstitutionalPublication
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publications", tags=["v1-publications"])


class PublicationItem(BaseModel):
    id: str
    source_slug: str
    institution_slug: str
    category: Optional[str] = None
    title: str
    summary: Optional[str] = None
    url: str
    language: str = "en"
    published_date: Optional[datetime] = None
    policy_areas: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)


@router.get(
    "",
    response_model=PaginatedResponse[PublicationItem],
    summary="Unified feed of EU institutional publications",
    description=(
        "Searchable, paginated feed of press releases, reports, and news items "
        "from across EU institutions and decentralised agencies. Powered by the "
        "Brubru RSS ingestion pipeline (26+ sources today, growing). Filters: "
        "institution_slug, source_slug, category, policy_area, q (full-text), "
        "published_from, published_to."
    ),
)
async def list_publications(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search on title + summary"),
    institution_slug: Optional[str] = Query(None, description="e.g. european_commission, ecb, ema, frontex"),
    source_slug: Optional[str] = Query(None, description="e.g. ec_press, ecb_press, ema_news"),
    category: Optional[str] = Query(None, description="press_release | report | consultation | agenda | ..."),
    policy_area: Optional[str] = Query(None, description="Single policy area tag"),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None, description="Alias of published_to"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PublicationItem]:
    if published_end and not published_to:
        published_to = published_end

    query = db.query(InstitutionalPublication)
    filters = []
    if institution_slug:
        filters.append(InstitutionalPublication.institution_slug == institution_slug)
    if source_slug:
        filters.append(InstitutionalPublication.source_slug == source_slug)
    if category:
        filters.append(InstitutionalPublication.category == category)
    if policy_area:
        filters.append(InstitutionalPublication.policy_areas.any(policy_area))
    if published_from:
        filters.append(InstitutionalPublication.published_date >= published_from)
    if published_to:
        # Inclusive upper bound
        filters.append(
            InstitutionalPublication.published_date <= datetime.combine(published_to, datetime.max.time())
        )
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                InstitutionalPublication.title.ilike(like),
                InstitutionalPublication.summary.ilike(like),
            )
        )

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(InstitutionalPublication.published_date.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        PublicationItem(
            id=str(r.id),
            source_slug=r.source_slug,
            institution_slug=r.institution_slug,
            category=r.category,
            title=r.title,
            summary=r.summary,
            url=r.url,
            language=r.language or "en",
            published_date=r.published_date,
            policy_areas=list(r.policy_areas or []),
            tags=list(r.tags or []),
        )
        for r in rows
    ]

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
    )


class SourceItem(BaseModel):
    source_slug: str
    institution_slug: str
    count: int
    category: Optional[str] = None


@router.get(
    "/sources",
    summary="List all ingested sources with item counts",
    description="Partners discover which institutional feeds are available and how fresh each is.",
)
async def list_sources(
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            InstitutionalPublication.source_slug,
            InstitutionalPublication.institution_slug,
            InstitutionalPublication.category,
            func.count().label("count"),
            func.max(InstitutionalPublication.published_date).label("latest"),
        )
        .group_by(
            InstitutionalPublication.source_slug,
            InstitutionalPublication.institution_slug,
            InstitutionalPublication.category,
        )
        .all()
    )
    return {
        "total_sources": len(rows),
        "sources": sorted(
            [
                {
                    "source_slug": r.source_slug,
                    "institution_slug": r.institution_slug,
                    "category": r.category,
                    "count": int(r.count),
                    "latest": r.latest.isoformat() if r.latest else None,
                }
                for r in rows
            ],
            key=lambda s: (s["count"] or 0),
            reverse=True,
        ),
    }
