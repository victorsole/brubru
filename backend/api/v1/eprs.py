"""
/api/v1/eprs — European Parliamentary Research Service publications.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — html_url fallback to pdf_url.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (currently the publication summary — EPRS full-text lives in the source HTML behind html_url).")
    body_html: Optional[str] = Field(None, description="Null for this endpoint — EPRS HTML lives on europarl.europa.eu/thinktank.")
    document_date: Optional[date] = Field(None, description="Publication date (date-only view of publication_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


@router.get(
    "",
    response_model=PaginatedResponse[EPRSItem],
    summary="EPRS think-tank publications — Parliament's research service (briefings, studies, in-depth)",
    description="""**What it does**
Returns publications from EPRS — the European Parliamentary Research Service, the EP's in-house think-tank. Covers briefings, studies, in-depth analyses, at-a-glance notes, "EU legislation in progress" tracker entries, initial appraisals, ex-post evaluations, and historical archives. Each row carries the publication ID + type, authors, summary, policy areas, related procedure refs and legal IDs, HTML + PDF URLs, and (when ingested) word + page counts.

**When to use it**
EPRS publications are the highest-quality non-partisan policy briefings on EU files — used by MEPs (and their staff) to understand legislation. Filter by `committee` to find what's been written for the LIBE committee, by `procedure_ref` for everything related to one file, or by `q` for free-text search.

**Input**
- `q` — substring on title + summary.
- `publication_type` — `BRIEFING` / `STUDY` / `IN_DEPTH_ANALYSIS` / `AT_A_GLANCE` / `EU_LEGISLATION_IN_PROGRESS` / `INITIAL_APPRAISAL` / `EX_POST_EVALUATION` / etc.
- `committee` — committee code.
- `procedure_ref` — OEIL reference.
- `celex` — legal identifier cross-link.
- `published_from`, `published_to` (and `published_end` alias).
- `updated_from`, `updated_to` (and `updated_end` alias) — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/eprs?committee=ENVI&publication_type=BRIEFING
GET /api/v1/eprs?q=CBAM&published_from=2026-01-01
```

**You get back**
A `PaginatedResponse[EPRSItem]` envelope. Each item carries `publication_id` (e.g. `EPRS_BRI(2026)762322`), `title`, `publication_type`, `publication_date`, `authors`, `summary`, `policy_areas`, `committees`, `related_celex_numbers`, `related_procedures`, `html_url`, `pdf_url`, `word_count`, `page_count`, plus the 5 envelope-level datapoints.

**Data freshness**
Synced every 12 hours (02:00 / 14:00 UTC, warm tier) from the EP Think Tank portal RSS (EPRS + ECTI + CASP) + the WordPress blog RSS as secondary source. EPRS publishes throughout the day; 12h sync catches new pieces inside a half-day.""",
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
    published_end: Optional[date] = Query(None, description="Alias of published_to. 422 if both differ."),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — rows last_updated >= value. Returns rows ordered by last_updated desc when set."),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to. 422 if both differ."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EPRSItem]:
    if published_end and published_to and published_end != published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
                "reason_code": "conflicting_params",
            },
        )
    if published_end and not published_to:
        published_to = published_end
    if published_from and published_to and published_from > published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: published_from={published_from} is after published_to={published_to}.",
                "reason_code": "invalid_date_range",
            },
        )
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
                "reason_code": "conflicting_params",
            },
        )
    if updated_end and not updated_to:
        updated_to = updated_end
    if updated_from and updated_to and updated_from > updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: updated_from={updated_from} is after updated_to={updated_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    query = db.query(EPRSPublication)
    filters = []
    if publication_type:
        # DB stores lowercase enum values ('briefing', 'study', 'at_a_glance', ...)
        filters.append(EPRSPublication.publication_type == publication_type.lower())
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
    if updated_from:
        filters.append(EPRSPublication.last_updated >= updated_from)
    if updated_to:
        filters.append(EPRSPublication.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(EPRSPublication.title.ilike(like), EPRSPublication.summary.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = EPRSPublication.last_updated.desc().nullslast()
    else:
        order_col = EPRSPublication.publication_date.desc().nullslast()
    rows = (
        query.order_by(order_col)
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
            public_url=r.html_url or r.pdf_url,
            body_txt=r.summary,
            body_html=None,
            document_date=r.publication_date.date() if r.publication_date and hasattr(r.publication_date, "date") else r.publication_date,
            creation_date=getattr(r, "last_updated", None) or getattr(r, "scraped_at", None) or getattr(r, "first_seen", None),
        )
        for r in rows
    ]

    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/{publication_id}",
    response_model=EPRSItem,
    summary="Look up one EPRS publication by its publication_id — full metadata + links",
    description="""**What it does**
Fetches a single EPRS publication by its publication_id. Returns the same shape as the list endpoint, including HTML + PDF URLs for the full text and the related procedures / legal IDs the publication cross-references.

**When to use it**
After locating an EPRS publication via the list endpoint, use this to deep-link into a specific publication. The HTML URL is the canonical EP Think Tank page; the PDF URL is the direct download.

**Input**
- `publication_id` (path) — EPRS publication ID (e.g. `EPRS_BRI(2026)762322`). The `:path` matcher accepts parentheses verbatim.

**Try it**
```
GET /api/v1/eprs/EPRS_BRI(2026)762322
```

**You get back**
A single `EPRSItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — synced every 12 hours from the EP Think Tank portal.""",
)
async def get_eprs_detail(
    publication_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> EPRSItem:
    r = (
        db.query(EPRSPublication)
        .filter(EPRSPublication.publication_id == publication_id)
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"EPRS publication_id {publication_id} not found",
                "reason_code": "not_found",
                "resource": "eprs_publication",
                "id": publication_id,
            },
        )
    return EPRSItem(
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
        public_url=r.html_url or r.pdf_url,
        body_txt=r.summary,
        body_html=None,
        document_date=r.publication_date.date() if r.publication_date and hasattr(r.publication_date, "date") else r.publication_date,
        creation_date=getattr(r, "last_updated", None) or getattr(r, "scraped_at", None) or getattr(r, "first_seen", None),
    )
