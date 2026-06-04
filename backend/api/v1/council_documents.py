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

import html as _html

from ._body import _strip_html_to_text
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/council-documents", tags=["v1-council-documents"])
configurations_router = APIRouter(prefix="/council-configurations", tags=["v1-council-configurations"])

# Official names of the 10 Council configurations (+ Eurogroup, an informal
# body, and the legacy EDUC/ENV aliases the calendar uses). Stable, factual.
CONFIG_NAMES = {
    "GAC": "General Affairs Council",
    "FAC": "Foreign Affairs Council",
    "ECOFIN": "Economic and Financial Affairs Council",
    "JHA": "Justice and Home Affairs Council",
    "EPSCO": "Employment, Social Policy, Health and Consumer Affairs Council",
    "COMPET": "Competitiveness Council",
    "TTE": "Transport, Telecommunications and Energy Council",
    "AGRIFISH": "Agriculture and Fisheries Council",
    "ENVI": "Environment Council",
    "ENV": "Environment Council",
    "EYCS": "Education, Youth, Culture and Sport Council",
    "EDUC": "Education, Youth, Culture and Sport Council",
    "EUROGROUP": "Eurogroup",
}


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
    oj_register_url: Optional[str] = None
    votes_register_url: Optional[str] = None
    calendar_filter_url: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of `url`).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — the document summary when present.")
    body_html: Optional[str] = Field(None, description="Null — Council documents are PDF/external links.")
    meeting_start_date: Optional[date] = Field(None, description="For calendar_event rows: meeting date.")
    document_date: Optional[date] = Field(None, description="For publication rows: publication date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


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


def _pub_body(r) -> tuple:
    """Body for an institutional-publication row. body_html prefers the stored
    html_content; body_txt is the summary or the stripped HTML. Never drops
    real content (the old endpoint hard-coded body_html=None)."""
    html_c = (getattr(r, "html_content", None) or "").strip() or None
    summ = (getattr(r, "summary", None) or "").strip() or None
    if html_c:
        return (summ or _strip_html_to_text(html_c) or None), html_c
    if summ:
        return summ, f"<article><p>{_html.escape(summ)}</p></article>"
    return None, None


def _compose_event_body(title, configuration, start_date, description, procedure_refs) -> tuple:
    """Compose (body_txt, body_html) for a Council meeting from the real
    structured facts we hold. Title always exists, so both fields are always
    populated — nothing is invented, only structured."""
    cfg_name = CONFIG_NAMES.get(configuration or "", configuration)
    desc = (description or "").strip() or None
    refs = [r for r in (procedure_refs or []) if r]
    date_str = start_date.isoformat() if start_date else None

    txt = [title]
    if cfg_name:
        txt.append(f"Council configuration: {cfg_name}")
    if date_str:
        txt.append(f"Meeting date: {date_str}")
    if desc:
        txt.append(desc)
    if refs:
        txt.append("Legislative files on the agenda:")
        txt.extend(f"- {r}" for r in refs)
    body_txt = "\n".join(txt)

    parts = [f"<h2>{_html.escape(title)}</h2>"]
    meta = []
    if cfg_name:
        meta.append(f"<li><strong>Configuration:</strong> {_html.escape(cfg_name)}</li>")
    if date_str:
        meta.append(f"<li><strong>Meeting date:</strong> {_html.escape(date_str)}</li>")
    if meta:
        parts.append("<ul>" + "".join(meta) + "</ul>")
    if desc:
        parts.append(f"<p>{_html.escape(desc)}</p>")
    if refs:
        parts.append(
            "<h3>Legislative files on the agenda</h3><ul>"
            + "".join(f"<li>{_html.escape(r)}</li>" for r in refs)
            + "</ul>"
        )
    body_html = "<article>" + "".join(parts) + "</article>"
    return body_txt, body_html


def _pub_to_item(r) -> CouncilDocumentItem:
    pub_date = r.published_date.date() if r.published_date and hasattr(r.published_date, "date") else r.published_date
    body_txt, body_html = _pub_body(r)
    return CouncilDocumentItem(
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
        public_url=r.url,
        body_txt=body_txt,
        body_html=body_html,
        document_date=pub_date,
        creation_date=getattr(r, "first_seen", None) or getattr(r, "fetched_at", None) or getattr(r, "created_at", None),
    )


def _cal_to_item(r) -> CouncilDocumentItem:
    institution = getattr(r.institution, "value", str(r.institution or ""))
    url = r.agenda_url or _derive_consilium_url(institution, r.council_configuration, r.start_date, r.source_url)
    body_txt, body_html = _compose_event_body(
        r.title, r.council_configuration, r.start_date, r.description, list(r.procedure_refs or [])
    )
    return CouncilDocumentItem(
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
        public_url=url,
        body_txt=body_txt,
        body_html=body_html,
        meeting_start_date=r.start_date,
        document_date=r.start_date,
        creation_date=getattr(r, "first_seen", None) or getattr(r, "created_at", None),
    )


@router.get(
    "",
    response_model=PaginatedResponse[CouncilDocumentItem],
    summary="Council of the EU documents — press releases, conclusions, meeting agendas, summits",
    description="""**What it does**
Returns a unified feed of Council of the EU + European Council documents and meetings — press releases, Council conclusions, meeting agendas, summit outcomes. Today the surface unions `institutional_publications` (Council-tagged rows) with `eu_calendar_events` for COUNCIL / EUROPEAN_COUNCIL events. A dedicated Council document register scraper (working-party + COREPER docs + Council conclusions full text) is queued.

**When to use it**
For tracking Council positions on legislative files (the "other half" of EP-Council co-decision), summit conclusions (the political guidance feeding into Commission proposals), and ministerial meetings. The Council moves more slowly than the EP but its political conclusions are the most authoritative signal of where EU policy is heading.

**Input**
- `q` — substring search.
- `document_type` — `press_release` / `conclusions` / `meeting_agenda` / etc.
- `policy_area` — single policy area tag.
- `published_from`, `published_to` (and `published_end` alias).
- `updated_from`, `updated_to` (and `updated_end` alias) — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/council-documents?document_type=conclusions&published_from=2026-01-01
GET /api/v1/council-documents?policy_area=energy
```

**You get back**
A `PaginatedResponse[CouncilDocumentItem]` envelope. Each item carries reference, title, document_type, policy_area, dates, source URL, and the 5 envelope-level datapoints.

**Data freshness**
Synced every 12 hours (02:00 / 14:00 UTC, warm tier) for now — will move to dedicated 6h scraper once the Council document register scraper ships. Meanwhile, this surface unions data from the publications sync (every 6h) and the calendar sync (every 6h).""",
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

    data: list = [_pub_to_item(r) for r in pub_rows]
    data.extend(_cal_to_item(r) for r in cal_rows)

    # Sort union by published_date desc
    data.sort(key=lambda x: x.published_date or datetime.min, reverse=True)
    # Apply page slice
    page_data = data[(page - 1) * limit : page * limit]

    return build_envelope(
        page_data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        op_core_title="Council of the EU documents",
        op_core_type="Council document",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/{doc_id}",
    response_model=CouncilDocumentItem,
    summary="One Council document or meeting by id — full body (text + HTML)",
    description="""**What it does**
Fetches a single Council of the EU item by its Brubru-internal UUID — either a Council institutional publication (press release, conclusions) or a Council / European Council meeting from the calendar. Returns the same shape as the list endpoint with the 5 datapoints filled: `public_url`, `body_txt`, `body_html`, `document_date`, `creation_date`.

**When to use it**
After locating an item via the list endpoint, use this to fetch the full record. For publications the body is the stored HTML content (or summary); for meetings the body is composed from the meeting facts (configuration, date, the legislative files on the agenda).

**Input**
- `doc_id` (path) — the Brubru-internal UUID from the list endpoint's `id`.

**Try it**
```
GET /api/v1/council-documents/{doc_id}
```

**You get back**
A single `CouncilDocumentItem`, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same sources as the list endpoint (publications sync + calendar sync).""",
)
async def get_council_document_detail(
    doc_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilDocumentItem:
    pub = db.query(InstitutionalPublication).filter(InstitutionalPublication.id == doc_id).first()
    if pub is not None:
        return _pub_to_item(pub)
    event = (
        db.query(EUCalendarEvent)
        .filter(
            EUCalendarEvent.id == doc_id,
            EUCalendarEvent.institution.in_([InstitutionEnum.COUNCIL, InstitutionEnum.EUROPEAN_COUNCIL]),
        )
        .first()
    )
    if event is not None:
        return _cal_to_item(event)
    raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No Council document with id {doc_id}"})


# --------------------------------------------------------------------------- #
# Council configurations (reference)                                          #
# --------------------------------------------------------------------------- #
# Canonical 10 Council configurations + the informal Eurogroup. Codes/slugs/
# entity ids reuse the maps the documents endpoint already maintains.
_CANONICAL_CONFIGS = ["GAC", "FAC", "ECOFIN", "JHA", "EPSCO", "COMPET", "TTE", "AGRIFISH", "ENVI", "EYCS", "EUROGROUP"]


class CouncilConfigurationItem(BaseModel):
    code: str
    name: str
    slug: Optional[str] = None
    register_entity_id: Optional[str] = None
    consilium_url: Optional[str] = None
    calendar_filter_url: Optional[str] = None
    informal: bool = False
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="The consilium 'council-meetings-explained' page for this configuration.")
    body_txt: Optional[str] = Field(None, description="Plain-text description of the configuration.")
    body_html: Optional[str] = Field(None, description="HTML description of the configuration.")
    document_date: Optional[date] = Field(None, description="Null — a configuration is reference data, not a dated document.")
    creation_date: Optional[datetime] = Field(None, description="When this response was generated (server time).")


@configurations_router.get(
    "",
    response_model=PaginatedResponse[CouncilConfigurationItem],
    summary="Council of the EU configurations — the 10 ministerial formations (+ Eurogroup)",
    description="""**What it does**
Returns the ten configurations the Council of the EU meets in (General Affairs, Foreign Affairs, ECOFIN, Justice and Home Affairs, EPSCO, Competitiveness, Transport/Telecommunications/Energy, Agriculture and Fisheries, Environment, Education/Youth/Culture/Sport) plus the informal Eurogroup. For each: the official name, the URL-slug, the consilium public-register entity id, the "council-meetings-explained" page, and a deep-link to the calendar filtered to that formation.

**When to use it**
As a reference list to drive a configuration picker, to resolve a configuration code to its full name, or to get the canonical consilium URLs for a formation. Pair with `/api/v1/council-documents?` (meetings are tagged with `council_configuration`).

**Input**
No parameters.

**Try it**
```
GET /api/v1/council-configurations
```

**You get back**
A `PaginatedResponse[CouncilConfigurationItem]` with one row per configuration: `code`, `name`, `slug`, `register_entity_id`, `consilium_url`, `calendar_filter_url`, `informal`, plus the 5 envelope datapoints (`public_url` = the consilium page, `body_txt`/`body_html` = the description, `document_date` = null, `creation_date` = server time).

**Data freshness**
Static reference data — the Council configurations are fixed by the Council's Rules of Procedure.""",
)
async def list_council_configurations(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CouncilConfigurationItem]:
    now = datetime.utcnow()
    items: list = []
    for code in _CANONICAL_CONFIGS:
        name = CONFIG_NAMES.get(code, code)
        slug = _CONFIG_TO_SLUG.get(code)
        entity_id = _CONFIG_TO_ENTITY_ID.get(code)
        consilium_url = (
            f"https://www.consilium.europa.eu/en/council-eu/council-meetings-explained/{slug}/"
            if slug else None
        )
        informal = code == "EUROGROUP"
        body_txt = f"{name} ({code}) is {'an informal body of euro-area finance ministers' if informal else 'a configuration of the Council of the EU'}."
        body_html = f"<article><p>{_html.escape(name)} (<strong>{_html.escape(code)}</strong>) is {'an informal body of euro-area finance ministers' if informal else 'a configuration of the Council of the EU'}.</p></article>"
        cal_url = _calendar_filter_url("EUROGROUP" if informal else "COUNCIL", code)
        items.append(CouncilConfigurationItem(
            code=code,
            name=name,
            slug=slug,
            register_entity_id=entity_id,
            consilium_url=consilium_url,
            calendar_filter_url=cal_url,
            informal=informal,
            public_url=consilium_url,
            body_txt=body_txt,
            body_html=body_html,
            document_date=None,
            creation_date=now,
        ))
    return build_envelope(
        items, total=len(items), page=1, limit=len(items),
        op_core_title="Council of the EU configurations",
        op_core_type="Council configuration",
        op_core_identifier=str(request.url),
    )
