"""
/api/v1/procedures — EU legislative procedures (legislative_carriages).

Each carriage represents one file moving through the ordinary legislative
procedure (Commission proposal -> EP/Council -> adoption). Filters by OEIL
procedure reference, status, committee, last-update date range.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from api.v1._date_bounds import UpperBoundDatetime
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.legislative_train import CarriageSourceEnum, LegislativeCarriage
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope
from core.identifiers import resolve_row
from ._curated_procedures import BrubruCuration, get_curation
from api.v1._pagination import stable
from ._row_dates import row_updated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/procedures", tags=["v1-procedures"])


class ProcedureItem(BaseModel):
    """LIST-shaped procedure row.

    Maintains LIST/DETAIL field parity with `ProcedureDetail` so partners (e.g.
    GovClipping) can iterate over the LIST without round-tripping to DETAIL just
    to read `description`, `oeil_key_events`, `ai_summary`, etc. The two models
    expose identical field names; values may be set or null per row.
    """
    id: str
    file_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    oeil_procedure_ref: Optional[str] = None

    current_status: Optional[str] = None
    stage: Optional[str] = Field(
        None,
        description=(
            "OEIL's own 'Stage reached in procedure', word for word (e.g. 'Awaiting committee "
            "decision', 'Procedure completed', 'Procedure lapsed or withdrawn'). `current_status` "
            "is Brubru's grouping of the same; when they seem to disagree, this is the authority."
        ),
    )
    is_blocked: bool = False
    days_in_current_status: Optional[int] = None
    text_type: Optional[str] = None

    lead_committee: Optional[str] = None
    opinion_committees: list = Field(default_factory=list)
    committees: list = Field(default_factory=list)
    rapporteur_mep_id: Optional[str] = None

    celex_numbers: list = Field(default_factory=list)
    eprs_briefing_ids: list = Field(default_factory=list)
    eprs_matched_briefings: list = Field(default_factory=list)
    policy_areas: list = Field(
        default_factory=list,
        description=(
            "The procedure's subjects as OEIL classifies it, code and label word for word "
            "(e.g. '3.70.03 Climate policy, climate change, ozone layer'), read from its "
            "procedure file. Empty for the non-OEIL rows that include_other_sources adds."
        ),
    )
    related_themes: list = Field(default_factory=list)
    spotlight_tags: list = Field(default_factory=list)
    ec_priority_ids: list = Field(default_factory=list)

    timeline: list = Field(default_factory=list)
    status_history: list = Field(default_factory=list)
    oeil_timeline: list = Field(default_factory=list)
    oeil_key_events: list = Field(default_factory=list)
    eurlex_documents: list = Field(default_factory=list)

    ai_summary: Optional[str] = None
    ai_entities: list = Field(default_factory=list)
    ai_policy_classifications: list = Field(default_factory=list)

    legal_text_url: Optional[str] = None
    url: Optional[str] = None
    # Aggregated procedure tracker on law-tracker.europa.eu — combines OEIL,
    # EUR-Lex and Commission events on a single page. Pattern:
    # https://law-tracker.europa.eu/procedure/{YYYY}_{NNN}?lang=en
    law_tracker_url: Optional[str] = None

    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    expected_completion: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    enrichment_quality: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints. A procedure is an OEIL file —
    # public_url is the OEIL procedure-file page; body_txt/html surface the
    # cached OEIL body (same source as /committees/{code}/work-items uses);
    # document_date is the most recent OEIL key-event date; creation_date
    # is when Brubru first ingested the carriage row.
    public_url: Optional[str] = Field(None, description="OEIL procedure-file URL — citizen-facing canonical page for the procedure.")
    body_txt: Optional[str] = Field(None, description="Plain-text of the OEIL procedure-file page (description + key events).")
    body_html: Optional[str] = Field(None, description="HTML of the OEIL procedure-file page.")
    document_date: Optional[date] = Field(None, description="Date of the latest OEIL key event.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this carriage (alias of first_seen).")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


def _oeil_url(oeil_ref: Optional[str]) -> Optional[str]:
    if not oeil_ref:
        return None
    return f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={oeil_ref}"


# EUR-Lex's canonical, language-explicit document address. The carriage rows store
# "https://eur-lex.europa.eu/./legal-content/AUTO/?uri=CELEX:..." instead, which carries
# a stray "/./" and uses AUTO: opened in a browser that renders no extractable document,
# so it was never a usable public_url even though it returns a response.
_EURLEX_DOC = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _public_url(r) -> Optional[str]:
    """The citizen-facing page for a carriage, whichever register it came from.

    legislative_carriages holds three populations and only one of them is an OEIL
    procedure file. Deriving public_url from oeil_procedure_ref alone left 1,519 of
    3,382 rows serving an empty contracted datapoint -- not because the address was
    unknown, but because the row's own CELEX and url columns were never consulted.

      OEIL_DIRECT (2,034 rows)      -> the OEIL procedure file. Always has a reference.
      EURLEX (1,094)                -> an adopted act. It has no OEIL reference because
                                       it is not a procedure in negotiation; its address
                                       is its CELEX on EUR-Lex.
      LEGISLATIVE_TRAIN (477)       -> an EP Legislative Train file, whose stored url is
                                       its real train page (verified 200).

    Order matters: a row carrying an OEIL reference is a procedure file first, and the
    OEIL page is the richer destination. Returns None rather than a substitute when the
    row has no address of its own.
    """
    oeil = _oeil_url(getattr(r, "oeil_procedure_ref", None))
    if oeil:
        return oeil

    celex = getattr(r, "celex_numbers", None)
    if celex:
        first = next((c for c in celex if c and str(c).strip()), None)
        if first:
            return _EURLEX_DOC.format(celex=str(first).strip())

    stored = (getattr(r, "url", None) or "").strip()
    return stored or None


_STAGE_RE = re.compile(r"Stage reached in procedure\s*\n?\s*([^\n]+)")
_STATUS_RE = re.compile(r"\bStatus\s*\n+\s*([^\n]+)")


def _oeil_stage(r) -> Optional[str]:
    """OEIL's 'Stage reached in procedure' line, read from the stored page."""
    body = getattr(r, "oeil_text_body", None) or ""
    m = _STAGE_RE.search(body) or _STATUS_RE.search(body)
    return (m.group(1).strip() or None) if m else None


