"""
/api/v1/{amendments, votes, ep-documents, press-releases, reports, opinions}

W3 P2 — EP entity endpoints not yet exposed in v1.

- /amendments      → mep_amendments (scraped EP committee amendments)
- /votes           → ep_votes (HowTheyVote roll-call votes)
- /votes/{id}/records → ep_member_votes per-MEP positions
- /ep-documents    → cross-committee unified view (committee_work + minutes
                     + amendment_documents + texts_adopted + mep_amendments)
- /press-releases  → first-class wrapper over publications.category=press_release
- /reports / /opinions → committee_work filtered by document type
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.committee_work import CommitteeWorkItem
from models.ep_voting import EPMemberVote, EPVote, VoteResult
from models.institutional_publication import InstitutionalPublication
from models.legislative_train import LegislativeCarriage
from models.mep_amendment import AmendmentDocument, MEPAmendment
from models.user import User

from ._body import body_from_html, body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)


def _build_lc_lookup(db: Session, refs: List[Optional[str]]) -> Dict[str, "LegislativeCarriage"]:
    """Bulk-fetch legislative_carriages for a list of OEIL procedure refs.

    Used to enrich amendment_documents responses (titles + rapporteur fallback)
    with the canonical proposal title and any rapporteur info OEIL has on the
    procedure. The amendment_documents table only carries the doc-level
    rapporteur (PR/RD); for AD/PA opinions we fall through to LC.
    """
    clean = sorted({r for r in refs if r})
    if not clean:
        return {}
    rows = (
        db.query(LegislativeCarriage)
        .filter(LegislativeCarriage.oeil_procedure_ref.in_(clean))
        .all()
    )
    return {row.oeil_procedure_ref: row for row in rows}


def _enrich_doc_title(
    raw_title_template: str,
    procedure_ref: Optional[str],
    lc_lookup: Dict[str, "LegislativeCarriage"],
) -> str:
    """Use the canonical LC title when we have it, falling back to the
    auto-generated 'doc_type for ref (committee)' template otherwise."""
    if procedure_ref and procedure_ref in lc_lookup and lc_lookup[procedure_ref].title:
        return lc_lookup[procedure_ref].title
    return raw_title_template


amendments_router = APIRouter(prefix="/amendments", tags=["v1-amendments"])
votes_router = APIRouter(prefix="/votes", tags=["v1-votes"])
ep_documents_router = APIRouter(prefix="/ep-documents", tags=["v1-ep-documents"])
press_releases_router = APIRouter(prefix="/press-releases", tags=["v1-press-releases"])
reports_router = APIRouter(prefix="/reports", tags=["v1-reports"])
opinions_router = APIRouter(prefix="/opinions", tags=["v1-opinions"])


# ============================================================================
# /amendments — EP committee amendments
# ============================================================================


class AmendmentItem(BaseModel):
    id: str
    procedure_reference: str
    committee_code: str
    pe_reference: str
    amendment_number: int
    author_names: list = Field(default_factory=list)
    political_group: Optional[str] = None
    on_behalf_of_group: bool = False
    element_type: str
    element_number: Optional[str] = None
    element_reference: str
    amendment_type: str
    original_text: Optional[str] = None
    proposed_text: Optional[str] = None
    justification: Optional[str] = None
    source_url: str
    document_date: Optional[date] = None
    scraped_at: Optional[datetime] = None


@amendments_router.get(
    "/{amendment_id}",
    response_model=AmendmentItem,
    summary="Single EP amendment by id (UUID)",
)
async def get_amendment_detail(
    amendment_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> AmendmentItem:
    r = db.query(MEPAmendment).filter(MEPAmendment.id == amendment_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Amendment {amendment_id} not found",
            "reason_code": "not_found",
            "resource": "amendment",
            "id": amendment_id,
        })
    return AmendmentItem(
        id=str(r.id), procedure_reference=r.procedure_reference,
        committee_code=r.committee_code, pe_reference=r.pe_reference,
        amendment_number=r.amendment_number,
        author_names=list(r.author_names or []),
        political_group=r.political_group, on_behalf_of_group=bool(r.on_behalf_of_group),
        element_type=r.element_type, element_number=r.element_number,
        element_reference=r.element_reference, amendment_type=r.amendment_type,
        original_text=r.original_text, proposed_text=r.proposed_text,
        justification=r.justification, source_url=r.source_url,
        document_date=r.document_date, scraped_at=r.scraped_at,
    )


@amendments_router.get(
    "",
    response_model=PaginatedResponse[AmendmentItem],
    summary="EP committee amendments (scraped from doceo)",
)
async def list_amendments(
    request: Request,
    procedure_reference: Optional[str] = Query(None),
    committee: Optional[str] = Query(None),
    political_group: Optional[str] = Query(None),
    pe_reference: Optional[str] = Query(None),
    amendment_type: Optional[str] = Query(None, description="modification | suppression | addition"),
    element_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Substring on element_reference + proposed_text"),
    published_from: Optional[date] = Query(None, description="document_date >= value"),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AmendmentItem]:
    query = db.query(MEPAmendment)
    filters = []
    if procedure_reference:
        filters.append(MEPAmendment.procedure_reference == procedure_reference)
    if committee:
        filters.append(MEPAmendment.committee_code == committee.upper())
    if political_group:
        filters.append(MEPAmendment.political_group == political_group.upper())
    if pe_reference:
        filters.append(MEPAmendment.pe_reference == pe_reference)
    if amendment_type:
        filters.append(MEPAmendment.amendment_type == amendment_type.lower())
    if element_type:
        filters.append(MEPAmendment.element_type == element_type.lower())
    if published_from:
        filters.append(MEPAmendment.document_date >= published_from)
    if published_to:
        filters.append(MEPAmendment.document_date <= published_to)
    if updated_from:
        filters.append(MEPAmendment.scraped_at >= updated_from)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            MEPAmendment.element_reference.ilike(like),
            MEPAmendment.proposed_text.ilike(like),
        ))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(MEPAmendment.document_date.desc().nullslast(), MEPAmendment.amendment_number.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    data = [
        AmendmentItem(
            id=str(r.id),
            procedure_reference=r.procedure_reference,
            committee_code=r.committee_code,
            pe_reference=r.pe_reference,
            amendment_number=r.amendment_number,
            author_names=list(r.author_names or []),
            political_group=r.political_group,
            on_behalf_of_group=bool(r.on_behalf_of_group),
            element_type=r.element_type,
            element_number=r.element_number,
            element_reference=r.element_reference,
            amendment_type=r.amendment_type,
            original_text=r.original_text,
            proposed_text=r.proposed_text,
            justification=r.justification,
            source_url=r.source_url,
            document_date=r.document_date,
            scraped_at=r.scraped_at,
        )
        for r in rows
    ]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from,
    )


# ============================================================================
# /votes — EP roll-call votes
# ============================================================================


class VoteItem(BaseModel):
    id: str
    htv_id: int
    timestamp: datetime
    display_title: str
    reference: Optional[str] = None
    description: Optional[str] = None
    procedure_reference: Optional[str] = None
    procedure_type: Optional[str] = None
    procedure_stage: Optional[str] = None
    amendment_number: Optional[str] = None
    is_main: bool = False
    count_for: int = 0
    count_against: int = 0
    count_abstention: int = 0
    count_did_not_vote: int = 0
    result: Optional[str] = None
    texts_adopted_reference: Optional[str] = None
    updated_at: Optional[datetime] = None
    # 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(
        None,
        description="Citizen URL — HowTheyVote vote page (https://howtheyvote.eu/votes/{htv_id}) — real, specific.",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text composition: title + reference + procedure + tallies + result.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML composition of the same fields.",
    )
    document_date: Optional[date] = Field(
        None,
        description="Vote date (date-only view of timestamp).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru last refreshed this vote (alias of updated_at).",
    )


def _vote_row_to_item(r: "EPVote") -> "VoteItem":
    """Build a VoteItem with the 5 mandatory v1 datapoints populated."""
    import html as _html
    title = r.display_title or (r.reference or "")
    lines = [title]
    parts_html = [f"<h2>{_html.escape(title)}</h2>"]
    for k, v in [
        ("HowTheyVote ID", r.htv_id),
        ("Reference", r.reference),
        ("Procedure", r.procedure_reference),
        ("Stage", r.procedure_stage),
        ("Amendment", r.amendment_number),
        ("For", r.count_for),
        ("Against", r.count_against),
        ("Abstention", r.count_abstention),
        ("Did not vote", r.count_did_not_vote),
        ("Result", r.result.value if hasattr(r.result, "value") else r.result),
        ("Texts adopted", r.texts_adopted_reference),
        ("Vote timestamp", r.timestamp),
    ]:
        if v in (None, "", 0) and k not in ("For", "Against", "Abstention", "Did not vote"):
            continue
        lines.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    public_url = f"https://howtheyvote.eu/votes/{r.htv_id}" if r.htv_id else None
    return VoteItem(
        id=str(r.id),
        htv_id=r.htv_id,
        timestamp=r.timestamp,
        display_title=r.display_title,
        reference=r.reference,
        description=r.description,
        procedure_reference=r.procedure_reference,
        procedure_type=r.procedure_type.value if hasattr(r.procedure_type, "value") else (str(r.procedure_type) if r.procedure_type else None),
        procedure_stage=r.procedure_stage,
        amendment_number=r.amendment_number,
        is_main=bool(r.is_main),
        count_for=int(r.count_for or 0),
        count_against=int(r.count_against or 0),
        count_abstention=int(r.count_abstention or 0),
        count_did_not_vote=int(r.count_did_not_vote or 0),
        result=r.result.value if hasattr(r.result, "value") else (str(r.result) if r.result else None),
        texts_adopted_reference=r.texts_adopted_reference,
        updated_at=r.updated_at,
        # 5 mandatory datapoints
        public_url=public_url,
        body_txt="\n".join(lines),
        body_html="<article>" + "".join(parts_html) + "</article>",
        document_date=r.timestamp.date() if hasattr(r.timestamp, "date") and r.timestamp else None,
        creation_date=r.updated_at or r.timestamp,
    )


@votes_router.get(
    "",
    response_model=PaginatedResponse[VoteItem],
    summary="EP roll-call votes — plenary results with tallies (HowTheyVote)",
    description="""**What it does**
