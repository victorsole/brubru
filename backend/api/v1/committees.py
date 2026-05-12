"""
/api/v1/committees/* — EP committee work items, minutes, and roster.
"""

import json
import re
from datetime import date, datetime
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.committee_minutes import CommitteeMinutes
from models.committee_work import CommitteeWorkItem
from models.legislative_train import LegislativeCarriage
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


def _enum_value(v) -> Optional[str]:
    """Return the underlying value of an Enum or string, or None."""
    if v is None:
        return None
    return getattr(v, "value", None) or str(v)


# ---------------------------------------------------------------------------
# Anti-hallucination helpers — Tier A enrichment from legislative_carriages
# JSON blobs. Every helper either returns the source-verbatim value or None;
# none of them synthesise data when the source is missing or ambiguous.
# ---------------------------------------------------------------------------

# Trailing political-group token: "GOZI Sandro (Renew)" -> ("GOZI Sandro", "Renew")
_GROUP_SUFFIX_RE = re.compile(r"^(.+?)\s*\(([A-Z&\-/]+)\)\s*$")
# Detect lowercase->UPPERCASE boundaries (likely glued co-rapporteur names)
_GLUED_NAME_RE = re.compile(r"[a-zà-ÿ][A-ZÀ-Ÿ]")
# Conservative committee-vote matcher: only fires on explicit OEIL phrasing.
_VOTE_EVENT_RE = re.compile(
    r"vote in committee|committee.*single reading|adopted in committee|committee vote",
    re.IGNORECASE,
)
# Procedure-type suffixes we treat as pre-adoption (CELEX assigned only
# post-adoption). Sourced from the EP procedure-type registry — extend when
# OEIL surfaces a new code we don't recognise. When in doubt, an unknown
# suffix falls through to celex_status="unknown" rather than lying.
_PRE_ADOPTION_SUFFIXES = {
    # Legislative
    "COD", "CNS", "NLE", "APP",
    # Non-legislative initiatives
    "INI", "INL", "RSP",
    # Budgetary
    "BUD", "BUI", "DEC", "DBU", "GBD", "BUS",
    # Secondary acts
    "DEA", "RPS",
    # Internal / Inter-institutional
    "REG", "ACI", "RSO",
    # Other
    "IMM", "ART",
}


def _safe_json(obj: Any) -> Any:
    """Coerce JSON columns (string / dict / list / None) to native Python.

    SQLAlchemy returns JSON columns as native dict/list when the column type
    is JSON/JSONB, but legacy text columns can hold serialised JSON strings.
    Return None if parsing fails — callers must treat None as "no data".
    """
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return obj
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except Exception:
            return None
    return None