_SUBJECT_SECTION_RE = re.compile(
    r"\bSubject\s*\n(.*?)(?:\n\s*(?:Geographical area|Legislative priorities|Status|Key players)\s*\n)", re.S)
_SUBJECT_LINE_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(\S.*?)\s*$", re.M)


def _oeil_subjects(r) -> list:
    """OEIL's subject codes and labels for the procedure, from the stored page."""
    m = _SUBJECT_SECTION_RE.search(getattr(r, "oeil_text_body", None) or "")
    return [f"{code} {label}" for code, label in _SUBJECT_LINE_RE.findall(m.group(1))] if m else []


def _document_date(r) -> Optional[date]:
    """The date this carriage is about.

    For a procedure in negotiation that is the most recent OEIL key event. The 1,090
    EURLEX carriages are adopted acts with no OEIL timeline, so that returned nothing
    and document_date came back empty on 1,545 of 3,382 rows. Those fall back to the
    act's own adoption date, read from eu_laws (which takes it from Cellar) into
    act_date by scripts/fill_carriage_bodies_from_acts.py.

    The event date comes first: on a live procedure it is the more recent fact, and
    the act date would freeze the row at adoption.
    """
    latest = _latest_event_date(getattr(r, "oeil_key_events", None))
    return latest or getattr(r, "act_date", None)


def _latest_event_date(events) -> Optional[date]:
    """Return the most recent date from oeil_key_events (or oeil_timeline)."""
    if not events or not isinstance(events, list):
        return None
    latest = ""
    for ev in events:
        if not isinstance(ev, dict):
            continue
        d = ev.get("date") or ev.get("event_date") or ""
        if isinstance(d, str) and d > latest:
            latest = d
    if latest:
        try:
            return date.fromisoformat(latest[:10])
        except ValueError:
            return None
    return None


