"""GET /api/v2/funding/all: an alias of /api/v2/funding/opportunities since 30 Oct 2026.

Until then /funding/all was its own union: the EU agencies' own tenders, grants and calls for expression of
interest, plus the funds' budget rows (cohesion allocations, Solidarity Fund cases, CAP payments). The
funding standard's consolidated lists replaced it (proposal of 23 Oct 2026 §6, Phase 3d): every call and
tender, each procedure once, on /opportunities, and the funds' money on /budgets. By Victor's decision the
alias waited for the funding matcher, which read /funding/all as its agency source, to read
/opportunities?body=agencies instead.

The route keeps answering until the date set for legacy routes, as /opportunities does, with its old
`type` (item_type's legacy name). A budget item type or fund code is refused with the list it moved to.
"""
from __future__ import annotations

import inspect
import typing
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1._envelope import PaginatedResponse
from services.funding.shared_fields import FUND_NAMES
from . import opportunities as _opp

router = APIRouter()

_BUDGET_TYPES = ("cohesion_allocation", "solidarity_case", "cap_payment")
_MOVED = ("The funds' budget rows (cohesion allocations, Solidarity Fund cases, CAP payments) moved to "
          "/api/v2/funding/budgets on 30 Oct 2026; /funding/all is now /funding/opportunities.")

_DESC = """**Deprecated alias (30 Oct 2026).** The same list as `/api/v2/funding/opportunities`: every call and tender Brubru holds (TED, the Funding & Tenders Portal and the EU agencies), each procedure once. It answers until the date set for legacy routes.

**What changed**
Until 30 Oct 2026 this route served the EU agencies' own tenders, grants and calls for expression of interest, and the funds' budget rows. The agencies' items are on `/api/v2/funding/opportunities` (`body=agencies` for all of them, or an agency's code); the budget rows (cohesion allocations, Solidarity Fund cases, CAP payments) are on `/api/v2/funding/budgets`. A request for a budget item type or a fund's code is refused with a 400 that names it. `order=title` is no longer offered.

**When to use it**
Only to keep an existing integration working: use `/api/v2/funding/opportunities` and `/api/v2/funding/budgets` for anything new.

**Input**
As `/api/v2/funding/opportunities`; `type` is still accepted as `item_type`'s legacy name.

**Try it**
```
GET /api/v2/funding/all?body=agencies
GET /api/v2/funding/all?item_type=tender&order=recent
```

**You get back**
What `/api/v2/funding/opportunities` returns.

**Data freshness**
As `/api/v2/funding/opportunities`."""


async def funding_all(**kwargs):
    legacy = kwargs.pop("type", None)
    item_type = kwargs.get("item_type") or legacy
    body = (kwargs.get("body") or "").strip().lower()
    if item_type in _BUDGET_TYPES or body in FUND_NAMES:
        raise HTTPException(status_code=400, detail=_MOVED)
    if legacy and not kwargs.get("item_type"):
        kwargs["item_type"] = legacy
    return await _opp.list_opportunities(**kwargs)


# The alias takes /opportunities' own parameters (resolved, since that module's annotations are strings
# FastAPI would read in this module) plus the old `type`.
_hints = typing.get_type_hints(_opp.list_opportunities)
_params = [p.replace(annotation=_hints.get(name, p.annotation))
           for name, p in inspect.signature(_opp.list_opportunities).parameters.items()]
_params.append(inspect.Parameter("type", inspect.Parameter.KEYWORD_ONLY, annotation=Optional[str],
                                 default=Query(None, description="The legacy name of item_type.")))
funding_all.__signature__ = inspect.Signature(_params)
# The handler it forwards every parameter to (tests read that one's source).
funding_all.forwards_to = _opp.list_opportunities

router.add_api_route(
    "/all", funding_all, methods=["GET"], response_model=PaginatedResponse[_opp.OpportunityItem],
    tags=["v2-funding"], deprecated=True, description=_DESC,
    summary="Deprecated alias of /funding/opportunities: every call and tender, each procedure once")
