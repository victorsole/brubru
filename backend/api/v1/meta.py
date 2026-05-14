"""
/api/v1 meta endpoints: ping, version.

Ping is unauthenticated so customers can health-check without spending a key.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from models.user import User
from ._deps import api_user_with_rate_limit

router = APIRouter(tags=["v1-meta"])


class PingResponse(BaseModel):
    status: str = "ok"
    service: str = "brubru-data-provider"
    version: str = "v1"
    time: datetime


class WhoAmIResponse(BaseModel):
    user_id: str
    tier: str
    api_tier: str = "free"               # Per-key rate-limit tier: free | pro | enterprise
    rate_limit_limit: int
    rate_limit_remaining: int


@router.get(
    "/ping",
    response_model=PingResponse,
    summary="Health check — confirm the API is reachable (unauthenticated, no rate-limit cost)",
    description="""**What it does**
Returns a small JSON heartbeat confirming the v1 API service is alive. Unauthenticated and rate-limit free — safe to poll from a status page or load balancer.

**When to use it**
For uptime monitoring, smoke-testing a CI deployment, or as the first call when integrating Brubru's API to confirm connectivity before testing authenticated endpoints.

**Input**
No parameters. No `X-API-Key` header required.

**Try it**
```
GET /api/v1/ping
```

**You get back**
A `PingResponse` with `status: "ok"`, `service: "brubru-data-provider"`, `version: "v1"`, and `time` (server UTC timestamp). The `time` field reflects the server clock — useful for diagnosing clock-skew issues.

**Data freshness**
Live pass-through (no cache; computed on each request). The `time` field is the server's UTC clock at the moment of the call.""",
)
async def ping() -> PingResponse:
    return PingResponse(time=datetime.utcnow())


@router.get(
    "/whoami",
    response_model=WhoAmIResponse,
    summary="Inspect the API key holder + rate-limit budget (costs 1 request)",
    description="""**What it does**
Returns identity + rate-limit info for the API key in the `X-API-Key` header — `user_id`, subscription tier, API rate-limit tier (free / pro / enterprise), and remaining requests in the current window.

**When to use it**
To confirm an API key is valid + which tier it belongs to + how many requests remain in the current minute. Useful when debugging a 429 (rate-limited) or 401 (invalid key) response. Costs 1 request against your rate-limit budget so don't poll it tight-loop.

**Input**
No parameters. Requires an `X-API-Key` header.

**Try it**
```
GET /api/v1/whoami
```

**You get back**
A `WhoAmIResponse` with `user_id` (UUID), `tier` (subscription tier — Starter / Advocate / Professional / EP / Admin / White), `api_tier` (rate-limit tier — `free` / `pro` / `enterprise`), `rate_limit_limit` (requests per minute), `rate_limit_remaining` (requests remaining in the current window).

**Data freshness**
Live pass-through (no cache; computed on each request). Reflects the live state of your API key + the current rate-limit bucket.""",
)
async def whoami(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
) -> WhoAmIResponse:
    return WhoAmIResponse(
        user_id=str(user.id),
        tier=user.subscription_tier or "",
        api_tier=getattr(request.state, "rate_limit_tier", "free"),
        rate_limit_limit=getattr(request.state, "rate_limit_limit", 60),
        rate_limit_remaining=getattr(request.state, "rate_limit_remaining", 60),
    )
