"""
Sync status / freshness API.

Read-only view of when each MEUB feed last refreshed, powering the
"Updated X ago" chips in the My EU Bubble feed headers. Written by the
cron tier endpoints (see api/cron.py + services/sync/).
"""

import logging
from datetime import datetime, timedelta, timezone

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


# Jobs judged one by one. The tier line averages its jobs: on 17 Oct 2026 `tris_titles` failed
# on its first run while `daily` read healthy (1 failure in 51 runs), and a job dropped from
# the schedule writes no row at all, so nothing there could ever turn red for it. Hours a job
# may go without running before it is stale; a tier added here gets the same list.
_JOB_STALE_AFTER_HOURS = {"daily": 36}
_JOB_WINDOW_DAYS = 30
_OK = ("success", "ok")
# Jobs taken off the schedule on purpose: not running is then expected, so they are listed as
# retired instead of stale. Retiring a job = one line here, or the page stays red for 30 days.
_RETIRED_JOBS = {
    "client_source_ledger": "13 Oct 2026, 2dad35a9 (Terraqui engagement ended)",
    "dpp_watch": "13 Oct 2026, 2dad35a9 (Terraqui engagement ended)",
}


def judge_jobs(rows, now: datetime, stale_after_hours: int, retired: dict | None = None) -> dict:
    """One tier's jobs, each judged on its own runs.

    `failing`: the last run's status is not success/ok/degraded (failed, skipped, a status
    nobody has thought about). `stale`: no run within `stale_after_hours`. `degraded`: the job
    finished but owes work (an engine missing, credits spent): listed, never counted as broken.
    `retired`: a job in `retired` that no longer runs; one that runs again is judged as any other.
    """
    retired = retired or {}
    def iso(t):
        if t is None:
            return None
        return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).isoformat()

    detail = []
    for r in rows:
        last_run = r["last_run"]
        if last_run is not None and last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        status = r["last_status"]
        detail.append({
            "job": r["source_key"],
            "last_run": iso(last_run),
            "last_status": status,
            "last_success": iso(r["last_success"]),
            "runs_7d": int(r["runs_7d"] or 0),
            "failures_7d": int(r["failures_7d"] or 0),
            "stale": last_run is None or last_run < now - timedelta(hours=stale_after_hours),
            "error": ((r["last_error"] or "")[:300] or None) if status not in _OK else None,
        })
    gone = {j["job"] for j in detail if j["stale"] and j["job"] in retired}
    for j in detail:
        if j["job"] in gone:
            j["retired"] = retired[j["job"]]
    live = [j for j in detail if j["job"] not in gone]
    failing = [j["job"] for j in live if j["last_status"] not in _OK + ("degraded",)]
    stale = [j["job"] for j in live if j["stale"]]
    degraded = [j["job"] for j in live if j["last_status"] == "degraded"]
    rank = {k: i for i, k in enumerate(failing + stale + degraded)}
    detail.sort(key=lambda j: (rank.get(j["job"], len(rank)), j["job"]))
    return {
        "stale_after_hours": stale_after_hours,
        "count": len(detail),
        "healthy": (not failing and not stale) if live else None,
        "failing": failing,
        "stale": stale,
        "degraded": degraded,
        "retired": sorted(gone),
        "detail": detail,
    }


def _jobs(db: Session, tier: str, stale_after_hours: int) -> dict:
    rows = db.execute(text("""
        SELECT source_key,
               (array_agg(status ORDER BY started_at DESC))[1]                 AS last_status,
               (array_agg(error ORDER BY started_at DESC))[1]                  AS last_error,
               max(coalesce(finished_at, started_at))                          AS last_run,
               max(finished_at) FILTER (WHERE status IN ('success', 'ok'))     AS last_success,
               count(*) FILTER (WHERE started_at > now() - interval '7 days') AS runs_7d,
               count(*) FILTER (WHERE status = 'failed'
                                 AND started_at > now() - interval '7 days') AS failures_7d
        FROM sync_runs
        WHERE tier = :tier
          AND runner IS DISTINCT FROM 'local'
          AND started_at > now() - make_interval(days => :days)
        GROUP BY source_key
    """), {"tier": tier, "days": _JOB_WINDOW_DAYS}).mappings().all()
    return judge_jobs(rows, datetime.now(timezone.utc), stale_after_hours, _RETIRED_JOBS)


