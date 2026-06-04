"""
Freshness tracking for MEUB auto-sync.

record_run() writes one sync_runs row per source run (called by the cron tier
endpoints). get_freshness() returns the latest run per source for the UI chip.
find_stale() returns sources whose last success is older than their threshold
(drives the staleness email).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.sync.source_registry import MEUB_SOURCES, get_source

logger = logging.getLogger(__name__)


def record_run(
    db: Session,
    *,
    source_key: str,
    tier: Optional[str],
    status: str,
    items_added: Optional[int] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> None:
    """Insert a sync_runs row. Fail-soft: never let bookkeeping break a sync."""
    try:
        db.execute(
            text(
                """
                INSERT INTO sync_runs
                    (source_key, tier, status, items_added, error, started_at, finished_at)
                VALUES
                    (:source_key, :tier, :status, :items_added, :error,
                     COALESCE(:started_at, now()), COALESCE(:finished_at, now()))
                """
            ),
            {
                "source_key": source_key,
                "tier": tier,
                "status": status,
                "items_added": items_added,
                "error": (error or None) and str(error)[:2000],
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("record_run failed for %s: %s", source_key, exc)
        db.rollback()


def get_freshness(db: Session) -> List[dict]:
    """Latest run per source, enriched with the registry label/tier."""
    try:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (source_key)
                    source_key, tier, status, items_added, error, started_at, finished_at
                FROM sync_runs
                ORDER BY source_key, started_at DESC
                """
            )
        ).mappings().all()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("get_freshness query failed: %s", exc)
        db.rollback()
        rows = []

    by_key = {r["source_key"]: r for r in rows}
    out: List[dict] = []
    for spec in MEUB_SOURCES:
        r = by_key.get(spec.key)
        last_ok = r["finished_at"] if (r and r["status"] == "success") else None
        out.append(
            {
                "key": spec.key,
                "label": spec.label,
                "tier": spec.tier,
                "status": r["status"] if r else "never",
                "last_run_at": (r["finished_at"].isoformat() if r and r["finished_at"] else None),
                "last_success_at": (last_ok.isoformat() if last_ok else None),
                "items_added": (r["items_added"] if r else None),
                "stale": _is_stale(spec.key, last_ok),
            }
        )
    return out


def _is_stale(source_key: str, last_success: Optional[datetime]) -> bool:
    spec = get_source(source_key)
    if not spec:
        return False
    if last_success is None:
        return True
    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=timezone.utc)
    return last_success < datetime.now(timezone.utc) - timedelta(hours=spec.stale_after_hours)


def find_stale(db: Session, tier: Optional[str] = None) -> List[dict]:
    """Sources past their staleness threshold, optionally filtered by tier."""
    fresh = get_freshness(db)
    return [
        f for f in fresh
        if f["stale"] and (tier is None or f["tier"] == tier)
    ]
