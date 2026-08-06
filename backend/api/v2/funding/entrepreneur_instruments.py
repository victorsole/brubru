"""GET /api/v2/funding/entrepreneur-instruments — EU financial instruments that
support entrepreneurs, delivered through intermediaries / platforms.

Xavier Arola (KinEtix Impact) asked for "instruments financers per suport a
emprenedors a través de plataformes o stakeholders de sistema" — the EU money an
entrepreneur reaches *through* a system intermediary (the EIC Fund, EISMEA, the
Enterprise Europe Network, a European Digital Innovation Hub, a national managing
authority, an Erasmus-for-Young-Entrepreneurs organisation), not the raw call
list. The Tenderator already covers his day-to-day profile-matched calls; this is
the machine-readable version so KinEtix can pull the intermediated-instrument
list into its own systems.

READS existing data (ft_calls_for_proposals) — no new scraper / cron. Scope is by
`topic_id` prefix (reliable) rather than free-text title. Each row carries a
derived `programme`, `instrument_family` and — the whole point — the
`intermediary` that delivers it.
"""
from __future__ import annotations

import fnmatch
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, false, or_
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
# Intermediated-entrepreneur-finance families. Ordered: first match wins for the
# per-item (programme, instrument_family, intermediary) label. The same patterns
# drive the `_base_condition` (which rows the endpoint serves at all) and the
# optional `programme` filter, so the filter and the displayed label never
# disagree on the rule set. Patterns are SQL ILIKE / fnmatch globs on topic_id.
# ---------------------------------------------------------------------------
_FAMILIES = [
    # EIC sub-instruments first (most specific), then the generic EIC catch-all.
    ("HORIZON-EIC%ACCELERATOR%", "HORIZON (EIC)", "EIC Accelerator",        "EIC Fund (direct equity) + EISMEA"),
    ("HORIZON-EIC%STEP%",        "HORIZON (EIC)", "EIC STEP Scale-up",      "EIC Fund (equity)"),
    ("HORIZON-EIC%TRANSITION%",  "HORIZON (EIC)", "EIC Transition",         "EISMEA (grant)"),
    ("HORIZON-EIC%PATHFINDER%",  "HORIZON (EIC)", "EIC Pathfinder",         "EISMEA (grant)"),
    ("HORIZON-EIC%",             "HORIZON (EIC)", "EIC (other)",            "EISMEA / EIC Fund"),
    ("SMP-%",                    "Single Market Programme", "SMP SME strand", "EISMEA + Enterprise Europe Network"),
    ("I3-%",                     "Interregional Innovation Investments (I3)", "I3 Instrument", "Regional innovation ecosystems (managing authorities)"),
    ("DIGITAL-%",                "Digital Europe", "European Digital Innovation Hubs", "EDIH platforms"),
    ("ESF-%",                    "ESF+ / EaSI", "EaSI microfinance / social entrepreneurship", "National managing authorities / EaSI intermediaries"),
    ("SOCPL%",                   "ESF+ / EaSI", "EaSI microfinance / social entrepreneurship", "National managing authorities / EaSI intermediaries"),
    ("ERASMUS%",                 "Erasmus+ (EYE)", "Erasmus for Young Entrepreneurs", "EYE intermediary organisations"),
]

# Valid `programme` filter values (the coarse labels above).
_PROGRAMMES = sorted({f[1] for f in _FAMILIES})


def _classify(r: FtCallForProposals) -> tuple[str, str, str]:
    """(programme, instrument_family, intermediary) for one row — first match wins."""
    tid = (r.topic_id or "").upper()
    for pat, programme, family, intermediary in _FAMILIES:
        if fnmatch.fnmatch(tid, pat.upper().replace("%", "*")):
            return programme, family, intermediary
    # Should not happen: _base_condition guarantees a family match.
    return "EU funding", "Entrepreneur instrument", "EU intermediary"


def _base_condition():
    """OR of every family prefix — the rows this endpoint serves at all."""
    return or_(*[FtCallForProposals.topic_id.ilike(pat) for pat, *_ in _FAMILIES])


def _programme_condition(programme: str):
    """Restrict to the family prefixes whose coarse programme label matches."""
    pl = programme.strip().lower()
    pats = [pat for pat, prog, *_ in _FAMILIES if pl in prog.lower()]
    return or_(*[FtCallForProposals.topic_id.ilike(p) for p in pats]) if pats else false()


class EntrepreneurInstrumentItem(FtCallProposalItem):
    programme: Optional[str] = None          # HORIZON (EIC) | Single Market Programme | ...
    instrument_family: Optional[str] = None  # EIC Accelerator | EDIH | EaSI microfinance | ...
    intermediary: Optional[str] = None       # who delivers it — the point of the endpoint


def _to_item(r: FtCallForProposals, body_threshold: int) -> EntrepreneurInstrumentItem:
    base = _proposal_to_item(r, body_threshold=body_threshold)
    programme, family, intermediary = _classify(r)
    return EntrepreneurInstrumentItem(
        **base.model_dump(), programme=programme,
        instrument_family=family, intermediary=intermediary,
    )