def _law_tracker_url(oeil_ref: Optional[str]) -> Optional[str]:
    """Map an OEIL procedure reference (e.g. '2025/0420(COD)') to the
    law-tracker.europa.eu URL ('2025_420'). Strips leading zeros from the
    sequential number to match the tracker's slug format. Returns None when
    we can't parse the ref."""
    if not oeil_ref:
        return None
    import re
    m = re.match(r"^\s*(\d{4})/0*(\d+)(?:\([A-Z]+\))?\s*$", oeil_ref)
    if not m:
        return None
    year, seq = m.group(1), m.group(2)
    return f"https://law-tracker.europa.eu/procedure/{year}_{seq}?lang=en"


@router.get(
    "",
    response_model=PaginatedResponse[ProcedureItem],
    summary="Search EU legislative procedures in negotiation — proposed but not yet adopted",
    description="""**What it does**
Returns EU legislative files that are currently in the institutional pipeline (proposed by the Commission, in EP committee, in Council negotiation, in trilogue, or recently adopted but not yet published). 1,200+ files tracked, sourced from OEIL — the EP's authoritative procedure file register. Each row carries the procedure reference (e.g. `2025/0726(COD)`), the title, the procedure type, the lead committee, the rapporteur, the current status, dates, and policy-area tags.

**When to use it**
The companion to `/api/v1/laws` (which covers adopted legislation). Use this surface for "what's coming next" advocacy work — tracking a file from proposal to adoption, monitoring rapporteur appointments, identifying procedures stuck in blocked status, or building a legislative-tracker dashboard. For procedures already adopted, the CELEX-keyed `/api/v1/laws` is faster.

**Input**
- `q` — substring match on title.
- `reference` — exact OEIL procedure reference (e.g. `2025/0726(COD)`).
- `committee` — lead committee code (e.g. `LIBE`, `ENVI`).
- `rapporteur_mep_id` — filter to procedures rapporteured by a specific MEP.
- `status` — procedure status enum (see `/api/v1/procedure-statuses`).
- `updated_from`, `updated_to` (and `updated_end` alias) — incremental sync.
- `limit`, `page`.

**Try it**
```
GET /api/v1/procedures?committee=ENVI&status=in_trilogue
GET /api/v1/procedures?reference=2024/0079(COD)
```

**You get back**
A `PaginatedResponse[ProcedureItem]` envelope. Each item carries the procedure metadata + envelope datapoints.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from OEIL XML feeds (oeil.secure.europarl.europa.eu). Procedure stages move on EP committee + Council cadences; 6h sync catches stage transitions inside a quarter-day.""",
)
async def list_procedures(
    request: Request,
    q: Optional[str] = Query(None, description="Substring match on title"),
    reference: Optional[str] = Query(None, description="OEIL procedure reference (e.g. 2025/0726(COD))"),
    committee: Optional[str] = Query(None, description="Lead committee code (e.g. LIBE, ENVI)"),
    rapporteur_mep_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Carriage status"),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[UpperBoundDatetime] = Query(None),
    updated_end: Optional[UpperBoundDatetime] = Query(None, description="Alias of updated_to (GovClipping-compatible)"),
    include_other_sources: bool = Query(
        False,
        description="Also return the EUR-Lex acts and Legislative Train files the mirror holds. "
                    "They are not OEIL procedures: no procedure file, and almost never a body.",
    ),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProcedureItem]:
    if updated_end and not updated_to:
        updated_to = updated_end
    query = db.query(LegislativeCarriage)
    filters = []
    # The mirror also holds 1,159 EUR-Lex acts and 477 Legislative Train files. Served as
    # "procedures" they had no OEIL page and no body (1,626 of 1,636), and 263 EUR-Lex
    # corrigenda linked the base act instead (7 Oct 2026). Adopted acts are /laws.
    # A procedure is served once Brubru holds its OEIL page, and not while OEIL answers
    # 404 (migration 277): otherwise its public_url is dead and its body null.
    oeil_served = and_(
        LegislativeCarriage.source == CarriageSourceEnum.OEIL_DIRECT,
        LegislativeCarriage.oeil_missing_since.is_(None),
        func.length(LegislativeCarriage.oeil_text_body) >= 200,
    )
    if include_other_sources is not True:
        filters.append(oeil_served)
    else:
        filters.append(or_(LegislativeCarriage.source != CarriageSourceEnum.OEIL_DIRECT, oeil_served))
    if reference:
        filters.append(LegislativeCarriage.oeil_procedure_ref == reference)
    if committee:
        filters.append(func.upper(LegislativeCarriage.lead_committee) == committee.upper())
    if rapporteur_mep_id:
        filters.append(LegislativeCarriage.rapporteur_mep_id == rapporteur_mep_id)
    if status:
        filters.append(func.lower(func.cast(LegislativeCarriage.current_status, func.TEXT.type)) == status.lower())  # type: ignore[attr-defined]
    if updated_from:
        filters.append(LegislativeCarriage.last_updated >= updated_from)
    if updated_to:
        filters.append(LegislativeCarriage.last_updated <= updated_to)
    if q:
        filters.append(LegislativeCarriage.title.ilike(f"%{q}%"))

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    # Add id as secondary sort to keep pagination deterministic when many rows
    # share last_updated (or it's NULL) — without it page=2 could return rows
    # already on page=1.
    rows = (
        stable(query.order_by(
            LegislativeCarriage.last_updated.desc().nullslast(),
            LegislativeCarriage.id.asc(),
        ))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        ProcedureItem(
            id=str(r.id),
            file_id=r.file_id,
            title=r.title,
            description=r.description,
            oeil_procedure_ref=r.oeil_procedure_ref,
            current_status=_enum_str(r.current_status),
            stage=_oeil_stage(r),
            is_blocked=bool(r.is_blocked),
            days_in_current_status=r.days_in_current_status,
            text_type=_enum_str(r.text_type),
            lead_committee=r.lead_committee,
            opinion_committees=list(r.opinion_committees or []),
            committees=list(r.committees or []),
            rapporteur_mep_id=r.rapporteur_mep_id,
            celex_numbers=list(r.celex_numbers or []),
            eprs_briefing_ids=list(r.eprs_briefing_ids or []),
            eprs_matched_briefings=_coerce_list(r.eprs_matched_briefings),
            # OEIL's own subjects, not Brubru's classifier, which tagged Solvency II
            # standards "Migration" and air-taxi rest rules "Taxation" (7 Oct 2026).
            policy_areas=_oeil_subjects(r),
            related_themes=list(r.related_themes or []),
            spotlight_tags=list(r.spotlight_tags or []),
            ec_priority_ids=list(r.ec_priority_ids or []),
            timeline=_coerce_list(r.timeline),
            status_history=_coerce_list(r.status_history),
            oeil_timeline=_coerce_list(r.oeil_timeline),
            oeil_key_events=_coerce_list(r.oeil_key_events),
            eurlex_documents=_coerce_list(r.eurlex_documents),
            ai_summary=r.ai_summary,
            ai_entities=_coerce_list(r.ai_entities),
            ai_policy_classifications=_coerce_list(r.ai_policy_classifications),
            legal_text_url=r.legal_text_url,
            url=r.url,
            law_tracker_url=_law_tracker_url(r.oeil_procedure_ref),
            first_seen=r.first_seen,
            last_updated=r.last_updated,
            expected_completion=r.expected_completion,
            enriched_at=r.enriched_at,
            enrichment_quality=r.enrichment_quality,
            # 5 mandatory datapoints
            public_url=_public_url(r),
            body_txt=getattr(r, "oeil_text_body", None),
            body_html=getattr(r, "oeil_html_body", None),
            document_date=_document_date(r),
            creation_date=r.first_seen,
            updated_date=row_updated(r),
        )
        for r in rows
    ]

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        updated_from=updated_from,
        updated_to=updated_to,
    )


