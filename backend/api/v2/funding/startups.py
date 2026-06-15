"""GET /api/v2/funding/startups — EU funding for startups, scale-ups & SMEs.

One bundled feed of the EU funding a company can actually *apply to*, drawn from
the data Brubru already holds (the F&T Portal calls in ft_calls_for_proposals):

  - European Innovation Council (EIC): Pathfinder, Transition, Pre-Accelerator,
    Accelerator, STEP Scale-up, Innovation Challenges, Prizes — the EU's flagship
    startup / deep-tech funding (grant / blended / equity).
  - Single Market Programme — COSME / EISMEA: Enterprise Europe Network,
    Euroclusters and SME-competitiveness calls.
  - Innovation Fund (net-zero / clean-tech) calls — relevant to cleantech startups.
  - Any other F&T-Portal call titled for startups / scale-ups / SMEs.

Each item is tagged with a derived `stage` (idea / seed / growth / scale-up / sme)
and `instrument` (grant / blended / equity / prize) so a founder can filter by
where they are. Structural funds (ERDF, ESF+, EMFAF, ...) are intentionally
excluded — they are Member-State allocations, not calls a startup applies to.
Not yet covered (no data source held): EaSI Microfinance, InvestEU.
"""
from __future__ import annotations

import fnmatch
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.funding_tenders import FtCallForProposals
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._body import body_threshold_param
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1.funding_tenders_collections import FtCallProposalItem, _proposal_to_item

router = APIRouter()


# ---------------------------------------------------------------------------
# Classification. Ordered rules: first match wins for the per-item stage/instrument.
# Each rule = (column, ILIKE-pattern, stage, instrument). The same rules drive both
# the per-item tag and the optional ?stage / ?instrument filters (so the filter and
# the displayed tag never disagree on the rule set).
# ---------------------------------------------------------------------------
_RULES = [
    ("topic_id", "%EIC%PATHFINDER%", "idea",     "grant"),
    ("topic_id", "%EIC%TRANSITION%", "seed",     "grant"),
    ("topic_id", "%EIC%PREACC%",     "seed",     "grant"),
    ("topic_id", "%EIC%PRE-ACC%",    "seed",     "grant"),
    ("topic_id", "%STEP%",           "scale-up", "equity"),
    ("topic_id", "%EIC%ACCELERATOR%","growth",   "blended"),
    ("topic_id", "%EIC%CHALLENGE%",  "growth",   "grant"),
    ("topic_id", "%EIC%PRIZE%",      "growth",   "prize"),
    ("topic_id", "INNOVFUND%",       "growth",   "grant"),
    ("topic_id", "SMP-COSME%",       "sme",      "grant"),
    ("topic_id", "%-EIC-%",          "growth",   "grant"),
    ("topic_id", "EIC-%",            "growth",   "grant"),
    ("call_id",  "%EIC%",            "growth",   "grant"),
]
# Title-only startup signals (no specific stage) — treated as 'sme' / 'grant'.
# Deliberately NOT "%SME%": that matches generic Horizon calls that merely mention
# SMEs in passing and floods the feed. The actual SME programme (COSME) is captured
# by the SMP-COSME topic_id prefix above, which is precise.
_TITLE_PATTERNS = ["%start-up%", "%startup%", "%scale-up%"]

_STAGES = {"idea", "seed", "growth", "scale-up", "sme"}
_INSTRUMENTS = {"grant", "blended", "equity", "prize"}


def _col(col_name: str):
    return FtCallForProposals.topic_id if col_name == "topic_id" else FtCallForProposals.call_id


def _classify(r: FtCallForProposals) -> tuple[str, str]:
    """Derive (stage, instrument) for one row from its topic_id / call_id."""
    tid = (r.topic_id or "").upper()
    cid = (r.call_id or "").upper()
    for col_name, pat, stage, instr in _RULES:
        val = tid if col_name == "topic_id" else cid
        if fnmatch.fnmatch(val, pat.upper().replace("%", "*")):
            return stage, instr
    return "sme", "grant"  # title-only match


class StartupFundingItem(FtCallProposalItem):
    stage: Optional[str] = None       # idea | seed | growth | scale-up | sme
    instrument: Optional[str] = None  # grant | blended | equity | prize


def _to_item(r: FtCallForProposals, body_threshold: int) -> StartupFundingItem:
    base = _proposal_to_item(r, body_threshold=body_threshold)
    stage, instrument = _classify(r)
    return StartupFundingItem(**base.model_dump(), stage=stage, instrument=instrument)


def _base_condition():
    """OR of every signal that makes a call 'startup funding'."""
    conds = [_col(c).ilike(p) for c, p, _, _ in _RULES]
    conds += [FtCallForProposals.title.ilike(p) for p in _TITLE_PATTERNS]
    return or_(*conds)


def _precedence_condition(matches) -> "object | None":
    """First-match-correct SQL for a derived class (stage or instrument).

    `matches(stage, instrument) -> bool` selects which rules yield the target
    class. A row belongs to the class iff it matches one of those rules AND none
    of the rules *earlier* in `_RULES` (so the SQL filter agrees exactly with the
    per-item first-match `_classify`). The title-only fallback ('sme'/'grant') is
    appended last, applying only when no rule matched.
    """
    clauses = []
    prior = []  # ilike conditions for all rules seen so far
    for c, p, stage, instr in _RULES:
        cond = _col(c).ilike(p)
        if matches(stage, instr):
            clauses.append(and_(cond, *[not_(x) for x in prior]) if prior else cond)
        prior.append(cond)
    if matches("sme", "grant"):  # title-only rows fall through to sme/grant
        title_cond = or_(*[FtCallForProposals.title.ilike(p) for p in _TITLE_PATTERNS])
        clauses.append(and_(title_cond, *[not_(x) for x in prior]))
    return or_(*clauses) if clauses else None


