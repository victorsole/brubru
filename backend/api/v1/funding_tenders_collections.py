"""
Three EU Funds & Tenders Portal collections, requested 1 May 2026:
  GET /api/v1/ft-calls-for-proposals    — open + forthcoming + closed funding calls
  GET /api/v1/ft-calls-for-tenders      — public-procurement opportunities
  GET /api/v1/ft-funded-projects        — completed/active EU-funded grant projects

Source: ec.europa.eu/info/funding-tenders/opportunities/portal — fully
SPA-rendered with Akamai WAF; anonymous REST/JSON access is blocked.
Real-data ingestion requires browser automation (Playwright). Until that
ships, these endpoints return honest empty (no fixtures).

All queries filter is_test=False so any future fixture row never leaks.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.database import get_db
from models.funding_tenders import (
    FtCallForProposals,
    FtCallForTenders,
    FtFundedProject,
)
from models.user import User

from ._body import (
    DEFAULT_HAS_BODY_THRESHOLD,
    body_threshold_param,
    compose_html_from_sections,
)
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


# ============================================================================
# Calls for proposals
# ============================================================================
calls_router = APIRouter(prefix="/ft-calls-for-proposals", tags=["v1-funding-tenders"])


class FtCallProposalItem(BaseModel):
    id: str
    topic_id: str
    call_id: Optional[str] = None
    framework_programme: Optional[str] = None
    title: str
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
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of source_url).")
    document_date: Optional[date] = Field(None, description="Publication date (date-only view of published_at).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _proposal_to_item(
    r: FtCallForProposals,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> FtCallProposalItem:
    body_html, body_text, has_body = compose_html_from_sections([
        ("Description", r.description),
    ], threshold=body_threshold)
    return FtCallProposalItem(
        id=str(r.id), topic_id=r.topic_id, call_id=r.call_id,
        framework_programme=r.framework_programme, title=r.title,
        description=r.description, status=r.status,
        type_of_action=r.type_of_action, deadline=r.deadline,
        deadline_secondary=r.deadline_secondary,
        indicative_budget=float(r.indicative_budget) if r.indicative_budget is not None else None,
        budget_currency=r.budget_currency, source_url=r.source_url,
        documents_url=r.documents_url,
        keywords=list(r.keywords or []), target_audience=list(r.target_audience or []),
        published_at=r.published_at, last_updated=r.last_updated,
        has_body=has_body, body_html=body_html, body_txt=body_text,
        public_url=r.source_url,
        document_date=r.published_at.date() if r.published_at and hasattr(r.published_at, "date") else r.published_at,
        creation_date=getattr(r, "scraped_at", None) or getattr(r, "first_seen", None) or r.last_updated,
    )


@calls_router.get(
    "",
    response_model=PaginatedResponse[FtCallProposalItem],
    summary="EU Funds & Tenders — calls for proposals (Horizon, EU4Health, Digital Europe, etc.)",
    description=(
        "Open + forthcoming + closed funding calls from the F&T Portal. "
        "Source: ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals. "
        "is_test=True rows are filtered out."
    ),
)
async def list_calls_for_proposals(
    request: Request,
    framework_programme: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="open | forthcoming | closed | under-evaluation"),
    type_of_action: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Substring match on title/description"),
    deadline_from: Optional[date] = Query(None),
    deadline_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FtCallProposalItem]:
    query = db.query(FtCallForProposals).filter(FtCallForProposals.is_test == False)  # noqa: E712
    filters = []
    if framework_programme:
        filters.append(FtCallForProposals.framework_programme.ilike(f"%{framework_programme}%"))
    if status:
        filters.append(FtCallForProposals.status == status.lower())
    if type_of_action:
        filters.append(FtCallForProposals.type_of_action.ilike(f"%{type_of_action}%"))
    if q:
        like = f"%{q}%"
        filters.append((FtCallForProposals.title.ilike(like)) | (FtCallForProposals.description.ilike(like)))
    if deadline_from:
        filters.append(FtCallForProposals.deadline >= deadline_from)
    if deadline_to:
        filters.append(FtCallForProposals.deadline <= deadline_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(FtCallForProposals.deadline.asc().nullslast(), FtCallForProposals.id.asc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    return build_envelope([_proposal_to_item(r, body_threshold=body_threshold) for r in rows], total=total, page=page, limit=limit)


@calls_router.get(
    "/{topic_id:path}",
    response_model=FtCallProposalItem,
    summary="Single call-for-proposals detail by topic_id",
)
async def get_call_for_proposals(
    topic_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtCallProposalItem:
    r = (
        db.query(FtCallForProposals)
        .filter(FtCallForProposals.topic_id == topic_id, FtCallForProposals.is_test == False)  # noqa: E712
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Call {topic_id} not found", "reason_code": "not_found",
                    "resource": "ft_call_for_proposals", "id": topic_id},
        )
    return _proposal_to_item(r, body_threshold=body_threshold)


# ============================================================================
# Calls for tenders
# ============================================================================
tenders_router = APIRouter(prefix="/ft-calls-for-tenders", tags=["v1-funding-tenders"])


class FtCallTenderItem(BaseModel):
    id: str
    tender_reference: str
    contracting_authority: Optional[str] = None
    title: str
    description: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None
    estimated_value: Optional[float] = None
    value_currency: Optional[str] = "EUR"
    deadline: Optional[datetime] = None
    source_url: str
    documents_url: Optional[str] = None
    cpv_codes: List[str] = Field(default_factory=list)
    published_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of source_url).")
    document_date: Optional[date] = Field(None, description="Publication date (date-only view of published_at).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _tender_to_item(
    r: FtCallForTenders,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> FtCallTenderItem:
    body_html, body_text, has_body = compose_html_from_sections([
        ("Description", r.description),
    ], threshold=body_threshold)
    return FtCallTenderItem(
        id=str(r.id), tender_reference=r.tender_reference,
        contracting_authority=r.contracting_authority, title=r.title,
        description=r.description, contract_type=r.contract_type,
        status=r.status,
        estimated_value=float(r.estimated_value) if r.estimated_value is not None else None,
        value_currency=r.value_currency, deadline=r.deadline,
        source_url=r.source_url, documents_url=r.documents_url,
        cpv_codes=list(r.cpv_codes or []),
        published_at=r.published_at, last_updated=r.last_updated,
        has_body=has_body, body_html=body_html, body_txt=body_text,
        public_url=r.source_url,
        document_date=r.published_at.date() if r.published_at and hasattr(r.published_at, "date") else r.published_at,
        creation_date=getattr(r, "scraped_at", None) or getattr(r, "first_seen", None) or r.last_updated,
    )


@tenders_router.get(
    "",
    response_model=PaginatedResponse[FtCallTenderItem],
    summary="EU Funds & Tenders — calls for tenders (public procurement)",
    description=(
        "Public procurement opportunities published by EU institutions/agencies. "
        "Source: ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-tenders. "
        "Note: TED notices live on a separate /tenders endpoint; this is the F&T-portal-specific view."
    ),
)
async def list_calls_for_tenders(
    request: Request,
    contracting_authority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    deadline_from: Optional[date] = Query(None),
    deadline_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FtCallTenderItem]:
    query = db.query(FtCallForTenders).filter(FtCallForTenders.is_test == False)  # noqa: E712
    filters = []
    if contracting_authority:
        filters.append(FtCallForTenders.contracting_authority.ilike(f"%{contracting_authority}%"))
    if status:
        filters.append(FtCallForTenders.status == status.lower())
    if contract_type:
        filters.append(FtCallForTenders.contract_type == contract_type.lower())
    if q:
        like = f"%{q}%"
        filters.append((FtCallForTenders.title.ilike(like)) | (FtCallForTenders.description.ilike(like)))
    if deadline_from:
        filters.append(FtCallForTenders.deadline >= deadline_from)
    if deadline_to:
        filters.append(FtCallForTenders.deadline <= deadline_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(FtCallForTenders.deadline.asc().nullslast(), FtCallForTenders.id.asc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    return build_envelope([_tender_to_item(r, body_threshold=body_threshold) for r in rows], total=total, page=page, limit=limit)


@tenders_router.get(
    "/{tender_reference:path}",
    response_model=FtCallTenderItem,
    summary="Single call-for-tenders detail",
)
async def get_call_for_tenders(
    tender_reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtCallTenderItem:
    r = (
        db.query(FtCallForTenders)
        .filter(
            FtCallForTenders.tender_reference == tender_reference,
            FtCallForTenders.is_test == False,  # noqa: E712
        )
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Tender {tender_reference} not found",
                    "reason_code": "not_found",
                    "resource": "ft_call_for_tenders", "id": tender_reference},
        )
    return _tender_to_item(r, body_threshold=body_threshold)


# ============================================================================
# Funded projects
# ============================================================================
projects_router = APIRouter(prefix="/ft-funded-projects", tags=["v1-funding-tenders"])


class FtFundedProjectItem(BaseModel):
    id: str
    project_id: str
    project_acronym: Optional[str] = None
    title: str
    objective: Optional[str] = None
    framework_programme: Optional[str] = None
    type_of_action: Optional[str] = None
    coordinator_name: Optional[str] = None
    coordinator_country: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_cost: Optional[float] = None
    eu_contribution: Optional[float] = None
    cost_currency: Optional[str] = "EUR"
    status: Optional[str] = None
    source_url: str
    published_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    # Body fields composed from objective + keywords — same pattern as the
    # `/discover/eurio/projects` listing on the same backing table, kept in
    # sync so partners get a consistent shape regardless of which surface
    # they use.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of source_url — the F&T Portal project page).")
    document_date: Optional[date] = Field(None, description="Project start date (the canonical 'when this happened' date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _project_to_item(
    r: FtFundedProject,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> FtFundedProjectItem:
    body_html, body_text, has_body = compose_html_from_sections([
        ("Objective", r.objective),
        ("Keywords", getattr(r, "keywords", None)),
    ], threshold=body_threshold)
    return FtFundedProjectItem(
        id=str(r.id), project_id=r.project_id,
        project_acronym=r.project_acronym, title=r.title, objective=r.objective,
        framework_programme=r.framework_programme, type_of_action=r.type_of_action,
        coordinator_name=r.coordinator_name, coordinator_country=r.coordinator_country,
        start_date=r.start_date, end_date=r.end_date,
        total_cost=float(r.total_cost) if r.total_cost is not None else None,
        eu_contribution=float(r.eu_contribution) if r.eu_contribution is not None else None,
        cost_currency=r.cost_currency, status=r.status, source_url=r.source_url,
        published_at=r.published_at, last_updated=r.last_updated,
        has_body=has_body, body_html=body_html, body_txt=body_text,
        public_url=r.source_url,
        document_date=r.start_date,
        creation_date=getattr(r, "scraped_at", None) or getattr(r, "first_seen", None) or r.last_updated,
    )


@projects_router.get(
    "",
    response_model=PaginatedResponse[FtFundedProjectItem],
    summary="EU Funds & Tenders — funded grant projects (project results)",
    description=(
        "Active and completed EU-funded grant projects. "
        "Source: ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/projects-results. "
        "Each row's source_url points to the project's portal page."
    ),
)
async def list_funded_projects(
    request: Request,
    framework_programme: Optional[str] = Query(None),
    coordinator_country: Optional[str] = Query(None, min_length=2, max_length=2),
    type_of_action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    start_from: Optional[date] = Query(None),
    end_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FtFundedProjectItem]:
    query = db.query(FtFundedProject).filter(FtFundedProject.is_test == False)  # noqa: E712
    filters = []
    if framework_programme:
        filters.append(FtFundedProject.framework_programme.ilike(f"%{framework_programme}%"))
    if coordinator_country:
        filters.append(FtFundedProject.coordinator_country == coordinator_country.upper())
    if type_of_action:
        filters.append(FtFundedProject.type_of_action.ilike(f"%{type_of_action}%"))
    if status:
        filters.append(FtFundedProject.status == status.lower())
    if q:
        like = f"%{q}%"
        filters.append((FtFundedProject.title.ilike(like)) | (FtFundedProject.objective.ilike(like)))
    if start_from:
        filters.append(FtFundedProject.start_date >= start_from)
    if end_to:
        filters.append(FtFundedProject.end_date <= end_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(FtFundedProject.start_date.desc().nullslast(), FtFundedProject.id.asc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    return build_envelope([_project_to_item(r, body_threshold=body_threshold) for r in rows], total=total, page=page, limit=limit)


@projects_router.get(
    "/{project_id:path}",
    response_model=FtFundedProjectItem,
    summary="Single funded-project detail",
)
async def get_funded_project(
    project_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtFundedProjectItem:
    r = (
        db.query(FtFundedProject)
        .filter(FtFundedProject.project_id == project_id, FtFundedProject.is_test == False)  # noqa: E712
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Project {project_id} not found", "reason_code": "not_found",
                    "resource": "ft_funded_project", "id": project_id},
        )
    return _project_to_item(r, body_threshold=body_threshold)