Roll-call vote results from European Parliament plenary sittings, sourced from HowTheyVote.eu (the open-source civic-tech mirror of the EP's official register of votes). Each row carries the vote title, procedure reference, EP committee report number, FOR/AGAINST/ABSTENTION/DID-NOT-VOTE tallies, ADOPTED/REJECTED result, and the timestamp.

Filterable by procedure, vote reference, main-vote-only, result, full-text search, and incremental sync.

**When to use it**
- Track how a specific legislative file was voted in plenary.
- Aggregate vote tallies by procedure or rapporteur.
- Build dashboards of EP plenary activity.
- Link to per-MEP voting positions via `/api/v1/votes/{vote_id}/records`.

**Input**
- `procedure_reference` — e.g. `2024/0123(COD)`.
- `reference` — e.g. `A10-0142/2026` (the EP committee report being voted on).
- `is_main` — true to exclude amendment-level votes.
- `result` — `ADOPTED | REJECTED | UNKNOWN`.
- `q` — substring on `display_title`.
- `published_from` / `published_to` — timestamp range.
- `updated_from` — incremental-sync upper-bound.
- `limit` (1–100, default 50), `page` (default 1).

**Try it**
```
GET /api/v1/votes?procedure_reference=2024%2F0106(COD)
GET /api/v1/votes?is_main=true&result=ADOPTED&limit=20
```

**You get back**
Paginated `VoteItem` envelope. `public_url` points to the specific HowTheyVote vote page (`https://howtheyvote.eu/votes/{htv_id}`). All 5 mandatory v1 datapoints present per row.""",
)
async def list_votes(
    request: Request,
    procedure_reference: Optional[str] = Query(None),
    reference: Optional[str] = Query(None, description="Vote reference (e.g. A10-XXXX/2026)"),
    is_main: Optional[bool] = Query(None),
    result: Optional[str] = Query(None, description="ADOPTED | REJECTED | UNKNOWN"),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None, description="timestamp >= value"),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[VoteItem]:
    query = db.query(EPVote)
    filters = []
    if procedure_reference:
        filters.append(EPVote.procedure_reference == procedure_reference)
    if reference:
        filters.append(EPVote.reference == reference)
    if is_main is not None:
        filters.append(EPVote.is_main == is_main)
    if result:
        try:
            filters.append(EPVote.result == VoteResult(result.upper()))
        except ValueError:
            pass
    if q:
        filters.append(EPVote.display_title.ilike(f"%{q}%"))
    if published_from:
        filters.append(EPVote.timestamp >= published_from)
    if published_to:
        filters.append(EPVote.timestamp <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        filters.append(EPVote.updated_at >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = query.order_by(EPVote.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()
    data = [_vote_row_to_item(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from,
    )


class MemberVoteItem(BaseModel):
    member_id: str
    position: str
    country_code: str
    group_code: str
    # 5 mandatory Brubru v1 datapoints. /votes/{vote_id}/records is a per-MEP
    # subview of a single vote; the vote-level URL applies to every row.
    public_url: Optional[str] = Field(
        None,
        description="The parent vote's HowTheyVote page (so each row links back to the vote context).",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text composition: MEP id + position + country + group.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML composition.",
    )
    document_date: Optional[date] = Field(
        None,
        description="Date of the parent vote.",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When the parent vote was last refreshed.",
    )


@votes_router.get(
    "/{vote_id}/records",
    response_model=PaginatedResponse[MemberVoteItem],
    summary="Per-MEP voting records for a single roll-call vote",
    description="""**What it does**
Per-MEP vote positions (FOR / AGAINST / ABSTENTION / DID_NOT_VOTE) for one specific roll-call vote. Joins `ep_member_votes` to `ep_votes` so callers can see exactly how each named MEP voted, with their country and political-group code at the moment of the vote.

**When to use it**
- Build a "how did my MEP vote?" widget for any specific roll-call.
- Aggregate per-group or per-country breakdowns.
- Feed group-cohesion analysis or position-prediction models.

**Input**
- `vote_id` (path) — `ep_votes.id` (UUID).
- `group` — EP group code (e.g. `EPP`, `S&D`, `Renew`).
- `country` — ISO-2 (e.g. `DE`, `FR`).
- `position` — `FOR | AGAINST | ABSTENTION | DID_NOT_VOTE`.
- `limit` (1–500, default 100), `page` (default 1).

**Try it**
```
GET /api/v1/votes/{vote_id}/records?group=EPP
GET /api/v1/votes/{vote_id}/records?country=DE&position=AGAINST
```

**You get back**
Paginated `MemberVoteItem` envelope. `public_url` on each row points to the parent vote's HowTheyVote page. All 5 mandatory v1 datapoints present per row.""",
)
async def list_member_votes(
    vote_id: str,
    group: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    position: Optional[str] = Query(None, description="FOR | AGAINST | ABSTENTION | DID_NOT_VOTE"),
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[MemberVoteItem]:
    vote = db.query(EPVote).filter(EPVote.id == vote_id).first()
    if not vote:
        raise HTTPException(status_code=404, detail={
            "error": f"Vote {vote_id} not found", "reason_code": "not_found",
            "resource": "vote", "id": vote_id,
        })
    query = db.query(EPMemberVote).filter(EPMemberVote.vote_id == vote_id)
    if group:
        query = query.filter(EPMemberVote.group_code == group.upper())
    if country:
        query = query.filter(EPMemberVote.country_code == country.upper())
    if position:
        query = query.filter(EPMemberVote.position == position.upper())
    total = query.count()
    rows = query.offset((page - 1) * limit).limit(limit).all()
    parent_url = f"https://howtheyvote.eu/votes/{vote.htv_id}" if vote.htv_id else None
    parent_date = vote.timestamp.date() if hasattr(vote.timestamp, "date") and vote.timestamp else None
    import html as _html
    data = []
    for r in rows:
        position = r.position.value if hasattr(r.position, "value") else str(r.position)
        lines = [
            f"MEP {r.member_id}",
            f"Position: {position}",
            f"Country: {r.country_code}",
            f"Group: {r.group_code}",
        ]
        parts_html = [
            f"<p><strong>MEP id:</strong> {_html.escape(str(r.member_id))}</p>",
            f"<p><strong>Position:</strong> {_html.escape(position)}</p>",
            f"<p><strong>Country:</strong> {_html.escape(r.country_code or '')}</p>",
            f"<p><strong>Group:</strong> {_html.escape(r.group_code or '')}</p>",
        ]
        data.append(MemberVoteItem(
            member_id=str(r.member_id),
            position=position,
            country_code=r.country_code,
            group_code=r.group_code,
            public_url=parent_url,
            body_txt="\n".join(lines),
            body_html="<article>" + "".join(parts_html) + "</article>",
            document_date=parent_date,
            creation_date=vote.updated_at,
        ))
    return build_envelope(data, total=total, page=page, limit=limit)


@votes_router.get(
    "/{vote_id}",
    response_model=VoteItem,
    summary="Single EP roll-call vote detail",
    description="""**What it does**
Returns full metadata for one EP roll-call vote, including title, procedure, committee report, tallies, result, and the citizen-facing HowTheyVote URL.

**Input**
- `vote_id` (path) — `ep_votes.id` (UUID).

**Try it**
```
GET /api/v1/votes/{vote_id}
```

**You get back**
A `VoteItem` with all 5 mandatory v1 datapoints. `public_url` resolves to `https://howtheyvote.eu/votes/{htv_id}` — the public vote page with per-MEP breakdown, country chart, and group cohesion.""",
)
async def get_vote_detail(
    vote_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> VoteItem:
    r = db.query(EPVote).filter(EPVote.id == vote_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Vote {vote_id} not found", "reason_code": "not_found",
            "resource": "vote", "id": vote_id,
        })
    return _vote_row_to_item(r)


# ============================================================================
# /ep-documents — Unified cross-committee EP documents view
# ============================================================================


class EPDocumentItem(BaseModel):
    id: str
    source: str  # "committee_work" | "amendment_document" | "mep_amendment_set" | "text_adopted"
    document_type: str  # "draft_report" | "amendments" | "report" | "opinion" | "minutes" | ...
    committee_code: Optional[str] = None
    procedure_reference: Optional[str] = None
    pe_reference: Optional[str] = None
    title: str
    rapporteur_name: Optional[str] = None
    document_date: Optional[date] = None
    document_url: Optional[str] = None
    total_amendments: Optional[int] = None
    last_updated: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of document_url).")
    body_txt: Optional[str] = Field(None, description="Null for this list endpoint — fetch body via the per-source detail endpoints (committee minutes, amendment docs).")
    body_html: Optional[str] = Field(None, description="Null for this list endpoint.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row (alias of last_updated for this union view).")


