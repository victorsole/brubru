"""
Personalization API

Endpoints for personalised experiences such as greeting generation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict

from api.auth import get_current_user
from models.user import User
from services.personalization.greeting_service import generate_personalized_greeting


router = APIRouter(prefix="/personalization", tags=["personalization"])


class GreetingResponse(BaseModel):
    message: str
    metadata: Dict[str, str]


@router.get("/greeting", response_model=GreetingResponse)
async def get_greeting(current_user: User = Depends(get_current_user)):
    """
    Generate a personalised greeting for the authenticated user.
    Uses preferred_name > first_name > derived first token from full_name.
    Defaults timezone to Europe/Brussels and language to 'en' if not provided.
    """
    # Feature gating: available only to Yellow and Blue tiers
    if (current_user.subscription_tier or "").lower() not in {"yellow", "blue"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Personalised greeting is available to Yellow and Blue tiers."
        )

    result = generate_personalized_greeting(
        first_name=current_user.first_name,
        preferred_name=current_user.preferred_name,
        timezone=current_user.timezone,
        language=current_user.language,
        full_name=current_user.full_name,
    )
    return GreetingResponse(message=result.message, metadata=result.metadata)
