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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.institutional_publication import InstitutionalPublication
from models.user import User

from ._body import body_from_html, body_from_html_or_text, body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope
from core.body_sources import read_body

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
    # Body fields populated from html_content (the source HTML stripped of
    # nav/footer/scripts during ingestion). body_html carries the raw HTML;
    # body_text is the stripped plain-text rendering.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # Deprecated alias kept one release; equals body_text or body_html.
    body: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — alias of url.")
    document_date: Optional[date] = Field(None, description="Publication date (date-only view of published_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


@router.get(
    "",
    response_model=PaginatedResponse[PublicationItem],
    summary="Unified feed of EU institutional publications — Commission, EP, Council, ECB, agencies",
    description="""**What it does**
Returns a searchable, paginated feed of press releases, reports, communications, and news items from across the EU institutional ecosystem. Aggregates 26+ official feeds today (growing) — Commission press corner + DG newsrooms, EP press service, Council, ECB, EMA, EFSA, ECHA, ENISA, FRA, Frontex, etc. Each row carries the institution + source feed slug, title + summary, the canonical URL, publication date, policy-area tags, and (when ingested) the full body in HTML + plain text.

**When to use it**
The single most useful endpoint for "what is the EU saying right now" — used by Brubru's chat for grounding answers in fresh institutional output, and by partners building monitoring dashboards. Filter by `institution_slug` for a single institution, `policy_area` for a topic, or use the incremental-sync pattern `updated_from=<last_check>` to poll deltas. For first-class filtered subsets see `/api/v1/press-releases` (category=press_release) and `/api/v1/eprs` (EPRS think-tank).

**Input**
- `q` — full-text search on title + summary.
- `institution_slug` — e.g. `european_commission`, `european_parliament`, `ecb`, `ema`, `frontex`.
- `source_slug` — narrower than institution (e.g. `ec_press`, `ecb_press`, `ema_news`).
- `category` — `press_release` / `report` / `consultation` / `agenda` / ...
- `policy_area` — single policy area tag.
- `published_from`, `published_to` (and `published_end` as alias for `published_to`).
- `updated_from`, `updated_to` (and `updated_end` as alias) — incremental sync on `fetched_at`.
- `limit` (default 50, max 100), `page` (1-indexed).
- `body_threshold` — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v1/publications?institution_slug=european_commission&limit=20
GET /api/v1/publications?q=AI%20Act&updated_from=2026-05-14T00:00:00
GET /api/v1/publications?policy_area=environment&published_from=2026-05-01
```

**You get back**
A `PaginatedResponse[PublicationItem]` envelope. Each item carries `institution_slug`, `source_slug`, `title`, `summary`, `url`, `language`, `published_date`, `policy_areas`, `tags`, `has_body`, `body_html`, `body_txt`, plus the 5 envelope-level datapoints (`public_url = url`, `document_date = published_date`, `creation_date = fetched_at`).

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from 26+ institutional RSS feeds. Press releases typically appear in the feed within minutes of being posted on the institutional site; the 6h sync cadence catches them inside a quarter-day.""",
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
    published_end: Optional[date] = Query(None, description="Alias of published_to. 422 if both differ."),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — rows fetched_at >= value. Returns rows ordered by fetched_at desc when set."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound — rows fetched_at <= value."),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to. 422 if both differ."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PublicationItem]:
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
    # Incremental sync filter: use fetched_at (when row first appeared in our DB).
    # InstitutionalPublication has no row-level updated_at; updated_date is the
    # source-side publication update time. fetched_at is the partner-friendly
    # signal for "what's new to me since X".
    if updated_from:
        filters.append(InstitutionalPublication.fetched_at >= updated_from)
    if updated_to:
        filters.append(InstitutionalPublication.fetched_at <= updated_to)
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
    if updated_from or updated_to:
        order_col = InstitutionalPublication.fetched_at.desc().nullslast()
    else:
        order_col = InstitutionalPublication.published_date.desc().nullslast()
    rows = (
        query.order_by(order_col)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = []
    for r in rows:
    # Which column holds this table's text is declared once in
    # core/body_sources.py; institutional_publications keeps HTML only, so
    # body_txt is derived from it rather than read from a column.
        _, _html_src = read_body("institutional_publications", r)
        body_html, body_text, has_body = body_from_html_or_text(_html_src, threshold=body_threshold)
        data.append(PublicationItem(
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
            has_body=has_body,
            body_html=body_html,
            body_txt=body_text,
            body=deprecated_body(body_text, body_html),
            public_url=r.url,
            document_date=r.published_date.date() if hasattr(r.published_date, "date") and r.published_date else None,
            creation_date=getattr(r, "fetched_at", None) or getattr(r, "first_seen", None),
        ))

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        updated_to=updated_to,
    )


class SourceItem(BaseModel):
    source_slug: str
    institution_slug: str
    count: int
    category: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints. /publications/sources is a
    # reference enumeration over institutional_publications.source_slug —
    # not a document — so the 4 content fields stay null. creation_date
    # is the response time.
    public_url: Optional[str] = Field(None, description="Null — sources are aggregations, not documents.")
    body_txt: Optional[str] = Field(None, description="Null — see /publications?source_slug=<slug> for documents.")
    body_html: Optional[str] = Field(None, description="Null.")
    document_date: Optional[date] = Field(None, description="Null — reference data is not dated.")
    creation_date: Optional[datetime] = Field(None, description="Response generation time.")


# IMPORTANT: /sources MUST be declared BEFORE /{publication_id}, otherwise
# FastAPI matches "sources" as a publication_id (UUID), the cast fails and
# returns 500. Static routes must precede param routes for correct dispatch.
@router.get(
    "/sources",
    summary="List every institutional source Brubru ingests, with item counts + freshness",
    description="""**What it does**
Returns every RSS / institutional source Brubru ingests, with the per-source article count and the timestamp of the most recent ingested item. Grouped by source_slug + institution_slug + category.

**When to use it**
Discover which institutional feeds your subscription covers before filtering the unified `/api/v1/publications` endpoint by `source_slug`. Also useful for monitoring — if `latest` is more than a few days old on a feed that should be daily, the upstream source is likely down (a real signal we use to alert on sync failures).

**Input**
No parameters. Requires an `X-API-Key` header.

**Try it**
```
GET /api/v1/publications/sources
```

**You get back**
A JSON object with `total_sources` (integer) and `sources` (array of `{source_slug, institution_slug, category, count, latest}`), sorted by `count` descending. The 5 envelope-level datapoints are null (this is a reference enumeration). `creation_date` is the API call time.

**Data freshness**
Live aggregate query over the `institutional_publications` table — recomputed on each request. Reflects what's currently in the DB; updated by the publications sync every 6 hours.""",
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
    now = datetime.utcnow()
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
        # The 5 mandatory Brubru v1 datapoints. /publications/sources is a
        # reference enumeration — public_url/body/document_date are null.
        "public_url": None,
        "body_txt": None,
        "body_html": None,
        "document_date": None,
        "creation_date": now.isoformat(),
    }


@router.get(
    "/{publication_id}",
    response_model=PublicationItem,
    summary="Look up one publication by its Brubru-internal UUID",
    description="""**What it does**
Fetches a single publication by its Brubru-internal UUID. Returns the same shape as the list endpoint's `data[i]`.

**When to use it**
After locating a publication via the list endpoint, use this when you want to fetch the full record (including the parsed body HTML/text) for a specific UUID in a deep-link context. For URL-based lookup, prefer the list endpoint's `q` search rather than constructing UUIDs manually.

**Input**
- `publication_id` (path) — Brubru UUID (returned in `id` from the list endpoint).

**Try it**
```
GET /api/v1/publications/<uuid>
```

**You get back**
A single `PublicationItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — synced every 6 hours from 26+ institutional RSS feeds.""",
)
async def get_publication_detail(
    publication_id: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PublicationItem:
    # Defensive: short-circuit if path looks like a known static sibling.
    # Without this, an accidental /publications/sources here would still 404
    # via the route-order fix above; this is belt + braces.
    if publication_id in ("sources",):
        raise HTTPException(status_code=404, detail={
            "error": "Reserved path", "reason_code": "not_found",
            "resource": "publication", "id": publication_id,
        })
    r = (
        db.query(InstitutionalPublication)
        .filter(InstitutionalPublication.id == publication_id)
        .first()
    )
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Publication id {publication_id} not found",
                "reason_code": "not_found",
                "resource": "publication",
                "id": publication_id,
            },
        )
    # Which column holds this table's text is declared once in
    # core/body_sources.py; institutional_publications keeps HTML only, so
    # body_txt is derived from it rather than read from a column.
    _, _html_src = read_body("institutional_publications", r)
    body_html, body_text, has_body = body_from_html_or_text(_html_src, threshold=body_threshold)
    return PublicationItem(
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
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        body=deprecated_body(body_text, body_html),
        public_url=r.url,
        document_date=r.published_date.date() if hasattr(r.published_date, "date") and r.published_date else None,
        creation_date=getattr(r, "fetched_at", None) or getattr(r, "first_seen", None),
    )