@ep_documents_router.get(
    "",
    response_model=PaginatedResponse[EPDocumentItem],
    summary="Cross-committee unified EP documents view",
    description=(
        "Unifies the four EP document streams: committee_work (work items), "
        "amendment_documents (PR/AM/RD/AD/PA), and texts_adopted. Filter "
        "across all of them by committee, procedure, document type, and date."
    ),
)
async def list_ep_documents(
    request: Request,
    committee: Optional[str] = Query(None),
    procedure_reference: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None, description="draft_report | report | amendments | opinion | minutes | resolution"),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EPDocumentItem]:
    items: List[EPDocumentItem] = []

    # Branch 1: amendment_documents (PR=draft report, AM=amendments, RD=draft recommendation, AD=opinion, PA=draft opinion)
    AD_TYPE_MAP = {
        "PR": "draft_report",
        "AM": "amendments",
        "RD": "draft_recommendation",
        "AD": "opinion",
        "PA": "draft_opinion",
    }
    REVERSE_AD_MAP = {v: k for k, v in AD_TYPE_MAP.items()}
    aq = db.query(AmendmentDocument)
    if committee:
        aq = aq.filter(AmendmentDocument.committee_code == committee.upper())
    if procedure_reference:
        aq = aq.filter(AmendmentDocument.procedure_reference == procedure_reference)
    if document_type and document_type in REVERSE_AD_MAP:
        aq = aq.filter(AmendmentDocument.document_type == REVERSE_AD_MAP[document_type])
    if published_from:
        aq = aq.filter(AmendmentDocument.document_date >= published_from)
    if published_to:
        aq = aq.filter(AmendmentDocument.document_date <= published_to)
    if updated_from:
        aq = aq.filter(AmendmentDocument.scraped_at >= updated_from)

    a_total = aq.count()
    a_rows = aq.order_by(AmendmentDocument.document_date.desc().nullslast()).limit(limit * 4).all()
    lc_lookup = _build_lc_lookup(db, [r.procedure_reference for r in a_rows])
    for r in a_rows:
        fallback = f"{AD_TYPE_MAP.get(r.document_type, r.document_type or 'doc')} for {r.procedure_reference} ({r.committee_code})"
        items.append(EPDocumentItem(
            id=str(r.id),
            source="amendment_document",
            document_type=AD_TYPE_MAP.get(r.document_type, r.document_type or "unknown"),
            committee_code=r.committee_code,
            procedure_reference=r.procedure_reference,
            pe_reference=r.pe_reference,
            title=_enrich_doc_title(fallback, r.procedure_reference, lc_lookup),
            rapporteur_name=r.rapporteur_name,
            document_date=r.document_date,
            document_url=r.doceo_url,
            total_amendments=r.total_amendments,
            last_updated=r.scraped_at,
            public_url=r.doceo_url,
            creation_date=r.scraped_at,
        ))

    # Branch 2: committee_work items
    cq = db.query(CommitteeWorkItem)
    if committee:
        cq = cq.filter(CommitteeWorkItem.committee_code == committee.upper())
    if procedure_reference:
        cq = cq.filter(CommitteeWorkItem.procedure_ref == procedure_reference)
    if q:
        cq = cq.filter(CommitteeWorkItem.title.ilike(f"%{q}%"))
    if updated_from:
        cq = cq.filter(CommitteeWorkItem.last_updated >= updated_from)
    c_total = cq.count()
    c_rows = cq.order_by(CommitteeWorkItem.last_updated.desc().nullslast()).limit(limit * 4).all()
    for r in c_rows:
        items.append(EPDocumentItem(
            id=str(r.id),
            source="committee_work",
            document_type=(r.stage or r.status or "work_item") if isinstance(r.stage, str) else "work_item",
            committee_code=r.committee_code,
            procedure_reference=r.procedure_ref,
            title=r.title or "",
            rapporteur_name=r.rapporteur_name,
            document_date=r.vote_date.date() if r.vote_date else None,
            document_url=r.ep_page_url or r.source_url or r.eurlex_url,
            last_updated=r.last_updated,
            public_url=r.ep_page_url or r.source_url or r.eurlex_url,
            creation_date=r.last_updated,
        ))

    # Sort union by document_date desc and apply page slice.
    # `total` reflects the FULL DB count across both source tables (honest).
    items.sort(key=lambda x: x.document_date or date.min, reverse=True)
    total = a_total + c_total
    page_data = items[(page - 1) * limit : page * limit]
    return build_envelope(
        page_data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from,
    )


