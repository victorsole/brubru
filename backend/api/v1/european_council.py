"""
The six European Council endpoints (the heads-of-state-or-government institution,
Art 15 TEU — distinct from the Council of the EU). Backed by the shared
``council_register_items`` cache (migration 109), populated by
``scripts/sync_council_register.py`` from consilium.europa.eu.

    /euco-conclusions       European Council conclusions (register, 2004-present)
    /euco-meetings          European Council summit meetings
    /euco-euro-summit       the Euro Summit (euro-area heads of state or government)
    /euco-strategic-agenda  the Strategic Agenda 2024-2029
    /euco-members           members of the European Council
    /euco-about             how the European Council works (institutional reference)

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


conclusions_router = APIRouter(prefix="/euco-conclusions", tags=["v1-euco-conclusions"])
meetings_router = APIRouter(prefix="/euco-meetings", tags=["v1-euco-meetings"])
euro_summit_router = APIRouter(prefix="/euco-euro-summit", tags=["v1-euco-euro-summit"])
strategic_agenda_router = APIRouter(prefix="/euco-strategic-agenda", tags=["v1-euco-strategic-agenda"])
members_router = APIRouter(prefix="/euco-members", tags=["v1-euco-members"])
about_router = APIRouter(prefix="/euco-about", tags=["v1-euco-about"])


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
# 1. European Council conclusions                                             #
# --------------------------------------------------------------------------- #
@conclusions_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="European Council conclusions — the conclusions register (2004-present)",
    description=_DESC(
        "Returns European Council conclusions from the conclusions register — the formal political guidance adopted by the EU heads of state or government at their summits, each with date, document number and a link to the PDF.",
        "To read the most authoritative signal of EU political direction — European Council conclusions set the strategic agenda that Commission proposals and Council decisions follow.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of conclusions documents.",
        "GET /api/v1/euco-conclusions?published_from=2025-01-01",
    ),
)
async def list_euco_conclusions(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euco_conclusions", op_title="European Council conclusions", op_type="European Council conclusions", **params)


@conclusions_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One European Council conclusions document by id — full body",
    description="Fetch a single European Council conclusions document by its Brubru UUID. Returns the five datapoints. 404 with `reason_code: not_found` if absent.",
)
async def get_euco_conclusion(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euco_conclusions")


# --------------------------------------------------------------------------- #
# 2. European Council meetings                                                #
# --------------------------------------------------------------------------- #
@meetings_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="European Council meetings — summit meetings of EU leaders",
    description=_DESC(
        "Returns European Council summit meetings (the gatherings of EU heads of state or government), with date and a body composed from the meeting facts plus the published outcomes where available.",
        "To track the European Council summit calendar and outcomes — the apex political meetings of the EU.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of summit meetings.",
        "GET /api/v1/euco-meetings",
    ),
)
async def list_euco_meetings(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euco_meeting", op_title="European Council meetings", op_type="European Council meeting", **params)


@meetings_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One European Council meeting by id — full body",
    description="Fetch a single European Council meeting by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_euco_meeting(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euco_meeting")


# --------------------------------------------------------------------------- #
# 3. Euro Summit                                                              #
# --------------------------------------------------------------------------- #
@euro_summit_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Euro Summit — heads of state or government of the euro area",
    description=_DESC(
        "Returns the Euro Summit reference — the meeting format that brings together the heads of state or government of the euro-area countries to discuss euro-area governance (distinct from the Eurogroup, which is finance ministers).",
        "To understand the Euro Summit's role and find its meeting calendar — the leaders'-level forum for the euro area.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` with the Euro Summit entry.",
        "GET /api/v1/euco-euro-summit",
    ),
)
async def list_euco_euro_summit(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euro_summit", op_title="Euro Summit", op_type="Euro Summit", **params)


@euro_summit_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Euro Summit entry by id — full body",
    description="Fetch a single Euro Summit entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_euco_euro_summit(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euro_summit")


# --------------------------------------------------------------------------- #
# 4. Strategic Agenda 2024-2029                                               #
# --------------------------------------------------------------------------- #
@strategic_agenda_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="European Council Strategic Agenda 2024-2029",
    description=_DESC(
        "Returns the European Council's Strategic Agenda 2024-2029 — the five-year political priorities agreed by EU leaders that frame the whole institutional cycle — with the agenda text and a link to the full PDF.",
        "To ground any analysis in the EU's top-level political priorities for the 2024-2029 cycle.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` with the Strategic Agenda entry.",
        "GET /api/v1/euco-strategic-agenda",
    ),
)
async def list_euco_strategic_agenda(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euco_strategic_agenda", op_title="Strategic Agenda 2024-2029", op_type="Strategic Agenda", **params)


@strategic_agenda_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One Strategic Agenda entry by id — full body",
    description="Fetch the Strategic Agenda entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_euco_strategic_agenda(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euco_strategic_agenda")


# --------------------------------------------------------------------------- #
# 5. Members                                                                  #
# --------------------------------------------------------------------------- #
@members_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="Members of the European Council",
    description=_DESC(
        "Returns the members of the European Council — the EU heads of state or government, plus the President of the European Council and the President of the European Commission — as a reference entry with the membership listing.",
        "As a reference for who sits on the European Council.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` with the members entry.",
        "GET /api/v1/euco-members",
    ),
)
async def list_euco_members(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euco_member", op_title="Members of the European Council", op_type="European Council member", **params)


@members_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One European Council members entry by id — full body",
    description="Fetch the European Council members entry by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_euco_member(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euco_member")


# --------------------------------------------------------------------------- #
# 6. About (institutional reference)                                          #
# --------------------------------------------------------------------------- #
@about_router.get(
    "",
    response_model=PaginatedResponse[CouncilRegisterItemModel],
    summary="About the European Council — how it works, president, role, history",
    description=_DESC(
        "Returns institutional reference pages about the European Council — how it works, the President of the European Council, the role/nominations/appointment process, and its history — each with the page text as body.",
        "As background reference on the European Council as an institution.",
        "A `PaginatedResponse[CouncilRegisterItemModel]` of reference entries.",
        "GET /api/v1/euco-about",
    ),
)
async def list_euco_about(
    request: Request, params: dict = Depends(_params),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[CouncilRegisterItemModel]:
    return _list(db, request, "euco_about", op_title="About the European Council", op_type="European Council reference", **params)


@about_router.get(
    "/{item_id}",
    response_model=CouncilRegisterItemModel,
    summary="One European Council reference page by id — full body",
    description="Fetch a single European Council reference page by its Brubru UUID. Returns the five datapoints. 404 if absent.",
)
async def get_euco_about(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> CouncilRegisterItemModel:
    return _detail(db, item_id, "euco_about")
