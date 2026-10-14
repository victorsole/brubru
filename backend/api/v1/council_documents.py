"""
/api/v1/council-documents — Council of the EU documents.

Two sources:
  1) institutional_publications rows of the Council: register documents found by
     reference on data.consilium (scripts/discover_council_documents.py, three times a
     day) and press releases from the Council's RSS feed
     (scripts/sync_council_press_releases.py, every three hours);
  2) with source=meetings or all, eu_calendar_events for COUNCIL / EUROPEAN_COUNCIL.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from api.v1._date_bounds import UpperBoundDatetime
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_calendar import EUCalendarEvent, InstitutionEnum
from models.institutional_publication import InstitutionalPublication
from models.user import User

import html as _html

from ._body import _strip_html_to_text
from ._row_dates import row_updated
from ._deps import api_user_with_rate_limit
from ._body import body_from_html_or_text
from core.body_sources import read_body
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


# Bounds of the ACTUAL corpus, both branches, computed per request. Cheap (two
# indexed min/max) and always true, unlike a hardcoded date that rots silently.
_COVERAGE_SQL = text("""
    SELECT least(p.lo, c.lo) AS lo, greatest(p.hi, c.hi) AS hi
    FROM (SELECT min(published_date) lo, max(published_date) hi
            FROM institutional_publications
           WHERE institution_slug ILIKE '%council%') p,
         (SELECT min(start_date) lo, max(start_date) hi
            FROM eu_calendar_events
           WHERE institution IN ('COUNCIL', 'EUROPEAN_COUNCIL')) c
""")

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
    body_txt: Optional[str] = Field(None, description="The whole text of the document, as plain text. The summary only when no text is held.")
    body_html: Optional[str] = Field(None, description="The same whole text as HTML, one paragraph per block.")
    meeting_start_date: Optional[date] = Field(None, description="For calendar_event rows: meeting date.")
    document_date: Optional[date] = Field(None, description="For publication rows: publication date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


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
    """Body for an institutional-publication row: the whole stored text, in both forms.

    The summary is only the fallback for a row that holds no text. Until 14 October
    2026 it came first, and for Council register documents the summary is the text's
    first 900 characters, so `body_txt` stopped at 900 characters on 524 of 615
    documents while `body_html` carried the whole document."""
    # Column name comes from core/body_sources.py, not from here.
    _, _html_src = read_body("institutional_publications", r)
    html_c = (_html_src or "").strip() or None
    summ = (getattr(r, "summary", None) or "").strip() or None
    if html_c:
        # html_content holds PLAIN TEXT on all 248 Council documents, so passing
        # it through as body_html told clients prose was markup. Compose real
        # markup from it instead; genuine HTML still passes through untouched.
        composed_html, text_form, _ = body_from_html_or_text(html_c)
        return (text_form or summ or None), composed_html
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
        creation_date=r.created_at,
        updated_date=row_updated(r),
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
        updated_date=row_updated(r),
    )


@router.get(
    "",
    response_model=PaginatedResponse[CouncilDocumentItem],
    summary="Council of the EU documents: the public register and press releases (meetings on request)",
    description="""**What it does**
Returns Council of the EU documents: the documents of the Council's public register (CM meeting notices and provisional agendas of the Council's working parties, ST standard documents, WK working documents, with their revisions, addenda and corrigenda) and the Council's press releases. With `source=meetings` it returns Council and European Council meetings from the calendar instead; `source=all` returns both.

**What the corpus covers, and what it does not**
- Register documents: every document data.consilium.europa.eu serves by its reference, from 15 July 2024 (the start of the 10th Parliament) onwards, plus about 130 older ones. A document the Council has not released is not served there and is not here. Each carries its whole text, read from the PDF, and the date printed on it.
- Press releases: read from the Council's RSS feed since 14 October 2026, plus 57 read between 14 August and 28 September 2026; releases published between 29 September and 8 October 2026 are not held. A release carries its title, date, topic and the feed's one-paragraph summary: the full text sits behind a browser check on the Council's website, which Brubru does not get past, so `body_txt` is that summary.
- Read `coverage_note`, `coverage_from` and `coverage_to` before concluding that an empty result means the Council said nothing.

