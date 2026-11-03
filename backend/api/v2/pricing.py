"""What each API call costs, read from the one table the meter itself uses (3 Nov 2026). Public, no key:
the API Console shows the price of a call before Send, and nothing may be charged by surprise."""
from fastapi import APIRouter, Response

from services.billing.api_meter import (
    SANDBOX_GLOBAL_CAP,
    SANDBOX_IP_CAP,
    SANDBOX_MAX_LIMIT,
    SANDBOX_MAX_PAGE,
    _DEFAULT_COST,
    _DEFAULT_LABEL,
    _PATTERNS,
)

router = APIRouter(tags=["v2-docs"])


@router.get(
    "/pricing",
    summary="What each API call costs",
    description="""**What it does**
Lists the price of a call to the API in euros: the default price and every route family that costs more, with what the public sandbox allows.

**When to use it**
Before spending a balance: to show or check what a call will cost. The price actually charged comes back on each call in the `X-Brubru-Cost-Eur` header, and the balance left in `X-Brubru-Balance-Eur`.

**Input**
None. No API key is needed and the call is free.

**Try it**
`GET /api/v2/pricing`

**You get back**
`currency`; `default` (`cost_eur`, `label`); `routes`, each with `pattern` (a regular expression over the path, first match wins), `cost_eur` and `label`; `sandbox`, the public try-it allowance (`calls_per_visitor_per_day`, `calls_per_day_in_total`, `max_limit`, `max_page`).""",
)
def api_pricing(response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {
        "currency": "EUR",
        "default": {"cost_eur": _DEFAULT_COST / 1_000_000, "label": _DEFAULT_LABEL},
        "routes": [
            {"pattern": pattern.pattern, "cost_eur": cost / 1_000_000, "label": label}
            for pattern, cost, label in _PATTERNS if pattern.pattern.startswith(("^/api/v2/", "^/api/v[12]/"))
        ],
        "sandbox": {
            "calls_per_visitor_per_day": SANDBOX_IP_CAP,
            "calls_per_day_in_total": SANDBOX_GLOBAL_CAP,
            "max_limit": SANDBOX_MAX_LIMIT,
            "max_page": SANDBOX_MAX_PAGE,
        },
    }
