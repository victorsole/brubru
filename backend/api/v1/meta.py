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


@router.get("/ping", response_model=PingResponse, summary="Health check (unauthenticated)")
async def ping() -> PingResponse:
    return PingResponse(time=datetime.utcnow())


@router.get(
    "/whoami",
    response_model=WhoAmIResponse,
    summary="Who is the key holder? (authenticated; costs 1 request)",
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
