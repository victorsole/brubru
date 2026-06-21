"""
Shared dependencies for /api/v1/* endpoints.

- api_user_with_rate_limit: authenticates via X-API-Key, enforces scope-based
  authorisation, applies the 60 req/min rate-limit, then debits the per-call
  euro cost (Phase B billing). Refund on 5xx happens in the billing middleware
  in api/v1/_billing_middleware.py.

Order of checks (fail-fast):
    1. Auth (get_api_user) — valid + non-revoked + non-expired key
    2. Scope match against requested path
    3. Rate limit
    4. Balance / sandbox-pool debit
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.auth_api_key import get_api_user
from core.database import get_db
from models.user import User
from services.api_keys.scopes import is_free_path, resolve_required_scope
from services.billing.api_meter import (
    debit,
    record_usage,
    resolve_cost_micro,
    sandbox_consume,
)
from services.rate_limiter.global_rate_limiter import get_rate_limiter


async def api_user_with_rate_limit(
    request: Request,
    user: User = Depends(get_api_user),
    db: Session = Depends(get_db),
) -> User:
    """Authenticated user + scope + rate-limit + per-call euro debit.

    Free paths (ping / whoami / meta-enums / openapi / docs) skip the debit
    entirely. Sandbox keys debit against the shared daily pool instead of the
    user's balance.
    """
    api_key = getattr(request.state, "api_key", None)
    if api_key is None:
        # Defensive: get_api_user should always attach it.
        raise HTTPException(status_code=500, detail="api_key missing from request state")

    path = request.url.path

    # --- Scope check ----------------------------------------------------
    required_scope = resolve_required_scope(path)
    if not api_key.grants_scope(required_scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": f"Forbidden: this API key is not scoped for {required_scope!r}",
                "reason_code": "scope_missing",
                "required_scope": required_scope,
            },
        )
    request.state.required_scope = required_scope

    # --- Rate limit -----------------------------------------------------
    tier = getattr(api_key, "api_tier", None) or "free"
    limiter = get_rate_limiter()
    allowed, retry_after = await limiter.check_api_key_limit(str(api_key.id), tier=tier)
    remaining = limiter.get_remaining_api_key_calls(str(api_key.id), tier=tier)
    cfg = limiter.get_limit_for_tier(tier)

    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_limit = cfg.calls
    request.state.rate_limit_tier = tier

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {cfg.calls} requests per minute (tier={tier})",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(cfg.calls),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Tier": tier,
            },
        )

    # --- Billing --------------------------------------------------------
    # Free paths: no debit, no usage event. Saves DB writes on the most-hit
    # endpoints (ping is the canonical health check).
    if is_free_path(path):
        request.state.billing_skipped = True
        return user

    # Admin users (role='admin') call their own API for free. Rate limit still
    # applies, but no euro debit and no usage event — Brubru's operators must
    # not pay to query infrastructure they own. Hardcoded list-of-one today
    # (hello@beresol.eu); extend via the users.role column if more admins land.
    if getattr(user, "role", None) == "admin":
        request.state.billing_skipped = True
        request.state.billing_admin_exempt = True
        return user

    cost_micro, _label = resolve_cost_micro(path)
    is_sandbox = bool(getattr(request.state, "api_key_is_sandbox", False))

    if is_sandbox:
        # Sandbox key: bills against the shared pool, not the user's balance.
        client_ip = request.client.host if request.client else "0.0.0.0"
        ok, reason = sandbox_consume(db, client_ip)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": (
                        "Public sandbox cap reached. Sign up at brubru.beresol.eu "
                        "and mint your own API key to keep building."
                    ),
                    "reason_code": reason,
                    "top_up_url": "https://brubru.beresol.eu/api",
                },
            )
    else:
        # Normal user-key debit. Atomic.
        ok, balance_or_remaining = debit(db, api_key.user_id, cost_micro)
        if not ok:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "Insufficient balance. Top up at /api/billing.",
                    "reason_code": "insufficient_balance",
                    "balance_eur_micro": balance_or_remaining,
                    "cost_eur_micro": cost_micro,
                    "top_up_url": "https://brubru.beresol.eu/api/billing",
                },
            )

    # Record usage. The middleware in _billing_middleware.py may flip
    # `refunded` after the response if the route 5xx'd.
    evt = record_usage(
        db,
        user_id=api_key.user_id,
        api_key_id=api_key.id,
        endpoint=path,
        method=request.method,
        cost_micro=cost_micro,
        request_id=None,  # set by the v1 error/envelope wrapper for 4xx/5xx
        status_code=None,
        is_sandbox=is_sandbox,
    )
    request.state.billing_event_id = evt.id
    request.state.billing_cost_micro = cost_micro
    request.state.billing_is_sandbox = is_sandbox
    request.state.billing_user_id = str(api_key.user_id)

    return user
