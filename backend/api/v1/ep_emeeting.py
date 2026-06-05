"""
/api/v1/emeeting — European Parliament eMeeting committee agendas + documents.

Backed by ``ep_emeeting_agendas`` (migration 110), populated by
``scripts/sync_ep_emeeting.py`` from the eMeeting open JSON API. One row per
committee OJ (agenda); the full item/document tree (draft reports, amendments,
voting lists, compromise amendments — each with multi-language PDF URLs) is in
``items``. ``procedure_refs`` (OEIL) + ``rapporteurs`` are denormalised for
filtering and for the MEUB anchor-linking layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.database import get_db
from models.ep_emeeting_agenda import EpEmeetingAgenda
from models.ep_emeeting_document import EpEmeetingDocument
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/emeeting", tags=["v1-emeeting"])
documents_router = APIRouter(prefix="/emeeting-documents", tags=["v1-emeeting-documents"])


class EmeetingAgendaItem(BaseModel):
    id: str
    oj_reference: str
    committee_code: str
    committee_name: Optional[str] = None
    meeting_reference: Optional[str] = None
    title: str
    procedure_refs: List[str] = Field(default_factory=list, description="OEIL procedure refs on the agenda (MEUB anchor).")
    rapporteurs: List[str] = Field(default_factory=list)
    document_count: int = 0
    event_reference: Optional[str] = Field(None, description="Ties the agenda to a calendar event.")
    agenda_pdf_url: Optional[str] = Field(None, description="The OJ agenda document PDF (EN).")
    items: List[Any] = Field(default_factory=list, description="Full item/document tree: items[].document_sets[].documents[].pdf_url.")
    source_url: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical URL — the agenda PDF (or eMeeting timeline).")
    body_txt: Optional[str] = Field(None, description="Plain-text rendering of the agenda — always populated.")
    body_html: Optional[str] = Field(None, description="HTML rendering of the agenda — always populated.")
    document_date: Optional[date] = Field(None, description="Meeting date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this agenda.")


def _to_item(r: EpEmeetingAgenda) -> EmeetingAgendaItem:
    return EmeetingAgendaItem(
        id=str(r.id),
        oj_reference=r.oj_reference,
        committee_code=r.committee_code,
        committee_name=r.committee_name,
        meeting_reference=r.meeting_reference,
        title=r.title,
        procedure_refs=list(r.procedure_refs or []),
        rapporteurs=list(r.rapporteurs or []),
        document_count=r.document_count or 0,
        event_reference=r.event_reference,
        agenda_pdf_url=r.agenda_pdf_url,
        items=list(r.items or []),
        source_url=r.source_url,
        public_url=r.public_url,
        body_txt=r.body_txt,
        body_html=r.body_html,
        document_date=r.meeting_date,
        creation_date=r.first_seen,
    )


@router.get(
    "",
    response_model=PaginatedResponse[EmeetingAgendaItem],
    summary="EP eMeeting — committee meeting agendas and their documents",
    description="""**What it does**
Returns European Parliament committee meeting agendas from eMeeting — one item per committee OJ (agenda). Each agenda carries its full item/document tree in `items`: every agenda item with its OEIL procedure reference, rapporteur(s), and the attached documents (draft reports, amendments, voting lists, compromise amendments) — each document with a direct multi-language PDF URL on the europarl meetdocs store.

**When to use it**
To pull the actual working documents for a committee file the moment they are tabled — the richest source of draft reports and amendments, keyed by the OEIL procedure reference so it joins straight to a tracked legislative file.

