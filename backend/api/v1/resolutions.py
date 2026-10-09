"""
/api/v1/resolutions — EP non-legislative resolutions (INL, INI, RSP).

Resolutions are EP outputs distinct from legislative texts: legislative-initiative
(INL), own-initiative reports (INI), and current-issues resolutions (RSP). They
are leading indicators of legislative pressure on the Commission.

Backed by the ep_resolutions table.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from api.v1._date_bounds import UpperBoundDatetime
from pydantic import BaseModel, Field
from sqlalchemy import and_, text as _sql_text, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.ep_resolutions import EPResolution
from models.user import User

from ._row_dates import row_updated
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope
from core.identifiers import resolve_row
from services.matching.resolution_followups import FOLLOWUP_MATCH
from api.v1._pagination import stable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resolutions", tags=["v1-resolutions"])

_STATUSES = ("adopted", "pending", "closed_without_resolution", "rejected")

# The Commission's follow-ups to each procedure's adopted text. The match is the
# one the enrichment job stores as has_commission_followup, so flag and events agree.
_FOLLOWUPS_SQL = (
    "SELECT t.procedure_ref, f.document_date, f.identifier, f.title "
    "FROM texts_adopted t JOIN ep_external_documents f ON " + FOLLOWUP_MATCH + " "
    "WHERE t.procedure_ref = ANY(:refs) AND t.ta_reference ~ '^P[0-9]+_TA' "
    "ORDER BY f.document_date"
)


def _followups_by_ref(db, refs: list) -> dict:
    """The Commission's follow-up documents for each procedure's adopted text."""
    out: dict = {}
    if refs:
        for ref, d, ident, title in db.execute(_sql_text(_FOLLOWUPS_SQL), {"refs": refs}).fetchall():
            out.setdefault(ref, []).append((d, ident, title))
    return out


class ResolutionItem(BaseModel):
    id: str
    procedure_ref: str
    title: str
    resolution_type: Optional[str] = None
    status: Optional[str] = Field(None, description=(
        "adopted | pending | closed_without_resolution | rejected. A null adoption_date is "
        "pending (tabled, in committee or close to adoption), closed_without_resolution (the "
        "debate or objection ended with no text put to a final vote) or rejected (the final "
        "vote was lost; its tally is in vote_for / vote_against / vote_abstention)."))
    adoption_date: Optional[date] = None
    # The plenary vote that adopted the resolution: a DATE. The stored value carried
    # a fabricated 00:00:00; the vote's time is not held (8 Oct 2026).
    vote_date: Optional[date] = None
    lead_committee: Optional[str] = None
    rapporteur: Optional[str] = None
    summary: Optional[str] = None
    eurovoc_codes: Optional[list] = Field(None, description=(
        "EuroVoc descriptor ids, as the Publications Office indexed the resolution. "
        "null = not read yet (the text is not in the Official Journal yet)."))
    eurovoc: Optional[list] = Field(None, description=(
        "The same descriptors with labels: [{id, uri, label, domain}]. [] = in the OJ, "
        "not indexed yet; null = not read yet."))
    eurovoc_domain: Optional[str] = Field(None, description="The EuroVoc domain most descriptors belong to.")
    policy_areas: list = Field(default_factory=list)
    # The final plenary vote; null when Brubru holds no count (a show-of-hands
    # vote, or not yet ingested). Never 0 for "unknown".
    vote_for: Optional[int] = None
    vote_against: Optional[int] = None
    vote_abstention: Optional[int] = None
    vote_total: Optional[int] = None
    vote_method: Optional[str] = Field(None, description=(
        "How the final vote was taken: roll-call | electronic | show of hands. A show of "
        "hands has no count, so the tallies are null. null = vote not held by Brubru."))
    # `key_events` synthesised from the row itself: a single canonical event
    # (the plenary vote) plus, when present, an "adoption" entry. Each event
    # is `{date, event_type, description}`. Surfaces what Jordi flagged as
    # missing on the LIST without requiring a join to the full procedure.
    key_events: list = Field(default_factory=list)
    oeil_url: Optional[str] = None
    text_url: Optional[str] = None
    has_commission_followup: Optional[bool] = Field(None, description=(
        "Whether the Commission has published its follow-up to the adopted text (EP "
        "Open Data ACT_FOLLOWUP). null = not checked (Brubru does not hold the adopted "
        "text's reference); the follow-up itself is in key_events."))
    updated_at: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — text_url (the doceo text) when present, else oeil_url.")
    body_txt: Optional[str] = Field(None, description="The adopted text itself; the OEIL procedure page when Parliament has not published it yet; a composition of the row's fields only when neither exists.")
    body_html: Optional[str] = Field(None, description="The same body as HTML.")
    document_date: Optional[date] = Field(None, description="Adoption date if set, else the plenary vote date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row (created_at). Until 8 Oct 2026 this repeated updated_at, so a bulk re-stamp dated every resolution 28 Sep 2026.")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Same value as updated_at; updated_date is the name every Brubru item uses.")


def _compose_resolution_body(r) -> tuple:
    """Plain text + HTML composition from the resolution row."""
    import html as _html
    lines_txt: list = [r.title or "?"]
    parts_html: list = [f"<h2>{_html.escape(r.title or '?')}</h2>"]
    kv: list = []
    if r.procedure_ref: kv.append(("Procedure", r.procedure_ref))
    if r.resolution_type:
        kv.append(("Type", r.resolution_type.value if hasattr(r.resolution_type, "value") else str(r.resolution_type)))
    if r.lead_committee: kv.append(("Lead committee", r.lead_committee))
    if r.rapporteur: kv.append(("Rapporteur", r.rapporteur))
    if r.vote_date: kv.append(("Vote date", str(r.vote_date)))
    if r.adoption_date: kv.append(("Adoption date", str(r.adoption_date)))
    if r.vote_total:
        kv.append(("Vote tally",
                   f"{int(r.vote_for or 0)} for, {int(r.vote_against or 0)} against, {int(r.vote_abstention or 0)} abstentions (total {int(r.vote_total)})"))
    if r.summary:
        kv.append(("Summary", r.summary))
    for k, v in kv:
        lines_txt.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    body_txt = "\n".join(lines_txt)
    body_html = "<article>" + "".join(parts_html) + "</article>"
    return body_txt, body_html


def _build_key_events(r: EPResolution, oeil_events: Optional[list] = None,
                      followups: Optional[list] = None) -> list:
    """Synthesise a key-events list from the resolution row.

    The resolutions table doesn't carry a structured timeline; the closest
    signals are `vote_date` (plenary vote) and `adoption_date` (publication).
    We emit those as canonical events so partners can render a basic timeline
    without round-tripping to /procedures/{ref}.
    """
    events: list = []
    if r.vote_date:
        descr_parts = []
        if r.vote_for or r.vote_against or r.vote_abstention or r.vote_total:
            descr_parts.append(f"Vote: {int(r.vote_for or 0)} for, {int(r.vote_against or 0)} against, {int(r.vote_abstention or 0)} abstentions")
            if r.vote_total:
                descr_parts.append(f"total {int(r.vote_total)}")
        events.append({
            "date": r.vote_date.date().isoformat() if hasattr(r.vote_date, "date") else str(r.vote_date),
            "event_type": "plenary_vote",
            "description": (("Rejected. " if r.status == "rejected" else "")
                            + (" (".join(descr_parts) + ")" if len(descr_parts) > 1
                               else (descr_parts[0] if descr_parts else "Plenary vote"))),
        })
    if r.adoption_date and (not r.vote_date or r.adoption_date != getattr(r.vote_date, "date", lambda: None)()):
        events.append({
            "date": r.adoption_date.isoformat() if hasattr(r.adoption_date, "isoformat") else str(r.adoption_date),
            "event_type": "adopted",
            "description": "Resolution adopted",
        })
    # The Commission's published follow-up, dated and named from EP Open Data.
    # (Was a dateless placeholder, emitted only when the never-computed flag was set.)
    for d, ident, title in followups or []:
        events.append({
            "date": d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else None),
            "event_type": "commission_followup",
            "description": f"Commission follow-up {ident}" + (f": {title}" if title else ""),
        })
    # Nothing from the structured columns (no vote, no adoption): serve the
    # procedure's own OEIL key events, dated by the Parliament. Until 8 Oct 2026
    # this emitted a "tracked" event dated with Brubru's write time, which a
    # client reads as something the EP did on that day. No OEIL events either
    # means an empty list: an honest absence, not an invented entry.
    if not events:
        for e in oeil_events or []:
            label = (e.get("event_type") or "").strip() if isinstance(e, dict) else ""
            if not label or not e.get("date"):
                continue
            events.append({
                "date": str(e["date"])[:10],
                "event_type": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"),
                "description": label,
            })
    return events


def _items_for(db, rows: list) -> list:
    """ResolutionItems for `rows`, enriched in one batch. The list AND the detail
    route call this, so a resolution reads the same whichever way it is fetched
    (until 8 Oct 2026 the detail route served the OEIL page as the body while the
    list served the adopted text)."""
    # Pull the cached OEIL body (backfilled by scripts/backfill_oeil_body.py)
    # for every resolution's procedure_ref in one batch — same enrichment we
    # already do for /committees/{code}/work-items.
    refs = [r.procedure_ref for r in rows if r.procedure_ref]
    oeil_bodies: dict = {}
    oeil_events: dict = {}
    vote_methods: dict = {}
    adopted_bodies: dict = {}
    if refs:
        oeil_rows = db.execute(_sql_text("""
            SELECT oeil_procedure_ref, oeil_text_body, oeil_html_body
            FROM legislative_carriages
            WHERE oeil_procedure_ref = ANY(:refs)
              AND (oeil_text_body IS NOT NULL OR oeil_html_body IS NOT NULL)
        """), {"refs": refs}).fetchall()
        oeil_bodies = {row[0]: (row[1], row[2]) for row in oeil_rows}
        # The same OEIL page, kept by sync_oeil_procedures.py (migration 289) for the
        # procedures no carriage holds: debates such as 2026/2561(RSP), 9th-term texts.
        no_body = [ref for ref in refs if ref not in oeil_bodies]
        if no_body:
            for ref, txt, html in db.execute(_sql_text("""
                SELECT procedure_ref, body_txt, body_html FROM oeil_procedures
                WHERE procedure_ref = ANY(:refs) AND body_txt IS NOT NULL
            """), {"refs": no_body}).fetchall():
                oeil_bodies[ref] = (txt, html)
        vote_methods = {row[0]: row[1] for row in db.execute(_sql_text("""
            SELECT procedure_ref,
                   CASE vote_results->>'source' WHEN 'ep_open_data' THEN vote_results->>'method'
                        WHEN 'ep_roll_call_votes' THEN 'roll-call' END
            FROM texts_adopted
            WHERE procedure_ref = ANY(:refs) AND ta_reference ~ '^P[0-9]+_TA'
              AND vote_results IS NOT NULL
        """), {"refs": refs}).fetchall()}
        oeil_events = {row[0]: row[1] for row in db.execute(_sql_text("""
            SELECT oeil_procedure_ref, oeil_key_events FROM legislative_carriages
            WHERE oeil_procedure_ref = ANY(:refs) AND oeil_key_events IS NOT NULL
        """), {"refs": refs}).fetchall()}
        # A procedure no carriage holds (2026/2561(RSP) and the rest of a January block)
        # still has its OEIL page in oeil_procedures (migration 288): same events, read
        # from the page's Key events table, in the shape _build_key_events expects.
        missing = [ref for ref in refs if not oeil_events.get(ref)]
        if missing:
            for ref, events in db.execute(_sql_text("""
                SELECT procedure_ref, key_events FROM oeil_procedures
                WHERE procedure_ref = ANY(:refs) AND served
                  AND jsonb_array_length(key_events) > 0
            """), {"refs": missing}).fetchall():
                oeil_events[ref] = [{"date": e.get("date"), "event_type": e.get("event")}
                                    for e in events if isinstance(e, dict)]

        # The resolution's OWN adopted text, which is what `body_txt` should be.
        # Until 27 Aug 2026 this surface served the OEIL PROCEDURE PAGE as the
        # body -- real content, but a description of the file rather than the
        # text the Parliament adopted. Now that `texts_adopted.full_text` is
        # populated (703/703), the actual resolution is available and takes
        # precedence; OEIL remains the fallback for procedures with no adopted
        # text yet. Read from texts_adopted rather than copied, so there stays
        # ONE source of truth for the document.
        #
        # Only the adopted text itself (`P10_TA(YYYY)NNNN`). texts_adopted also
        # holds committee REPORTS (`A10/YYYY/NNNN`) under the same procedure_ref,
        # and until 8 Oct 2026 whichever row came last won: the draft report was
        # served as the resolution for 2025/2039(INI) and 2025/2210(INI). When
        # the adopted text has no body yet, OEIL is the honest fallback; the
        # report is not.
        adopted_rows = db.execute(_sql_text("""
            SELECT procedure_ref, full_text
            FROM texts_adopted
            WHERE procedure_ref = ANY(:refs) AND full_text IS NOT NULL
              AND ta_reference ~ '^P[0-9]+_TA'
        """), {"refs": refs}).fetchall()
        adopted_bodies = {row[0]: row[1] for row in adopted_rows}

    followups = _followups_by_ref(db, refs)
    data = []
    for r in rows:
        adopted = adopted_bodies.get(r.procedure_ref)
        if adopted:
            # Minimal, faithful HTML: the adopted text is plain text, so it is
            # wrapped rather than invented.
            import html as _html_mod
            body = (adopted,
                    "<article>" + "".join(
                        f"<p>{_html_mod.escape(p)}</p>"
                        for p in adopted.split("\n") if p.strip()
                    ) + "</article>")
        else:
            body = oeil_bodies.get(r.procedure_ref) or (None, None)
        item = _row_to_item(r, oeil_body_txt=body[0], oeil_body_html=body[1],
                            oeil_events=oeil_events.get(r.procedure_ref),
                            followups=followups.get(r.procedure_ref))
        item.vote_method = vote_methods.get(r.procedure_ref)
        data.append(item)

    return data


def _row_to_item(r: EPResolution, oeil_body_txt: Optional[str] = None,
                 oeil_body_html: Optional[str] = None,
                 oeil_events: Optional[list] = None,
                 followups: Optional[list] = None) -> ResolutionItem:
    body_txt, body_html = _compose_resolution_body(r)
    # Prefer the cached OEIL body (from migration 070 backfill) when present —
    # it carries the full procedure-file content (~2KB), vs the row composition
    # which only has the resolution metadata.
    if oeil_body_txt:
        body_txt = oeil_body_txt
    if oeil_body_html:
        body_html = oeil_body_html
    # Document date: prefer adoption_date, else vote_date (as date).
    doc_date = None
    if r.adoption_date:
        doc_date = r.adoption_date if isinstance(r.adoption_date, date) else None
    elif r.vote_date:
        doc_date = r.vote_date.date() if hasattr(r.vote_date, "date") else None
    return ResolutionItem(
        id=str(r.id),
        procedure_ref=r.procedure_ref,
        title=r.title,
        resolution_type=r.resolution_type.value if hasattr(r.resolution_type, "value") else (str(r.resolution_type) if r.resolution_type else None),
        status=r.status,
        adoption_date=r.adoption_date,
        vote_date=(r.vote_date.date() if hasattr(r.vote_date, "date") else r.vote_date),
        lead_committee=r.lead_committee,
        rapporteur=r.rapporteur,
        summary=r.summary,
        eurovoc_codes=(list(r.eurovoc_codes or []) if r.eurovoc_fetched_at else None),
        eurovoc=(list(r.eurovoc or []) if r.eurovoc_fetched_at else None),
        eurovoc_domain=r.eurovoc_domain,
        policy_areas=list(r.policy_areas or []),
        vote_for=r.vote_for,
        vote_against=r.vote_against,
        vote_abstention=r.vote_abstention,
        vote_total=r.vote_total,
        key_events=_build_key_events(r, oeil_events, followups),
        oeil_url=r.oeil_url,
        text_url=r.text_url,
        has_commission_followup=(bool(r.has_commission_followup)
                                 if r.followup_checked_at else None),
        updated_at=r.updated_at,
        # 5 mandatory datapoints
        public_url=r.text_url or r.oeil_url,
        body_txt=body_txt,
        body_html=body_html,
        document_date=doc_date,
        creation_date=r.created_at,
        updated_date=row_updated(r),
    )


@router.get(
    "",
    response_model=PaginatedResponse[ResolutionItem],
    summary="EP non-legislative resolutions — own-initiative reports, legislative initiatives, topical resolutions",
    description="""**What it does**
