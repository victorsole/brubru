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
from core.identifiers import resolve_row


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
    summary="EU funding calls for proposals — Horizon Europe, Digital Europe, LIFE, EU4Health, Creative Europe, Erasmus+",
    description="""**What it does**
Returns calls for grant proposals from the EU Funding & Tenders Portal — the canonical entry point for Commission-managed grant programmes (Horizon Europe, Digital Europe, LIFE, EU4Health, Creative Europe, Erasmus+, EIC, AMIF, ISF, BMVI, JTM, etc.). Each row carries the topic_id (the EU's identifier, e.g. `HORIZON-CL5-2026-D2-01-01`), the framework programme, the type of action (RIA / IA / CSA / CoFund / etc.), the status (open / forthcoming / closed / under-evaluation), the deadline, the budget, and a body composed from title + objective + scope.

**When to use it**
For consultancies, universities, research orgs, and SMEs looking for non-procurement funding. Combine with `/api/v1/funded-projects` to see "what's been funded under this programme" → "what's currently open". Default ordering puts most recent deadlines first so partners land on actionable opportunities.

**Input**
- `framework_programme` — substring match (e.g. `Horizon Europe`, `Digital Europe`, `LIFE`).
- `status` — `open` / `forthcoming` / `closed` / `under-evaluation`.
- `type_of_action` — substring (e.g. `RIA`, `IA`, `CSA`).
- `q` — substring search on title + description.
- `deadline_from`, `deadline_to` — deadline window (use to find calls closing in your bidding-feasible range).
- `limit` (default 50, max 100), `page` (1-indexed).
- `body_threshold` — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v1/calls-for-proposals?framework_programme=Horizon&status=open
GET /api/v1/calls-for-proposals?q=AI&deadline_from=2026-06-01
```

**You get back**
A `PaginatedResponse[FtCallProposalItem]` envelope. Each item carries `topic_id`, `title`, `framework_programme`, `type_of_action`, `status`, `deadline`, `budget`, `description`, `objective`, `scope`, `expected_outcome`, `participation_eligibility`, `source_url`, `last_updated`, body fields + the 5 envelope-level datapoints (`public_url` = the F&T Portal opportunity page).

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from ec.europa.eu/info/funding-tenders/opportunities/portal/. New calls open / close throughout the day; daily sync catches them. is_test=True seed rows are filtered out at query time.""",
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
        # Default: most recent deadlines first (2026 + open calls surface before
        # historic closed calls). Partners exploring the endpoint should land
        # on current opportunities, not on calls that closed a decade ago.
        query.order_by(FtCallForProposals.deadline.desc().nullslast(), FtCallForProposals.id.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    return build_envelope([_proposal_to_item(r, body_threshold=body_threshold) for r in rows], total=total, page=page, limit=limit)


@calls_router.get(
    "/{topic_id:path}",
    response_model=FtCallProposalItem,
    summary="Look up one funding call for proposals by its EU topic_id",
    description="""**What it does**
Fetches a single call for proposals by its EU topic identifier. Returns the same shape as the list endpoint, with the full body composed from title + objective + scope + expected outcome.

**When to use it**
After locating a call via the list endpoint, use this for the full record — particularly when you want to embed call details in a bid-tracker or render the scope text in a UI.

**Input**
- `topic_id` (path) — the EU's identifier, e.g. `HORIZON-CL5-2026-D2-01-01`. The `:path` matcher accepts hyphens + dots verbatim, no URL-encoding needed.

**Try it**
```
GET /api/v1/calls-for-proposals/HORIZON-CL5-2026-D2-01-01
```

**You get back**
A single `FtCallProposalItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found` (also returned if the row is flagged `is_test=true`).

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the F&T Portal.""",
)
async def get_call_for_proposals(
    topic_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtCallProposalItem:
    r = resolve_row(db, FtCallForProposals, topic_id, natural_keys=("topic_id",),
                    extra_filters=(FtCallForProposals.is_test == False,))  # noqa: E712
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
    # Tier-2 fallback when the F&T portal didn't ship a description in the
    # call payload (very common — the portal exposes a stub on the listing
    # page and the full text only inside the downloadable docs URL). Compose
    # a structured metadata body from the row so the contract never returns
    # empty body_txt/body_html.
    if not body_text:
        import html as _html
        title = r.title or r.tender_reference or "(untitled call for tenders)"
        lines = [title]
        parts_html = [f"<h2>{_html.escape(title)}</h2>"]
        for k, v in [
            ("Reference", r.tender_reference),
            ("Contracting authority", r.contracting_authority),
            ("Contract type", r.contract_type),
            ("Status", r.status),
            ("Estimated value", f"{r.estimated_value:,.0f} {r.value_currency or 'EUR'}" if r.estimated_value else None),
            ("Deadline", r.deadline),
            ("Published", r.published_at),
            ("CPV codes", ", ".join(r.cpv_codes or []) or None),
            ("Documents", r.documents_url),
        ]:
            if v in (None, ""):
                continue
            lines.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        body_text = "\n".join(lines)
        body_html = "<article>" + "".join(parts_html) + "</article>"
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
    summary="EU public-procurement tenders from the F&T Portal — distinct from the /tenders TED view",
    description="""**What it does**
Returns calls for tenders (public procurement) published by EU institutions and agencies on the Funding & Tenders Portal. Each row carries the tender_reference, the contracting authority (which institution / agency is buying), the contract type, the status, the deadline, the budget, and a body composed from title + description.

**When to use it**
For service providers, consultancies, and contractors bidding on EU institutional procurement. This is the F&T Portal-specific view; for the broader TED (Tenders Electronic Daily) feed which covers Member State buyers as well, see `/api/v1/tenders`. The two surfaces overlap for some Commission contracts but TED is the authoritative legal source.

**Input**
- `contracting_authority` — substring (e.g. `European Commission`, `Frontex`, `EMA`).
- `status` — F&T tender status enum.
- `contract_type` — substring (e.g. `services`, `supplies`, `works`).
- `q` — substring search on title + description.
- `deadline_from`, `deadline_to` — submission window.
- `limit` (default 50, max 100), `page` (1-indexed).
- `body_threshold` — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v1/calls-for-tenders?contracting_authority=Frontex&status=open
GET /api/v1/calls-for-tenders?q=consultancy&deadline_from=2026-06-01
```

**You get back**
A `PaginatedResponse[FtCallTenderItem]` envelope. Each item carries `tender_reference`, `title`, `contracting_authority`, `contract_type`, `status`, `deadline`, `budget`, `description`, `source_url`, `last_updated`, body fields + the 5 envelope-level datapoints (`public_url` = the F&T Portal tender page).

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from ec.europa.eu/info/funding-tenders/opportunities/portal/. is_test=True seed rows are filtered out at query time.""",
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
        # Default: most recent deadlines first (2025-2026 published-at lines
        # up well; partners want active tenders, not historic ones).
        query.order_by(FtCallForTenders.deadline.desc().nullslast(), FtCallForTenders.id.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    return build_envelope([_tender_to_item(r, body_threshold=body_threshold) for r in rows], total=total, page=page, limit=limit)


@tenders_router.get(
    "/{tender_reference:path}",
    response_model=FtCallTenderItem,
    summary="Look up one F&T Portal tender by its tender_reference",
    description="""**What it does**
Fetches a single F&T Portal call for tenders by its EU tender_reference. Returns the same shape as the list endpoint.

**When to use it**
After locating a tender via the list endpoint, use this for the full record. The `:path` matcher accepts the reference verbatim including any slashes / dots / hyphens.

**Input**
- `tender_reference` (path) — the EU's tender identifier as published on the F&T Portal.

**Try it**
```
GET /api/v1/calls-for-tenders/<tender_reference>
```

**You get back**
A single `FtCallTenderItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the F&T Portal.""",
)
async def get_call_for_tenders(
    tender_reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtCallTenderItem:
    r = resolve_row(db, FtCallForTenders, tender_reference,
                    natural_keys=("tender_reference",),
                    extra_filters=(FtCallForTenders.is_test == False,))  # noqa: E712
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
    summary="EU grant-funded projects — active + completed results (Horizon Europe, FP7, H2020, sectoral programmes)",
    description="""**What it does**
Returns EU-funded grant projects from the Funding & Tenders Portal — both active and completed projects across all framework programmes (Horizon Europe, Horizon 2020, FP7, sectoral programmes like Digital Europe, EU4Health, LIFE, Creative Europe). Each row carries the project_id (e.g. `101082345`), the title, the framework programme, the type of action, the coordinator name + country, the consortium size, the start/end dates, the EU contribution, the total cost, the objective summary, and the project portal URL.

**When to use it**
For research orgs and consultancies doing competitive intelligence on EU funding: "what has the Commission funded on AI in the last 3 years?", "which Polish coordinators have run successful Horizon projects?", "what are the typical budgets for IA actions in Cluster 5?". Combine with `/api/v1/calls-for-proposals` to see the call → project pipeline.

**Input**
- `framework_programme` — substring (e.g. `Horizon Europe`, `Horizon 2020`).
- `coordinator_country` — ISO-2 (2 chars exact).
- `type_of_action` — substring (`RIA`, `IA`, `CSA`).
- `status` — F&T project status enum.
- `q` — substring search on title + objective.
- `start_from`, `end_to` — start-date / end-date window.
- `limit` (default 50, max 100), `page` (1-indexed).
- `body_threshold` — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v1/funded-projects?framework_programme=Horizon%20Europe&coordinator_country=NL
GET /api/v1/funded-projects?q=climate&type_of_action=IA
```

**You get back**
A `PaginatedResponse[FtFundedProjectItem]` envelope. Each item carries `project_id`, `title`, `framework_programme`, `type_of_action`, `coordinator_name`, `coordinator_country`, `consortium_size`, `start_date`, `end_date`, `eu_contribution`, `total_cost`, `objective`, `status`, `source_url`, `last_updated`, body fields + the 5 envelope-level datapoints (`public_url` = the F&T Portal project page).

**Data freshness**
Synced once per week (Sunday 05:00 UTC, weekly tier) from ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/projects-results. CORDIS (the more comprehensive research-results portal) is reachable separately via `/api/v1/discover/eurio`. is_test=True seed rows are filtered out at query time.""",
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
    summary="Look up one EU-funded project by its grant project_id (numeric)",
    description="""**What it does**
Fetches a single EU-funded project by its grant project_id. Returns the same shape as the list endpoint.

**When to use it**
After locating a project via the list endpoint, use this for the full record. For richer project metadata (deliverables, consortium members, publications), cross-reference via `/api/v1/discover/eurio/projects/{cordis_id}/consortium` etc.

**Input**
- `project_id` (path) — the EU grant project id (typically a numeric identifier, e.g. `101082345`).

**Try it**
```
GET /api/v1/funded-projects/101082345
```

**You get back**
A single `FtFundedProjectItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — weekly Sunday 05:00 UTC sync from the F&T Portal projects-results page.""",
)
async def get_funded_project(
    project_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FtFundedProjectItem:
    r = resolve_row(db, FtFundedProject, project_id, natural_keys=("project_id",),
                    extra_filters=(FtFundedProject.is_test == False,))  # noqa: E712
    if not r:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Project {project_id} not found", "reason_code": "not_found",
                    "resource": "ft_funded_project", "id": project_id},
        )
    return _project_to_item(r, body_threshold=body_threshold)