def _parse_cwi_rapporteur(raw_name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse the CWI rapporteur_name string.

    'GOZI Sandro (Renew)' -> ('GOZI Sandro', 'Renew', None)
    'VINCZE Loránt (EPP)GOERENS Charles (Renew)' -> raw glued, flag and pass through.
    Returns (name, group, quality_flag). NEVER invents data.
    """
    if not raw_name or not raw_name.strip():
        return None, None, None
    raw = raw_name.strip()
    # Multiple "(GROUP)" tokens means co-rapporteurs glued by the scraper.
    if raw.count("(") > 1:
        return raw, None, "multiple_rapporteurs_glued"
    m = _GROUP_SUFFIX_RE.match(raw)
    if m:
        name = m.group(1).strip()
        group = m.group(2)
        quality = "potentially_glued" if _GLUED_NAME_RE.search(name) else None
        return name, group, quality
    quality = "potentially_glued" if _GLUED_NAME_RE.search(raw) else None
    return raw, None, quality


def _safe_dict_get(parent: Any, key: str) -> Any:
    """Defensive .get() — returns None if parent isn't a dict.

    OEIL JSON blobs occasionally have explicit nulls where we expect dicts
    (e.g. key_players.committee_responsible = null when no committee
    assigned yet), so chained .get() calls would crash on None.
    """
    if isinstance(parent, dict):
        return parent.get(key)
    return None


def _extract_lc_rapporteur(
    lc_oeil_data: Any,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Pull rapporteur from LC's oeil_procedure_data.key_players.committee_responsible."""
    data = _safe_json(lc_oeil_data)
    if not isinstance(data, dict):
        return None, None, None
    key_players = _safe_dict_get(data, "key_players")
    cr = _safe_dict_get(key_players, "committee_responsible")
    rap = _safe_dict_get(cr, "rapporteur")
    if not isinstance(rap, dict):
        return None, None, None
    name = (rap.get("name") or "").strip() or None
    group = (rap.get("political_group") or "").strip() or None
    if not name:
        return None, None, None
    quality = "potentially_glued" if _GLUED_NAME_RE.search(name) else None
    return name, group, quality


def _extract_lc_shadow_rapporteurs(lc_oeil_data: Any) -> list:
    """Pass through OEIL shadow_rapporteurs verbatim. Empty list when none."""
    data = _safe_json(lc_oeil_data)
    if not isinstance(data, dict):
        return []
    key_players = _safe_dict_get(data, "key_players")
    cr = _safe_dict_get(key_players, "committee_responsible")
    shadows = _safe_dict_get(cr, "shadow_rapporteurs") or []
    if not isinstance(shadows, list):
        return []
    out = []
    for s in shadows:
        if not isinstance(s, dict):
            continue
        name = (s.get("name") or "").strip() or None
        if not name:
            continue
        out.append({
            "name": name,
            "group": (s.get("political_group") or "").strip() or None,
            "committee": (s.get("committee") or "").strip() or None,
        })
    return out


def _extract_lc_documents(lc_oeil_data: Any) -> list:
    """Pass through OEIL documentation_gateway verbatim with field renaming."""
    data = _safe_json(lc_oeil_data)
    if not isinstance(data, dict):
        return []
    gw = _safe_dict_get(data, "documentation_gateway") or []
    if not isinstance(gw, list):
        return []
    out = []
    for d in gw:
        if not isinstance(d, dict):
            continue
        out.append({
            "type": d.get("doc_type_code"),
            "type_label": d.get("doc_type_text"),
            "pe_reference": d.get("pe_reference"),
            "a_reference": d.get("a_reference"),
            "url": d.get("doceo_url"),
            "committee": d.get("committee"),
            "date": d.get("date"),
        })
    return out


def _derive_celex_status(celex_numbers: list, procedure_ref: Optional[str]) -> str:
    """Honest CELEX lifecycle flag — no upstream lookup, pure derivation."""
    if celex_numbers and len(celex_numbers) > 0:
        return "adopted"
    proc_type = _proc_type_from_ref(procedure_ref)
    if proc_type and proc_type.upper() in _PRE_ADOPTION_SUFFIXES:
        return "pre_adoption"
    return "unknown"


def _parse_event_date(raw: Any) -> Optional[date]:
    """Parse OEIL event date strings — never guess on ambiguous formats."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # ISO-8601 (with or without time)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:19] if "T" in s else s, fmt).date()
        except ValueError:
            continue
    return None


def _extract_vote_date_from_events(lc_oeil_key_events: Any) -> Optional[date]:
    """Tier C: scan oeil_key_events for explicit committee-vote phrasing.

    Conservative — only matches strings that explicitly mention a committee
    vote. Multiple matches resolve to the LATEST date (final vote, not
    preliminary). No match -> None (we don't infer from generic 'Event').
    """
    events = _safe_json(lc_oeil_key_events)
    if not isinstance(events, list):
        return None
    matches = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        desc = ev.get("description") or ""
        ev_type = ev.get("event_type") or ""
        haystack = f"{ev_type} {desc}"
        if _VOTE_EVENT_RE.search(haystack):
            d = _parse_event_date(ev.get("date"))
            if d:
                matches.append(d)
    return max(matches) if matches else None


_PROC_TYPE_RE = re.compile(r"\(([A-Z]{2,5})\)\s*$")
# Heuristic: titles like "Delegated acts (DEA) IMCO",
# "Resolution on topical subjects (RSP) IMCO",
# "***I Ordinary legislative procedure (COD) first reading ENVI IMCO TRAN",
# "Mep's role All roles reporter role ..." are scrape artifacts, not real
# proposal titles. Detect them so we can prefer the legislative_carriages title.
_PLACEHOLDER_TITLE_PATTERNS = (
    re.compile(r"^Delegated acts \([A-Z]+\)\s+\w+", re.IGNORECASE),
    re.compile(r"^Resolution on topical subjects", re.IGNORECASE),
    re.compile(r"^\*+\s*I+\s*Ordinary legislative procedure", re.IGNORECASE),
    re.compile(r"^Mep'?s role All roles", re.IGNORECASE),
    re.compile(r"^Implementing acts \([A-Z]+\)", re.IGNORECASE),
    re.compile(r"^Own-initiative procedure \([A-Z]+\)\s+\w+", re.IGNORECASE),
    re.compile(r"^Consultation procedure \([A-Z]+\)\s+\w+", re.IGNORECASE),
    re.compile(r"^Consent procedure \([A-Z]+\)\s+\w+", re.IGNORECASE),
    # Tier B: backfill_lc_for_committee_work_items.py inserts LC rows whose
    # title is a placeholder when OEIL didn't return basic_info.title cleanly.
    re.compile(r"^Procedure File:\s*\d{4}/\d+\([A-Z]+\)\s*$", re.IGNORECASE),
)


def _is_placeholder_title(title: Optional[str]) -> bool:
    if not title:
        return True
    return any(p.search(title) for p in _PLACEHOLDER_TITLE_PATTERNS)


def _proc_type_from_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    m = _PROC_TYPE_RE.search(ref)
    return m.group(1) if m else None

router = APIRouter(prefix="/committees", tags=["v1-committees"])


def _committee_streaming_url(code: str) -> str:
    return f"https://multimedia.europarl.europa.eu/en/webstreaming?committee={code.upper()}"


def _committee_homepage_url(code: str) -> str:
    return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/home/highlights"


def _committee_documents_url(code: str) -> str:
    return f"https://www.europarl.europa.eu/committees/en/{code.lower()}/documents/latest-documents"


def _clean_event_description(s: Optional[str]) -> Optional[str]:
    """OEIL scrapes occasionally capture page chrome ('Key events / pdf / Date /
    Event / Reference / Summary / \\n…') in the event description. Strip the
    chrome and collapse whitespace so body_txt stays readable."""
    if not s:
        return None
    txt = re.sub(r"(?i)\b(key events|date|event|reference|summary|pdf)\b", "", s)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt or None


def _compose_oeil_body(lc) -> Tuple[Optional[str], Optional[str]]:
    """Build body_txt and body_html from already-cached legislative_carriages
    data. Pulls from lc.description (procedure summary) and lc.oeil_key_events
    (timeline). No upstream HTTP — pure DB join. Returns (None, None) when the
    carriage row is missing or all source fields are empty.
    """
    if lc is None:
        return None, None
    desc = (getattr(lc, "description", None) or "").strip() or None
    events_raw = getattr(lc, "oeil_key_events", None) or []
    events: list = []
    if isinstance(events_raw, list):
        for ev in events_raw:
            if not isinstance(ev, dict):
                continue
            d = ev.get("date") or ""
            t = ev.get("event_type") or ev.get("type") or ""
            descr = _clean_event_description(ev.get("description") or "")
            if not (d or t or descr):
                continue
            events.append({"date": d, "type": t, "description": descr})
    if not desc and not events:
        return None, None

    # Plain text
    parts_txt: list = []
    if desc:
        parts_txt.append(desc)
    if events:
        parts_txt.append("Key events:")
        for ev in events:
            line = f"- {ev['date']}: {ev['type']}" if ev["date"] or ev["type"] else "-"
            if ev["description"]:
                line += f" — {ev['description']}"
            parts_txt.append(line)
    body_txt = "\n\n".join(parts_txt) if parts_txt else None

    # HTML
    import html as _html
    parts_html: list = []
    if desc:
        parts_html.append(f"<p>{_html.escape(desc)}</p>")
    if events:
        parts_html.append("<h3>Key events</h3>")
        lis = []
        for ev in events:
            head = f"<strong>{_html.escape(ev['date'])}</strong>" if ev["date"] else ""
            mid = f" — {_html.escape(ev['type'])}" if ev["type"] else ""
            tail = f": {_html.escape(ev['description'])}" if ev["description"] else ""
            lis.append(f"<li>{head}{mid}{tail}</li>")
        parts_html.append("<ul>" + "".join(lis) + "</ul>")
    body_html = "<article>" + "".join(parts_html) + "</article>" if parts_html else None
    return body_txt, body_html


class CommitteeWorkEnvelope(PaginatedResponse["CommitteeWorkOut"]):
    committee_code: str
    streaming_url: str
    homepage: str
    documents_url: str


class CommitteeMinutesEnvelope(PaginatedResponse["CommitteeMinutesOut"]):
    committee_code: str
    streaming_url: str
    homepage: str
    documents_url: str


class CommitteeWorkOut(BaseModel):
    id: str
    procedure_ref: Optional[str] = None
    committee_code: str
    title: Optional[str] = None
    procedure_type: Optional[str] = None
    committee_role: Optional[str] = None
    rapporteur_name: Optional[str] = None
    rapporteur_mep_id: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    vote_date: Optional[date] = None
    vote_result: Optional[str] = None
    celex_numbers: list = Field(default_factory=list)
    relevance_score: Optional[int] = None
    # Closes Jordi's "falta links" complaint — derive canonical URLs from
    # procedure_ref so each row points back to its OEIL file and the
    # law-tracker.europa.eu aggregator.
    url: Optional[str] = None
    law_tracker_url: Optional[str] = None

    # ---- Tier A enrichment from legislative_carriages JSON blobs ----
    # Source-verbatim values; when absent, fields stay None / [] rather than
    # being synthesised. Provenance fields document where each value came from.
    rapporteur_group: Optional[str] = None
    rapporteur_source: Optional[str] = None  # "cwi" | "lc_oeil" | None
    rapporteur_name_quality: Optional[str] = None  # None | "potentially_glued" | "multiple_rapporteurs_glued"
    shadow_rapporteurs: list = Field(default_factory=list)  # [{name, group, committee}]
    shadow_rapporteurs_source: Optional[str] = None  # "lc_oeil" | None
    documents: list = Field(default_factory=list)  # [{type, type_label, pe_reference, a_reference, url, committee, date}]
    documents_source: Optional[str] = None  # "lc_oeil" | None
    celex_status: str = "unknown"  # "pre_adoption" | "adopted" | "unknown"
    vote_date_source: Optional[str] = None  # "cwi" | "oeil_key_events" | None

    # The 5 mandatory Brubru v1 datapoints. A work item is a tracked
    # procedure — public_url is the OEIL file (citizen-facing canonical URL),
    # body_txt / body_html stay null because the body lives on the underlying
    # documents (use `documents[]` for download URLs), meeting_start_date is
    # the committee vote date when scheduled, and creation_date is when
    # Brubru first scraped this work-item row.
    public_url: Optional[str] = Field(
        None,
        description="Canonical citizen URL for the procedure (OEIL procedure-file page).",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text body. Null on work-items — see the individual PDFs in `documents[]`.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML body. Null on work-items — see the individual PDFs in `documents[]`.",
    )
    meeting_start_date: Optional[date] = Field(
        None,
        description="The committee vote date when scheduled (alias of vote_date for the uniform datapoint convention).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this work-item row (committee_work.first_seen).",
    )


def _oeil_url_for_ref(oeil_ref: Optional[str]) -> Optional[str]:
    if not oeil_ref:
        return None
    return f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={oeil_ref}"


def _law_tracker_url_for_ref(oeil_ref: Optional[str]) -> Optional[str]:
    """Map OEIL ref (YYYY/NNNN(COD)) to law-tracker.europa.eu/procedure/YYYY_N."""
    if not oeil_ref:
        return None
    import re as _re
    m = _re.match(r"^\s*(\d{4})/0*(\d+)(?:\([A-Z]+\))?\s*$", oeil_ref)
    if not m:
        return None
    return f"https://law-tracker.europa.eu/procedure/{m.group(1)}_{m.group(2)}?lang=en"


class CommitteeMinutesOut(BaseModel):
    id: str
    committee_code: str
    meeting_date: datetime
    title: str
    pe_reference: Optional[str] = None
    document_reference: Optional[str] = None
    pdf_url: Optional[str] = None
    agenda_items: list = Field(default_factory=list)
    votes: list = Field(default_factory=list)
    decisions: list = Field(default_factory=list)
    attendees_count: Optional[int] = None
    has_full_text: bool = False
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description="Canonical citizen URL — pdf_url → doc_url → source_url fallback chain.",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text body extracted from the PDF minutes.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML body. Null for this endpoint — minutes are PDF-source.",
    )
    meeting_start_date: Optional[date] = Field(
        None,
        description="The meeting date (date-only view of meeting_date for the uniform datapoint convention).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this minutes row (committee_minutes.first_seen).",
    )


@router.get(
    "/{code}/work-items",
    response_model=CommitteeWorkEnvelope,
    summary="Work items tracked by an EP committee",
)
async def list_committee_work(
    request: Request,
    code: str,
    q: Optional[str] = Query(None, description="Substring on title"),
    status: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeWorkEnvelope:
    # LEFT JOIN legislative_carriages on procedure_ref so we can enrich every
    # row with the canonical title / current_status / celex_numbers when the
    # CWI scrape only captured a placeholder. Applies to all committees.
    query = (
        db.query(CommitteeWorkItem, LegislativeCarriage)
        .outerjoin(
            LegislativeCarriage,
            LegislativeCarriage.oeil_procedure_ref == CommitteeWorkItem.procedure_ref,
        )
        .filter(func.upper(CommitteeWorkItem.committee_code) == code.upper())
    )
    if q:
        query = query.filter(CommitteeWorkItem.title.ilike(f"%{q}%"))
    if status:
        query = query.filter(func.lower(func.cast(CommitteeWorkItem.status, func.TEXT.type)) == status.lower())  # type: ignore
    if stage:
        query = query.filter(func.lower(CommitteeWorkItem.stage) == stage.lower())

    total = query.count()
    pairs = (
        query.order_by(CommitteeWorkItem.vote_date.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    data = []
    for r, lc in pairs:
        # Title: prefer whichever source has a non-placeholder title. CWI
        # scrapes are sometimes filter-bar text ("Delegated acts (DEA) IMCO"),
        # LC-from-OEIL backfills sometimes have "Procedure File: 2025/...".
        # Use the first non-placeholder. Fall back to either if both are bad.
        cwi_title = r.title
        lc_title = lc.title if lc and getattr(lc, "title", None) else None
        if cwi_title and not _is_placeholder_title(cwi_title):
            title = cwi_title
        elif lc_title and not _is_placeholder_title(lc_title):
            title = lc_title
        else:
            title = cwi_title or lc_title

        # procedure_type: enum stored on CWI is restricted to COD/APP/CNS/NLE/INI
        # — it doesn't cover DEA/RSP/RPS/INL/etc. The procedure ref suffix is
        # the canonical type, so derive from there and only fall back to the
        # CWI enum when the ref has no suffix.
        proc_type = _proc_type_from_ref(r.procedure_ref) or _enum_value(r.procedure_type)

        # status: CWI default is "unknown". When LC has a current_status,
        # surface that — it tracks the procedure across the whole pipeline.
        cwi_status = _enum_value(r.status)
        if (cwi_status is None or cwi_status.lower() in ("unknown", "")) and lc and lc.current_status:
            status_out = _enum_value(lc.current_status)
        else:
            status_out = cwi_status

        # celex_numbers: prefer LC's array when CWI is empty.
        celex = list(r.celex_numbers or [])
        if not celex and lc and lc.celex_numbers:
            celex = list(lc.celex_numbers)

        # rapporteur_mep_id: fall back to LC when CWI is null.
        rap_mep = r.rapporteur_mep_id or (lc.rapporteur_mep_id if lc else None)

        # Compose body_txt / body_html from cached OEIL data (description +
        # key events). Done once per row; both fields share the work.
        oeil_body_txt, oeil_body_html = _compose_oeil_body(lc)

        # ---- Tier A: rapporteur enrichment with provenance ----
        # Path 1 (preferred): parse CWI rapporteur_name for "(GROUP)" suffix.
        # Path 2 (fallback): read LC oeil_procedure_data.key_players blob.
        # Quality flag surfaces upstream gluing — never split heuristically.
        cwi_rap_name, cwi_rap_group, cwi_rap_quality = _parse_cwi_rapporteur(r.rapporteur_name)
        rap_name_out: Optional[str] = cwi_rap_name
        rap_group_out: Optional[str] = cwi_rap_group
        rap_quality_out: Optional[str] = cwi_rap_quality
        rap_source: Optional[str] = "cwi" if cwi_rap_name else None
        if rap_name_out is None and lc and getattr(lc, "oeil_procedure_data", None) is not None:
            lc_name, lc_group, lc_quality = _extract_lc_rapporteur(lc.oeil_procedure_data)
            if lc_name:
                rap_name_out = lc_name
                rap_group_out = lc_group
                rap_quality_out = lc_quality
                rap_source = "lc_oeil"

        # ---- Tier A: shadow rapporteurs + documentation gateway ----
        shadows: list = []
        shadow_source: Optional[str] = None
        documents: list = []
        docs_source: Optional[str] = None
        if lc and getattr(lc, "oeil_procedure_data", None) is not None:
            shadows = _extract_lc_shadow_rapporteurs(lc.oeil_procedure_data)
            shadow_source = "lc_oeil" if shadows else None
            documents = _extract_lc_documents(lc.oeil_procedure_data)
            docs_source = "lc_oeil" if documents else None

        # ---- celex_status derivation ----
        celex_status = _derive_celex_status(celex, r.procedure_ref)

        # ---- Tier C: vote_date — CWI value first, then OEIL key events scan ----
        vote_date_out: Optional[date] = None
        vote_date_src: Optional[str] = None
        if r.vote_date:
            # CWI vote_date column was historically a datetime; downgrade to date for the response.
            vote_date_out = r.vote_date.date() if hasattr(r.vote_date, "date") else r.vote_date
            vote_date_src = "cwi"
        elif lc and getattr(lc, "oeil_key_events", None) is not None:
            extracted = _extract_vote_date_from_events(lc.oeil_key_events)
            if extracted:
                vote_date_out = extracted
                vote_date_src = "oeil_key_events"

        data.append(
            CommitteeWorkOut(
                id=str(r.id),
                procedure_ref=r.procedure_ref,
                committee_code=r.committee_code,
                title=title,
                procedure_type=proc_type,
                committee_role=_enum_value(r.committee_role),
                rapporteur_name=rap_name_out,
                rapporteur_mep_id=rap_mep,
                status=status_out,
                stage=r.stage,
                vote_date=vote_date_out,
                vote_result=r.vote_result,
                celex_numbers=celex,
                relevance_score=r.relevance_score,
                url=_oeil_url_for_ref(r.procedure_ref),
                law_tracker_url=_law_tracker_url_for_ref(r.procedure_ref),
                rapporteur_group=rap_group_out,
                rapporteur_source=rap_source,
                rapporteur_name_quality=rap_quality_out,
                shadow_rapporteurs=shadows,
                shadow_rapporteurs_source=shadow_source,
                documents=documents,
                documents_source=docs_source,
                celex_status=celex_status,
                vote_date_source=vote_date_src,
                # 5 mandatory datapoints — body_txt / body_html composed from
                # already-cached legislative_carriages data (description +
                # key events). No upstream fetch; pure DB join.
                public_url=_oeil_url_for_ref(r.procedure_ref),
                body_txt=oeil_body_txt,
                body_html=oeil_body_html,
                meeting_start_date=vote_date_out,
                creation_date=getattr(r, "first_seen", None),
            )
        )
    envelope = build_envelope(data, total=total, page=page, limit=limit)
    return CommitteeWorkEnvelope(
        **envelope.model_dump(),
        committee_code=code.upper(),
        streaming_url=_committee_streaming_url(code),
        homepage=_committee_homepage_url(code),
        documents_url=_committee_documents_url(code),
    )


@router.get(
    "/{code}/minutes",
    response_model=CommitteeMinutesEnvelope,
    summary="Minutes of a committee's meetings",
)
async def list_committee_minutes(
    request: Request,
    code: str,
    published_from: Optional[date] = Query(None, alias="date_from"),
    published_to: Optional[date] = Query(None, alias="date_to"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommitteeMinutesEnvelope:
    query = db.query(CommitteeMinutes).filter(func.upper(CommitteeMinutes.committee_code) == code.upper())
    if published_from:
        query = query.filter(CommitteeMinutes.meeting_date >= published_from)
    if published_to:
        query = query.filter(CommitteeMinutes.meeting_date <= datetime.combine(published_to, datetime.max.time()))
    total = query.count()
    rows = query.order_by(CommitteeMinutes.meeting_date.desc()).offset((page - 1) * limit).limit(limit).all()
    data = [
        CommitteeMinutesOut(
            id=str(r.id),
            committee_code=r.committee_code,
            meeting_date=r.meeting_date,
            title=r.title,
            pe_reference=r.pe_reference,
            document_reference=r.document_reference,
            pdf_url=r.pdf_url,
            agenda_items=list(r.agenda_items or []),
            votes=list(r.votes or []),
            decisions=list(r.decisions or []),
            attendees_count=r.attendees_count,
            has_full_text=bool(r.has_full_text),
            # 5 mandatory datapoints
            public_url=r.pdf_url or r.doc_url or r.source_url,
            body_txt=r.full_text,
            body_html=None,  # PDF source — never synthesise HTML
            meeting_start_date=r.meeting_date.date() if hasattr(r.meeting_date, "date") else r.meeting_date,
            creation_date=r.first_seen,
        )
        for r in rows
    ]
    envelope = build_envelope(data, total=total, page=page, limit=limit, published_from=published_from, published_to=published_to)
    return CommitteeMinutesEnvelope(
        **envelope.model_dump(),
        committee_code=code.upper(),
        streaming_url=_committee_streaming_url(code),
        homepage=_committee_homepage_url(code),
        documents_url=_committee_documents_url(code),
    )
