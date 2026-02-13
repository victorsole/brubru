"""
Personalization API

Endpoints for personalised experiences such as greeting generation.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Dict, Optional

from api.auth import get_current_user
from models.user import User
from services.personalization.greeting_service import generate_personalized_greeting


router = APIRouter(prefix="/personalization", tags=["personalization"])


class GreetingResponse(BaseModel):
    message: str
    metadata: Dict[str, str]


@router.get("/greeting", response_model=GreetingResponse)
async def get_greeting(
    previous_last_login: Optional[str] = Query(
        None,
        description="ISO datetime of user's previous login (from login response)"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a personalised greeting for the authenticated user.
    Uses preferred_name > first_name > derived first token from full_name.
    Defaults timezone to Europe/Brussels and language to 'en' if not provided.

    Available to all tiers to improve engagement and retention.
    """
    # Parse previous_last_login if provided
    prev_login = None
    if previous_last_login:
        try:
            prev_login = datetime.fromisoformat(previous_last_login)
        except (ValueError, TypeError):
            pass  # Silently ignore malformed dates

    result = generate_personalized_greeting(
        first_name=current_user.first_name,
        preferred_name=current_user.preferred_name,
        timezone=current_user.timezone,
        language=current_user.language,
        full_name=current_user.full_name,
        previous_last_login=prev_login,
    )
    return GreetingResponse(message=result.message, metadata=result.metadata)
