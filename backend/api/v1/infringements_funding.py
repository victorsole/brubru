"""
/api/v1/infringements
/api/v1/funding-opportunities

Two new collections requested for the GovClipping partnership.

Source-URL discipline: every row is required to have a row-specific source_url
(not a listing page). Fixture rows (is_test=True) are filtered out at the
query layer so they cannot leak into responses.
"""

from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.infringement_funding import FundingOpportunity, InfringementProcedure
from models.user import User

from ._body import (
    DEFAULT_HAS_BODY_THRESHOLD,
    body_threshold_param,
    compose_html_from_sections,
)
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


# ============================================================================
# /api/v1/infringements
# ============================================================================
infringements_router = APIRouter(prefix="/infringements", tags=["v1-infringements"])


class InfringementItem(BaseModel):
    id: str
    inf_reference: str
    member_state: Optional[str] = None
    procedure_stage: Optional[str] = None
    sector: Optional[str] = None
    title: str
    summary: Optional[str] = None
    decision_date: Optional[date] = None
    source_url: str
    pdf_url: Optional[str] = None
    related_celex: List[str] = Field(default_factory=list)
    policy_areas: List[str] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — source_url fallback to pdf_url.")
    body_txt: Optional[str] = Field(None, description="Plain-text body — the procedure summary when present.")
    body_html: Optional[str] = Field(None, description="Null — infringement decisions are PDF-source.")
    document_date: Optional[date] = Field(None, description="Decision date (alias of decision_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _infringement_to_item(r: InfringementProcedure) -> InfringementItem:
    return InfringementItem(
        id=str(r.id),
        inf_reference=r.inf_reference,
        member_state=r.member_state,
        procedure_stage=r.procedure_stage,
        sector=r.sector,
        title=r.title,
        summary=r.summary,
        decision_date=r.decision_date,
        source_url=r.source_url,
        pdf_url=r.pdf_url,
        related_celex=list(r.related_celex or []),
        policy_areas=list(r.policy_areas or []),
        last_updated=r.last_updated,
        public_url=r.source_url or r.pdf_url,
        body_txt=r.summary,
        body_html=None,
        document_date=r.decision_date,
        creation_date=getattr(r, "first_seen", None) or getattr(r, "scraped_at", None) or r.last_updated,
    )


@infringements_router.get(
    "",
    response_model=PaginatedResponse[InfringementItem],
    summary="Commission infringement procedure decisions",
    description=(
        "Decisions adopted by the College in the monthly infringement packages: "
        "letters of formal notice, reasoned opinions, referrals to the Court of "
        "Justice, closures. Source: ec.europa.eu/commission/presscorner. "
        "Fixture rows (is_test=True) are filtered out."
    ),
)
async def list_infringements(
    request: Request,
    member_state: Optional[str] = Query(None, min_length=2, max_length=2),
    procedure_stage: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Substring match on title/summary"),
    decision_from: Optional[date] = Query(None),
    decision_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[InfringementItem]:
    query = db.query(InfringementProcedure).filter(InfringementProcedure.is_test == False)  # noqa: E712
    filters = []
    if member_state:
        filters.append(InfringementProcedure.member_state == member_state.upper())
    if procedure_stage:
        filters.append(InfringementProcedure.procedure_stage.ilike(f"%{procedure_stage}%"))
    if sector:
        filters.append(InfringementProcedure.sector.ilike(f"%{sector}%"))
    if q:
        like = f"%{q}%"
        filters.append(
            (InfringementProcedure.title.ilike(like))
            | (InfringementProcedure.summary.ilike(like))
        )
    if decision_from:
        filters.append(InfringementProcedure.decision_date >= decision_from)
    if decision_to:
        filters.append(InfringementProcedure.decision_date <= decision_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(
            InfringementProcedure.decision_date.desc().nullslast(),
            InfringementProcedure.id.asc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return build_envelope(
        [_infringement_to_item(r) for r in rows],
        total=total, page=page, limit=limit,
        published_from=decision_from, published_to=decision_to,
    )


@infringements_router.get(
    "/{inf_reference:path}",
    response_model=InfringementItem,
    summary="Single infringement decision detail by INF reference",
)
async def get_infringement(
    inf_reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> InfringementItem:
    r = (
        db.query(InfringementProcedure)
        .filter(
            InfringementProcedure.inf_reference == inf_reference,
            InfringementProcedure.is_test == False,  # noqa: E712
        )
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Infringement {inf_reference} not found",
                "reason_code": "not_found",
                "resource": "infringement_procedure",
                "id": inf_reference,
            },
        )
    return _infringement_to_item(r)


# ============================================================================
# /api/v1/funding-opportunities
# ============================================================================
funding_router = APIRouter(prefix="/funding-opportunities", tags=["v1-funding"])


class FundingItem(BaseModel):
    id: str
    topic_id: str
    call_id: Optional[str] = None
    programme: Optional[str] = None
    title: str
    short_summary: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    type_of_action: Optional[str] = None
    deadline: Optional[datetime] = None
    deadline_secondary: Optional[datetime] = None
    indicative_budget: Optional[float] = None
    budget_currency: Optional[str] = "EUR"
    source_url: str
    documents_url: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    target_audience: List[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    # Body fields composed from short_summary + description (call objective +
    # scope text, ~4k chars typical). Source is HTML-page-derived but we
    # don't store the raw HTML, so body_html is composed semantic markup.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of source_url — the F&T Portal topic page).")
    document_date: Optional[date] = Field(None, description="Publication date (date-only view of published_at).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _funding_to_item(
    r: FundingOpportunity,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> FundingItem:
    body_html, body_text, has_body = compose_html_from_sections([
        ("Summary", r.short_summary),
        ("Description", r.description),
    ], threshold=body_threshold)
    return FundingItem(
        id=str(r.id),
        topic_id=r.topic_id,
        call_id=r.call_id,
        programme=r.programme,
        title=r.title,
        short_summary=r.short_summary,
        description=r.description,
        status=r.status,
        type_of_action=r.type_of_action,
        deadline=r.deadline,
        deadline_secondary=r.deadline_secondary,
        indicative_budget=float(r.indicative_budget) if r.indicative_budget is not None else None,
        budget_currency=r.budget_currency,
        source_url=r.source_url,
        documents_url=r.documents_url,
        keywords=list(r.keywords or []),
        target_audience=list(r.target_audience or []),
        published_at=r.published_at,
        last_updated=r.last_updated,
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        public_url=r.source_url,
        document_date=r.published_at.date() if r.published_at and hasattr(r.published_at, "date") else r.published_at,
        creation_date=getattr(r, "scraped_at", None) or getattr(r, "first_seen", None) or r.last_updated,
    )


@funding_router.get(
    "",
    response_model=PaginatedResponse[FundingItem],
    summary="EU Funds & Tenders opportunities",
    description=(
        "Calls for proposals across EU programmes (Horizon Europe, Digital Europe, "
        "CEF, EU4Health, Erasmus+, etc.) from the Funding & Tenders Portal. "
        "Source: ec.europa.eu/info/funding-tenders/opportunities/portal. "
        "Fixture rows (is_test=True) are filtered out."
    ),
)
async def list_funding_opportunities(
    request: Request,
    programme: Optional[str] = Query(None, description="Programme name (Horizon, CEF, Digital Europe, ...)"),
    status: Optional[str] = Query(None, description="open | forthcoming | closed | under-evaluation"),
    type_of_action: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Substring match on title/short_summary"),
    deadline_from: Optional[date] = Query(None),
    deadline_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FundingItem]:
    query = db.query(FundingOpportunity).filter(FundingOpportunity.is_test == False)  # noqa: E712
    filters = []
    if programme:
        filters.append(FundingOpportunity.programme.ilike(f"%{programme}%"))
    if status:
        filters.append(FundingOpportunity.status == status.lower())
    if type_of_action:
        filters.append(FundingOpportunity.type_of_action.ilike(f"%{type_of_action}%"))
    if q:
        like = f"%{q}%"
        filters.append(
            (FundingOpportunity.title.ilike(like))
            | (FundingOpportunity.short_summary.ilike(like))
        )
    if deadline_from:
        filters.append(FundingOpportunity.deadline >= deadline_from)
    if deadline_to:
        filters.append(FundingOpportunity.deadline <= deadline_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        # Default: most recent deadlines first (2025-2026 before decade-old
        # closed calls). Partners hit the endpoint to find opportunities they
        # can still apply to, not historic data.
        query.order_by(
            FundingOpportunity.deadline.desc().nullslast(),
            FundingOpportunity.id.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return build_envelope(
        [_funding_to_item(r, body_threshold=body_threshold) for r in rows],
        total=total, page=page, limit=limit,
    )


@funding_router.get(
    "/{topic_id:path}",
    response_model=FundingItem,
    summary="Single funding opportunity detail by topic_id",
)
async def get_funding_opportunity(
    topic_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FundingItem:
    r = (
        db.query(FundingOpportunity)
        .filter(
            FundingOpportunity.topic_id == topic_id,
            FundingOpportunity.is_test == False,  # noqa: E712
        )
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Funding opportunity {topic_id} not found",
                "reason_code": "not_found",
                "resource": "funding_opportunity",
                "id": topic_id,
            },
        )
    return _funding_to_item(r, body_threshold=body_threshold)
