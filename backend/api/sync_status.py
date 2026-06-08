"""
Sync status / freshness API.

Read-only view of when each MEUB feed last refreshed, powering the
"Updated X ago" chips in the My EU Bubble feed headers. Written by the
cron tier endpoints (see api/cron.py + services/sync/).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
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


@router.get(
    "/health",
    summary="Is the hourly sync dispatcher alive?",
    description=(
        "**What it does**\n"
        "Reports when the hourly cron dispatcher (`scripts/cron_dispatch.py`) "
        "last fired its liveness heartbeat, plus when the registry `fast` "
        "(News/OJ/Votes) and `warm` (Calendar/Transcripts/Lobby/Questions) "
        "tiers last ran.\n\n"
        "**When to use it**\n"
        "To confirm the Railway cron is actually scheduled — `alive` is true "
        "only if the dispatcher checked in within the last 90 minutes (it runs "
        "hourly). If `alive` is false, the cron service is not running and MEUB "
        "feeds will drift.\n\n"
        "**Input**\nNone.\n\n"
        "**You get back**\n"
        "`dispatcher` (last_seen, minutes_ago, alive) and `tiers` (last "
        "fast/warm registry sync time)."
    ),
)
def get_sync_health(db: Session = Depends(get_db)) -> dict:
    """Cron-dispatcher liveness from the hourly heartbeat + last fast/warm sync."""
    last_seen = db.execute(
        text("SELECT max(finished_at) FROM sync_runs WHERE source_key = 'cron_dispatch'")
    ).scalar()
    minutes_ago = None
    alive = False
    if last_seen is not None:
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        minutes_ago = int((datetime.now(timezone.utc) - last_seen).total_seconds() // 60)
        alive = minutes_ago <= 90  # dispatcher runs hourly; 1.5h grace

    tiers = {}
    for tier in ("fast", "warm"):
        ts = db.execute(
            text("SELECT max(finished_at) FROM sync_runs WHERE tier = :t AND status = 'success'"),
            {"t": tier},
        ).scalar()
        tiers[tier] = ts.isoformat() if ts else None

    return {
        "dispatcher": {
            "last_seen": last_seen.isoformat() if last_seen else None,
            "minutes_ago": minutes_ago,
            "alive": alive,
        },
        "tiers": tiers,
    }
