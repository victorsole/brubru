"""GET /api/v2/funding/startups — EU funding for startups & SMEs (EIC-led).

The European Innovation Council (EIC) is the EU's flagship startup/deep-tech
funding: the EIC Accelerator (grants + equity for startups), EIC Transition, EIC
Pathfinder, EIC STEP Scale-up and the EIC prizes. These are calls on the F&T
Portal whose topic/call id is under the EIC programme; this endpoint surfaces
them (plus any startup/SME-tagged call) as one "startup funding" feed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.funding_tenders import FtCallForProposals
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._body import body_threshold_param
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1.funding_tenders_collections import FtCallProposalItem, _proposal_to_item

router = APIRouter()

_DESC = """**What it does**
Returns EU funding aimed at **startups and SMEs**, led by the European Innovation Council (EIC): the **EIC Accelerator** (grants + equity for deep-tech startups), **EIC Transition**, **EIC Pathfinder**, **EIC STEP Scale-up** and the **EIC prizes** — plus any other Funding & Tenders Portal call tagged for startups/SMEs.

**When to use it**
For a startup, scale-up or SME (or an advisor/accelerator) looking specifically for EU money it can apply to. One feed of the EU's startup funding, instead of digging through the whole F&T Portal. Filter by `status` (open/forthcoming) and `deadline` to find what's actionable now.

**Input**
`status` (open | forthcoming | closed | under-evaluation), `q` (free text), `deadline_from` / `deadline_to`, `page`, `limit`.

**Try it**
```
GET /api/v2/funding/startups?status=open
GET /api/v2/funding/startups?q=accelerator
```

**You get back**
A `PaginatedResponse[FtCallProposalItem]` — each item carries `topic_id` (e.g. `HORIZON-EIC-2026-ACCELERATOR-01`), title, status, deadline, indicative budget, description and the F&T Portal link. Most recent deadlines first. Note: the EU publishes some titles in the applicant's language, so the stable English identifier is the `topic_id`.

**Data freshness**
Daily sync from the EU Funding & Tenders Portal (SEDIA)."""


@router.get("/startups", response_model=PaginatedResponse[FtCallProposalItem], tags=["v2-funding"],
            summary="EU startup & SME funding — EIC Accelerator, Transition, Pathfinder, STEP, prizes")
async def funding_startups(
    request: Request,
    status: Optional[str] = Query(None, description="open | forthcoming | closed | under-evaluation"),
    q: Optional[str] = Query(None, description="Substring match on title/description."),
    deadline_from: Optional[date] = Query(None),
    deadline_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[FtCallProposalItem]:
    # EIC programme (topic/call id is the reliable, language-independent spine —
    # it also captures the EIC Accelerator). Title 'accelerator' is intentionally
    # NOT matched: it false-positives on particle/physics "accelerator" calls.
    startup = or_(
        FtCallForProposals.topic_id.ilike("%-EIC-%"),
        FtCallForProposals.topic_id.ilike("EIC-%"),
        FtCallForProposals.call_id.ilike("%EIC%"),
        FtCallForProposals.title.ilike("%start-up%"),
        FtCallForProposals.title.ilike("%startup%"),
        FtCallForProposals.title.ilike("%scale-up%"),
    )
    filters = [FtCallForProposals.is_test == False, startup]  # noqa: E712
    if status:
        filters.append(FtCallForProposals.status == status.lower())
    if q:
        like = f"%{q}%"
        filters.append((FtCallForProposals.title.ilike(like)) | (FtCallForProposals.description.ilike(like)))
    if deadline_from:
        filters.append(FtCallForProposals.deadline >= deadline_from)
    if deadline_to:
        filters.append(FtCallForProposals.deadline <= deadline_to)
    query = db.query(FtCallForProposals).filter(and_(*filters))
    total = query.count()
    rows = (query.order_by(FtCallForProposals.deadline.desc().nullslast(), FtCallForProposals.id.desc())
            .offset((page - 1) * limit).limit(limit).all())
    return build_envelope([_proposal_to_item(r, body_threshold=body_threshold) for r in rows],
                          total=total, page=page, limit=limit)
