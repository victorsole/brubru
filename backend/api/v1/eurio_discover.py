"""
/api/v1/discover/eurio — EU-funded research project discovery.

Source: ft_funded_projects table, populated quarterly from CORDIS bulk
exports (https://cordis.europa.eu/data/cordis-{HORIZON,h2020,fp7}projects-csv.zip).

History note: this surface was originally wired against an EURIO SPARQL
endpoint, but the EURIO RDF graph isn't exposed on the public Cellar
endpoint (verified May 2026). Rewired to read from the local CORDIS
ingest, which contains the same data — project metadata, organisations,
topics, EuroSciVoc tags, legal basis, web links — covering ~80k Horizon
Europe + H2020 + FP7 projects.

Endpoints:
    GET /api/v1/discover/eurio/projects?topic=...&framework=...
    GET /api/v1/discover/eurio/projects/{cordis_id}/consortium
    GET /api/v1/discover/eurio/projects/{cordis_id}/deliverables
    GET /api/v1/discover/eurio/projects/{cordis_id}/funding
    GET /api/v1/discover/eurio/organisations/{org_name}/projects
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import (
    DEFAULT_HAS_BODY_THRESHOLD,
    body_threshold_param,
    compose_html_from_sections,
)
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover/eurio", tags=["v1-discover-eurio"])


# ----------------------------- response shapes -----------------------------


class ResearchProjectItem(BaseModel):
    cordis_id: str
    acronym: Optional[str] = None
    title: Optional[str] = None
    objective: Optional[str] = None
    framework: Optional[str] = None  # HORIZON / H2020 / FP7
    type_of_action: Optional[str] = None
    topic_code: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_cost: Optional[float] = None
    eu_contribution: Optional[float] = None
    coordinator_name: Optional[str] = None
    coordinator_country: Optional[str] = None
    cordis_url: Optional[str] = None
    # Body fields composed from project objective + keywords. The CORDIS
    # source is structured (not HTML upstream), so body_html is composed
    # locally — semantic <article> with <h2>Objective</h2> + paragraphs.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description="Canonical citizen URL — the CORDIS project page (alias of cordis_url).",
    )
    document_date: Optional[date] = Field(
        None,
        description="Project start_date (the canonical 'when this project happened' date).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this project row (ft_funded_projects.scraped_at).",
    )


class ConsortiumPayload(BaseModel):
    cordis_id: str
    project_acronym: Optional[str] = None
    title: Optional[str] = None
    organisations: list = Field(default_factory=list)
    coordinator_name: Optional[str] = None
    coordinator_country: Optional[str] = None
    organisation_count: int = 0
    # The 5 mandatory Brubru v1 datapoints (sourced from the parent project)
    public_url: Optional[str] = Field(None, description="CORDIS URL of the parent project.")
    body_txt: Optional[str] = Field(None, description="Parent project's objective as plain text.")
    body_html: Optional[str] = Field(None, description="Parent project's objective as HTML.")
    document_date: Optional[date] = Field(None, description="Parent project's start_date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the parent project (ft_funded_projects.scraped_at).")


class DeliverablesPayload(BaseModel):
    cordis_id: str
    project_acronym: Optional[str] = None
    title: Optional[str] = None
    web_links: list = Field(default_factory=list)
    note: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints (sourced from the parent project)
    public_url: Optional[str] = Field(None, description="CORDIS URL of the parent project.")
    body_txt: Optional[str] = Field(None, description="Parent project's objective as plain text.")
    body_html: Optional[str] = Field(None, description="Parent project's objective as HTML.")
    document_date: Optional[date] = Field(None, description="Parent project's start_date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the parent project.")


class FundingPayload(BaseModel):
    cordis_id: str
    project_acronym: Optional[str] = None
    title: Optional[str] = None
    framework: Optional[str] = None
    total_cost: Optional[float] = None
    eu_contribution: Optional[float] = None
    cost_currency: str = "EUR"
    legal_basis: list = Field(default_factory=list)
    by_organisation: list = Field(default_factory=list)
    # The 5 mandatory Brubru v1 datapoints (sourced from the parent project)
    public_url: Optional[str] = Field(None, description="CORDIS URL of the parent project.")
    body_txt: Optional[str] = Field(None, description="Parent project's objective as plain text.")
    body_html: Optional[str] = Field(None, description="Parent project's objective as HTML.")
    document_date: Optional[date] = Field(None, description="Parent project's start_date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the parent project.")


# ----------------------------- helpers -----------------------------


def _row_to_item(r, body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD) -> ResearchProjectItem:
    # Compose body from objective + keywords. compose_html_from_sections
    # honestly skips empty fields and emits None when nothing's there.
    body_html, body_text, has_body = compose_html_from_sections([
        ("Objective", r.objective),
        ("Keywords", r.keywords),
    ], threshold=body_threshold)
    return ResearchProjectItem(
        cordis_id=r.project_id,
        acronym=r.project_acronym,
        title=r.title,
        objective=r.objective,
        framework=r.framework_programme,
        type_of_action=r.type_of_action,
        topic_code=r.topic_code,
        status=r.status,
        start_date=r.start_date,
        end_date=r.end_date,
        total_cost=float(r.total_cost) if r.total_cost is not None else None,
        eu_contribution=float(r.eu_contribution) if r.eu_contribution is not None else None,
        coordinator_name=r.coordinator_name,
        coordinator_country=r.coordinator_country,
        cordis_url=r.source_url,
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        # 5 mandatory datapoints
        public_url=r.source_url,
        document_date=r.start_date,
        creation_date=getattr(r, "scraped_at", None),
    )


def _normalise_framework(f: str) -> str:
    """Map 'Horizon Europe' / 'horizon' / 'H2020' / 'FP7' to canonical uppercase."""
    if not f:
        return ""
    norm = f.strip().upper().replace("HORIZON EUROPE", "HORIZON").replace(" ", "")
    return norm


def _project_or_404(db: Session, cordis_id: str):
    """Look up by cordis_id; raise 404 with a structured detail when missing."""
    sql = text("""
        SELECT * FROM ft_funded_projects
        WHERE project_id = :pid AND COALESCE(is_test, false) = false
        LIMIT 1
    """)
    row = db.execute(sql, {"pid": cordis_id}).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Research project {cordis_id} not found",
                "reason_code": "not_found",
                "resource": "research_project",
                "id": cordis_id,
            },
        )
    return row


# ----------------------------- endpoints -----------------------------


@router.get(
    "/projects",
    response_model=PaginatedResponse[ResearchProjectItem],
    summary="Search EU-funded research projects by topic",
    description=(
        "Free-text search over the ft_funded_projects table populated from "
        "CORDIS quarterly bulk exports. Covers Horizon Europe (2021–present), "
        "H2020 (2014–2020), and FP7 (2007–2013). Filter by `framework` to "
        "restrict to a single programme."
    ),
)
async def find_projects(
    request: Request,
    topic: Optional[str] = Query(None, min_length=2, description="Free-text search on title + objective + keywords"),
    framework: Optional[str] = Query(None, description="HORIZON / H2020 / FP7"),
    country: Optional[str] = Query(None, description="ISO-2 coordinator country code"),
    status: Optional[str] = Query(None, description="signed / closed / terminated"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ResearchProjectItem]:
    where = ["COALESCE(is_test, false) = false"]
    params: Dict[str, Any] = {}
    if topic:
        where.append("""
            (to_tsvector('english',
                coalesce(title, '') || ' ' ||
                coalesce(objective, '') || ' ' ||
                coalesce(keywords, '')
            ) @@ plainto_tsquery('english', :topic))
        """)
        params["topic"] = topic
    if framework:
        where.append("framework_programme = :fw")
        params["fw"] = _normalise_framework(framework)
    if country:
        where.append("coordinator_country = :country")
        params["country"] = country.upper()
    if status:
        where.append("status = :status")
        params["status"] = status.lower()
    where_sql = " AND ".join(where) if where else "true"

    count_sql = text(f"SELECT COUNT(*) FROM ft_funded_projects WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    sql = text(f"""
        SELECT *
        FROM ft_funded_projects
        WHERE {where_sql}
        ORDER BY start_date DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = limit
    params["offset"] = (page - 1) * limit
    rows = db.execute(sql, params).fetchall()

    items = [_row_to_item(r, body_threshold=body_threshold) for r in rows]
    return build_envelope(
        items=items,
        total=int(total),
        page=page,
        limit=limit,
        coverage_complete=True,
    )