# ============================================================================
# Procedure DETAIL endpoint (W1 P0 — Thursday brief 1.6 / Jordi P0.3)
# ============================================================================


class ProcedureDetail(BaseModel):
    id: str
    file_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    oeil_procedure_ref: Optional[str] = None

    current_status: Optional[str] = None
    stage: Optional[str] = Field(
        None,
        description=(
            "OEIL's own 'Stage reached in procedure', word for word (e.g. 'Awaiting committee "
            "decision', 'Procedure completed', 'Procedure lapsed or withdrawn'). `current_status` "
            "is Brubru's grouping of the same; when they seem to disagree, this is the authority."
        ),
    )
    is_blocked: bool = False
    days_in_current_status: Optional[int] = None
    text_type: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints (see ProcedureItem for the contract).
    public_url: Optional[str] = Field(None, description="OEIL procedure-file URL.")
    body_txt: Optional[str] = Field(None, description="Plain-text body sourced from the cached OEIL page.")
    body_html: Optional[str] = Field(None, description="HTML body sourced from the cached OEIL page.")
    document_date: Optional[date] = Field(None, description="Date of the latest OEIL key event.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this carriage.")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")

    # Committees + rapporteurs
    lead_committee: Optional[str] = None
    opinion_committees: list = Field(default_factory=list)
    committees: list = Field(default_factory=list)
    rapporteur_mep_id: Optional[str] = None

    # Cross-references
    celex_numbers: list = Field(default_factory=list)
    eprs_briefing_ids: list = Field(default_factory=list)
    eprs_matched_briefings: list = Field(default_factory=list)
    policy_areas: list = Field(
        default_factory=list,
        description=(
            "The procedure's subjects as OEIL classifies it, code and label word for word "
            "(e.g. '3.70.03 Climate policy, climate change, ozone layer'), read from its "
            "procedure file. Empty for the non-OEIL rows that include_other_sources adds."
        ),
    )
    related_themes: list = Field(default_factory=list)
    spotlight_tags: list = Field(default_factory=list)
    ec_priority_ids: list = Field(default_factory=list)

    # Timeline & history
    timeline: list = Field(default_factory=list)
    status_history: list = Field(default_factory=list)
    oeil_timeline: list = Field(default_factory=list)
    oeil_key_events: list = Field(default_factory=list)
    eurlex_documents: list = Field(default_factory=list)

    # AI enrichment
    ai_summary: Optional[str] = None
    ai_entities: list = Field(default_factory=list)
    ai_policy_classifications: list = Field(default_factory=list)

    # Links
    legal_text_url: Optional[str] = None
    url: Optional[str] = None
    # https://law-tracker.europa.eu/procedure/{YYYY}_{N}?lang=en
    law_tracker_url: Optional[str] = None

    # Temporal
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    expected_completion: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    enrichment_quality: Optional[str] = None

    # Brubru curated overlay (hand-verified editorial layer) for high-salience
    # files. Present only for procedures Brubru curates (e.g. EU Inc.); null
    # otherwise. See api/v1/_curated_procedures.py.
    curated: Optional[BrubruCuration] = None


