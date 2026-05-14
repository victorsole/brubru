"""
/api/v1/commissioners — Commission College agendas (live).

Thin wrapper over CommissionerAgendaClient. Resolves name accent-insensitively,
scrapes the official Commission calendar, filters by date range.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text as _sql
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commissioners", tags=["v1-commissioners"])


class AgendaItemOut(BaseModel):
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description="Citizen-facing URL on commission.europa.eu for the event detail page.",
    )
    body_txt: Optional[str] = Field(
        None,
        description=(
            "Plain-text body of the event detail page. Typically null for this "
            "endpoint because commission.europa.eu calendar detail URLs "
            "301-redirect to Drupal admin paths (/node/NNNN/edit_en) that "
            "return 403 to anonymous traffic. The title + location are the "
            "richest body-equivalent currently reachable; we publish them as "
            "separate fields rather than synthesising a fake body."
        ),
    )
    body_html: Optional[str] = Field(
        None,
        description=(
            "HTML body of the event detail page. Same upstream limit as "
            "body_text — typically null for this endpoint."
        ),
    )
    meeting_start_date: Optional[date] = Field(
        None,
        description="The event date (same value as the legacy `date` field, surfaced as the canonical meeting_start_date for the uniform v1 datapoint set).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first observed this agenda item (commission_calendar_urls.first_seen_at).",
    )

    # Kept-for-compat fields
    date: date
    title: str
    location: Optional[str] = None
    detail_url: Optional[str] = None  # alias of public_url, kept one release


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
    # 5 mandatory Brubru v1 datapoints. A profile is a reference object (a
    # person), not a document — public_url maps to the bio page; body_txt
    # and body_html stay null (the agenda has its own endpoint); document_date
    # is null (a profile has no publication date); creation_date is the
    # time the API call was served.
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    creation_date: Optional[datetime] = None


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
        public_url=profile.bio_url,
        creation_date=datetime.utcnow(),
    )


@router.get(
    "/{slug}",
    response_model=CommissionerProfileOut,
    summary="Look up one Commissioner profile by slug — bio + portfolio + agenda URLs",
    description="""**What it does**
Profile-only view of one Commission College member. Returns the same shape as a row from `GET /commissioners` — name, portfolio, country, bio URL, plus three working URLs to their meeting agenda (filtered unified-calendar URL, agenda PDF, unified-calendar entry point). Does NOT return the agenda items themselves — for that, call `GET /commissioners/{slug}/agenda`.

**When to use it**
After locating a commissioner via the list endpoint, use this for the profile-only view (no agenda fetch overhead). Useful when embedding a commissioner card without needing the full meeting list.

**Input**
- `slug` (path) — commissioner slug (stable kebab-case form of their name).

**Try it**
```
GET /api/v1/commissioners/von-der-leyen
GET /api/v1/commissioners/ribera
```

**You get back**
A single `CommissionerProfileOut` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Reads from `backend/data/commissioners.json` (hand-curated) + on-demand bio-page hydration (24h client cache). Refreshed on Brubru redeploy after manual JSON updates.""",
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
    # Trigger leader_id discovery so agenda_url can be built. Cached 24h on the
    # client, so subsequent profile reads are free.
    try:
        await client._discover_leader_id(profile)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[v1] leader_id discovery failed for %s: %s", slug, exc)
    return _build_profile_out(profile)


@router.get(
    "/{name}/agenda",
    response_model=PaginatedResponse[AgendaItemOut],
    summary="Calendar events for one Commissioner — meetings, speeches, College sessions",
    description="""**What it does**
Returns the live calendar of meeting events for one Commission College member — meetings with lobbyists / industry / NGOs, public speeches, College sessions, summit attendance. Name resolution is accent-insensitive and accepts the full name, the slug, or known nicknames (e.g. `ribera` → Teresa Ribera).

**When to use it**
For lobbying-transparency work: "who did Ribera meet last month?", "what speeches did the President give in May?", or "show me Hoekstra's upcoming public events". Combined with `/api/v1/meetings`, gives you a full picture of a Commissioner's engagement.

**Input**
- `name` (path) — full name, slug, or nickname (accent-insensitive).
- `date_from`, `date_to` — date filter on agenda items.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v1/commissioners/ribera/agenda?date_from=2026-05-01
GET /api/v1/commissioners/Von der Leyen/agenda
```

**You get back**
A `PaginatedResponse[AgendaItemOut]` envelope. Each item carries the meeting date/time, title, location, type (meeting / speech / college session), and participants where available.

**Data freshness**
Live pull from the Commission's calendar items page (commission.europa.eu/about/organisation/college-commissioners/calendar-items-president-and-commissioners_en), with a 24h client cache per commissioner. Commissioners' agendas are updated by their Cabinet within hours of confirmation.""",
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
        profile, items = await client.fetch_agenda(
            name, date_from=date_from, date_to=date_to, db=db,
        )
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

    # Bulk-fetch the 5 mandatory datapoints from commission_calendar_urls cache
    # in one query rather than N round-trips. NOTE: we no longer filter by
    # leader_id — the RSS persists items under legacy authority codes
    # (0001-0004 for President/VPs/EVPs/Commissioners groups) while per-
    # commissioner profiles now use the new COM_xxxx authority format. The
    # (event_date, title_normalised) pair is unique enough to disambiguate
    # without the leader_id constraint, and dropping it lifts public_url
    # coverage from 5% to whatever the cache has accumulated globally.
    cache_map: dict = {}
    if page_items:
        try:
            rows = db.execute(
                _sql("""
                    SELECT DISTINCT ON (event_date, title_normalised)
                           event_date, title, detail_url, body_text, body_html,
                           first_seen_at
                      FROM commission_calendar_urls
                     WHERE event_date = ANY(:dates)
                  ORDER BY event_date, title_normalised, last_seen_at DESC
                """),
                {
                    "dates": list({it.date for it in page_items}),
                },
            ).fetchall()
            for r in rows:
                cache_map[(r.event_date, (r.title or "").strip().lower())] = r
        except Exception as exc:  # noqa: BLE001
            logger.warning("[v1] commissioner-agenda cache lookup failed: %s", exc)

    data = []
    now_ts = datetime.utcnow()
    for it in page_items:
        key = (it.date, (it.title or "").strip().lower())
        cached = cache_map.get(key)
        public = it.detail_url or (cached.detail_url if cached else None)
        body_text = cached.body_text if cached else None
        body_html = cached.body_html if cached else None
        creation = cached.first_seen_at if cached else now_ts
        data.append(AgendaItemOut(
            public_url=public,
            body_txt=body_text,
            body_html=body_html,
            meeting_start_date=it.date,
            creation_date=creation,
            date=it.date,
            title=it.title,
            location=it.location or None,
            detail_url=public,
        ))

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=date_from,
        published_to=date_to,
    )
