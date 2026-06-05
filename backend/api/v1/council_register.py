"""
The eight Council-of-the-EU register endpoints, backed by ``council_register_items``
(migration 109), populated by ``scripts/sync_council_register.py`` from
consilium.europa.eu (fresh-context Playwright) + the un-walled data.consilium PDF
store.

    /council-meetings            Council ministerial meetings (agenda + outcomes)
    /council-voting-results      results of public Council votes (+ procedure ref)
    /council-register            latest documents in the Council public register
    /council-oj-agendas          OJ-of-the-Council meeting agendas
    /council-preparatory-bodies  COREPER + working-party meetings
    /council-press-releases      Council press releases and statements
    /council-research-papers     Council ART research papers
    /council-treaties-agreements Council treaties & agreements database

Every row carries the five mandatory v1 datapoints — ``public_url``, ``body_txt``,
``body_html``, ``document_date``, ``creation_date`` — composed at scrape time and
stored, so the API never scrapes on the request path and the body is always present.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.council_register_item import CouncilRegisterItem
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


# --------------------------------------------------------------------------- #
# Routers                                                                     #
# --------------------------------------------------------------------------- #
meetings_router = APIRouter(prefix="/council-meetings", tags=["v1-council-meetings"])
votes_router = APIRouter(prefix="/council-voting-results", tags=["v1-council-voting-results"])
register_router = APIRouter(prefix="/council-register", tags=["v1-council-register"])
oj_router = APIRouter(prefix="/council-oj-agendas", tags=["v1-council-oj-agendas"])
prep_router = APIRouter(prefix="/council-preparatory-bodies", tags=["v1-council-preparatory-bodies"])
press_router = APIRouter(prefix="/council-press-releases", tags=["v1-council-press-releases"])
research_router = APIRouter(prefix="/council-research-papers", tags=["v1-council-research-papers"])
treaties_router = APIRouter(prefix="/council-treaties-agreements", tags=["v1-council-treaties-agreements"])


# --------------------------------------------------------------------------- #
# Schema                                                                      #
# --------------------------------------------------------------------------- #
class CouncilRegisterItemModel(BaseModel):
    id: str
    content_type: str
    title: str
    council_configuration: Optional[str] = None
    document_ref: Optional[str] = Field(None, description="Council document number, e.g. 'ST 9727 2026 INIT'.")
    interinstitutional_ref: Optional[str] = Field(None, description="Interinstitutional procedure file, e.g. '2021/0297(COD)' — joins to OEIL.")
    subject_matters: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    pdf_url: Optional[str] = Field(None, description="Direct PDF on the un-walled data.consilium store, where present.")
    source_url: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — the consilium page or PDF.")
    body_txt: Optional[str] = Field(None, description="Plain-text body — always populated.")
    body_html: Optional[str] = Field(None, description="HTML body — composed from the real facts; null only for honest PDF-text rows.")
    document_date: Optional[date] = Field(None, description="Meeting / publication date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _to_item(r: CouncilRegisterItem) -> CouncilRegisterItemModel:
    return CouncilRegisterItemModel(
        id=str(r.id),
        content_type=r.content_type,
        title=r.title,
        council_configuration=r.council_configuration,
        document_ref=r.document_ref,
        interinstitutional_ref=r.interinstitutional_ref,
        subject_matters=list(r.subject_matters or []),
        policy_areas=list(r.policy_areas or []),
        pdf_url=r.pdf_url,
        source_url=r.source_url,
        public_url=r.public_url,
        body_txt=r.body_txt,
        body_html=r.body_html,
        document_date=r.document_date,
        creation_date=r.first_seen,
    )


# --------------------------------------------------------------------------- #
# Shared list / detail helpers                                                #
# --------------------------------------------------------------------------- #
def _list(
    db: Session,
    request: Request,
    content_type: str,
    *,
    q: Optional[str],
    council_configuration: Optional[str],
    interinstitutional_ref: Optional[str],
    published_from: Optional[date],
    published_to: Optional[date],
    updated_from: Optional[datetime],
    updated_to: Optional[datetime],
    limit: int,
    page: int,
    op_title: str,
    op_type: str,
) -> PaginatedResponse[CouncilRegisterItemModel]:
    query = db.query(CouncilRegisterItem).filter(CouncilRegisterItem.content_type == content_type)
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(
            CouncilRegisterItem.title.ilike(like),
            CouncilRegisterItem.body_txt.ilike(like),
            CouncilRegisterItem.document_ref.ilike(like),
        ))
    if council_configuration:
        filters.append(CouncilRegisterItem.council_configuration == council_configuration.upper())
    if interinstitutional_ref:
        filters.append(CouncilRegisterItem.interinstitutional_ref == interinstitutional_ref)
    if published_from:
        filters.append(CouncilRegisterItem.document_date >= published_from)
    if published_to:
        filters.append(CouncilRegisterItem.document_date <= published_to)
    if updated_from:
        filters.append(CouncilRegisterItem.fetched_at >= updated_from)
    if updated_to:
        filters.append(CouncilRegisterItem.fetched_at <= updated_to)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(CouncilRegisterItem.document_date.desc().nullslast(),
                       CouncilRegisterItem.first_seen.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    data = [_to_item(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        op_core_title=op_title, op_core_type=op_type,
        op_core_identifier=str(request.url),
    )


def _detail(db: Session, item_id: str, content_type: str) -> CouncilRegisterItemModel:
    row = (
        db.query(CouncilRegisterItem)
        .filter(CouncilRegisterItem.id == item_id,
                CouncilRegisterItem.content_type == content_type)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail={
            "reason_code": "not_found",
            "message": f"No {content_type.replace('_', ' ')} with id {item_id}",
        })
    return _to_item(row)


def _DESC(what: str, when: str, gives: str, example: str) -> str:
    return f"""**What it does**
{what}

