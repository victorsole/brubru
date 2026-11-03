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
    is_probe_header,
    resolve_cost_micro,
    sandbox_consume_counted,
    sandbox_refusal,
)
from services.rate_limiter.global_rate_limiter import get_rate_limiter
from api.v1._query_guard import check_query_params


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

    # --- Unknown query parameters ---------------------------------------
    # FastAPI drops an undeclared query param and answers 200, so a filter that did
    # nothing looks like a filtered result. Warn by default; 422 when
    # API_STRICT_QUERY_PARAMS=true. See api/v1/_query_guard.py for the three
    # measured instances this exists for.
    check_query_params(request)

    # --- Scope check ----------------------------------------------------
    required_scope = resolve_required_scope(path)
    if required_scope is not None and not api_key.grants_route(path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "This evaluation key covers a selection of routes, and this is not one of them.",
                "reason_code": "route_not_included",
            },
        )
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

    cost_micro, _label = resolve_cost_micro(path)
    is_sandbox = bool(getattr(request.state, "api_key_is_sandbox", False))

    # Admin users (role='admin') call their own API for free. Rate limit still
    # applies, but no euro debit and no usage event — Brubru's operators must
    # not pay to query infrastructure they own. Hardcoded list-of-one today
    # (hello@beresol.eu); extend via the users.role column if more admins land.
    # The public sandbox key is OWNED by an admin, so it is asked first: until
    # 3 Nov 2026 this check came first and no sandbox cap could ever apply.
    if not is_sandbox and getattr(user, "role", None) == "admin":
        request.state.billing_skipped = True
        request.state.billing_admin_exempt = True
        return user

    balance_micro = None
    if is_sandbox:
        refusal = sandbox_refusal(request.method, path, request.query_params, cost_micro)
        if refusal is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": refusal[1], "reason_code": refusal[0], "top_up_url": "https://brubru.beresol.eu/api"},
            )
        # Sandbox key: bills against the shared pool, not the user's balance.
        client_ip = request.client.host if request.client else "0.0.0.0"
        ok, reason, ip_left, pool_left = sandbox_consume_counted(db, client_ip)
        request.state.sandbox_ip_left = ip_left
        request.state.sandbox_pool_left = pool_left
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
        balance_micro = balance_or_remaining
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
        # Our own verification traffic still bills and still rate-limits -- it is
        # only excluded from usage ANALYTICS. Marking it must never become a way
        # to call the API for free.
        is_probe=is_probe_header(request.headers.get("X-Brubru-Probe")),
    )
    request.state.billing_event_id = evt.id
    request.state.billing_cost_micro = cost_micro
    request.state.billing_is_sandbox = is_sandbox
    request.state.billing_user_id = str(api_key.user_id)
    request.state.billing_balance_micro = balance_micro

    return user
