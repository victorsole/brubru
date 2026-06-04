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
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.w4_endpoints import SecondaryActItem

delegated_router = APIRouter(prefix="/delegated-acts", tags=["v2-legislative-delegated-acts"])
implementing_router = APIRouter(prefix="/implementing-acts", tags=["v2-legislative-implementing-acts"])


@delegated_router.get(
    "",
    response_model=PaginatedResponse[SecondaryActItem],
    summary="Commission delegated acts — secondary legislation under Article 290 TFEU",
    description="""**What it does**
Returns Commission delegated acts — secondary legislation adopted by the Commission under powers delegated by a basic legislative act (Article 290 TFEU). Each row carries the act reference (e.g. `C(2026)1234`), the parent CELEX (the basic act granting the delegation), the parent procedure reference, the status, the proposing DG, the publication date, the EP/Council objection deadline (typically 2-3 months), the EP scrutiny status, the Council scrutiny status, the CELEX if adopted, plus body text + the 5 envelope-level datapoints.

**When to use it**
To monitor secondary legislation flowing from a flagship regulation (e.g. all delegated acts under the AI Act), track the EP/Council objection window for delegated acts you might want to scrutinise, or audit which DGs are most active in delegated-act production. The `parent_celex` filter scopes to a specific parent act.

**Input**
- `parent_celex` — CELEX of the parent (basic) act granting the delegation (e.g. `32024R1689` for AI Act).
- `proposing_dg` — DG code.
- `status` — `proposed` / `scrutiny` / `adopted` / `objected` / `withdrawn` (status enum).
- `q` — substring search on title + description.
- `published_from`, `published_to` — date filter on `publication_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v2/legislative/delegated-acts?parent_celex=32024R1689&limit=20
GET /api/v2/legislative/delegated-acts?proposing_dg=CNECT&status=scrutiny
```

**You get back**
A `PaginatedResponse[SecondaryActItem]` envelope. Each item carries `reference`, `title`, `description`, `parent_celex`, `parent_procedure_ref`, `status`, `proposing_dg`, `publication_date`, `objection_deadline`, `ep_scrutiny` (dict with EP rapporteur / motion status), `council_scrutiny` (dict), `celex` (if adopted), `source_url`, `pdf_url`, `policy_areas`, body fields, and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from the RegDel register + EUR-Lex C-series. New delegated acts appear on a steady drumbeat; daily sync catches them. Backed by `backend/scripts/backfill_eu_comitology.py`.""",
)
async def list_delegated_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return await _v1.list_delegated_acts(
        request, parent_celex=parent_celex, proposing_dg=proposing_dg, status=status, q=q,
        published_from=published_from, published_to=published_to, updated_from=updated_from,
        limit=limit, page=page, body_threshold=body_threshold, user=user, db=db,
    )


@delegated_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="Look up one delegated act by its Commission reference (e.g. C(2026)1234)",
    description="""**What it does**
Fetches a single delegated act by its Commission reference. Returns the same shape as the list endpoint, with body text composed from the publication PDF when ingested.

**When to use it**
After locating a delegated act via the list endpoint, use this to fetch the full record (including body text + scrutiny details) in a deeper-link context.

**Input**
- `reference` (path) — the Commission reference, format `C(YYYY)NNNN`. The `:path` matcher means the parentheses are accepted verbatim — no URL-encoding needed.

**Try it**
```
GET /api/v2/legislative/delegated-acts/C(2026)1234
```

**You get back**
A single `SecondaryActItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the RegDel register + EUR-Lex C-series.""",
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
    summary="Commission implementing acts — uniform implementation of EU law (Article 291 TFEU)",
    description="""**What it does**
Returns Commission implementing acts — secondary legislation adopted by the Commission under Article 291 TFEU to ensure uniform conditions for implementation of EU law (typically with a comitology committee opinion). Each row carries the act reference (e.g. `C(2026)0234`), the parent CELEX, the parent procedure reference, the status, the proposing DG, the publication date, the comitology examination/advisory procedure outcome, the CELEX if adopted, plus body text + the 5 envelope-level datapoints.

**When to use it**
To monitor secondary legislation flowing from a flagship regulation (e.g. all implementing acts under MDR, REACH, CRR), track comitology committee outcomes (e.g. SCoPAFF votes on pesticides), or audit which DGs are most active in implementing-act production. The `parent_celex` filter scopes to a specific parent act.

**Input**
- `parent_celex` — CELEX of the parent (basic) act (e.g. `32016R0679` for GDPR).
- `proposing_dg` — DG code.
- `status` — implementing-act status enum.
- `q` — substring search on title + description.
- `published_from`, `published_to` — date filter on `publication_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v2/legislative/implementing-acts?proposing_dg=SANTE&q=glyphosate
GET /api/v2/legislative/implementing-acts?parent_celex=32016R0679&limit=20
```

**You get back**
A `PaginatedResponse[SecondaryActItem]` envelope. Each item carries `reference`, `title`, `description`, `parent_celex`, `parent_procedure_ref`, `status`, `proposing_dg`, `publication_date`, `ep_scrutiny`, `council_scrutiny`, `celex`, `source_url`, `pdf_url`, `policy_areas`, body fields, and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from the Comitology Register + EUR-Lex C-series.""",
)
async def list_implementing_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return await _v1.list_implementing_acts(
        request, parent_celex=parent_celex, proposing_dg=proposing_dg, status=status, q=q,
        published_from=published_from, published_to=published_to, updated_from=updated_from,
        limit=limit, page=page, body_threshold=body_threshold, user=user, db=db,
    )


@implementing_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="Look up one implementing act by its Commission reference (e.g. C(2026)0234)",
    description="""**What it does**
Fetches a single Commission implementing act by its reference. Implementing acts (Article 291 TFEU) lay down uniform conditions for the implementation of EU legislation across Member States. Returns the same shape as the list endpoint, with body text composed from the publication PDF when ingested.

**When to use it**
After locating an implementing act via the list endpoint, use this to fetch the full record in a deeper-link context. Note: the difference between delegated acts (Art. 290, modify or supplement the basic act) and implementing acts (Art. 291, uniform implementation) is constitutionally significant for legal-affairs work.

**Input**
- `reference` (path) — the Commission reference, format `C(YYYY)NNNN`. Path-matching accepts parentheses verbatim.

**Try it**
```
GET /api/v2/legislative/implementing-acts/C(2026)0234
```

**You get back**
A single `SecondaryActItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the Comitology Register + EUR-Lex C-series.""",
)
async def get_implementing_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SecondaryActItem:
    return await _v1.get_implementing_detail(reference, body_threshold=body_threshold, user=user, db=db)
