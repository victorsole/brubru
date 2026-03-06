"""
Daily EU Brief API

Serves today's EU institutional headlines for the chat page Daily Brief.
Public endpoint (no auth required) -- pre-users need to see this.
"""

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.database import get_db
from models.daily_brief import DailyBrief

router = APIRouter(prefix="/api/daily-brief", tags=["daily-brief"])


class BriefItem(BaseModel):
    headline: str
    url: str
    source: str
    category: str
    snippet: Optional[str] = None
    suggested_query: Optional[str] = None

    model_config = {"from_attributes": True}


class DailyBriefResponse(BaseModel):
    date: str
    items: List[BriefItem]
    total: int


@router.get("", response_model=DailyBriefResponse)
def get_daily_brief(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Get today's EU institutional headlines.

    Falls back to yesterday if no items for today yet (scraper hasn't run).
    Public endpoint -- no auth required.
    """
    today = date.today()

    # Try today first
    items = (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority, DailyBrief.created_at)
        .limit(limit)
        .all()
    )

    brief_date = today

    # Fallback to yesterday if empty
    if not items:
        yesterday = today - timedelta(days=1)
        items = (
            db.query(DailyBrief)
            .filter(DailyBrief.brief_date == yesterday)
            .order_by(DailyBrief.priority, DailyBrief.created_at)
            .limit(limit)
            .all()
        )
        brief_date = yesterday

    # Fallback to most recent date with data
    if not items:
        latest = (
            db.query(DailyBrief.brief_date)
            .order_by(desc(DailyBrief.brief_date))
            .first()
        )
        if latest:
            brief_date = latest[0]
            items = (
                db.query(DailyBrief)
                .filter(DailyBrief.brief_date == brief_date)
                .order_by(DailyBrief.priority, DailyBrief.created_at)
                .limit(limit)
                .all()
            )

    return DailyBriefResponse(
        date=brief_date.isoformat(),
        items=[BriefItem.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/stats")
def get_brief_stats(db: Session = Depends(get_db)):
    """Knowledge base stats for the chat page badge."""
    from models.legislative_train import LegislativeCarriage

    total_files = db.query(LegislativeCarriage).count()

    # Count knowledge guides
    import os
    guides_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'guides')
    total_guides = len([f for f in os.listdir(guides_dir) if f.endswith('.md')]) if os.path.isdir(guides_dir) else 0

    # Latest brief date
    latest = (
        db.query(DailyBrief.brief_date)
        .order_by(desc(DailyBrief.brief_date))
        .first()
    )

    return {
        "total_guides": total_guides,
        "total_files": total_files,
        "last_trained": latest[0].isoformat() if latest else None,
    }
