"""
The five Eurogroup endpoints (the informal body of euro-area finance ministers).
Backed by the shared ``council_register_items`` cache (migration 109), populated
by ``scripts/sync_council_register.py`` from consilium.europa.eu.

    /eurogroup-meetings        Eurogroup meetings (agenda + Main results)
    /eurogroup-documents       Eurogroup document register (agendas, summing-up letters)
    /eurogroup-work-programme   the Eurogroup work programme
    /eurogroup-members         members of the Eurogroup
    /eurogroup-about           how the Eurogroup works (institutional reference)

Every row carries the five mandatory v1 datapoints, with body_txt/body_html
always present. Shares the schema + list/detail helpers with the Council-of-the-EU
``council-register`` surface.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse
from .council_register import CouncilRegisterItemModel, _list, _detail


meetings_router = APIRouter(prefix="/eurogroup-meetings", tags=["v1-eurogroup-meetings"])
documents_router = APIRouter(prefix="/eurogroup-documents", tags=["v1-eurogroup-documents"])
work_programme_router = APIRouter(prefix="/eurogroup-work-programme", tags=["v1-eurogroup-work-programme"])
members_router = APIRouter(prefix="/eurogroup-members", tags=["v1-eurogroup-members"])
about_router = APIRouter(prefix="/eurogroup-about", tags=["v1-eurogroup-about"])


def _DESC(what: str, when: str, gives: str, example: str) -> str:
    return f"""**What it does**
{what}

**When to use it**
{when}

**Input**
- `q` — substring search over title / body.
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
Synced from consilium.europa.eu (fresh-context browser fetch) + the un-walled data.consilium PDF store. Bodies are composed/captured at scrape time and stored, so the body is always present and the API never scrapes on the request path."""


def _params(
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
):
    return dict(q=q, council_configuration=None, interinstitutional_ref=None,
                published_from=published_from, published_to=published_to,
                updated_from=updated_from, updated_to=updated_to, limit=limit, page=page)


# --------------------------------------------------------------------------- #
# 1. Eurogroup meetings                                                       #
# --------------------------------------------------------------------------- #
@meetings_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Eurogroup meetings — meetings of euro-area finance ministers",
    description=_DESC(
        "Returns Eurogroup meetings (the euro-area finance ministers), with date and a body that includes the published 'Main results' outcome narrative for recent meetings — macroeconomic discussions, the digital euro, euro-area competitiveness, and more.",
        "To track what euro-area finance ministers discussed and concluded — the political steer on euro-area economic policy.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of Eurogroup meetings.",
        "GET /api/v1/eurogroup-meetings",
    ),
)
async def list_eurogroup_meetings(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "eurogroup_meeting", op_title="Eurogroup meetings", op_type="Eurogroup meeting", **params)


@meetings_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Eurogroup meeting by id — full body (agenda + outcomes)",
    description="Fetch a single Eurogroup meeting by its Brubru UUID. Returns the five datapoints. 404 with `reason_code: not_found` if absent.",
)
async def get_eurogroup_meeting(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "eurogroup_meeting")


# --------------------------------------------------------------------------- #
# 2. Eurogroup documents                                                      #
# --------------------------------------------------------------------------- #
@documents_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Eurogroup documents — the Eurogroup document register",
    description=_DESC(
        "Returns documents from the Eurogroup document register — draft agendas, annotated agendas, summing-up letters, lists of participants, and the President's remarks — each with date and a link to the PDF.",
        "To read the Eurogroup's own meeting documents, especially the summing-up letters that record the outcome of each meeting.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of Eurogroup documents.",
        "GET /api/v1/eurogroup-documents?q=summing-up",
    ),
)
async def list_eurogroup_documents(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "eurogroup_document", op_title="Eurogroup documents", op_type="Eurogroup document", **params)


@documents_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Eurogroup document by id — full body",
    description="Fetch a single Eurogroup document by its Brubru UUID. Returns the five datapoints; `pdf_url` is the document PDF. 404 if absent.",
)
async def get_eurogroup_document(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "eurogroup_document")


# --------------------------------------------------------------------------- #
# 3. Eurogroup work programme                                                 #
# --------------------------------------------------------------------------- #
@work_programme_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Eurogroup work programme",
    description=_DESC(
        "Returns the Eurogroup work programme — the rolling agenda of priorities the Eurogroup sets itself for the coming period — with the programme text and a link to the PDF.",
        "To see what the Eurogroup plans to work on, the forward calendar of euro-area economic policy themes.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` with the work-programme entry.",
        "GET /api/v1/eurogroup-work-programme",
    ),
)
async def list_eurogroup_work_programme(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "eurogroup_work_programme", op_title="Eurogroup work programme", op_type="Eurogroup work programme", **params)


@work_programme_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Eurogroup work-programme entry by id — full body",
    description="Fetch the Eurogroup work-programme entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_eurogroup_work_programme(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "eurogroup_work_programme")


# --------------------------------------------------------------------------- #
# 4. Eurogroup members                                                        #
# --------------------------------------------------------------------------- #
@members_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Members of the Eurogroup",
    description=_DESC(
        "Returns the members of the Eurogroup — the finance ministers of the euro-area member states, plus the Eurogroup President — including the inclusive-format membership, as a reference entry.",
        "As a reference for who sits in the Eurogroup, in both regular and inclusive formats.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of members entries.",
        "GET /api/v1/eurogroup-members",
    ),
)
async def list_eurogroup_members(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "eurogroup_member", op_title="Members of the Eurogroup", op_type="Eurogroup member", **params)


@members_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Eurogroup members entry by id — full body",
    description="Fetch a single Eurogroup members entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_eurogroup_member(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "eurogroup_member")


# --------------------------------------------------------------------------- #
# 5. About (institutional reference)                                          #
# --------------------------------------------------------------------------- #
@about_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="About the Eurogroup — how it works, the working group, transparency, history",
    description=_DESC(
        "Returns institutional reference pages about the Eurogroup — how it works, the Eurogroup Working Group (EWG) that prepares its meetings, its transparency arrangements, and its history — each with the page text as body.",
        "As background reference on the Eurogroup as a body and how it operates.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of reference entries.",
        "GET /api/v1/eurogroup-about",
    ),
)
async def list_eurogroup_about(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "eurogroup_about", op_title="About the Eurogroup", op_type="Eurogroup reference", **params)


@about_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Eurogroup reference page by id — full body",
    description="Fetch a single Eurogroup reference page by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_eurogroup_about(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "eurogroup_about")