@router.get(
    "/health",
    summary="Is the hourly sync dispatcher alive?",
    description=(
        "**What it does**\n"
        "Reports when the hourly cron dispatcher (`scripts/cron_dispatch.py`) "
        "last fired its liveness heartbeat, then, for **every** sync tier, when "
        "it last succeeded, when it last ran at all, and how often it has failed "
        "in the last 24 hours, and each nightly job by name: whether its last "
        "run failed and whether it has stopped running. Also surfaces the nightly scraper-health "
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
        "`healthy` flag; `jobs.daily`, every nightly job seen in the last 30 days, "
        "with the lists `failing` (its last run failed), `stale` (no run in 36 "
        "hours) and `degraded` (it finished but still owes work: listed, never "
        "counted as broken), `retired` (taken off the schedule on purpose), a "
        "`healthy` flag, and per job `last_run`, "
        "`last_status`, `last_success`, `runs_7d`, `failures_7d` and the last "
        "`error`; and `scrapers` with the last detector run, the number "
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
          -- A run from a laptop is not this service's health. Rows written before
          -- migration 235 have no runner and are counted as they always were.
          AND runner IS DISTINCT FROM 'local'
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

    jobs: dict = {}
    for tier, hours in _JOB_STALE_AFTER_HOURS.items():
        try:
            jobs[tier] = _jobs(db, tier, hours)
        except Exception as exc:  # noqa: BLE001
            # An error key, never an empty list: a check that could not run must not
            # read like a tier with nothing failing.
            logger.warning("[sync-health] jobs of %s unreadable: %s", tier, exc)
            db.rollback()
            jobs[tier] = {"healthy": None, "error": f"{type(exc).__name__}: {exc}"}

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

    # --- body coverage --------------------------------------------------
    # A null body_txt is either an API defect (the data exists and the handler
    # hides it) or a scraper gap (it was never fetched). They look identical from
    # outside, which is how 350 v2 endpoints served a null body over a corpus
    # that was 99.6% populated without anyone noticing. The defects are fixed and
    # guarded by tests/test_v2_body_contract.py; this counts the remaining gaps
    # so they stay visible instead of silent.
    #
    # Reported, never failed: a thin slice is a scraper backlog, and making the
    # health endpoint red until every agency body is fetched would train everyone
    # to ignore it.
    try:
        from scripts.api_body_coverage import coverage
        cov = coverage(db.connection())
        empty = [c for c in cov if c["empty"]]
        bodies = {
            "slices": len(cov),
            "empty_slices": len(empty),
            "worst": [{"slice": c["slice"], "rows": c["rows"], "pct": c["pct"]}
                      for c in cov[:8]],
            "detail": [c["slice"] for c in empty],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[sync-health] body coverage failed: %s", exc)
        bodies = {"slices": 0, "empty_slices": None,
                  "error": f"{type(exc).__name__}: {exc}"}

    return {
        "dispatcher": {
            "last_seen": last_seen.isoformat() if last_seen else None,
            "minutes_ago": minutes_ago,
            "alive": alive,
        },
        "process_limits": _process_limits(),
        "memory": _memory_usage(),
        "tiers": tiers,
        "jobs": jobs,
        "scrapers": scrapers,
        "corpora": corpora,
        "bodies": bodies,
    }


def _memory_usage() -> dict:
    """What is holding the container's memory (23 Sep 2026).

    Memory was 63% of the Railway bill (about 1.2 GB sustained) and headless
    Chromium was the suspect, but nothing measured it, so the suspicion could not
    be tested. cgroup v2 `memory.current` is the figure Railway bills; the RSS of
    this web process and the resident total of every Chromium/Playwright process
    in the container say how much of it is ours and how much is browsers.

    Three-state like _process_limits: "unknown" off-Linux, never a guess.
    """
    import os

    def _read(path: str):
        try:
            with open(path) as fh:
                raw = fh.read().strip()
            return None if raw == "max" else int(raw)
        except (OSError, ValueError):
            return None

    def _rss_kb(pid: str):
        try:
            with open(f"/proc/{pid}/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return None
        return None

    current = _read("/sys/fs/cgroup/memory.current")
    limit = _read("/sys/fs/cgroup/memory.max")
    if current is None:
        return {"state": "unknown", "note": "cgroup memory counters unreadable here (expected off-Linux)"}

    browsers = {"count": 0, "rss_mb": 0.0}
    web_rss = _rss_kb(str(os.getpid()))
    try:
        for pid in (d for d in os.listdir("/proc") if d.isdigit()):
            try:
                with open(f"/proc/{pid}/comm") as fh:
                    comm = fh.read().strip().lower()
            except OSError:
                continue
            if "chrom" in comm or comm in ("headless_shell", "node") or "playwright" in comm:
                rss = _rss_kb(pid)
                browsers["count"] += 1
                browsers["rss_mb"] += (rss or 0) / 1024
    except OSError:
        pass
    browsers["rss_mb"] = round(browsers["rss_mb"], 1)
    return {
        "state": "ok",
        "container_mb": round(current / 1048576, 1),
        "container_max_mb": round(limit / 1048576, 1) if limit else None,
        "web_process_rss_mb": round(web_rss / 1024, 1) if web_rss else None,
        "browser_processes": browsers,
    }


def _process_limits() -> dict:
    """How close the container is to being unable to spawn a process.

    Every sync runs as a subprocess of this container, so when the cgroup pid
    allowance is exhausted the whole ingestion pipeline dies at once with a bare
    `[Errno 11] Resource temporarily unavailable` -- EAGAIN from the spawn. That
    happened on 19 September 2026 and ran undetected for 3.5 days, because
    nothing measured this. It is two file reads; it is now measured.

    Three-state by design: `state` is "unknown" when the counters cannot be read
    (non-Linux dev machines, cgroup v1 layouts), never a reassuring number.
    """
    import os

    def _read_int(path: str):
        try:
            with open(path) as fh:
                raw = fh.read().strip()
            return None if raw == "max" else int(raw)
        except (OSError, ValueError):
            return None

    current = _read_int("/sys/fs/cgroup/pids.current")
    limit = _read_int("/sys/fs/cgroup/pids.max")
    try:
        threads = len(os.listdir("/proc/self/task"))
    except OSError:
        threads = None

    out = {"pids_current": current, "pids_max": limit, "threads_in_web_process": threads}
    if current is None:
        out["state"] = "unknown"
        out["note"] = "cgroup pid counters unreadable here (expected off-Linux)"
        return out
    if limit:
        pct = round(100.0 * current / limit, 1)
        out["pids_used_pct"] = pct
        # 80% is a warning, not a failure: the ceiling is only reached when a
        # spawn is attempted, so a high reading is the last chance to act.
        out["state"] = "critical" if pct >= 90 else ("warn" if pct >= 80 else "ok")
    else:
        out["state"] = "ok"
        out["note"] = "no cgroup pid ceiling set"
    return out
