"""
Sync status / freshness API.

Read-only view of when each MEUB feed last refreshed, powering the
"Updated X ago" chips in the My EU Bubble feed headers. Written by the
cron tier endpoints (see api/cron.py + services/sync/).
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from services.sync.freshness import get_freshness

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Sync Status"])


@router.get(
    "/freshness",
    summary="See when each My EU Bubble feed last updated",
    description=(
        "**What it does**\n"
        "Lists every auto-synced My EU Bubble feed (News, My OJ, Votes, "
        "Calendar, Transcripts, Lobby Meetings, Parliamentary Questions) with "
        "when it last refreshed and whether it is currently stale.\n\n"
        "**When to use it**\n"
        "To show an 'Updated X ago' indicator on a feed, or to check whether "
        "a feed is behind.\n\n"
        "**Input**\nNone.\n\n"
        "**Try it**\nOpen it directly; no sign-in needed.\n\n"
        "**You get back**\n"
        "One entry per feed: its key, label, cadence tier, last run/success "
        "time, and a `stale` flag."
    ),
)
def get_sync_freshness(db: Session = Depends(get_db)) -> dict:
    """Latest run per MEUB feed for the freshness chips."""
    return {"sources": get_freshness(db)}
