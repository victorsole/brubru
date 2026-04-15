"""
/api/v1/laws — EU legislation from the eu_laws corpus (28,500+ laws).

Wraps the TSVECTOR-backed eu_laws table with canonical filters:
    celex, doc_type, policy_area, q (full-text), published_from, published_to.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_law import EULaw
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/laws", tags=["v1-laws"])


class LawItem(BaseModel):
    celex: Optional[str] = None
    title: Optional[str] = None
    doc_type: Optional[str] = None
    adopted_on: Optional[date] = Field(None, description="Adoption / publication date")
    oj_reference: Optional[str] = None
    policy_area: Optional[str] = None
    legal_basis: list = Field(default_factory=list)
    eurlex_url: Optional[str] = None


def _eurlex_url(celex: Optional[str]) -> Optional[str]:
    if not celex:
        return None
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


@router.get(
    "",
    response_model=PaginatedResponse[LawItem],
    summary="Search adopted EU legislation",
    description=(
        "Full-text search across 28,500+ adopted EU laws. Filters by CELEX, doc type, "
        "policy area, and publication-date range. Powered by PostgreSQL TSVECTOR."
    ),
)
async def list_laws(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search (title + subject matter)"),
    celex: Optional[str] = Query(None, description="Exact CELEX filter"),
    doc_type: Optional[str] = Query(None, description="Document type (Regulation, Directive, Decision, ...)"),
    policy_area: Optional[str] = Query(None, description="Policy area slug"),
    published_from: Optional[date] = Query(None, description="Publication date from (YYYY-MM-DD)"),
    published_to: Optional[date] = Query(None, description="Publication date to (YYYY-MM-DD)"),
    published_end: Optional[date] = Query(None, description="Alias of published_to (GovClipping-compatible)"),
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LawItem]:
    # Alias: published_end -> published_to
    if published_end and not published_to:
        published_to = published_end

    query = db.query(EULaw)

    filters = []
    if celex:
        filters.append(EULaw.celex == celex.upper())
    if doc_type:
        filters.append(func.lower(EULaw.doc_type_normalized) == doc_type.lower())
    if policy_area:
        filters.append(EULaw.policy_area == policy_area)
    if published_from:
        filters.append(EULaw.date >= published_from)
    if published_to:
        filters.append(EULaw.date <= published_to)

    if q:
        # Use search_vector if available, fall back to ILIKE on title
        ts_query = func.plainto_tsquery("english", q)
        filters.append(
            or_(
                EULaw.search_vector.op("@@")(ts_query),
                EULaw.title.ilike(f"%{q}%"),
            )
        )

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(EULaw.date.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        LawItem(
            celex=r.celex,
            title=r.title,
            doc_type=r.doc_type_normalized or r.doc_type,
            adopted_on=r.date,
            oj_reference=r.oj_reference,
            policy_area=r.policy_area,
            legal_basis=list(r.legal_basis or []),
            eurlex_url=_eurlex_url(r.celex),
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
