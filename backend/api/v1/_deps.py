"""
Shared dependencies for /api/v1/* endpoints.

- api_user_with_rate_limit: authenticates via X-API-Key and enforces the
  60 req/min soft sliding window on the key.
"""

from fastapi import Depends, HTTPException, Request, status

from api.auth_api_key import get_api_user
from models.user import User
from services.rate_limiter.global_rate_limiter import get_rate_limiter


async def api_user_with_rate_limit(
    request: Request,
    user: User = Depends(get_api_user),
) -> User:
    """Authenticated user + per-key, tier-aware rate-limit enforcement."""
    api_key = getattr(request.state, "api_key", None)
    if api_key is None:
        # Defensive: get_api_user should always attach it.
        raise HTTPException(status_code=500, detail="api_key missing from request state")

    tier = getattr(api_key, "api_tier", None) or "free"

    limiter = get_rate_limiter()
    allowed, retry_after = await limiter.check_api_key_limit(str(api_key.id), tier=tier)
    remaining = limiter.get_remaining_api_key_calls(str(api_key.id), tier=tier)
    cfg = limiter.get_limit_for_tier(tier)

    # Expose rate-limit info on the response via request.state; middleware emits headers.
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
    return user