Returns EP non-legislative outputs — files where the Parliament expresses a position WITHOUT directly amending EU law. Covers: `INL` (legislative initiative reports — EP asks the Commission to propose), `INI` (own-initiative reports — EP positions on horizontal themes), `RSP` (topical resolutions — urgent matters of EU concern, e.g. human rights, foreign policy). Each row carries the procedure ref, title, type, lead committee, rapporteur, adoption date, vote tallies, Commission follow-up status, and full text URL.

One row per procedure, whatever its outcome: every INI, INL and RSP procedure the Legislative Observatory (OEIL) serves from 2024 onwards, read from OEIL itself. So a topical debate that ended with no motion voted is here as `closed_without_resolution`, and an own-initiative report still in committee as `pending`. Use `status=adopted` for adopted resolutions only.

**When to use it**
EP resolutions don't have legal force but signal political direction — useful for advocacy work tracking what the EP demands of the Commission, urgent geopolitical positions, or thematic priorities. Filter by `has_commission_followup=true` to find resolutions where the Commission has actually responded.

**Input**
- `q` — substring on title + summary.
- `resolution_type` — `INL` / `INI` / `RSP` / `OTHER`.
- `lead_committee` — 4-letter committee code.
- `rapporteur` — name substring.
- `procedure_ref` — OEIL reference.
- `has_commission_followup` — boolean.
- `status` — `adopted` / `pending` / `closed_without_resolution` (a debate or objection that ended in Parliament with no text adopted) / `rejected` (the final vote was lost).
- `published_from`, `published_to` (and `published_end` alias) — adoption_date filter.
- `updated_from`, `updated_to` (and `updated_end` alias) — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/resolutions?resolution_type=INL&lead_committee=ENVI
GET /api/v1/resolutions?q=Ukraine&resolution_type=RSP
```

**You get back**
A `PaginatedResponse[ResolutionItem]` envelope. Each item carries `procedure_ref`, `title`, `resolution_type`, `status`, `lead_committee`, `rapporteur`, `adoption_date`, `vote_date`, the final plenary vote (`vote_for` / `vote_against` / `vote_abstention` / `vote_total`, null when not counted), `has_commission_followup`, `eurovoc` / `eurovoc_codes` / `eurovoc_domain` (the Publications Office's EuroVoc indexing, once the text is in the Official Journal), `key_events` (the plenary vote, the Commission's dated follow-ups, or OEIL's own events for a resolution not adopted), `oeil_url`, `text_url`, plus `public_url` (the adopted text's own page), `body_txt` / `body_html` (the adopted text; the OEIL procedure page when Parliament has not published it yet), `document_date`, `creation_date` and `updated_date`.

**Data freshness**
Refreshed about every 6 hours (warm tier) from the Parliament's own sources: texts adopted and their full text (doceo), procedure pages and events (OEIL), final roll-call votes, and the Commission's follow-ups (EP Open Data). A resolution adopted at a plenary sitting appears once Parliament publishes its text, usually within a few days.""",
)
async def list_resolutions(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + summary"),
    resolution_type: Optional[str] = Query(None, description="INL | INI | RSP | OTHER"),
    lead_committee: Optional[str] = Query(None),
    rapporteur: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    has_commission_followup: Optional[bool] = Query(None),
    status: Optional[str] = Query(None, description="adopted | pending | closed_without_resolution | rejected"),
    published_from: Optional[date] = Query(None, description="adoption_date >= value"),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[UpperBoundDatetime] = Query(None),
    updated_end: Optional[UpperBoundDatetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ResolutionItem]:
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

    query = db.query(EPResolution)
    filters = []
    if resolution_type:
        filters.append(EPResolution.resolution_type == resolution_type.upper())
    if lead_committee:
        filters.append(EPResolution.lead_committee == lead_committee.upper())
    if rapporteur:
        filters.append(EPResolution.rapporteur.ilike(f"%{rapporteur}%"))
    if procedure_ref:
        filters.append(EPResolution.procedure_ref == procedure_ref)
    if has_commission_followup is not None:
        filters.append(EPResolution.has_commission_followup == has_commission_followup)
    if status:
        if status not in _STATUSES:
            raise HTTPException(status_code=422, detail={
                "error": f"status must be one of {', '.join(_STATUSES)}; got {status!r}.",
                "reason_code": "invalid_param",
            })
        filters.append(EPResolution.status == status)
    if published_from:
        filters.append(EPResolution.adoption_date >= published_from)
    if published_to:
        filters.append(EPResolution.adoption_date <= published_to)
    if updated_from:
        filters.append(EPResolution.updated_at >= updated_from)
    if updated_to:
        filters.append(EPResolution.updated_at <= updated_to)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        filters.append(or_(EPResolution.title.ilike(like), EPResolution.summary.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = EPResolution.updated_at.desc().nullslast()
    else:
        order_col = EPResolution.adoption_date.desc().nullslast()
    rows = stable(query.order_by(order_col)).offset((page - 1) * limit).limit(limit).all()

    data = _items_for(db, rows)

    # Declare the corpus, and say what a NULL adoption date means (D3).
    #
    # All 72 rows carried `adoption_date = NULL`, so date filtering could not work
    # and every dated query returned nothing. 34 of those were genuinely missing a
    # date and have been recovered from `texts_adopted` and the OEIL "Decision by
    # Parliament" event. The REST are NULL correctly: their procedures are still
    # TABLED or CLOSE_TO_ADOPTION, so no adoption date exists yet. Those are
    # different facts and the response has to distinguish them.
    cov = db.query(
        func.min(EPResolution.adoption_date), func.max(EPResolution.adoption_date),
        func.count(EPResolution.id), func.count(EPResolution.adoption_date),
    ).one()
    undated = (cov[2] or 0) - (cov[3] or 0)
    by_status = dict(db.query(EPResolution.status, func.count(EPResolution.id))
                     .group_by(EPResolution.status).all())

    return build_envelope(
        data,
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        coverage_from=cov[0], coverage_to=cov[1],
        coverage_note=(
            f"{cov[3]} of {cov[2]} resolutions carry an adoption date. The other "
            f"{undated} have not been adopted, for the reason given in each item's "
            f"`status`: {by_status.get('pending', 0)} are `pending` (tabled, in "
            f"committee or close to adoption), {by_status.get('closed_without_resolution', 0)} "
            "are `closed_without_resolution` (the debate or objection ended in "
            "Parliament with no text adopted, so they never will be) and "
            f"{by_status.get('rejected', 0)} are `rejected` (the final vote was lost). A null "
            "adoption_date is therefore NOT 'date unknown', and a date-filtered query "
            "excludes both by design; filter with `status=` instead. "
            "SCOPE: this surface holds own-initiative and topical resolutions "
            "(INI / RSP / INL). The Parliament's positions on LEGISLATIVE "
            "procedures (COD, NLE, CNS, APP) are a different instrument and live "
            "in /api/v1/texts-adopted -- their absence here is scope, not a gap."
        ),
    )


@router.get(
    "/{procedure_ref:path}",
    response_model=ResolutionItem,
    summary="Look up one EP resolution by its procedure reference",
    description="""**What it does**
Fetches a single EP resolution by its procedure reference. Returns the same shape as the list endpoint, with the full text URL + adoption details + Commission follow-up status.

**When to use it**
After locating a resolution via the list endpoint, use this for the full record — common pattern in chat answers when a user references a specific INI / RSP / INL number.

**Input**
- `procedure_ref` (path) — procedure reference (e.g. `2025/2125(INI)`, `2025/2887(RSP)`). The `:path` matcher accepts slashes + parentheses verbatim.

**Try it**
```
GET /api/v1/resolutions/2025/2125(INI)
```

**You get back**
A single `ResolutionItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint: refreshed about every 6 hours from the Parliament's own sources.""",
)
async def get_resolution_detail(
    procedure_ref: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ResolutionItem:
    r = resolve_row(db, EPResolution, procedure_ref, natural_keys=("procedure_ref",))
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Resolution {procedure_ref} not found",
            "reason_code": "not_found",
            "resource": "resolution",
            "id": procedure_ref,
        })
    return _items_for(db, [r])[0]