def _coerce_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _enum_str(v) -> Optional[str]:
    """Render enums as their string value, not as 'EnumClass.MEMBER'."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else str(v)


def _carriage_to_detail(r: LegislativeCarriage) -> ProcedureDetail:
    return ProcedureDetail(
        id=str(r.id),
        file_id=r.file_id,
        title=r.title,
        description=r.description,
        oeil_procedure_ref=r.oeil_procedure_ref,
        current_status=_enum_str(r.current_status),
        stage=_oeil_stage(r),
        is_blocked=bool(r.is_blocked),
        days_in_current_status=r.days_in_current_status,
        text_type=_enum_str(r.text_type),
        lead_committee=r.lead_committee,
        opinion_committees=list(r.opinion_committees or []),
        committees=list(r.committees or []),
        rapporteur_mep_id=r.rapporteur_mep_id,
        celex_numbers=list(r.celex_numbers or []),
        eprs_briefing_ids=list(r.eprs_briefing_ids or []),
        eprs_matched_briefings=_coerce_list(r.eprs_matched_briefings),
        # OEIL's own subjects, not Brubru's classifier, which tagged Solvency II
        # standards "Migration" and air-taxi rest rules "Taxation" (7 Oct 2026).
        policy_areas=_oeil_subjects(r),
        related_themes=list(r.related_themes or []),
        spotlight_tags=list(r.spotlight_tags or []),
        ec_priority_ids=list(r.ec_priority_ids or []),
        timeline=_coerce_list(r.timeline),
        status_history=_coerce_list(r.status_history),
        oeil_timeline=_coerce_list(r.oeil_timeline),
        oeil_key_events=_coerce_list(r.oeil_key_events),
        eurlex_documents=_coerce_list(r.eurlex_documents),
        ai_summary=r.ai_summary,
        ai_entities=_coerce_list(r.ai_entities),
        ai_policy_classifications=_coerce_list(r.ai_policy_classifications),
        legal_text_url=r.legal_text_url,
        url=r.url,
        law_tracker_url=_law_tracker_url(r.oeil_procedure_ref),
        first_seen=r.first_seen,
        last_updated=r.last_updated,
        expected_completion=r.expected_completion,
        enriched_at=r.enriched_at,
        enrichment_quality=r.enrichment_quality,
        # 5 mandatory datapoints
        public_url=_public_url(r),
        body_txt=getattr(r, "oeil_text_body", None),
        body_html=getattr(r, "oeil_html_body", None),
        document_date=_document_date(r),
        creation_date=r.first_seen,
        updated_date=row_updated(r),
        # Brubru curated editorial overlay (null unless Brubru curates this file)
        curated=get_curation(r.oeil_procedure_ref),
    )


@router.get(
    "/{reference:path}",
    response_model=ProcedureDetail,
    summary="Look up one legislative procedure by its reference — full timeline + rapporteurs + briefings",
    description="""**What it does**