_DESC = """**What it does**
Returns the EU financial instruments that support **entrepreneurs delivered through an intermediary or platform** — the money a founder reaches *via* a system stakeholder, not the raw call list. Scoped by `topic_id` family and tagged with the **`intermediary`** that actually delivers each instrument:
- **EIC** (Accelerator, STEP Scale-up, Transition, Pathfinder) → **EIC Fund** (blended finance / equity) + **EISMEA**.
- **Single Market Programme (SME strand)** → **EISMEA + Enterprise Europe Network**.
- **Interregional Innovation Investments (I3)** → regional innovation ecosystems (managing authorities).
- **Digital Europe** → **European Digital Innovation Hubs (EDIH)**.
- **ESF+ / EaSI** → national managing authorities / EaSI microfinance intermediaries.
- **Erasmus for Young Entrepreneurs** → EYE intermediary organisations.

Each item carries a derived **`programme`**, **`instrument_family`** and **`intermediary`** so the payload answers *who delivers it*.

**When to use it**
For an accelerator, incubator, business angel or ecosystem builder (like KinEtix Impact) that wants the intermediated-instrument list in one call, to pull into its own systems. The Tenderator is the profile-matched day-to-day view; this is the machine-readable equivalent.

**Input**
- `status` — comma list, default `open,forthcoming` (also `closed`, `under-evaluation`; `all` for every status).
- `programme` — one of the coarse labels (e.g. `HORIZON (EIC)`, `Digital Europe`, `Single Market Programme`).
- `deadline_before` — only calls closing on/before this date.
- `q` — free text over title / description.
- `limit` (default 20, max 50), `page`.

**Try it**
```
GET /api/v2/funding/entrepreneur-instruments
GET /api/v2/funding/entrepreneur-instruments?programme=HORIZON%20(EIC)&status=open
GET /api/v2/funding/entrepreneur-instruments?status=all&q=accelerator
```

**You get back**
A `PaginatedResponse[EntrepreneurInstrumentItem]` — each item carries `topic_id` (stable English id, e.g. `HORIZON-EIC-2026-ACCELERATOR-01`), `programme`, `instrument_family`, **`intermediary`**, `title`, `status`, `deadline`, `indicative_budget`, `source_url` and the 5 datapoints. Most recent deadlines first.

**Coverage note**
`ESF+ / EaSI` and `Erasmus for Young Entrepreneurs` families are wired but Brubru currently holds few or no open rows for them (they appear once the F&T Portal publishes calls). `Digital Europe` is matched on the whole `DIGITAL-` prefix, which is broader than EDIH alone.

**Data freshness**
Daily sync from the EU Funding & Tenders Portal (SEDIA). Reads existing data — no dedicated scraper."""


@router.get(
    "/entrepreneur-instruments",
    response_model=PaginatedResponse[EntrepreneurInstrumentItem],
    tags=["v2-funding"],
    summary="EU financial instruments for entrepreneurs, by delivery intermediary",
    description=_DESC,
)
async def entrepreneur_instruments(
    request: Request,
    status: str = Query("open,forthcoming", description="Comma list: open,forthcoming (default) | closed | under-evaluation | all"),
    programme: Optional[str] = Query(None, description="Coarse programme label, e.g. 'HORIZON (EIC)', 'Digital Europe', 'Single Market Programme'"),
    deadline_before: Optional[date] = Query(None, description="Only calls closing on/before this date (YYYY-MM-DD)"),
    q: Optional[str] = Query(None, description="Substring match on title / description"),
    limit: int = Query(20, ge=1, le=50),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EntrepreneurInstrumentItem]:
    filters = [FtCallForProposals.is_test == False, _base_condition()]  # noqa: E712

    status_n = (status or "open,forthcoming").strip().lower()
    if status_n != "all":
        wanted = [s.strip() for s in status_n.split(",") if s.strip()]
        if wanted:
            filters.append(FtCallForProposals.status.in_(wanted))

    if programme:
        filters.append(_programme_condition(programme))
    if deadline_before:
        filters.append(FtCallForProposals.deadline <= deadline_before)
    if q:
        like = f"%{q}%"
        filters.append((FtCallForProposals.title.ilike(like)) | (FtCallForProposals.description.ilike(like)))

    query = db.query(FtCallForProposals).filter(and_(*filters))
    total = query.count()
    rows = (
        query.order_by(FtCallForProposals.deadline.desc().nullslast(), FtCallForProposals.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return build_envelope(
        [_to_item(r, body_threshold) for r in rows],
        total=total, page=page, limit=limit,
        op_core_title="EU entrepreneur financial instruments (intermediated)",
        op_core_type="EU funding instruments",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["/api/v2/funding/startups", "/api/v2/funding/calls-for-proposals"],
    )