# ============================================================================
# /press-releases — first-class wrapper over publications.category=press_release
# ============================================================================


class PressReleaseItem(BaseModel):
    id: str
    institution_slug: str
    source_slug: str
    title: str
    summary: Optional[str] = None
    url: str
    language: str = "en"
    published_date: Optional[datetime] = None
    policy_areas: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    # Body fields populated from html_content (the source HTML stripped of
    # nav/footer/scripts during ingestion).
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # Deprecated alias kept one release; equals body_text or body_html.
    body: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — alias of url (the press-release page on the institutional site).")
    document_date: Optional[date] = Field(None, description="Publication date of the press release (date-only view of published_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


@press_releases_router.get(
    "",
    response_model=PaginatedResponse[PressReleaseItem],
    summary="EU institutional press releases (first-class)",
    description=(
        "First-class endpoint over institutional_publications filtered to "
        "category=press_release / news. Wraps the same data as "
        "/publications?category=press_release but with a stable name."
    ),
)
async def list_press_releases(
    request: Request,
    institution_slug: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    policy_area: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PressReleaseItem]:
    query = db.query(InstitutionalPublication).filter(
        or_(
            InstitutionalPublication.category == "press_release",
            InstitutionalPublication.category == "news",
            InstitutionalPublication.category == "press",
        )
    )
    if institution_slug:
        query = query.filter(InstitutionalPublication.institution_slug == institution_slug)
    if policy_area:
        query = query.filter(InstitutionalPublication.policy_areas.any(policy_area))
    if published_from:
        query = query.filter(InstitutionalPublication.published_date >= published_from)
    if published_to:
        query = query.filter(InstitutionalPublication.published_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        query = query.filter(InstitutionalPublication.fetched_at >= updated_from)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            InstitutionalPublication.title.ilike(like),
            InstitutionalPublication.summary.ilike(like),
        ))

    total = query.count()
    rows = (
        query.order_by(InstitutionalPublication.published_date.desc().nullslast())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = []
    for r in rows:
        body_html, body_text, has_body = body_from_html(r.html_content, threshold=body_threshold)
        data.append(PressReleaseItem(
            id=str(r.id),
            institution_slug=r.institution_slug,
            source_slug=r.source_slug,
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
            # 5 mandatory datapoints
            public_url=r.url,
            document_date=r.published_date.date() if hasattr(r.published_date, "date") and r.published_date else None,
            creation_date=getattr(r, "fetched_at", None) or getattr(r, "first_seen", None),
        ))
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from,
    )