def _stage_condition(stage: str):
    return _precedence_condition(lambda st, ins: st == stage)


def _instrument_condition(instrument: str):
    return _precedence_condition(lambda st, ins: ins == instrument)


_DESC = """**What it does**
One bundled feed of the EU funding a company can actually **apply to** — startups, scale-ups and SMEs — drawn together from the EU Funding & Tenders Portal:
- **European Innovation Council (EIC)**: Pathfinder (idea), Transition (seed), Pre-Accelerator, **Accelerator** (grant + equity), **STEP Scale-up** (equity), Innovation Challenges and Prizes.
- **Single Market Programme — COSME / EISMEA**: Enterprise Europe Network, Euroclusters, SME-competitiveness calls.
- **Innovation Fund** (net-zero / clean-tech) calls — for cleantech startups.
- Any other F&T-Portal call titled for startups / scale-ups / SMEs.

Each item is tagged with a derived **`stage`** (idea / seed / growth / scale-up / sme) and **`instrument`** (grant / blended / equity / prize), so you can filter by where your company is.

**When to use it**
For a founder, scale-up or SME (or an advisor / accelerator) who wants the EU money they can apply to, in one call, instead of digging through the whole portal. Combine `stage=growth&status=open` to find, say, the open Accelerator round.

**Input**
`stage` (idea | seed | growth | scale-up | sme), `instrument` (grant | blended | equity | prize), `status` (open | forthcoming | closed | under-evaluation), `q` (free text), `deadline_from` / `deadline_to`, `page`, `limit`.

**Try it**
```
GET /api/v2/funding/startups?status=open
GET /api/v2/funding/startups?stage=scale-up
GET /api/v2/funding/startups?instrument=equity
```

**You get back**
A `PaginatedResponse[StartupFundingItem]` — each item carries `topic_id` (the stable English id, e.g. `HORIZON-EIC-2026-ACCELERATOR-01`), title, `stage`, `instrument`, status, deadline, budget, description, the F&T Portal link and the 5 datapoints (`body_txt` / `body_html` null on the list — fetch `/startups/{topic_id}` for the full body). Most recent deadlines first.

**Not yet covered**
EaSI Microfinance (loans ≤ €25k) and InvestEU (equity / guarantees) are useful for founders but Brubru does not yet hold their data. Structural funds (ERDF, ESF+, EMFAF) are excluded here because they are Member-State allocations, not direct-apply calls.

**Data freshness**
Daily sync from the EU Funding & Tenders Portal (SEDIA)."""


@router.get("/startups", response_model=PaginatedResponse[StartupFundingItem], tags=["v2-funding"],
            summary="EU startup, scale-up & SME funding — EIC, COSME/EISMEA, Innovation Fund (stage-tagged)",
            description=_DESC)
async def funding_startups(
    request: Request,
    stage: Optional[str] = Query(None, description="idea | seed | growth | scale-up | sme"),
    instrument: Optional[str] = Query(None, description="grant | blended | equity | prize"),
    status: Optional[str] = Query(None, description="open | forthcoming | closed | under-evaluation"),
    q: Optional[str] = Query(None, description="Substring match on title/description."),
    deadline_from: Optional[date] = Query(None),
    deadline_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[StartupFundingItem]:
    if stage and stage not in _STAGES:
        raise HTTPException(status_code=400, detail=f"stage must be one of {sorted(_STAGES)}")
    if instrument and instrument not in _INSTRUMENTS:
        raise HTTPException(status_code=400, detail=f"instrument must be one of {sorted(_INSTRUMENTS)}")

    filters = [FtCallForProposals.is_test == False, _base_condition()]  # noqa: E712
    if stage:
        cond = _stage_condition(stage)
        if cond is not None:
            filters.append(cond)
    if instrument:
        cond = _instrument_condition(instrument)
        if cond is not None:
            filters.append(cond)
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
    return build_envelope([_to_item(r, body_threshold) for r in rows], total=total, page=page, limit=limit)


@router.get("/startups/{topic_id:path}", response_model=StartupFundingItem, tags=["v2-funding"],
            summary="EU startup funding — one call (full body), by its F&T topic_id",
            description="""**What it does**
Fetches a single startup-funding call by its EU topic_id, with the full body and the derived `stage` / `instrument` tags.

**When to use it**
After locating a call in the `/startups` list, fetch the complete record (full `body_txt` / `body_html` + the 5 datapoints).

**Input**
`topic_id` (path) — the EU's identifier, e.g. `HORIZON-EIC-2026-ACCELERATOR-01` or `INNOVFUND-2024-NZT-GENERAL-LSP`.

**Try it**
```
GET /api/v2/funding/startups/HORIZON-EIC-2026-ACCELERATOR-01
```

**You get back**
A single `StartupFundingItem` (same shape as a list row, with the full body), or HTTP 404 if no such call.

**Data freshness**
Daily sync from the EU Funding & Tenders Portal (SEDIA).""")
async def get_startup_funding(
    topic_id: str = Path(..., description="The EU topic_id of the call."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> StartupFundingItem:
    r = (db.query(FtCallForProposals)
         .filter(FtCallForProposals.is_test == False, FtCallForProposals.topic_id == topic_id)  # noqa: E712
         .first())
    if r is None:
        raise HTTPException(status_code=404, detail=f"No startup-funding call with topic_id {topic_id}")
    return _to_item(r, body_threshold)
