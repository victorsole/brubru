"""Catch a query parameter the API does not accept, instead of ignoring it silently.

The failure this exists for
---------------------------
FastAPI drops an undeclared query parameter and answers **HTTP 200**. On a filtered
collection endpoint that means the caller gets the UNFILTERED corpus back and no
indication that their filter did nothing. It has happened three times on one endpoint:

  * 28 Jul 2026 - `days` was never declared on `/api/v2/news/all`; callers got all
    11,900 items believing the window applied.
  * 28 Jul 2026 - the same on `/api/v2/events/all`, 7,300 events.
  * 8 Sep 2026 - `since`/`until` on `/api/v2/news/all`, which takes `from`/`to`.
    Measured: `?since=2026-09-01&until=2026-09-08` returned **14,720** rows where
    `?from=..&to=..` returned **152**. A 97x over-count, HTTP 200, no warning.

The aliases added the same day fix that specific case. This guard fixes the CLASS, so
the fourth instance is an error rather than a wrong answer.

Two modes, and the default is deliberately not strict
-----------------------------------------------------
Rejecting outright is a **breaking change**: any caller currently passing a stray
parameter starts getting 422. So:

  * default -> **warn**. The response carries `X-Brubru-Unknown-Params: since,foo`.
    Nothing breaks; the mistake becomes visible to the caller and greppable in logs.
  * `API_STRICT_QUERY_PARAMS=true` -> **422** `invalid_query`, listing the offenders
    and what the endpoint does accept.

Flip the flag once the warn header has been quiet in production for a while. That is
the deprecation window, and it is a one-variable change rather than a redeploy.

Why a dependency and not middleware
-----------------------------------
The accepted parameter names come from the MATCHED route, which only exists after
routing. A pure ASGI middleware runs before that, so it would have to re-implement
path matching (which `core/self_links.py` does, and which is the sort of duplicated
production logic `feedback_verify_the_instrument_before_the_reading` warns about).
A dependency runs after routing and before the handler body, which is exactly right.
"""
from __future__ import annotations

import logging
import os
from typing import FrozenSet

from fastapi import HTTPException, Request
from fastapi.dependencies.utils import get_flat_dependant

logger = logging.getLogger(__name__)

# Parameters consumed by middleware rather than by a route signature, so they are
# legitimate everywhere even when a given route does not declare them.
#   format          TabularExportMiddleware (?format=csv|xlsx)
#   key / api_key   query-string auth, accepted on the MCP endpoints
_GLOBAL_ALLOWED: FrozenSet[str] = frozenset({"format", "key", "api_key"})

# Cache per route object: the flat dependant walk is not free and the answer is fixed
# for the process lifetime. Keyed by id() of the route, held weakly by value only.
_ACCEPTED_CACHE: dict[int, FrozenSet[str]] = {}


def _accepted_names(route) -> FrozenSet[str]:
    cached = _ACCEPTED_CACHE.get(id(route))
    if cached is not None:
        return cached
    names: set[str] = set()
    dependant = getattr(route, "dependant", None)
    if dependant is not None:
        flat = get_flat_dependant(dependant, skip_repeats=True)
        for f in list(flat.query_params or []):
            # `.alias` is the name on the wire; `.name` is the Python identifier.
            # They differ exactly where we added an alias (from_ -> "from").
            names.add(getattr(f, "alias", None) or f.name)
    result = frozenset(names)
    _ACCEPTED_CACHE[id(route)] = result
    return result


def strict_mode() -> bool:
    return os.getenv("API_STRICT_QUERY_PARAMS", "false").strip().lower() == "true"


def check_query_params(request: Request) -> None:
    """Compare the request's query keys against what the matched route accepts.

    Never raises in warn mode. Never raises on an introspection failure either: a
    guard that can 500 a working endpoint is worse than the bug it guards against,
    so an unexpected shape degrades to a log line and the request proceeds.
    """
    try:
        route = request.scope.get("route")
        if route is None:
            return
        accepted = _accepted_names(route)
        if not accepted:
            # A route with no declared query params at all. Introspection may simply
            # have found nothing; do not accuse the caller on that basis.
            return
        sent = set(request.query_params.keys())
        unknown = sorted(sent - accepted - _GLOBAL_ALLOWED)
        if not unknown:
            return

        request.state.unknown_query_params = unknown
        logger.warning(
            "[query-guard] %s %s: unknown query params %s (accepts %s)",
            request.method, request.url.path, unknown, sorted(accepted),
        )
        if strict_mode():
            raise HTTPException(
                status_code=422,
                detail={
                    "error": ("Unknown query parameter(s): "
                              + ", ".join(unknown)
                              + ". They were NOT applied."),
                    "reason_code": "invalid_query",
                    "unknown_params": unknown,
                    "accepted_params": sorted(accepted | _GLOBAL_ALLOWED),
                },
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("[query-guard] introspection failed on %s: %s: %s",
                     request.url.path, type(exc).__name__, exc)