# ============================================================================
# /reports & /opinions — semantic aliases over the unified ep_documents view
# ============================================================================


@reports_router.get(
    "",
    response_model=PaginatedResponse[EPDocumentItem],
    summary="EP committee reports (draft + final)",
)
async def list_reports(
    request: Request,
    committee: Optional[str] = Query(None),
    procedure_reference: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EPDocumentItem]:
    aq = db.query(AmendmentDocument).filter(AmendmentDocument.document_type.in_(["PR", "RD"]))
    if committee:
        aq = aq.filter(AmendmentDocument.committee_code == committee.upper())
    if procedure_reference:
        aq = aq.filter(AmendmentDocument.procedure_reference == procedure_reference)
    if published_from:
        aq = aq.filter(AmendmentDocument.document_date >= published_from)
    if published_to:
        aq = aq.filter(AmendmentDocument.document_date <= published_to)

    total = aq.count()
    rows = aq.order_by(AmendmentDocument.document_date.desc().nullslast()).offset((page - 1) * limit).limit(limit).all()

    AD_TYPE_MAP = {"PR": "draft_report", "RD": "draft_recommendation"}
    lc_lookup = _build_lc_lookup(db, [r.procedure_reference for r in rows])
    data = []
    for r in rows:
        fallback = f"{AD_TYPE_MAP.get(r.document_type, 'report')} for {r.procedure_reference} ({r.committee_code})"
        data.append(EPDocumentItem(
            id=str(r.id),
            source="amendment_document",
            document_type=AD_TYPE_MAP.get(r.document_type, "report"),
            committee_code=r.committee_code,
            procedure_reference=r.procedure_reference,
            pe_reference=r.pe_reference,
            title=_enrich_doc_title(fallback, r.procedure_reference, lc_lookup),
            rapporteur_name=r.rapporteur_name,
            document_date=r.document_date,
            document_url=r.doceo_url,
            total_amendments=r.total_amendments,
            last_updated=r.scraped_at,
        ))
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to)


