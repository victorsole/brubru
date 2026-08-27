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
        "last fired its liveness heartbeat, then, for **every** sync tier, when "
        "it last succeeded, when it last ran at all, and how often it has failed "
        "in the last 24 hours. Also surfaces the nightly scraper-health "
        "detector: how many scrapers it checked, and which ones are confirmed "
        "broken.\n\n"
        "**When to use it**\n"
        "To confirm the Railway cron is actually scheduled — `alive` is true "
        "only if the dispatcher checked in within the last 90 minutes (it runs "
        "hourly). If `alive` is false, the cron service is not running and MEUB "
        "feeds will drift.\n\n"
        "**Input**\nNone.\n\n"
        "**Try it**\nOpen it directly; no sign-in needed. "
        "`GET /api/sync/health`\n\n"
        "**You get back**\n"
        "`dispatcher` (last_seen, minutes_ago, alive); `tiers`, one entry per "
        "tier with `last_success`, `last_run`, `failures_24h`, `runs_24h` and a "
        "`healthy` flag; and `scrapers` with the last detector run, the number "
        "checked, and any confirmed breaks by body and item type."
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

    # Every tier, discovered from the data. The old version iterated a hardcoded
    # ("fast", "warm"), so scraper_health, economy_b0/b1/b2, commission_heavy and
    # monthly could never appear here -- including on 22-23 Aug 2026, when the
    # scraper-health detector stopped running and this endpoint kept reporting
    # a clean bill of health. A fixed list cannot report on what it does not name.
    tier_rows = db.execute(text("""
        SELECT tier,
               -- Two spellings of success are written today: the tier syncs use
               -- 'success', the hourly heartbeat writes 'ok'. Filtering on
               -- 'success' alone reported `last_success: null` for a tier that
               -- had run 168 times without a single failure. Kept as an explicit
               -- allowlist rather than `status <> 'failed'`, so a new status
               -- nobody has thought about is not silently counted as fine.
               max(finished_at) FILTER (WHERE status IN ('success', 'ok')) AS last_success,
               max(finished_at)                                   AS last_run,
               count(*) FILTER (WHERE status = 'failed'
                                 AND started_at > now() - interval '24 hours') AS failures_24h,
               count(*) FILTER (WHERE started_at > now() - interval '24 hours') AS runs_24h
        FROM sync_runs
        WHERE tier IS NOT NULL
        GROUP BY tier
        ORDER BY tier
    """)).mappings().all()

    tiers = {}
    for r in tier_rows:
        runs, fails = int(r["runs_24h"] or 0), int(r["failures_24h"] or 0)
        # A tier reporting only its last SUCCESS looks perfect while failing most
        # of the time: on 24 Aug 2026 `fast` had 57 failures against 79 successes
        # and still showed a fresh timestamp. Judge on the failure RATE, and say
        # `null` rather than `true` when there is nothing to judge -- an untested
        # tier is unproven, not healthy.
        tiers[r["tier"]] = {
            "last_success": r["last_success"].isoformat() if r["last_success"] else None,
            "last_run": r["last_run"].isoformat() if r["last_run"] else None,
            "runs_24h": runs,
            "failures_24h": fails,
            "failure_rate_24h": round(fails / runs, 3) if runs else None,
            "healthy": (fails / runs < 0.2) if runs else None,
        }

    # The scraper-health detector's verdict, which until now reached only a
    # logger.warning in the container logs. A canary nobody can hear is not a
    # canary. DISABLED is excluded deliberately: it means "empty by design".
    scrapers: dict = {"last_checked": None, "checked": 0, "confirmed_breaks": []}
    try:
        srows = db.execute(text("""
            SELECT body_code, item_type, last_status, consecutive_fails, detail, last_checked
            FROM scraper_health_state
            WHERE last_status IN ('BROKEN', 'ERROR') AND consecutive_fails >= 2
            ORDER BY consecutive_fails DESC, body_code, item_type
            LIMIT 50
        """)).mappings().all()
        agg = db.execute(text(
            "SELECT count(*) n, max(last_checked) t FROM scraper_health_state")).mappings().first()
        scrapers = {
            "last_checked": agg["t"].isoformat() if agg and agg["t"] else None,
            "checked": int(agg["n"] or 0) if agg else 0,
            "confirmed_breaks": [
                {"body": r["body_code"], "item_type": r["item_type"],
                 "status": r["last_status"], "consecutive_fails": int(r["consecutive_fails"] or 0),
                 "detail": r["detail"]}
                for r in srows
            ],
        }
    except Exception as exc:  # noqa: BLE001 - table may predate a migration
        # Loud in the payload, not silent: an unreadable health table must not
        # render identically to a fleet with nothing wrong.
        logger.warning("[sync-health] scraper_health_state unreadable: %s", exc)
        scrapers = {"last_checked": None, "checked": 0, "confirmed_breaks": [],
                    "error": f"{type(exc).__name__}"}

    # --- corpus completeness -------------------------------------------
    # The tier table says whether jobs RAN. This says whether the corpora they
    # maintain are actually COMPLETE, which is a different question: every
    # defect found on 27 Aug 2026 was a corpus that looked fine while a job
    # reported success over a range that was itself wrong.
    #
    # Computed live rather than read from a cached verdict, so it can never be
    # stale in the direction that matters.
    try:
        from scripts.ep_council_completeness import run_checks
        checks = run_checks(db.connection())
        gaps = [c for c in checks if c["gap"]]
        corpora = {
            "checks": len(checks),
            "gaps": len(gaps),
            "healthy": len(gaps) == 0,
            "detail": [{"check": g["check"], "detail": g["detail"], "fix": g["fix"]}
                       for g in gaps],
        }
    except Exception as exc:  # noqa: BLE001
        # An error key, never an empty gap list: a check that could not run must
        # not render identically to a corpus with nothing missing.
        logger.warning("[sync-health] completeness checks failed: %s", exc)
        corpora = {"checks": 0, "gaps": None, "healthy": None,
                   "error": f"{type(exc).__name__}: {exc}"}

    return {
        "dispatcher": {
            "last_seen": last_seen.isoformat() if last_seen else None,
            "minutes_ago": minutes_ago,
            "alive": alive,
        },
        "tiers": tiers,
        "scrapers": scrapers,
        "corpora": corpora,
    }
