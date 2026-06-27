"""
Billing refund middleware (Phase B, 21 May 2026).

The per-call euro debit happens in `api_user_with_rate_limit` BEFORE the
route handler runs. If the route handler crashes (5xx), the user shouldn't
be billed for work that didn't ship.

This Starlette middleware observes the final response status:
    - 5xx → refund the debit + mark the usage event refunded
    - 4xx → no refund (caller-side error; the work that ran still consumed budget)
    - 2xx/3xx → no refund

The middleware looks at `request.state.billing_event_id` and
`request.state.billing_cost_micro` (set by the dependency). If those are
absent, this middleware is a no-op — applies to free endpoints and to
non-v1 routes.

Sandbox keys are NOT refunded; the sandbox pool counter advances regardless
of route success (otherwise a bug in our handler would let an attacker
exceed the daily cap by triggering 500s).
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.database import SessionLocal
from services.billing.api_meter import mark_event_refunded, refund

logger = logging.getLogger(__name__)


class BillingRefundMiddleware(BaseHTTPMiddleware):
    """Refund the per-call debit on 5xx responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # Consider both metered API surfaces (the per-call debit runs for v1 and v2).
        if not request.url.path.startswith(("/api/v1/", "/api/v2/")):
            return response

        # If the dependency didn't set billing state, nothing to refund.
        event_id = getattr(request.state, "billing_event_id", None)
        cost_micro = getattr(request.state, "billing_cost_micro", None)
        user_id_str = getattr(request.state, "billing_user_id", None)
        is_sandbox = getattr(request.state, "billing_is_sandbox", False)

        if event_id is None or cost_micro is None or user_id_str is None:
            return response

        # Sandbox keys are not refunded — sandbox pool counter advances
        # regardless to prevent abuse via deliberate 500 triggers.
        if is_sandbox:
            return response

        # Refund only on 5xx.
        if response.status_code < 500 or response.status_code >= 600:
            return response

        db = SessionLocal()
        try:
            refund(db, user_id_str, int(cost_micro))
            mark_event_refunded(db, int(event_id))
            logger.info(
                f"[billing] refunded {cost_micro} μEUR to user {user_id_str} "
                f"(event {event_id}, status {response.status_code})"
            )
        except Exception as exc:
            logger.error(f"[billing] refund failed for event {event_id}: {exc}")
        finally:
            db.close()

        return response