**Input**
- `committee` — committee code (AFCO, ENVI, IMCO, LIBE, ...).
- `procedure_ref` — an OEIL procedure reference (e.g. `2026/2013(INI)`); returns agendas whose items touch that file.
- `q` — substring search over title / body / OJ reference.
- `published_from`, `published_to` — bound on the meeting date.
- `updated_from`, `updated_to` — incremental sync on ingest time.
- `limit` (default 25, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/emeeting?committee=AFCO
GET /api/v1/emeeting?procedure_ref=2026/2013(INI)
```

**You get back**
A `PaginatedResponse[EmeetingAgendaItem]` envelope. Each agenda carries `procedure_refs`, `rapporteurs`, `document_count`, `agenda_pdf_url`, the full `items` tree (document PDF URLs live at `items[].document_sets[].documents[].pdf_url`), and the five envelope datapoints (`public_url`, `body_txt`, `body_html`, `document_date`, `creation_date`).

**Data freshness**
Synced from the eMeeting open JSON API (no scraping). Bodies are composed at ingest time, so the API never calls eMeeting on the request path.""",
)
async def list_emeeting_agendas(
    request: Request,
    committee: Optional[str] = Query(None, description="Committee code, e.g. AFCO."),
    procedure_ref: Optional[str] = Query(None, description="OEIL procedure ref, e.g. 2026/2013(INI)."),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EmeetingAgendaItem]:
    query = db.query(EpEmeetingAgenda)
    filters = []
    if committee:
        filters.append(EpEmeetingAgenda.committee_code == committee.upper())
    if procedure_ref:
        filters.append(EpEmeetingAgenda.procedure_refs.any(procedure_ref))
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        filters.append(or_(
            EpEmeetingAgenda.title.ilike(like),
            EpEmeetingAgenda.body_txt.ilike(like),
            EpEmeetingAgenda.oj_reference.ilike(like),
        ))
    if published_from:
        filters.append(EpEmeetingAgenda.meeting_date >= published_from)
    if published_to:
        filters.append(EpEmeetingAgenda.meeting_date <= published_to)
    if updated_from:
        filters.append(EpEmeetingAgenda.fetched_at >= updated_from)
    if updated_to:
        filters.append(EpEmeetingAgenda.fetched_at <= updated_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(EpEmeetingAgenda.meeting_date.desc().nullslast(),
                       EpEmeetingAgenda.first_seen.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [_to_item(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        op_core_title="EP eMeeting committee agendas",
        op_core_type="EP committee agenda",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/{item_id}",
    response_model=EmeetingAgendaItem,
    summary="One EP eMeeting agenda by id — full item/document tree",
    description="""**What it does**
Fetches a single EP committee agenda by its Brubru UUID, with the complete item/document tree: every agenda item, its OEIL procedure reference and rapporteur(s), and all attached documents with their multi-language PDF URLs.

**When to use it**
After locating an agenda via the list endpoint, to pull every document URL (draft reports, amendments, voting lists, compromise amendments) for that committee meeting.

**Input**
- `item_id` (path) — the Brubru-internal UUID from the list endpoint's `id`.

**Try it**
```
GET /api/v1/emeeting/{item_id}
```

**You get back**
A single `EmeetingAgendaItem` with the five datapoints filled and the full `items` tree, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Synced from the eMeeting open JSON API.""",
)
async def get_emeeting_agenda(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> EmeetingAgendaItem:
    row = db.query(EpEmeetingAgenda).filter(EpEmeetingAgenda.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={
            "reason_code": "not_found", "message": f"No eMeeting agenda with id {item_id}"})
    return _to_item(row)


# --------------------------------------------------------------------------- #
# eMeeting documents (document-level — every PDF, all languages)              #
# --------------------------------------------------------------------------- #
class EmeetingDocumentItem(BaseModel):
    id: str
    gepro_code: Optional[str] = Field(None, description="Raw eMeeting document type code: PR, AM, DV, RR, AD, OJ, PV ...")
    doc_kind: Optional[str] = Field(None, description="Normalised kind: draft_report, amendment, voting_list, compromise_amendments, agenda, minutes, report, opinion, adopted_text, miscellaneous.")
    gepro_description: Optional[str] = None
    reference: Optional[str] = Field(None, description="PE-number, e.g. PE784.388.")
    visual_reference: Optional[str] = None
    committee_code: Optional[str] = None
    committee_name: Optional[str] = None
    oj_reference: Optional[str] = Field(None, description="The agenda this document sits on.")
    agenda_id: Optional[str] = None
    dossier_reference: Optional[str] = None
    procedure_ref: Optional[str] = Field(None, description="OEIL procedure ref (MEUB anchor).")
    item_title: Optional[str] = None
    document_set_type: Optional[str] = None
    rapporteurs: List[str] = Field(default_factory=list)
    pdf_urls: dict = Field(default_factory=dict, description="{lang_code: url} — every language PDF on the meetdocs store.")
    languages: List[str] = Field(default_factory=list)
    # 5 mandatory datapoints
    public_url: Optional[str] = Field(None, description="The EN PDF (or first available).")
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="Meeting date.")
    creation_date: Optional[datetime] = None


def _to_doc(r: EpEmeetingDocument) -> EmeetingDocumentItem:
    return EmeetingDocumentItem(
        id=str(r.id),
        gepro_code=r.gepro_code,
        doc_kind=r.doc_kind,
        gepro_description=r.gepro_description,
        reference=r.reference,
        visual_reference=r.visual_reference,
        committee_code=r.committee_code,
        committee_name=r.committee_name,
        oj_reference=r.oj_reference,
        agenda_id=str(r.agenda_id) if r.agenda_id else None,
        dossier_reference=r.dossier_reference,
        procedure_ref=r.procedure_ref,
        item_title=r.item_title,
        document_set_type=r.document_set_type,
        rapporteurs=list(r.rapporteurs or []),
        pdf_urls=dict(r.pdf_urls or {}),
        languages=list(r.languages or []),
        public_url=r.pdf_url,
        body_txt=r.body_txt,
        body_html=r.body_html,
        document_date=r.meeting_date,
        creation_date=r.first_seen,
    )


@documents_router.get(
    "",
    response_model=PaginatedResponse[EmeetingDocumentItem],
    summary="EP eMeeting documents — every committee document with all-language PDF URLs",
    description="""**What it does**
Returns individual European Parliament committee documents from eMeeting — one item per document (draft reports, amendments, voting lists, compromise amendments, reports, opinions, agendas, minutes). Each carries the document type (`gepro_code`), the PE-number, the OEIL procedure reference, the rapporteur(s), and **every language PDF URL** (`pdf_urls` — up to ~24 languages) on the un-walled europarl meetdocs store.

**When to use it**
This is the document-level feed (far more rows than the agenda-level `/emeeting`). Use it to pull, say, every draft report (`gepro_code=PR`) or every amendment (`AM`) for a procedure, or all documents for a committee in a date range, with direct PDF links in any EU language.

**Input**
- `committee` — committee code (AFCO, ENVI, ...).
- `doc_kind` — the document category most people want: `draft_report`, `amendment`, `voting_list`, `compromise_amendments`, `agenda`, `minutes`, `report`, `opinion`, `adopted_text`, `miscellaneous`. (Voting lists and compromise amendments both come from the raw `DV` code and are split here by the document filename.)
- `gepro_code` — the raw eMeeting code if you prefer: `PR`, `AM`, `DV`, `RR`, `AD`, `OJ`, `PV`.
- `procedure_ref` — OEIL procedure reference (e.g. `2026/2013(INI)`).
- `q` — substring search over title / reference.
- `published_from`, `published_to` — bound on the meeting date.
- `updated_from`, `updated_to` — incremental sync on ingest time.
- `limit` (default 25, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/emeeting-documents?doc_kind=draft_report&committee=AFCO
GET /api/v1/emeeting-documents?doc_kind=voting_list
GET /api/v1/emeeting-documents?doc_kind=compromise_amendments
GET /api/v1/emeeting-documents?procedure_ref=2026/2013(INI)
```

**You get back**
A `PaginatedResponse[EmeetingDocumentItem]`. Each document carries `pdf_urls` (every language → URL), `reference`, `gepro_code`, `procedure_ref`, `rapporteurs`, and the five envelope datapoints (`public_url` = the EN PDF).

**Data freshness**
Synced from the eMeeting open JSON API. No scraping; bodies composed at ingest.""",
)
async def list_emeeting_documents(
    request: Request,
    committee: Optional[str] = Query(None),
    doc_kind: Optional[str] = Query(None, description="Normalised kind: draft_report | amendment | voting_list | compromise_amendments | agenda | minutes | report | opinion | adopted_text | miscellaneous."),
    gepro_code: Optional[str] = Query(None, description="Raw code: PR | AM | DV | RR | AD | OJ | PV"),
    procedure_ref: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EmeetingDocumentItem]:
    query = db.query(EpEmeetingDocument)
    filters = []
    if committee:
        filters.append(EpEmeetingDocument.committee_code == committee.upper())
    if doc_kind:
        filters.append(EpEmeetingDocument.doc_kind == doc_kind.lower())
    if gepro_code:
        filters.append(EpEmeetingDocument.gepro_code == gepro_code.upper())
    if procedure_ref:
        filters.append(EpEmeetingDocument.procedure_ref == procedure_ref)
    if q:
        from sqlalchemy import or_
        like = f"%{q}%"
        filters.append(or_(
            EpEmeetingDocument.title.ilike(like),
            EpEmeetingDocument.reference.ilike(like),
            EpEmeetingDocument.body_txt.ilike(like),
        ))
    if published_from:
        filters.append(EpEmeetingDocument.meeting_date >= published_from)
    if published_to:
        filters.append(EpEmeetingDocument.meeting_date <= published_to)
    if updated_from:
        filters.append(EpEmeetingDocument.fetched_at >= updated_from)
    if updated_to:
        filters.append(EpEmeetingDocument.fetched_at <= updated_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(EpEmeetingDocument.meeting_date.desc().nullslast(),
                       EpEmeetingDocument.first_seen.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [_to_doc(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        op_core_title="EP eMeeting documents",
        op_core_type="EP committee document",
        op_core_identifier=str(request.url),
    )


@documents_router.get(
    "/{item_id}",
    response_model=EmeetingDocumentItem,
    summary="One EP eMeeting document by id — all-language PDF URLs",
    description="""**What it does**
Fetches a single EP committee document by its Brubru UUID, with every language PDF URL and the full linking metadata (committee, meeting date, OEIL procedure ref, rapporteurs, dossier).

**Input**
- `item_id` (path) — the Brubru-internal UUID from the list endpoint's `id`.

**Try it**
```
GET /api/v1/emeeting-documents/{item_id}
```

**You get back**
A single `EmeetingDocumentItem` with the five datapoints and `pdf_urls` (all languages), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Synced from the eMeeting open JSON API.""",
)
async def get_emeeting_document(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> EmeetingDocumentItem:
    row = db.query(EpEmeetingDocument).filter(EpEmeetingDocument.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={
            "reason_code": "not_found", "message": f"No eMeeting document with id {item_id}"})
    return _to_doc(row)
