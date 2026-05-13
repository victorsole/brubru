"""
Personalised Impact API.

Endpoints:
- GET /api/impact/{procedure_ref}  Returns the "what this means for you"
                                   briefing for the authenticated user on a
                                   specific legislative file.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.legislative_train import LegislativeCarriage
from models.user import User
from services.impact import compose_impact_for_carriage

from .auth import get_current_user


router = APIRouter(prefix="/api/impact", tags=["Personalised Impact"])


class ActionLinkResponse(BaseModel):
    label: str
    path: str
    rationale: str = ""


class ImpactBlockResponse(BaseModel):
    procedure_ref: Optional[str]
    title: str
    headline: str
    what_it_is: str
    why_it_touches_you: str
    what_to_watch: str
    actions_you_can_take: List[ActionLinkResponse]
    matched_policy_areas: List[str]
    matched_sectors: List[str]
    user_profile_was_partial: bool


@router.get(
    "/{procedure_ref:path}",
    response_model=ImpactBlockResponse,
    summary="Get the personalised impact briefing for a file",
    description=(
        "**What it does**\n\n"
        "Composes a four-section 'what this means for you' briefing for a "
        "specific legislative file from the user's profile and the file's "
        "real data (status, lead committee, policy areas, days in status, "
        "blocked flag). No LLM call; no synthesis.\n\n"
        "**When to use it**\n\n"
        "Call from the legislative file detail modal, the Dashboard 'New "
        "this week' tile, or from Chat when the user asks about a specific "
        "tracked file.\n\n"
        "**Input**\n\n"
        "URL path parameter `procedure_ref` = OEIL procedure reference, e.g. "
        "`2024/0176(COD)`. Authentication via Bearer JWT.\n\n"
        "**Try it**\n\n"
        "`GET /api/impact/2024%2F0176%28COD%29` with the Bearer token.\n\n"
        "**You get back**\n\n"
        "`what_it_is`, `why_it_touches_you`, `what_to_watch`, four concrete "
        "`actions_you_can_take` with paths, plus a `user_profile_was_partial` "
        "flag that's true when the user has not yet supplied enough profile "
        "data for personalisation. The block is always grounded in real DB "
        "rows — never fabricated."
    ),
)
async def get_impact_for_file(
    procedure_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImpactBlockResponse:
    carriage = (
        db.query(LegislativeCarriage)
        .filter(LegislativeCarriage.oeil_procedure_ref == procedure_ref)
        .first()
    )
    if not carriage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No legislative file found with procedure_ref={procedure_ref}",
        )

    block = compose_impact_for_carriage(current_user, carriage)
    payload = block.to_dict()
    return ImpactBlockResponse(**payload)
