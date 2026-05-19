"""
Personalization API

Endpoints for personalised experiences such as greeting generation. The
greeting now ships with 0 to 2 policy hooks: short, clickable chips that
turn the empty chat state into a proactive opener.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.daily_brief import DailyBrief
from models.user import User
from services.personalization.greeting_service import (
    compose_hooks_from_brief_headlines,
    compose_hooks_from_briefings,
    generate_personalized_greeting,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/personalization", tags=["personalization"])


class PolicyHook(BaseModel):
    label: str
    spoken: str
    suggested_query: str
    source: str


class GreetingResponse(BaseModel):
    message: str
    metadata: Dict[str, str]
    policy_hooks: List[PolicyHook] = []


def _recent_brief_headlines(db: Session, limit: int = 2) -> List[DailyBrief]:
    """
    Return the top headlines from the most recent daily_briefs date that has
    any rows. Falls back through today, yesterday, and most recent.
    """
    today = date.today()
    for d in (today, today - timedelta(days=1)):
        items = (
            db.query(DailyBrief)
            .filter(DailyBrief.brief_date == d)
            .order_by(DailyBrief.priority, DailyBrief.created_at)
            .limit(limit)
            .all()
        )
        if items:
            return items
    latest = (
        db.query(DailyBrief.brief_date)
        .order_by(desc(DailyBrief.brief_date))
        .first()
    )
    if not latest:
        return []
    return (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == latest[0])
        .order_by(DailyBrief.priority, DailyBrief.created_at)
        .limit(limit)
        .all()
    )


def _compute_user_hooks(db: Session, user: User) -> List[Dict[str, str]]:
    """
    For an authenticated user, prefer real proactive briefings (tracked file
    movement, amendment surge, new file matches, morning brief). Fall back
    to the public daily_brief headlines so the chip strip is never empty
    when there is something worth saying.
    """
    hooks: List[Dict[str, str]] = []
    try:
        from services.proactive.trigger_engine import compute_pending_briefings

        briefings = compute_pending_briefings(db, user)
        hooks = compose_hooks_from_briefings(briefings)
    except Exception as exc:
        logger.warning("greeting hook briefing computation failed: %s", exc)
        db.rollback()
        hooks = []

    if hooks:
        return hooks

    try:
        items = _recent_brief_headlines(db, limit=2)
        hooks = compose_hooks_from_brief_headlines(items)
    except Exception as exc:
        logger.warning("greeting hook brief fallback failed: %s", exc)
        db.rollback()
        hooks = []
    return hooks


@router.get("/greeting", response_model=GreetingResponse)
async def get_greeting(
    previous_last_login: Optional[str] = Query(
        None,
        description="ISO datetime of user's previous login (from login response)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a personalised greeting for the authenticated user, plus up
    to two policy hooks Brubru wants to mention proactively.
    """
    prev_login = None
    if previous_last_login:
        try:
            prev_login = datetime.fromisoformat(previous_last_login)
        except (ValueError, TypeError):
            pass

    result = generate_personalized_greeting(
        first_name=current_user.first_name,
        preferred_name=current_user.preferred_name,
        timezone=current_user.timezone,
        language=current_user.language,
        full_name=current_user.full_name,
        previous_last_login=prev_login,
    )
    hooks = _compute_user_hooks(db, current_user)
    return GreetingResponse(
        message=result.message,
        metadata=result.metadata,
        policy_hooks=[PolicyHook(**h) for h in hooks],
    )


@router.get("/greeting/public", response_model=GreetingResponse)
async def get_public_greeting(
    db: Session = Depends(get_db),
):
    """
    Generate a generic greeting for pre-users (no auth). Hooks come from
    the public daily_brief so a first-time visitor still sees Brubru
    speaking, not just waiting.
    """
    result = generate_personalized_greeting(
        first_name=None,
        preferred_name=None,
        timezone=None,
        language=None,
        full_name=None,
        previous_last_login=None,
    )
    # For pre-users the resolved name is "there"; drop the awkward ", there".
    result.message = result.message.replace(", there.", ".", 1)

    hooks: List[Dict[str, str]] = []
    try:
        items = _recent_brief_headlines(db, limit=2)
        hooks = compose_hooks_from_brief_headlines(items)
    except Exception as exc:
        logger.warning("public greeting hook fallback failed: %s", exc)
        db.rollback()
        hooks = []

    return GreetingResponse(
        message=result.message,
        metadata=result.metadata,
        policy_hooks=[PolicyHook(**h) for h in hooks],
    )
