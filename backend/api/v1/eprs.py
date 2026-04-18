"""
/api/v1/eprs — European Parliamentary Research Service publications.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.eprs_publication import EPRSPublication
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/eprs", tags=["v1-eprs"])


class EPRSItem(BaseModel):
    id: str
    publication_id: Optional[str] = None
    title: Optional[str] = None
    publication_type: Optional[str] = None
    publication_date: Optional[datetime] = None
    authors: list = Field(default_factory=list)
    summary: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    committees: list = Field(default_factory=list)
    related_celex_numbers: list = Field(default_factory=list)
    related_procedures: list = Field(default_factory=list)
    html_url: Optional[str] = None
    pdf_url: Optional[str] = None
    word_count: Optional[int] = None
    page_count: Optional[int] = None
    has_full_text: bool = False


@router.get(
    "",
    response_model=PaginatedResponse[EPRSItem],
    summary="Search EPRS publications",
    description=(
        "European Parliamentary Research Service studies, briefings, in-depth analyses, "
        "EU legislation in progress updates, and more. Filters by type, committee, "
        "procedure reference, CELEX, publication-date range, full-text search."
    ),
)
async def list_eprs(
    request: Request,
    q: Optional[str] = Query(None, description="Substring search on title + summary"),
    publication_type: Optional[str] = Query(None, description="BRIEFING | STUDY | IN_DEPTH_ANALYSIS | AT_A_GLANCE | EU_LEGISLATION_IN_PROGRESS | ..."),
    committee: Optional[str] = Query(None, description="Committee code (LIBE, ENVI, ECON, ...)"),
    procedure_ref: Optional[str] = Query(None, description="OEIL procedure reference"),
    celex: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None, description="Alias of published_to"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EPRSItem]:
    if published_end and not published_to:
        published_to = published_end

    query = db.query(EPRSPublication)
    filters = []
    if publication_type:
        filters.append(EPRSPublication.publication_type == publication_type.upper())
    if committee:
        filters.append(EPRSPublication.committees.any(committee.upper()))
    if procedure_ref:
        filters.append(EPRSPublication.related_procedures.any(procedure_ref))
    if celex:
        filters.append(EPRSPublication.related_celex_numbers.any(celex.upper()))
    if published_from:
        filters.append(EPRSPublication.publication_date >= published_from)
    if published_to:
        filters.append(EPRSPublication.publication_date <= published_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(EPRSPublication.title.ilike(like), EPRSPublication.summary.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(EPRSPublication.publication_date.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        EPRSItem(
            id=str(r.id),
            publication_id=r.publication_id,
            title=r.title,
            publication_type=r.publication_type.value if hasattr(r.publication_type, "value") else (str(r.publication_type) if r.publication_type else None),
            publication_date=r.publication_date,
            authors=list(r.authors or []),
            summary=r.summary,
            policy_areas=list(r.policy_areas or []),
            committees=list(r.committees or []),
            related_celex_numbers=list(r.related_celex_numbers or []),
            related_procedures=list(r.related_procedures or []),
            html_url=r.html_url,
            pdf_url=r.pdf_url,
            word_count=r.word_count,
            page_count=r.page_count,
            has_full_text=bool(r.has_full_text),
        )
        for r in rows
    ]

    return build_envelope(data, total=total, page=page, limit=limit, published_from=published_from, published_to=published_to)
