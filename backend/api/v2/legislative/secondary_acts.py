"""
Legislative Documents source — /api/v2/legislative/delegated-acts/* and
/api/v2/legislative/implementing-acts/*.

Backend: Commission secondary legislation — delegated acts (Article 290 TFEU)
and implementing acts (Article 291 TFEU). LIVE — delegates to the v1 handlers
in api.v1.w4_endpoints so there is exactly one implementation during the v1+v2
coexistence period.

Scope: read:commission, same as the v1 surface.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1 import w4_endpoints as _v1
from api.v1._body import body_threshold_param
from api.v1._date_bounds import UpperBoundDatetime
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.w4_endpoints import SecondaryActItem

delegated_router = APIRouter(prefix="/delegated-acts", tags=["v2-legislative-delegated-acts"])
implementing_router = APIRouter(prefix="/implementing-acts", tags=["v2-legislative-implementing-acts"])


@delegated_router.get(
    "",
    response_model=PaginatedResponse[SecondaryActItem],
    summary="EU delegated acts: Commission acts that supplement or amend a law, with their scrutiny and full text",
    description="""**What it does**
Returns the Commission's delegated acts: acts that supplement or amend an EU law under a power that law gives the Commission (Article 290 TFEU). Every act the Interinstitutional Register of Delegated Acts (RegDel) lists is here, at every stage: announced (`planned`), `adopted`, `published` in the Official Journal, `objected` to by Parliament or the Council, `withdrawn` or `cancelled`. Each act carries the law it comes from, the scrutiny Parliament and the Council exercised over it, and its full text.

**When to use it**
To follow what the Commission adopts under a law you track (`parent_celex`), to catch acts whose objection period may still be running (`status=adopted`, then `objection_deadline_earliest`), or to keep a copy in sync (`updated_from` / `updated_to`).

**Input**
- `parent_celex`: CELEX of the law that grants the power, e.g. `32018R0858` (motor vehicle type-approval).
- `celex`: the act's own CELEX.
- `proposing_dg`: the lead Commission department, e.g. `FISMA`.
- `status`: `planned`, `adopted`, `published`, `objected`, `scrutiny_finished`, `notified`, `withdrawn`, `cancelled`, `on_hold`, `rejected`, `draft` or `unknown`. Any other value is a 422.
- `q`: words in the title or summary.
- `published_from`, `published_to`: the Official Journal date (`publication_date`).
- `updated_from`, `updated_to`: incremental sync on `updated_date`, which moves only when something served changes. A bare date in `updated_to` covers the whole day.
- `limit` (default 50, max 100), `page`.

**Try it**
```
GET /api/v2/legislative/delegated-acts?status=adopted
GET /api/v2/legislative/delegated-acts?parent_celex=32018R0858
GET /api/v2/legislative/delegated-acts?proposing_dg=FISMA&published_from=2026-01-01
GET /api/v2/legislative/delegated-acts?q=battery
```