@opinions_router.get(
    "",
    response_model=PaginatedResponse[EPDocumentItem],
    summary="EP committee opinions (AD + PA)",
)
async def list_opinions(
    request: Request,
    committee: Optional[str] = Query(None),
    procedure_reference: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EPDocumentItem]:
    aq = db.query(AmendmentDocument).filter(AmendmentDocument.document_type.in_(["AD", "PA"]))
    if committee:
        aq = aq.filter(AmendmentDocument.committee_code == committee.upper())
    if procedure_reference:
        aq = aq.filter(AmendmentDocument.procedure_reference == procedure_reference)
    if published_from:
        aq = aq.filter(AmendmentDocument.document_date >= published_from)
    if published_to:
        aq = aq.filter(AmendmentDocument.document_date <= published_to)

    total = aq.count()
    rows = aq.order_by(AmendmentDocument.document_date.desc().nullslast()).offset((page - 1) * limit).limit(limit).all()

    AD_TYPE_MAP = {"AD": "opinion", "PA": "draft_opinion"}
    lc_lookup = _build_lc_lookup(db, [r.procedure_reference for r in rows])
    data = []
    for r in rows:
        fallback = f"{AD_TYPE_MAP.get(r.document_type, 'opinion')} for {r.procedure_reference} ({r.committee_code})"
        title = _enrich_doc_title(fallback, r.procedure_reference, lc_lookup)
        # Compose body from the structured row. The full PDF body lives on
        # the amendment_documents/{id} detail surface — partners hitting
        # /opinions get the metadata view with a readable summary.
        body_lines = [title]
        if r.committee_code:
            body_lines.append(f"Committee: {r.committee_code}")
        if r.rapporteur_name:
            body_lines.append(f"Rapporteur: {r.rapporteur_name}")
        if r.procedure_reference:
            body_lines.append(f"Procedure: {r.procedure_reference}")
        if r.pe_reference:
            body_lines.append(f"PE reference: {r.pe_reference}")
        if r.document_date:
            body_lines.append(f"Document date: {r.document_date}")
        if r.total_amendments is not None:
            body_lines.append(f"Total amendments: {r.total_amendments}")
        if r.doceo_url:
            body_lines.append(f"Source: {r.doceo_url}")
        body_txt = "\n".join(body_lines)
        body_html = (
            "<article><h2>" + title + "</h2>"
            + "".join(f"<p><strong>{k}:</strong> {v}</p>" for line in body_lines[1:]
                      for k, v in [line.split(": ", 1)] if ": " in line)
            + "</article>"
        )
        data.append(EPDocumentItem(
            id=str(r.id),
            source="amendment_document",
            document_type=AD_TYPE_MAP.get(r.document_type, "opinion"),
            committee_code=r.committee_code,
            procedure_reference=r.procedure_reference,
            pe_reference=r.pe_reference,
            title=title,
            rapporteur_name=r.rapporteur_name,
            document_date=r.document_date,
            document_url=r.doceo_url,
            total_amendments=r.total_amendments,
            last_updated=r.scraped_at,
            # 5 mandatory datapoints
            public_url=r.doceo_url,
            body_txt=body_txt,
            body_html=body_html,
            creation_date=r.scraped_at,
        ))
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to)
