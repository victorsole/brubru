"""
Freshness tracking for MEUB auto-sync.

record_run() writes one sync_runs row per source run (called by the cron tier
endpoints). get_freshness() returns the latest run per source for the UI chip.
find_stale() returns sources whose last success is older than their threshold
(drives the staleness email).
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.sync.source_registry import MEUB_SOURCES, get_source

logger = logging.getLogger(__name__)

# How a job that stopped itself at its time budget opens its `degraded` reason (14 Oct
# 2026). It kept what it had stored, so it is not a failure; but the cron verdict counts
# it as a problem, and two in a row of the same source turn the run red: a source that
# never finishes inside its budget must not sit quietly in `degraded` for ever.
BUDGET_STOP = "time budget reached"

# A site that will not serve us (a timeout, a refused connection, a WAF page, an HTTP error
# status) is the site's state, not a broken job (Victor, 30 Oct 2026: epthinktank.eu has been
# unreachable since 29 Oct, and its two EPRS jobs made the cron red twice a day). Such a run is
# recorded `degraded`, with the reason, while the job's last success is less than
# UNREACHABLE_GRACE_HOURS old; after that it fails as before, and two failures in a row are red.
# A page that answers but no longer parses is never this: it fails at once.
UNREACHABLE = "source unreachable"
UNREACHABLE_GRACE_HOURS = 72


def unreachable_exit(reasons: List[str], last_success: Optional[datetime],
                     now: Optional[datetime] = None) -> int:
    """The exit code of a job whose only errors are refusals: 0 with a `[SYNC_STATUS] degraded:`
    line (the cron runner records it degraded) inside the grace, 1 after it or with no success on
    record. Prints the line itself."""
    now = now or datetime.now(timezone.utc)
    why = "; ".join(reasons)[:600]
    if last_success is not None:
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)
        hours = (now - last_success).total_seconds() / 3600
        if hours < UNREACHABLE_GRACE_HOURS:
            print(f"[SYNC_STATUS] degraded: {UNREACHABLE} ({why}); last good run "
                  f"{last_success:%d %b %H:%M} UTC, {hours:.0f}h ago; it fails after {UNREACHABLE_GRACE_HOURS}h",
                  flush=True)
            return 0
        print(f"[ERROR] {UNREACHABLE} for {hours:.0f}h, over {UNREACHABLE_GRACE_HOURS}h ({why})", flush=True)
        return 1
    print(f"[ERROR] {UNREACHABLE}, and no good run on record ({why})", flush=True)
    return 1


def last_success_at(db: Session, source_key: str) -> Optional[datetime]:
    """When the source last finished with `success` on a deployed runner (a laptop's runs are not
    the production verdict)."""
    return db.execute(text(
        "SELECT max(finished_at) FROM sync_runs WHERE source_key = :k AND status = 'success' "
        "AND runner IS DISTINCT FROM 'local'"), {"k": source_key}).scalar()


def current_runner() -> str:
    """Where this process runs. sync_runs is shared, so a laptop run used to be
    indistinguishable from a container run and could set the production health
    verdict (22 Sep 2026, migration 235)."""
    return os.environ.get("BRUBRU_RUNNER") or (
        "railway" if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME")
        else "local")


def in_app_schedulers_enabled() -> bool:
    """Whether this process may start the in-app schedulers (16 Oct 2026).

    They write to the production database from `.env`, so a laptop backend started
    for chat probes ran them beside Railway's: on 15 Oct a local tender digest gave
    5 users a second digest, and the weekly re-engagement email job could mail real
    users from a laptop. ON on Railway, OFF elsewhere; ENABLE_IN_APP_SCHEDULERS=true
    or =false overrides either way.
    """
    flag = os.environ.get("ENABLE_IN_APP_SCHEDULERS", "").strip().lower()
    if flag in ("true", "1", "yes"):
        return True
    if flag in ("false", "0", "no"):
        return False
    return current_runner() == "railway"


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
                    (source_key, tier, status, items_added, error, started_at, finished_at, runner)
                VALUES
                    (:source_key, :tier, :status, :items_added, :error,
                     COALESCE(:started_at, now()), COALESCE(:finished_at, now()), :runner)
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
                "runner": current_runner(),
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
