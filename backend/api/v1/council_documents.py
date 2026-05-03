"""
/api/v1/council-documents — Council of the EU document register.

W2 P1 deliverable from Marcadors B.2 (consilium.europa.eu/en/documents/).
Council documents are a critical signal for trilogue + Council position tracking.

Implementation note: this endpoint UNIONs three sources today:
  1) institutional_publications rows whose institution_slug matches Council
  2) eu_calendar_events with institution in (COUNCIL, EUROPEAN_COUNCIL)
     (Council meetings are first-class "Council documents" via their agendas)

A dedicated council_documents table with COREPER + working-party + Council
configuration linkage is queued for week 4. Until then this surface returns
the Council data we already have ingested.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_calendar import EUCalendarEvent, InstitutionEnum
from models.institutional_publication import InstitutionalPublication
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/council-documents", tags=["v1-council-documents"])


COUNCIL_INSTITUTION_SLUGS = (
    "council_of_the_eu",
    "european_council",
    "consilium",
    "council",
)


class CouncilDocumentItem(BaseModel):
    id: str
    source: str  # "publication" | "calendar_event"
    document_type: Optional[str] = None
    council_configuration: Optional[str] = None  # only for calendar events
    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    language: str = "en"
    published_date: Optional[datetime] = None
    policy_areas: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    # Per-meeting auxiliary URLs on consilium.europa.eu's public register.
    # Surfaced for every calendar_event row so consumers can navigate to the
    # provisional agenda (OJ Council) and the votes register without having
    # to know the URL patterns themselves. Programmatic ingestion of those
    # pages is blocked by Cloudflare's bot challenge — these are display-only
    # links for the human audience.
    oj_register_url: Optional[str] = None
    votes_register_url: Optional[str] = None
    calendar_filter_url: Optional[str] = None


_CONFIG_TO_SLUG = {
    "GAC": "gac",
    "FAC": "fac",
    "ECOFIN": "ecofin",
    "EUROGROUP": "eurogroup",
    "JHA": "jha",
    "EPSCO": "epsco",
    "COMPET": "compet",
    "TTE": "tte",
    "EDUC": "eycs",
    "EYCS": "eycs",
    "AGRIFISH": "agrifish",
    "ENV": "env",
    "ENVI": "env",
}

# Council Public Register entity IDs — provided by consilium.europa.eu's own
# calendar filter. These let us deep-link to the council-formation-specific
# calendar view, which shows past meetings + agendas + outcomes.
_CONFIG_TO_ENTITY_ID = {
    "GAC": "122475",
    "FAC": "122484",
    "ECOFIN": "122485",
    "JHA": "122493",
    "EPSCO": "122501",
    "COMPET": "122504",
    "TTE": "122512",
    "EYCS": "122516",
    "EDUC": "122516",
    "AGRIFISH": "122589",
    "ENV": "122518",
    "ENVI": "122518",
    "EUROGROUP": "122523",
}
# Top-level entities
_INSTITUTION_ENTITY_ID = {
    "EUROPEAN_COUNCIL": "122152",
    # Council of the EU "ministerial" filter — useful for ministerial-level meetings
    "COUNCIL": "122158",
}

OJ_COUNCIL_REGISTER = "https://www.consilium.europa.eu/en/documents/public-register/oj-council/"
VOTES_REGISTER = "https://www.consilium.europa.eu/en/documents/public-register/votes/"


def _calendar_filter_url(institution: str, council_configuration: Optional[str]) -> str:
    """Deep-link to the consilium calendar filtered to this entity/formation."""
    base = "https://www.consilium.europa.eu/en/meetings/calendar/?daterange=past"
    if institution == "EUROPEAN_COUNCIL" and "EUROPEAN_COUNCIL" in _INSTITUTION_ENTITY_ID:
        return f"{base}&Entity={_INSTITUTION_ENTITY_ID['EUROPEAN_COUNCIL']}"
    eid = _CONFIG_TO_ENTITY_ID.get(council_configuration or "")
    if eid:
        return f"{base}&CouncilConfiguration={eid}"
    return base


def _derive_consilium_url(
    institution: str,
    council_configuration: Optional[str],
    start_date: Optional[date],
    fallback: Optional[str],
) -> Optional[str]:
    """Construct the per-meeting URL on consilium.europa.eu.

    The Council exposes meetings at predictable URLs:
        /en/meetings/{configuration_slug}/{YYYY}/{MM}/{DD}/
    For European Council (heads of state):
        /en/meetings/european-council/{YYYY}/{MM}/{DD}/

    The scraper stores `source_url` as the generic `/en/meetings/calendar/`
    when it can't resolve the specific page, which is unhelpful. This helper
    builds the canonical per-meeting URL when we have enough info; falls
    back to the stored URL otherwise.
    """
    if not start_date:
        return fallback
    y, m, d = start_date.year, start_date.month, start_date.day
    slug = None
    if institution == "EUROPEAN_COUNCIL":
        slug = "european-council"
    elif council_configuration:
        slug = _CONFIG_TO_SLUG.get(council_configuration)
    if not slug:
        return fallback
    return f"https://www.consilium.europa.eu/en/meetings/{slug}/{y:04d}/{m:02d}/{d:02d}/"


@router.get(
    "",
    response_model=PaginatedResponse[CouncilDocumentItem],
    summary="Council of the EU document register",
    description=(
        "Council of the EU + European Council documents and meetings. "
        "Today the surface unions institutional_publications (council-tagged) "
        "with eu_calendar_events for COUNCIL / EUROPEAN_COUNCIL. A dedicated "
        "Council document register scraper (working-party + COREPER docs + "
        "Council conclusions full text) is queued for week 4."
    ),
)
async def list_council_documents(
    request: Request,
    q: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None, description="press_release | conclusions | meeting_agenda | ..."),
    policy_area: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilDocumentItem]:
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    # Branch 1: institutional_publications filtered to Council sources
    pub_q = db.query(InstitutionalPublication).filter(
        or_(*[
            InstitutionalPublication.institution_slug.ilike(f"%{slug}%")
            for slug in COUNCIL_INSTITUTION_SLUGS
        ])
    )
    pub_filters = []
    if document_type:
        pub_filters.append(InstitutionalPublication.category == document_type)
    if policy_area:
        pub_filters.append(InstitutionalPublication.policy_areas.any(policy_area))
    if published_from:
        pub_filters.append(InstitutionalPublication.published_date >= published_from)
    if published_to:
        pub_filters.append(InstitutionalPublication.published_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        pub_filters.append(InstitutionalPublication.fetched_at >= updated_from)
    if updated_to:
        pub_filters.append(InstitutionalPublication.fetched_at <= updated_to)
    if q:
        like = f"%{q}%"
        pub_filters.append(or_(
            InstitutionalPublication.title.ilike(like),
            InstitutionalPublication.summary.ilike(like),
        ))
    if pub_filters:
        pub_q = pub_q.filter(and_(*pub_filters))

    # Branch 2: eu_calendar_events for Council meetings (= meeting_agenda docs)
    cal_q = db.query(EUCalendarEvent).filter(
        EUCalendarEvent.institution.in_([InstitutionEnum.COUNCIL, InstitutionEnum.EUROPEAN_COUNCIL])
    )
    if published_from:
        cal_q = cal_q.filter(EUCalendarEvent.start_date >= published_from)
    if published_to:
        cal_q = cal_q.filter(EUCalendarEvent.start_date <= published_to)
    if updated_from:
        cal_q = cal_q.filter(EUCalendarEvent.last_updated >= updated_from)
    if updated_to:
        cal_q = cal_q.filter(EUCalendarEvent.last_updated <= updated_to)
    if q:
        cal_q = cal_q.filter(EUCalendarEvent.title.ilike(f"%{q}%"))
    if document_type and document_type != "meeting_agenda":
        # if filter is not meeting_agenda, exclude calendar events
        cal_q = cal_q.filter(False)

    pub_total = pub_q.count()
    cal_total = cal_q.count()
    total = pub_total + cal_total

    pub_rows = pub_q.order_by(InstitutionalPublication.published_date.desc().nullslast()).limit(limit).all()
    cal_rows = cal_q.order_by(EUCalendarEvent.start_date.desc()).limit(limit).all()

    data: list = []
    for r in pub_rows:
        data.append(CouncilDocumentItem(
            id=str(r.id),
            source="publication",
            document_type=r.category,
            title=r.title,
            summary=r.summary,
            url=r.url,
            language=r.language or "en",
            published_date=r.published_date,
            policy_areas=list(r.policy_areas or []),
            tags=list(r.tags or []),
        ))
    for r in cal_rows:
        institution = getattr(r.institution, "value", str(r.institution or ""))
        # Prefer the specific per-meeting URL on consilium.europa.eu; fall
        # back to whatever the scraper stored. The generic /en/meetings/calendar/
        # URL is unhelpful — build the canonical per-meeting page instead.
        url = r.agenda_url or _derive_consilium_url(
            institution,
            r.council_configuration,
            r.start_date,
            r.source_url,
        )
        data.append(CouncilDocumentItem(
            id=str(r.id),
            source="calendar_event",
            document_type="meeting_agenda",
            council_configuration=r.council_configuration,
            title=r.title,
            summary=r.description,
            url=url,
            published_date=datetime.combine(r.start_date, datetime.min.time()) if r.start_date else None,
            policy_areas=list(r.policy_areas or []),
            oj_register_url=OJ_COUNCIL_REGISTER,
            votes_register_url=VOTES_REGISTER,
            calendar_filter_url=_calendar_filter_url(institution, r.council_configuration),
        ))

    # Sort union by published_date desc
    data.sort(key=lambda x: x.published_date or datetime.min, reverse=True)
    # Apply page slice
    page_data = data[(page - 1) * limit : page * limit]

    return build_envelope(
        page_data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )
