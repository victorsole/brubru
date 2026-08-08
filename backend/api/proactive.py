"""
Proactive Chat API.

Endpoints:
- GET /api/proactive/pending   Returns up to 3 briefings Brubru should
                               surface to the authenticated user right now.

The triggers themselves live in ``services/proactive/trigger_engine.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from services.proactive import compute_pending_briefings

from .auth import get_current_user


router = APIRouter(prefix="/api/proactive", tags=["Proactive Chat"])


class ProactiveBriefingResponse(BaseModel):
    trigger_source: str
    title: str
    summary: str
    suggested_query: str
    evidence_refs: List[str] = []
    drill_down_path: Optional[str] = None
    # One entry per file behind the briefing: {title, ref, carriage_id,
    # detail}. Render these as separate lines; do not fold them back into a
    # sentence. Empty for triggers that name no specific file.
    items: List[Dict[str, Any]] = []


class ProactivePendingResponse(BaseModel):
    briefings: List[ProactiveBriefingResponse]
    cap_reached: bool


@router.get(
    "/pending",
    response_model=ProactivePendingResponse,
    summary="Get proactive briefings Brubru wants to surface",
    description=(
        "**What it does**\n\n"
        "Returns up to three briefings that Brubru should bring up to the "
        "authenticated user without being asked: morning brief, new file "
        "matches, tracked-file movement, amendment surges. All briefings are "
        "grounded in real DB rows.\n\n"
        "**When to use it**\n\n"
        "Call from the Chat page on first load each session, and from the "
        "Dashboard. Render any briefings as openers; clicking 'Tell me more' "
        "starts a chat with the `suggested_query` pre-filled.\n\n"
        "**Input**\n\n"
        "Authentication via Bearer JWT. No query parameters.\n\n"
        "**Try it**\n\n"
        "`GET /api/proactive/pending` with `Authorization: Bearer <token>`.\n\n"
        "**You get back**\n\n"
        "An array of 0-3 briefings, each with `trigger_source`, `title`, "
        "`summary`, `suggested_query`, optional `evidence_refs` (procedure "
        "refs) and `drill_down_path`. Briefings that name specific files also "
        "carry `items`: one entry per file with `title`, `ref`, `carriage_id` "
        "and `detail`. Render those as separate lines — `summary` is a short "
        "lead-in to the list, not a substitute for it. Empty array if Brubru "
        "has nothing to surface — never fabricates."
    ),
)
async def get_pending_proactive(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProactivePendingResponse:
    briefings = compute_pending_briefings(db, current_user)
    return ProactivePendingResponse(
        briefings=[
            ProactiveBriefingResponse(**b.to_dict()) for b in briefings
        ],
        cap_reached=len(briefings) >= 3,
    )