**When to use it**
{when}

**Input**
- `q` — substring search over title / body / document number.
- `council_configuration` — GAC / FAC / ECOFIN / JHA / EPSCO / COMPET / TTE / AGRIFISH / ENVI / EYCS (where applicable).
- `interinstitutional_ref` — exact procedure file (e.g. `2021/0297(COD)`).
- `published_from`, `published_to` — bound on the document/meeting date.
- `updated_from`, `updated_to` — incremental sync on ingest time.
- `limit` (default 25, max 100), `page` (1-indexed).

**Try it**
```
{example}
```

**You get back**
{gives} Each item carries the five envelope datapoints: `public_url`, `body_txt`, `body_html`, `document_date`, `creation_date`.

**Data freshness**
Synced from consilium.europa.eu (fresh-context browser fetch) + the un-walled data.consilium PDF store. Bodies are composed at scrape time and stored, so the body is always present and the API never scrapes on the request path."""


# --------------------------------------------------------------------------- #
# 1. Council meetings                                                         #
# --------------------------------------------------------------------------- #
@meetings_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU meetings — ministerial meetings with agenda and outcomes",
    description=_DESC(
        "Returns Council of the EU ministerial meetings (the ten configurations) with their date, configuration, and a body composed from the meeting facts — including the published 'Main results' outcome narrative for recent meetings.",
        "To track what the Council decided in a given configuration (the co-legislator opposite the European Parliament), or to list upcoming and recent ministerial meetings by formation.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of meetings.",
        "GET /api/v1/council-meetings?council_configuration=ECOFIN",
    ),
)
async def list_council_meetings(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "meeting", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU meetings", op_type="Council meeting")


@meetings_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council meeting by id — full body (agenda + outcomes)",
    description="Fetch a single Council meeting by its Brubru UUID. Returns the same shape as the list endpoint with the five datapoints filled. 404 with `reason_code: not_found` if absent.",
)
async def get_council_meeting(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "meeting")


# --------------------------------------------------------------------------- #
# 2. Council voting results                                                   #
# --------------------------------------------------------------------------- #
@votes_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU voting results — results of public Council votes",
    description=_DESC(
        "Returns the results of public Council votes from the Council's public document register — the document number (ST/CM), the act being voted, the interinstitutional procedure file, the subject matters, and a link to the full voting-result PDF on the un-walled data.consilium store.",
        "To see how the Council voted on a legislative act (the per-member-state for/against/abstain tally is in the linked PDF), and to join a Council vote to its EP co-decision file via the interinstitutional reference.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of voting-result documents.",
        "GET /api/v1/council-voting-results?interinstitutional_ref=2021/0297(COD)",
    ),
)
async def list_council_voting_results(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "voting_result", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU voting results", op_type="Council voting result")


@votes_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council voting result by id — full body",
    description="Fetch a single Council voting-result document by its Brubru UUID. Returns the five datapoints; the per-member-state tally is in the linked PDF. 404 if absent.",
)
async def get_council_voting_result(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "voting_result")


# --------------------------------------------------------------------------- #
# 3. Council register (latest documents)                                      #
# --------------------------------------------------------------------------- #
@register_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU public register — latest documents",
    description=_DESC(
        "Returns the latest documents from the Council of the EU public document register — working-party notes, meeting documents (CM), Council notes (ST) — each with its document number, date, and a link to the PDF on the un-walled data.consilium store.",
        "To monitor what the Council's working parties and COREPER are circulating in near-real-time — the earliest signal of Council-side legislative activity.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of register documents.",
        "GET /api/v1/council-register?q=working+party",
    ),
)
async def list_council_register(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "register_doc", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU public register", op_type="Council register document")


@register_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council register document by id — full body",
    description="Fetch a single Council public-register document by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_council_register_document(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "register_doc")


# --------------------------------------------------------------------------- #
# 4. Council OJ agendas                                                        #
# --------------------------------------------------------------------------- #
@oj_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU OJ agendas — meeting agendas from the OJ of the Council",
    description=_DESC(
        "Returns the agendas of Council meetings as published in the OJ-of-the-Council section of the public register — one row per configuration meeting, with the agenda document number and a link to the agenda PDF.",
        "To read the formal agenda of a Council meeting (the legal record of what each configuration was convened to decide), ahead of or after the meeting.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of meeting-agenda documents.",
        "GET /api/v1/council-oj-agendas?published_from=2026-01-01",
    ),
)
async def list_council_oj_agendas(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "oj_agenda", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU OJ agendas", op_type="Council OJ agenda")


@oj_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council OJ agenda by id — full body",
    description="Fetch a single Council OJ meeting-agenda document by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_council_oj_agenda(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "oj_agenda")


# --------------------------------------------------------------------------- #
# 5. Council preparatory bodies                                               #
# --------------------------------------------------------------------------- #
@prep_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU preparatory bodies — COREPER and working-party meetings",
    description=_DESC(
        "Returns meetings of the Council's preparatory bodies — COREPER I/II and the working parties that do the technical groundwork before ministerial Council meetings.",
        "To track where on the Council ladder a file currently sits (working party -> COREPER -> Council), the most granular view of Council-side progress on a dossier.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of preparatory-body meetings.",
        "GET /api/v1/council-preparatory-bodies?q=land+transport",
    ),
)
async def list_council_preparatory_bodies(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "preparatory_body", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU preparatory bodies", op_type="Council preparatory body meeting")


@prep_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council preparatory-body meeting by id — full body",
    description="Fetch a single Council preparatory-body (COREPER / working party) meeting by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_council_preparatory_body(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "preparatory_body")


# --------------------------------------------------------------------------- #
# 6. Council press releases                                                    #
# --------------------------------------------------------------------------- #
@press_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU press releases — press releases and statements",
    description=_DESC(
        "Returns Council of the EU press releases and statements with their full text body — the official communication of Council decisions, agreements and ministerial remarks.",
        "To read the Council's own account of what it decided, in plain language, the moment it is published — the fastest authoritative narrative of Council outcomes.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of press releases.",
        "GET /api/v1/council-press-releases?q=defence",
    ),
)
async def list_council_press_releases(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "press_release", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU press releases", op_type="Council press release")


@press_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council press release by id — full text",
    description="Fetch a single Council press release by its Brubru UUID. The body is the full press-release text. Returns the five datapoints. 404 if absent.",
)
async def get_council_press_release(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "press_release")


# --------------------------------------------------------------------------- #
# 7. Council research papers                                                   #
# --------------------------------------------------------------------------- #
@research_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU research papers — ART (Analysis and Research Team) papers",
    description=_DESC(
        "Returns Council research papers published by the General Secretariat's Analysis and Research Team (ART) — foresight and analytical papers feeding Council strategic discussions. Each row links to the paper PDF.",
        "To mine the Council's in-house strategic analysis — an under-used source of where Council thinking is heading on cross-cutting themes.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of research papers. `public_url`/`pdf_url` point to the paper PDF.",
        "GET /api/v1/council-research-papers",
    ),
)
async def list_council_research_papers(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "research_paper", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU research papers", op_type="Council research paper")


@research_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council research paper by id — full body",
    description="Fetch a single Council ART research paper by its Brubru UUID. Returns the five datapoints; `pdf_url` is the paper PDF. 404 if absent.",
)
async def get_council_research_paper(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "research_paper")


# --------------------------------------------------------------------------- #
# 8. Council treaties & agreements                                            #
# --------------------------------------------------------------------------- #
@treaties_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Council of the EU treaties & agreements — the Council's treaties database",
    description=_DESC(
        "Returns a reference entry for the Council of the EU's Treaties and Agreements database (the Council is depositary for many EU international agreements), with the canonical search URL and the database description as the body.",
        "As a pointer to the authoritative Council database of EU treaties and international agreements when you need to look one up by name or party.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` with the treaties-database reference entry.",
        "GET /api/v1/council-treaties-agreements",
    ),
)
async def list_council_treaties_agreements(
    request: Request,
    q: Optional[str] = Query(None),
    council_configuration: Optional[str] = Query(None),
    interinstitutional_ref: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "treaty_agreement", q=q, council_configuration=council_configuration,
                 interinstitutional_ref=interinstitutional_ref, published_from=published_from,
                 published_to=published_to, updated_from=updated_from, updated_to=updated_to,
                 limit=limit, page=page, op_title="Council of the EU treaties and agreements", op_type="Council treaty/agreement")


@treaties_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Council treaties/agreements entry by id — full body",
    description="Fetch a single Council treaties-&-agreements entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_council_treaty_agreement(
    item_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "treaty_agreement")