**You get back**
A paginated envelope. Each act carries:
- `reference` (the Commission number, `C(2026)3147`), `celex` once published, `title`, `description` (the register's summary, where it has one), `status`, `urgency_procedure`, `proposing_dg`, `policy_areas` (the lead department's area).
- `parent_celex` and `parent_procedure_ref` (`2016/0014(COD)`), as the register records them.
- `adoption_date`, `publication_date`, and `planned_adoption_period` for an announced act (`Q3 2026`).
- `scrutiny_period` (`2 months`, `3 months`, or `1 or 3 months`), `ep_scrutiny` and `council_scrutiny`: the dates of each extension, objection, early non-objection and rejected motion, null where the register records none.
- `objection_deadline_earliest`: adoption date + scrutiny period + extension, the earliest the objection period can end. No source publishes the day the period starts (the notification to Parliament and the Council), so the deadline itself, `objection_deadline`, is null.
- `body_txt` and `body_html`: the full text. `body_source` says which: `official_journal` for a published act, `commission_document` for one adopted but not in the Official Journal (from the Commission's document register). An announced or cancelled act has no text.
- `public_url`, `document_date`, `creation_date`, `updated_date`, `self`.

**Coverage and freshness**
Every delegated act in RegDel, about 2,160 adopted or announced since September 2010, with the register's gaps filled from the Publications Office: an act the register still shows without a CELEX takes the one the Publications Office records for its Commission number. Checked on 14 October 2026: every delegated act published in the Official Journal since 15 July 2024 is held (Regulation 2025/1511 under its republication, 2025/2273). Updated three times a day, at about 08:00, 14:00 and 20:00 UTC; an act's text arrives in the same run.""",
)
async def list_delegated_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    celex: Optional[str] = Query(None, description="Exact CELEX of the act itself (not its parent)."),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Upper bound of the incremental-sync window, on the same change date as updated_from. A bare date covers that whole day."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return await _v1.list_delegated_acts(
        request, parent_celex=parent_celex, celex=celex, proposing_dg=proposing_dg, status=status, q=q,
        published_from=published_from, published_to=published_to, updated_from=updated_from,
        updated_to=updated_to, limit=limit, page=page, body_threshold=body_threshold, user=user, db=db,
    )


@delegated_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="One delegated act, by its Commission number, CELEX or id",
    description="""**What it does**
Returns one delegated act, with everything the list gives: its scrutiny, its dates and its full text.

**When to use it**
To follow an item's `self` link, or to check one act's scrutiny before its objection period ends.

**Input**
- `reference` (path): the Commission number, with its parentheses as they are (`C(2026)3147`), the CELEX (`32026R1753`) or the `id`. The id or number of a row merged into this one still resolves. An implementing act's number is a 404 that names the implementing-acts route.

**Try it**
```
GET /api/v2/legislative/delegated-acts/C(2026)3147
GET /api/v2/legislative/delegated-acts/32026R1753
```

**You get back**
One act in the list's shape, or a 404 with `reason_code: not_found`.

**Data freshness**
As the list: three times a day.""",
)
async def get_delegated_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SecondaryActItem:
    return await _v1.get_delegated_detail(reference, body_threshold=body_threshold, user=user, db=db)


@implementing_router.get(
    "",
    response_model=PaginatedResponse[SecondaryActItem],
    summary="EU implementing acts: Commission acts that set uniform rules for applying a law, with their full text",
    description="""**What it does**
Returns the Commission's implementing acts: acts that lay down uniform conditions for applying an EU law (Article 291 TFEU), usually after a vote in a committee of Member State experts. It holds every act the Register of Delegated Acts lists as an implementing act, at every stage (`planned`, `adopted`, `published`, `cancelled`, `on_hold`), and published implementing acts found in the Publications Office.

**When to use it**
To follow the implementing acts under a law you track (`parent_celex`), for example the approvals of active substances under the plant protection products regulation, or to keep a copy in sync (`updated_from` / `updated_to`).

**Input**
- `parent_celex`: CELEX of the law being implemented, e.g. `32009R1107` (plant protection products) or `32016R0679` (GDPR).
- `celex`: the act's own CELEX.
- `proposing_dg`: the lead Commission department, e.g. `SANTE`.
- `status`: `planned`, `adopted`, `published`, `cancelled` or `on_hold` (the other delegated-act values are accepted and match nothing). Any value outside the list is a 422.
- `q`: words in the title or summary.
- `published_from`, `published_to`: the Official Journal date (`publication_date`).
- `updated_from`, `updated_to`: incremental sync on `updated_date`. A bare date in `updated_to` covers the whole day.
- `limit` (default 50, max 100), `page`.

**Try it**
```
GET /api/v2/legislative/implementing-acts?parent_celex=32009R1107
GET /api/v2/legislative/implementing-acts?parent_celex=32016R0679
GET /api/v2/legislative/implementing-acts?q=residue
```

**You get back**
A paginated envelope of acts in the same shape as `/delegated-acts`. The scrutiny fields (`scrutiny_period`, `ep_scrutiny`, `council_scrutiny`, `objection_deadline_earliest`) are empty: Parliament and the Council do not scrutinise implementing acts the way they scrutinise delegated ones. `body_source` says where the text comes from (`official_journal` or `commission_document`); an announced or cancelled act has none.

**Coverage and freshness**
Every implementing act in the register, about 5,600 since 2009, plus about 600 published ones the Publications Office lists. Updated three times a day, at about 08:00, 14:00 and 20:00 UTC; an act's text arrives in the same run.""",
)
async def list_implementing_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    celex: Optional[str] = Query(None, description="Exact CELEX of the act itself (not its parent)."),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Upper bound of the incremental-sync window, on the same change date as updated_from. A bare date covers that whole day."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return await _v1.list_implementing_acts(
        request, parent_celex=parent_celex, celex=celex, proposing_dg=proposing_dg, status=status, q=q,
        published_from=published_from, published_to=published_to, updated_from=updated_from,
        updated_to=updated_to, limit=limit, page=page, body_threshold=body_threshold, user=user, db=db,
    )


@implementing_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="One implementing act, by its Commission number, CELEX or id",
    description="""**What it does**
Returns one implementing act, with its dates and its full text.

**When to use it**
To follow an item's `self` link.

**Input**
- `reference` (path): the Commission number, with its parentheses as they are (`C(2026)6950`), the CELEX (`32026R2212`) or the `id`. The id or number of a row merged into this one still resolves. A delegated act's number is a 404 that names the delegated-acts route.

**Try it**
```
GET /api/v2/legislative/implementing-acts/C(2026)6950
GET /api/v2/legislative/implementing-acts/32026R2212
```

**You get back**
One act in the list's shape, or a 404 with `reason_code: not_found`.

**Data freshness**
As the list: three times a day.""",
)
async def get_implementing_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SecondaryActItem:
    return await _v1.get_implementing_detail(reference, body_threshold=body_threshold, user=user, db=db)