@router.get(
    "/projects/{cordis_id}/consortium",
    response_model=ConsortiumPayload,
    summary="Project consortium — WHO is in the project (orgs, roles, countries)",
    description="""**What it does**
Returns the CORDIS project's consortium: every participating organisation, its country, role (coordinator / participant / third-party), short name, EC contribution, and total cost. Built from `ft_funded_projects.organisations` (JSONB).

**How this differs from the sibling routes**
- `/consortium` — **who** is in the project (this endpoint).
- `/deliverables` — **what** the project has published (CORDIS web links).
- `/funding` — **how much money** flows where (totals + per-org breakdown + legal basis).

The three routes share project-level headers (cordis_id, title, project_acronym, public_url, body_txt, body_html, document_date) because they all describe the same project, but each carries a different primary payload — `organisations[]` here, `web_links[]` on /deliverables, `total_cost` + `eu_contribution` on /funding.

**Input**
- `cordis_id` (path) — numeric CORDIS project ID (e.g. `101131342`). Discover one via `/api/v1/discover/eurio/projects?topic=<your-topic>`.

**Try it**
```
GET /api/v1/discover/eurio/projects/101131342/consortium
```

**You get back**
A `ConsortiumPayload` object — see `organisations[]` for the per-org records, `coordinator_name` / `coordinator_country` for the lead, `organisation_count` for the size.""",
)
async def project_consortium(
    request: Request,
    cordis_id: str = Path(..., description="CORDIS project numeric id, e.g. 101131342"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ConsortiumPayload:
    row = _project_or_404(db, cordis_id)
    orgs = list(row.organisations or [])
    bh, bt, _ = compose_html_from_sections([("Objective", row.objective), ("Keywords", row.keywords)])
    return ConsortiumPayload(
        cordis_id=cordis_id,
        project_acronym=row.project_acronym,
        title=row.title,
        organisations=orgs,
        coordinator_name=row.coordinator_name,
        coordinator_country=row.coordinator_country,
        organisation_count=len(orgs),
        public_url=row.source_url,
        body_txt=bt,
        body_html=bh,
        document_date=row.start_date,
        creation_date=getattr(row, "scraped_at", None),
    )


@router.get(
    "/projects/{cordis_id}/deliverables",
    response_model=DeliverablesPayload,
    summary="Project deliverables — WHAT the project has published (web links)",
    description="""**What it does**
Returns the CORDIS-published web links for a project: project website, public reports, dissemination URLs. Sourced from CORDIS's `webLink` table inside `ft_funded_projects.web_links` (JSONB).

**Important caveat**
CORDIS does NOT publish per-deliverable metadata in its quarterly bulk dump. The "deliverables" you get here are the **published-output web links** the consortium chose to share via the CORDIS portal — typically a handful of URLs, often empty for in-progress projects. The route's `note` field explains this when `web_links` is empty.

**How this differs from the sibling routes**
- `/consortium` — **who** is in the project.
- `/deliverables` — **what** the project has published (this endpoint).
- `/funding` — **how much money** flows where.

Shared project-level headers (cordis_id, title, project_acronym, public_url, body_txt, body_html, document_date) are identical across all three because it's the same project; the primary payload differs.

**Input**
- `cordis_id` (path) — numeric CORDIS project ID. Discover one via `/api/v1/discover/eurio/projects?topic=<your-topic>`.

**Try it**
```
GET /api/v1/discover/eurio/projects/101131342/deliverables
```

**You get back**
A `DeliverablesPayload` — see `web_links[]` for the published URLs and `note` for context when the list is empty.""",
)
async def project_deliverables(
    request: Request,
    cordis_id: str = Path(..., description="CORDIS project numeric id"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> DeliverablesPayload:
    row = _project_or_404(db, cordis_id)
    links = list(row.web_links or [])
    note = (
        None if links else
        "CORDIS does not publish per-deliverable metadata in its quarterly bulk "
        "dump. Web links (project websites, public reports) appear here when the "
        "consortium publishes them via the CORDIS portal."
    )
    bh, bt, _ = compose_html_from_sections([("Objective", row.objective), ("Keywords", row.keywords)])
    return DeliverablesPayload(
        cordis_id=cordis_id,
        project_acronym=row.project_acronym,
        title=row.title,
        web_links=links,
        note=note,
        public_url=row.source_url,
        body_txt=bt,
        body_html=bh,
        document_date=row.start_date,
        creation_date=getattr(row, "scraped_at", None),
    )


@router.get(
    "/projects/{cordis_id}/funding",
    response_model=FundingPayload,
    summary="Project funding — HOW MUCH MONEY flows where (totals + per-org + legal basis)",
    description="""**What it does**
Returns the funding picture for one CORDIS project: total project cost + EU contribution headline figures, currency, per-organisation breakdown (when CORDIS published it), and the `legal_basis[]` array naming the Horizon / H2020 / FP7 programme part(s) the funding comes from (e.g. `HORIZON.1.2` = MSCA, `HORIZON.2.4` = Digital, Industry and Space).

**How this differs from the sibling routes**
- `/consortium` — **who** is in the project (organisations[]).
- `/deliverables` — **what** the project has published (web_links[]).
- `/funding` — **how much money** flows where (this endpoint).

Shared project-level headers (cordis_id, title, project_acronym, public_url, body_txt, body_html, document_date) are identical across all three because it's the same project; the primary payload differs — `total_cost`, `eu_contribution`, `cost_currency`, `legal_basis[]`, `by_organisation[]` are unique to this route.

**Input**
- `cordis_id` (path) — numeric CORDIS project ID. Discover one via `/api/v1/discover/eurio/projects?topic=<your-topic>`.

**Try it**
```
GET /api/v1/discover/eurio/projects/101131342/funding
```

**You get back**
A `FundingPayload` — see `eu_contribution` for the headline figure, `legal_basis[]` for the programme part, `by_organisation[]` for the per-org allocation.""",
)
async def project_funding(
    request: Request,
    cordis_id: str = Path(..., description="CORDIS project numeric id"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> FundingPayload:
    row = _project_or_404(db, cordis_id)
    by_org = []
    for o in (row.organisations or []):
        if o.get("ec_contribution") is not None or o.get("total_cost") is not None:
            by_org.append({
                "name": o.get("name"),
                "country": o.get("country"),
                "role": o.get("role"),
                "ec_contribution": o.get("ec_contribution"),
                "total_cost": o.get("total_cost"),
            })
    bh, bt, _ = compose_html_from_sections([("Objective", row.objective), ("Keywords", row.keywords)])
    return FundingPayload(
        cordis_id=cordis_id,
        project_acronym=row.project_acronym,
        title=row.title,
        framework=row.framework_programme,
        total_cost=float(row.total_cost) if row.total_cost is not None else None,
        eu_contribution=float(row.eu_contribution) if row.eu_contribution is not None else None,
        cost_currency=row.cost_currency or "EUR",
        legal_basis=list(row.legal_basis_details or []),
        by_organisation=by_org,
        public_url=row.source_url,
        body_txt=bt,
        body_html=bh,
        document_date=row.start_date,
        creation_date=getattr(row, "scraped_at", None),
    )


@router.get(
    "/organisations/{org_name}/projects",
    response_model=PaginatedResponse[ResearchProjectItem],
    summary="Research projects an organisation participated in",
    description="""**What it does**
Returns every CORDIS project where the named organisation appears in the consortium (any role: coordinator, participant, third-party). Match is **case-insensitive substring** on the organisation name — you don't need to know the exact legal name.

**Where to find an `org_name` to test**
The CORDIS data uses the organisation's full legal name (often ALL CAPS, sometimes localised). Three ways to discover one:

1. **Worked examples (top EU research orgs, copy-paste ready)** — each has 1,000+ projects in the DB:
   - `CNRS` — Centre National de la Recherche Scientifique (4,798 projects)
   - `Fraunhofer` — German applied-research society (2,989)
   - `CSIC` — Spanish CSIC (2,387)
   - `CNR` — Italian CNR (1,980)
   - `Max-Planck` — German Max Planck Society (1,825)
   - `Leuven` — KU Leuven (1,798)
   - `Cambridge` — University of Cambridge (1,772)
   - `Oxford` — University of Oxford (1,760)
   - `Imperial College` — Imperial College London (1,492)
2. **Pick one from /discover/eurio/projects** — call `/api/v1/discover/eurio/projects?topic=<your-topic>` and read any project's `organisations[]` array; copy the `name` field.
3. **Use a partial match** — the route accepts any substring, so `Sapienza` matches "SAPIENZA UNIVERSITÀ DI ROMA", `Karolinska` matches "KAROLINSKA INSTITUTET", etc. Lowercase works too.

**Input**
- `org_name` (path) — full or partial organisation name, case-insensitive.
- `framework` — HORIZON / H2020 / FP7 (optional).
- `limit` (1-200, default 50), `page` (default 1).

**Try it**
```
GET /api/v1/discover/eurio/organisations/CNRS/projects?limit=20
GET /api/v1/discover/eurio/organisations/Karolinska/projects?framework=HORIZON
```

**You get back**
Paginated envelope of `ResearchProjectItem` rows. Each row has `public_url` pointing to the project's CORDIS page.""",
)
async def org_projects(
    request: Request,
    org_name: str = Path(..., description="Organisation name (full or partial; case-insensitive)"),
    framework: Optional[str] = Query(None, description="HORIZON / H2020 / FP7"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ResearchProjectItem]:
    # Use ILIKE on the JSONB array values via jsonb_array_elements. ILIKE is
    # cheap given the GIN-indexed organisations column already narrows the set.
    where = ["COALESCE(is_test, false) = false"]
    where.append("""
        EXISTS (
            SELECT 1 FROM jsonb_array_elements(organisations) AS o
            WHERE o->>'name' ILIKE :name
        )
    """)
    params: Dict[str, Any] = {"name": f"%{org_name}%"}
    if framework:
        where.append("framework_programme = :fw")
        params["fw"] = _normalise_framework(framework)
    where_sql = " AND ".join(where)

    count_sql = text(f"SELECT COUNT(*) FROM ft_funded_projects WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    sql = text(f"""
        SELECT *
        FROM ft_funded_projects
        WHERE {where_sql}
        ORDER BY start_date DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = limit
    params["offset"] = (page - 1) * limit
    rows = db.execute(sql, params).fetchall()

    items = [_row_to_item(r, body_threshold=body_threshold) for r in rows]
    return build_envelope(
        items=items,
        total=int(total),
        page=page,
        limit=limit,
        coverage_complete=True,
    )