**When to use it**
For tracking Council positions on legislative files (the "other half" of EP-Council co-decision), the agendas and outcomes of Council and Coreper meetings, working-party work in progress, and what the Council announces. The register shows a file moving weeks before a press release does.

**Input**
- `source` — `documents` (default): register documents and press releases. `meetings`: Council and European Council meetings from the calendar. `all`: both.
- `q` — words searched in the title, the summary and the whole text.
- `document_type` — `document` (a register document) or `press_release`; `meeting_agenda` with `source=meetings`.
- `policy_area` — the register's subject code printed on a document read before 28 September 2026 (for example `AGRI`, `ENER`), or a press release's topic (for example `Social policy`). Most register documents carry none: search with `q`.
- `published_from`, `published_to` (and `published_end` alias) — the document's own date.
- `updated_from`, `updated_to` (and `updated_end` alias) — when the row's content last changed in Brubru, which each item carries as `updated_date`: use them for incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/council-documents?q=conclusions&published_from=2026-01-01
GET /api/v1/council-documents?document_type=press_release
GET /api/v1/council-documents?q=minors
GET /api/v1/council-documents?source=meetings
```

**You get back**
A `PaginatedResponse[CouncilDocumentItem]` envelope. Each item carries `id`, `self`, `title`, `document_type`, `url` and `public_url` (the PDF on data.consilium for a register document, the release page for a press release), `document_date` (the date printed on the document), the whole text in `body_txt` and `body_html`, `creation_date` (when Brubru first stored it) and `updated_date` (when its content last changed).

**Data freshness**
Register documents three times a day (about 07:00, 13:00 and 19:00 UTC): each run asks for the new reference numbers and again for those of the last three weeks, so a document released late is found within a day. Press releases every three hours from the RSS feed. Meetings with the calendar sync.""",
)
async def list_council_documents(
    request: Request,
    q: Optional[str] = Query(None),
    source: str = Query("documents", pattern="^(documents|meetings|all)$",
                        description="documents (default): the register and press corpus. "
                                    "meetings: Council meetings from the calendar. "
                                    "all: both, as this endpoint used to return by default."),
    document_type: Optional[str] = Query(None, description="press_release | conclusions | meeting_agenda | ..."),
    policy_area: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[UpperBoundDatetime] = Query(None),
    updated_end: Optional[UpperBoundDatetime] = Query(None),
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
    # Why `documents` is the default (24 Sep 2026): the union is ordered by date and
    # Council MEETINGS are future-dated, so an endpoint called council-documents opened
    # with next month's summits and the register documents began below them. It read as
    # a calendar. Meetings are still here, on request, and `all` restores the old answer.
    want_pubs = source in ("documents", "all")
    want_cal = source in ("meetings", "all")

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
    # updated_at, the change signal of migration 290, which is what each item serves as
    # updated_date. Until 14 Oct 2026 this filtered on fetched_at, which every upsert
    # moves and no item showed: 672 of 672 items carried updated_date null.
    if updated_from:
        pub_filters.append(InstitutionalPublication.updated_at >= updated_from)
    if updated_to:
        pub_filters.append(InstitutionalPublication.updated_at <= updated_to)
    if q:
        like = f"%{q}%"
        # Search the BODY as well as the title. Council register subject lines are
        # bureaucratic ("ANNEX to the COUNCIL IMPLEMENTING DECISION amending ..."),
        # so the documents that actually discuss a topic frequently do not name it
        # in their title. Title-only matching is how a populated corpus can still
        # answer "nothing" to a real question.
        pub_filters.append(or_(
            InstitutionalPublication.title.ilike(like),
            InstitutionalPublication.summary.ilike(like),
            InstitutionalPublication.html_content.ilike(like),
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

    # A branch the caller did not ask for contributes nothing, to the count as well as
    # to the rows: a `total` that counts meetings while the page holds only documents is
    # the kind of number that sends a client paging for rows that are not there.
    pub_total = pub_q.count() if want_pubs else 0
    cal_total = cal_q.count() if want_cal else 0
    total = pub_total + cal_total

    # Take page*limit from EACH branch, not `limit`. The union is merged and
    # sorted in Python, so the slice below can only see what was fetched: with
    # `.limit(limit)` the merged list held at most 2*limit rows and every page
    # from 3 onwards came back EMPTY while `total` still advertised more.
    # Found 27 Aug 2026 while filling branch 1 (D1).
    depth = page * limit
    pub_rows = (pub_q.order_by(InstitutionalPublication.published_date.desc().nullslast())
                .limit(depth).all()) if want_pubs else []
    cal_rows = (cal_q.order_by(EUCalendarEvent.start_date.desc())
                .limit(depth).all()) if want_cal else []

    data: list = [_pub_to_item(r) for r in pub_rows]
    data.extend(_cal_to_item(r) for r in cal_rows)

    # Sort the union by published_date desc.
    #
    # The key must normalise tzinfo. `institutional_publications.published_date`
    # is timestamptz (AWARE) while calendar rows and the `datetime.min` fallback
    # are NAIVE, and Python refuses to compare the two. This raised a TypeError
    # the moment branch 1 stopped being empty on 27 Aug 2026 -- so the endpoint
    # could never have worked with real documents in it, and nobody could tell
    # while it was serving only meetings.
    _FLOOR = datetime.min.replace(tzinfo=timezone.utc)

    def _sort_key(item):
        d = item.published_date
        if d is None:
            return _FLOOR
        return d if d.tzinfo is not None else d.replace(tzinfo=timezone.utc)

    data.sort(key=_sort_key, reverse=True)
    # Apply page slice
    page_data = data[(page - 1) * limit : page * limit]

    # State what the corpus IS, so an empty result is readable. Until 27 Aug 2026
    # branch 1 held zero rows and this endpoint returned only Council MEETINGS,
    # so `?q=minors` came back empty and read as "the Council has said nothing"
    # -- while 25 Member States had signed the Jutland Declaration on minors
    # online. The corpus is now real but still a SLICE: the Council register is
    # queryable, not enumerable (a date-only search returns nothing and there is
    # no listing API), so documents are pulled per policy term.
    cov = db.execute(_COVERAGE_SQL).fetchone()
    coverage_note = (
        "Council register documents (CM, ST, WK, with revisions, addenda and corrigenda) "
        "as data.consilium serves them by reference, from 15 July 2024, each with its "
        "whole text; Council press releases from the Council's RSS feed since 14 October "
        "2026 (title, date, topic and summary: the full text is behind a browser check), "
        "plus 57 from 14 August to 28 September 2026; Council and European Council "
        "meetings with source=meetings or all. A document the Council has not released "
        "is not here. An empty result means nothing matched THIS corpus, not that the "
        "Council was silent."
    )

    return build_envelope(
        page_data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        coverage_from=(cov.lo.date() if cov and cov.lo else None),
        coverage_to=(cov.hi.date() if cov and cov.hi else None),
        coverage_note=coverage_note,
        op_core_title="Council of the EU documents",
        op_core_type="Council document",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/{doc_id}",
    response_model=CouncilDocumentItem,
    summary="One Council document or meeting by id — full body (text + HTML)",
    description="""**What it does**
Fetches a single Council of the EU item by its Brubru-internal UUID: a register document, a press release, or a Council / European Council meeting from the calendar. Returns the same shape as the list endpoint: `public_url`, `body_txt`, `body_html`, `document_date`, `creation_date`, `updated_date`.

**When to use it**
After locating an item via the list endpoint, use this to fetch the full record. A register document carries its whole text; a press release the feed's summary; a meeting a body composed from the meeting facts (configuration, date, the legislative files on the agenda).

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
    pub = db.query(InstitutionalPublication).filter(
        InstitutionalPublication.id == doc_id,
        # Only a Council publication: the table holds every institution's, and until 14 Oct
        # 2026 this route answered an ECB or EMA publication's id as a Council document.
        or_(*[InstitutionalPublication.institution_slug.ilike(f"%{slug}%") for slug in COUNCIL_INSTITUTION_SLUGS]),
    ).first()
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
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


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
