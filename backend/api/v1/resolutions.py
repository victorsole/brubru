"""
/api/v1/resolutions — EP non-legislative resolutions (INL, INI, RSP).

Resolutions are EP outputs distinct from legislative texts: legislative-initiative
(INL), own-initiative reports (INI), and current-issues resolutions (RSP). They
are leading indicators of legislative pressure on the Commission.

Backed by the ep_resolutions table.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, text as _sql_text
from sqlalchemy.orm import Session

from core.database import get_db
from models.ep_resolutions import EPResolution
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resolutions", tags=["v1-resolutions"])


class ResolutionItem(BaseModel):
    id: str
    procedure_ref: str
    title: str
    resolution_type: Optional[str] = None
    adoption_date: Optional[date] = None
    vote_date: Optional[datetime] = None
    lead_committee: Optional[str] = None
    rapporteur: Optional[str] = None
    summary: Optional[str] = None
    eurovoc_codes: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    vote_for: int = 0
    vote_against: int = 0
    vote_abstention: int = 0
    vote_total: int = 0
    # `key_events` synthesised from the row itself: a single canonical event
    # (the plenary vote) plus, when present, an "adoption" entry. Each event
    # is `{date, event_type, description}`. Surfaces what Jordi flagged as
    # missing on the LIST without requiring a join to the full procedure.
    key_events: list = Field(default_factory=list)
    oeil_url: Optional[str] = None
    text_url: Optional[str] = None
    has_commission_followup: bool = False
    updated_at: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — text_url (the doceo text) when present, else oeil_url.")
    body_txt: Optional[str] = Field(None, description="Plain-text composition: title + procedure + lead committee + rapporteur + dates + vote tally + summary.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields.")
    document_date: Optional[date] = Field(None, description="Adoption date if set, else the plenary vote date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row (alias of updated_at).")


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


def _build_key_events(r: EPResolution) -> list:
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
            "description": " (".join(descr_parts) + ")" if len(descr_parts) > 1 else (descr_parts[0] if descr_parts else "Plenary vote"),
        })
    if r.adoption_date and (not r.vote_date or r.adoption_date != getattr(r.vote_date, "date", lambda: None)()):
        events.append({
            "date": r.adoption_date.isoformat() if hasattr(r.adoption_date, "isoformat") else str(r.adoption_date),
            "event_type": "adopted",
            "description": "Resolution adopted",
        })
    if r.has_commission_followup:
        events.append({
            "date": None,
            "event_type": "commission_followup",
            "description": "Commission has followed up on this resolution (see /api/v1/commission-register-documents)",
        })
    # If we have nothing at all from the structured columns, fall back to the
    # last_updated timestamp as a single "tracked" event. Better to surface a
    # minimal timeline than to return an empty array — partners use the
    # presence of any event as a signal that the row exists in OEIL.
    if not events and r.updated_at:
        events.append({
            "date": r.updated_at.date().isoformat() if hasattr(r.updated_at, "date") else str(r.updated_at),
            "event_type": "tracked",
            "description": (
                "Tracked by Brubru — vote and adoption dates not yet ingested from OEIL. "
                "See /api/v1/procedures/{procedure_ref} for the full timeline."
            ),
        })
    return events


def _row_to_item(r: EPResolution, oeil_body_txt: Optional[str] = None,
                 oeil_body_html: Optional[str] = None) -> ResolutionItem:
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
        adoption_date=r.adoption_date,
        vote_date=r.vote_date,
        lead_committee=r.lead_committee,
        rapporteur=r.rapporteur,
        summary=r.summary,
        eurovoc_codes=list(r.eurovoc_codes or []),
        policy_areas=list(r.policy_areas or []),
        vote_for=int(r.vote_for or 0),
        vote_against=int(r.vote_against or 0),
        vote_abstention=int(r.vote_abstention or 0),
        vote_total=int(r.vote_total or 0),
        key_events=_build_key_events(r),
        oeil_url=r.oeil_url,
        text_url=r.text_url,
        has_commission_followup=bool(r.has_commission_followup),
        updated_at=r.updated_at,
        # 5 mandatory datapoints
        public_url=r.text_url or r.oeil_url,
        body_txt=body_txt,
        body_html=body_html,
        document_date=doc_date,
        creation_date=r.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedResponse[ResolutionItem],
    summary="List EP resolutions (INL / INI / RSP)",
    description=(
        "Non-legislative EP outputs: legislative initiative (INL), own-initiative "
        "reports (INI), and resolutions (RSP). Filter by type, lead committee, "
        "rapporteur, adoption date, and incremental sync via updated_from."
    ),
)
async def list_resolutions(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + summary"),
    resolution_type: Optional[str] = Query(None, description="INL | INI | RSP | OTHER"),
    lead_committee: Optional[str] = Query(None),
    rapporteur: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    has_commission_followup: Optional[bool] = Query(None),
    published_from: Optional[date] = Query(None, description="adoption_date >= value"),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
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
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    # Pull the cached OEIL body (backfilled by scripts/backfill_oeil_body.py)
    # for every resolution's procedure_ref in one batch — same enrichment we
    # already do for /committees/{code}/work-items.
    refs = [r.procedure_ref for r in rows if r.procedure_ref]
    oeil_bodies: dict = {}
    if refs:
        oeil_rows = db.execute(_sql_text("""
            SELECT oeil_procedure_ref, oeil_text_body, oeil_html_body
            FROM legislative_carriages
            WHERE oeil_procedure_ref = ANY(:refs)
              AND (oeil_text_body IS NOT NULL OR oeil_html_body IS NOT NULL)
        """), {"refs": refs}).fetchall()
        oeil_bodies = {row[0]: (row[1], row[2]) for row in oeil_rows}

    data = []
    for r in rows:
        body = oeil_bodies.get(r.procedure_ref) or (None, None)
        data.append(_row_to_item(r, oeil_body_txt=body[0], oeil_body_html=body[1]))

    return build_envelope(
        data,
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/{procedure_ref:path}",
    response_model=ResolutionItem,
    summary="Single resolution detail by procedure_ref",
)
async def get_resolution_detail(
    procedure_ref: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ResolutionItem:
    r = db.query(EPResolution).filter(EPResolution.procedure_ref == procedure_ref).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Resolution {procedure_ref} not found",
            "reason_code": "not_found",
            "resource": "resolution",
            "id": procedure_ref,
        })
    # Reuse the same cached-OEIL-body enrichment as the list endpoint.
    oeil_body_txt = oeil_body_html = None
    if r.procedure_ref:
        row = db.execute(_sql_text("""
            SELECT oeil_text_body, oeil_html_body FROM legislative_carriages
            WHERE oeil_procedure_ref = :ref LIMIT 1
        """), {"ref": r.procedure_ref}).fetchone()
        if row:
            oeil_body_txt, oeil_body_html = row[0], row[1]
    return _row_to_item(r, oeil_body_txt=oeil_body_txt, oeil_body_html=oeil_body_html)