Returns the complete legislative carriage for one procedure — the full OEIL timeline (every event from Commission proposal to adoption with dates + actors), rapporteurs by committee, committee assignments, EPRS-matched briefings, EUR-Lex linked documents, and AI-enriched summary. The richest single-procedure surface in the v1 API.

**When to use it**
When you need the complete picture of a legislative file in one call — for an advocacy briefing, a chat answer about "where is the AI Act now", or a legislative-tracker UI deep-link. The endpoint accepts either the OEIL procedure_ref (most common: `2025/0419(COD)`) or Brubru's internal file_id.

**Input**
- `reference` (path) — either OEIL procedure ref (e.g. `2021/0106(COD)`) or Brubru file_id. The `:path` matcher accepts slashes + parentheses verbatim; no URL-encoding needed.

**Try it**
```
GET /api/v1/procedures/2024/0079(COD)
GET /api/v1/procedures/2021/0106(COD)
```

**You get back**
A `ProcedureDetail` object with `oeil_procedure_ref`, `file_id`, `title`, `procedure_type`, `procedure_stage`, `lead_committee`, full `events[]` timeline, `rapporteurs[]`, EPRS briefings, EUR-Lex documents, AI summary, and the 5 envelope-level datapoints. HTTP 404 with `reason_code: not_found` if no procedure matches.

For a small set of high-salience files, the response also carries a `curated` object: a hand-verified Brubru editorial overlay with a plain-English status, the committee + rapporteur + shadow map, debate highlights, the political dynamics, related procedures, source links, and links to Brubru's multilingual deep-dive. `curated` is `null` for procedures Brubru does not curate. The flagship example is EU Inc., the 28th Regime corporate legal framework: `GET /api/v1/procedures/2026/0074(COD)`.

**Data freshness**
Raw carriage fields sync every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from OEIL XML feeds. The `curated` overlay is maintained editorially and carries its own `as_of` verification date.""",
)
async def get_procedure_detail(
    reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ProcedureDetail:
    # Accepts the `id` the collection publishes, then the OEIL procedure ref,
    # then file_id. The surrogate has to be tried: oeil_procedure_ref is present
    # on only 1,440 of 2,789 carriages and repeats three times, so it cannot be
    # this resource's identifier even though it is the one people cite.
    r = resolve_row(db, LegislativeCarriage, reference,
                    natural_keys=("oeil_procedure_ref", "file_id"))
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Procedure {reference} not found (tried oeil_procedure_ref and file_id)",
                "reason_code": "not_found",
                "resource": "procedure",
                "id": reference,
            },
        )
    return _carriage_to_detail(r)
