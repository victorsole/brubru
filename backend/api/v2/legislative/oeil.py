"""
Legislative Observatory (OEIL) source — /api/v2/legislative/oeil/*.

Backend: the European Parliament's Legislative Observatory via Brubru's
legislative_carriages mirror. Covers procedures in negotiation (proposed but
not yet adopted): the procedure-file register and per-procedure detail.

LIVE endpoints delegate to api.v1.procedures (single source of truth during
v1+v2 coexistence). PROPOSED: /procedures/latest (lands in a later checkpoint).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1 import procedures as _v1_procedures
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.procedures import ProcedureDetail, ProcedureItem

router = APIRouter(prefix="/oeil", tags=["v2-legislative-oeil"])


@router.get(
    "/procedures",
    response_model=PaginatedResponse[ProcedureItem],
    summary="Search EU legislative procedures in negotiation — proposed but not yet adopted",
    description="""**What it does**
Returns EU legislative files currently in the institutional pipeline (Commission proposal, EP committee, Council negotiation, trilogue, or recently adopted but not yet published). 1,200+ files tracked from OEIL — the EP's authoritative procedure-file register. Each row carries the procedure reference (e.g. `2025/0726(COD)`), title, procedure type, lead committee, rapporteur, current status, dates, and policy-area tags.

**When to use it**
The companion to `/api/v2/legislative/eur-lex/laws` (adopted legislation). Use this for "what's coming next" advocacy work — tracking a file from proposal to adoption, monitoring rapporteur appointments, finding blocked procedures.

**Input**
- `q` — substring match on title.
- `reference` — exact OEIL procedure reference (e.g. `2025/0726(COD)`).
- `committee` — lead committee code (e.g. `LIBE`, `ENVI`).
- `rapporteur_mep_id` — filter to a specific MEP's files.
- `status` — procedure status enum.
- `updated_from`, `updated_to` (+ `updated_end` alias) — incremental sync.
- `limit`, `page`.

**Try it**
```
GET /api/v2/legislative/oeil/procedures?committee=ENVI&status=in_trilogue
GET /api/v2/legislative/oeil/procedures?reference=2024/0079(COD)
```

**You get back**
A `PaginatedResponse[ProcedureItem]` envelope; each item carries the procedure metadata + the 5 envelope-level datapoints.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from OEIL XML feeds.""",
)
async def list_procedures(
    request: Request,
    q: Optional[str] = Query(None, description="Substring match on title"),
    reference: Optional[str] = Query(None, description="OEIL procedure reference (e.g. 2025/0726(COD))"),
    committee: Optional[str] = Query(None, description="Lead committee code (e.g. LIBE, ENVI)"),
    rapporteur_mep_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Carriage status"),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to (GovClipping-compatible)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProcedureItem]:
    return await _v1_procedures.list_procedures(
        request,
        q=q,
        reference=reference,
        committee=committee,
        rapporteur_mep_id=rapporteur_mep_id,
        status=status,
        updated_from=updated_from,
        updated_to=updated_to,
        updated_end=updated_end,
        limit=limit,
        page=page,
        user=user,
        db=db,
    )


@router.get(
    "/procedures/latest",
    response_model=PaginatedResponse[ProcedureItem],
    summary="Most recently updated legislative procedures",
    description="""**What it does**
Returns the procedures whose status changed most recently — the "what just moved" feed. Backed by the same carriage mirror as `/procedures`, filtered to files updated within the last N days and ordered newest-first.

**When to use it**
For a daily "what advanced in the EU pipeline" digest, or to poll for stage transitions without scanning the whole register.

**Input**
- `days` (1-90, default 7) — look-back window on the last-updated date.
- `limit` (1-100, default 50).

**Try it**
```
GET /api/v2/legislative/oeil/procedures/latest?days=7
```

**You get back**
A `PaginatedResponse[ProcedureItem]` ordered by last-updated descending.

**Data freshness**
Synced every 6 hours (hot tier) from OEIL XML feeds.""",
)
async def latest_procedures(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Look-back window in days"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProcedureItem]:
    since = datetime.utcnow() - timedelta(days=days)
    return await _v1_procedures.list_procedures(
        request,
        q=None,
        reference=None,
        committee=None,
        rapporteur_mep_id=None,
        status=None,
        updated_from=since,
        updated_to=None,
        updated_end=None,
        limit=limit,
        page=1,
        user=user,
        db=db,
    )


@router.get(
    "/procedures/{reference:path}",
    response_model=ProcedureDetail,
    summary="Look up one legislative procedure by its reference — full timeline + rapporteurs + briefings",
    description="""**What it does**
Returns the complete legislative carriage for one procedure — the full OEIL timeline (every event from Commission proposal to adoption with dates + actors), rapporteurs by committee, committee assignments, EPRS-matched briefings, EUR-Lex linked documents, and AI-enriched summary.

**When to use it**
When you need the complete picture of a legislative file in one call — for an advocacy briefing, a chat answer about "where is the AI Act now", or a tracker deep-link.

**Input**
- `reference` (path) — OEIL procedure ref (e.g. `2021/0106(COD)`) or Brubru file_id. The `:path` matcher accepts slashes + parentheses verbatim; no URL-encoding needed.

**Try it**
```
GET /api/v2/legislative/oeil/procedures/2024/0079(COD)
```

**You get back**
A `ProcedureDetail` with `oeil_procedure_ref`, `title`, `current_status`, `lead_committee`, full timeline + key events, rapporteurs, EPRS briefings, EUR-Lex documents, AI summary, plus the 5 envelope-level datapoints. HTTP 404 (`reason_code: not_found`) if no procedure matches.

**Data freshness**
Synced every 6 hours (hot tier) from OEIL XML feeds.""",
)
async def get_procedure_detail(
    reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ProcedureDetail:
    return await _v1_procedures.get_procedure_detail(reference, user=user, db=db)
