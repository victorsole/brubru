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
    """Authenticated user + per-key rate limit enforcement."""
    api_key = getattr(request.state, "api_key", None)
    if api_key is None:
        # Defensive: get_api_user should always attach it.
        raise HTTPException(status_code=500, detail="api_key missing from request state")

    limiter = get_rate_limiter()
    allowed, retry_after = await limiter.check_api_key_limit(str(api_key.id))
    remaining = limiter.get_remaining_api_key_calls(str(api_key.id))

    # Expose rate-limit info on the response via request.state; endpoints/middleware can surface headers.
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_limit = 60

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 60 requests per minute",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": "0",
            },
        )
    return user
