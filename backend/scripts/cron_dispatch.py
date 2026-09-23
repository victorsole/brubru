#!/usr/bin/env python3
"""
Railway Cron Dispatcher (single-service pattern, set 14 May 2026).

Replaces the per-tier Railway cron services with ONE service that wakes up every
hour (CRON_SCHEDULE = "0 * * * *") and decides which tier(s) to fire based on
the current UTC time.

Why a single dispatcher: Railway bills per service. Five tier services = five
service minimums. One dispatcher service that wakes hourly = one minimum.

Schedule (from backend/config/sync_cadence.json):

    hot_6h    → hours 00, 06, 12, 18 UTC                 (every 6h)
    warm_12h  → hours 02, 14 UTC                          (every 12h)
    daily     → hour 04 UTC                               (every day)
    weekly    → Sunday hour 05 UTC                        (once per week)
    monthly   → 1st of month hour 02 UTC                  (once per month)
    daily-brief         → hour 11 UTC                     (Brubru Brief email)
    authority-labels    → hour 03 UTC                     (NAL sync)
    journey-precompute  → hours 01, 09, 17 UTC            (legislative-journey AI, limit=8)

Each fire is a POST to the main backend (BACKEND_URL) at
    /api/cron/sync/<tier>
or
    /api/cron/<dedicated-endpoint>
with `Authorization: Bearer $CRON_SECRET`. The backend runs the sync and
returns a JSON summary.

Fail-soft EXECUTION, honest REPORTING (changed 22 September 2026). One tier
failing still does not stop the next. But the exit code is now 1 whenever any
tier, or any job inside a tier, failed -- so the Railway job goes red.

It used to exit 0 unconditionally, "the operator reads the log". No operator
reads a green log: ingestion was dead from 19 to 22 September 2026 and this
service reported success every hour throughout.

A job recorded as `degraded` does NOT make the run red. That status belongs to
an AUDIT source (SourceSpec.is_audit), which exits non-zero to report gaps it
found -- that is the auditor working. Counting it would paint every run red for
ever and the signal would die again, the other way round.

Usage:
    BACKEND_URL=https://brubru-production.up.railway.app \\
    CRON_SECRET=... \\
    python scripts/cron_dispatch.py
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request


BACKEND_URL = os.environ.get("BACKEND_URL", "https://brubru-production.up.railway.app")
CRON_SECRET = os.environ.get("CRON_SECRET", "")


# Railway's edge closes a request at ~300 seconds, and every real tier runs longer
# (fast 1,317s, warm 728s, daily 1,242s, economy 1,778s, measured 23 Sep 2026). The
# backend keeps working after the caller goes away, so a cut connection means "still
# running", not "failed". Fire, let go, then read what the container recorded.
EDGE_TIMEOUT = 280
DETACHED = "detached"
POLL_SECONDS = 60
MAX_WAIT_SECONDS = 50 * 60


def _fire(endpoint_path: str, timeout: int = 1800) -> dict:
    """POST to a backend cron endpoint with the Bearer token. Returns response dict or error."""
    url = f"{BACKEND_URL}{endpoint_path}"
    headers = {"Authorization": f"Bearer {CRON_SECRET}"}
    print(f"[FIRE] {url}", flush=True)
    try:
        req = urllib.request.Request(url, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                data = json.loads(body)
                print(f"[OK]   {endpoint_path} → status={data.get('status', '?')}", flush=True)
                return data
            except json.JSONDecodeError:
                print(f"[OK]   {endpoint_path} → non-JSON response (len={len(body)})", flush=True)
                return {"status": "success", "raw": body[:500]}
    except urllib.error.HTTPError as e:
        # 502/504 from the edge = our connection was cut while the backend works on.
        if e.code in (502, 503, 504):
            print(f"[WAIT] {endpoint_path} → HTTP {e.code} from the edge; the tier runs on", flush=True)
            return {"status": DETACHED, "http_code": e.code}
        print(f"[ERR]  {endpoint_path} → HTTP {e.code}: {e.reason}", flush=True)
        return {"status": "failed", "http_code": e.code, "reason": str(e.reason)}
    except urllib.error.URLError as e:
        print(f"[WAIT] {endpoint_path} → connection dropped ({e.reason}); the tier runs on", flush=True)
        return {"status": DETACHED, "error": str(e.reason)}
    except TimeoutError as e:
        print(f"[WAIT] {endpoint_path} → read timed out; the tier runs on", flush=True)
        return {"status": DETACHED, "error": str(e)}
    except Exception as e:
        print(f"[ERR]  {endpoint_path} → {type(e).__name__}: {e}", flush=True)
        return {"status": "failed", "error": str(e)}


def _status_since(minutes: int) -> dict | None:
    """What the container has recorded, and what it is still working on (None if unreadable)."""
    url = f"{BACKEND_URL}/api/cron/runs-since?minutes={minutes}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CRON_SECRET}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode()) or {}
    except Exception as e:  # noqa: BLE001
        print(f"[ERR]  runs-since → {type(e).__name__}: {e}", flush=True)
        return None


def _endpoint_path(endpoint: str) -> str:
    return endpoint.split("?")[0]


def _wait_for_detached(started: float, endpoints: list[str] | None = None) -> tuple[list[dict] | None, list[str]]:
    """Wait until the container is no longer working, then return what it recorded.

    Not "no new rows for a while": a row is written when a source FINISHES, and one
    source can work for seven minutes (votes_ep, 418s on 23 Sep) or, in the daily tier,
    for half an hour. A quiet ledger is a slow job as often as a finished tier, so the
    backend is asked what is in flight instead.
    """
    wanted = [_endpoint_path(e) for e in (endpoints or [])]
    last = None
    while time.time() - started < MAX_WAIT_SECONDS:
        time.sleep(POLL_SECONDS)
        status = _status_since(int((time.time() - started) / 60) + 2)
        if status is None:
            continue
        last = status.get("runs") or []
        in_flight = status.get("in_flight") or []
        if not in_flight:
            # Nothing in flight is not enough: a deploy replaces the container mid-tier
            # and the work simply stops. Only the backend's own record of reaching the
            # end counts, and that record dies with the process, which is what we want.
            completed = status.get("completed") or {}
            unfinished = [p for p in wanted
                          if float((completed.get(p) or {}).get("seconds_ago", 1e9)) > time.time() - started]
            return last, unfinished
        print(f"[WAIT] still running: {', '.join(in_flight)} ({len(last)} recorded)", flush=True)
    print(f"[ERR]  still working after {MAX_WAIT_SECONDS // 60} minutes; judging what there is", flush=True)
    return last, ["timed out: " + ",".join(wanted)]


def _iter_job_statuses(payload) -> list[tuple[str, str]]:
    """Yield (job_name, status) for every per-job result inside a tier response.

    The cron endpoints do not share one response shape, and the differences are
    exactly what hid the September 2026 outage:

      * `/api/cron/sync/tier/{tier}` -> {"tier":..., "ran": {"oj": "failed", ...}}
        (no top-level "status" at all)
      * economy batches              -> {"ok": 0, "failures": ["eea: ...", ...]}
      * simple endpoints             -> {"status": "success"}

    Pure function, no I/O -- unit-tested in tests/test_cron_dispatch_exit_code.py.
    """
    out: list[tuple[str, str]] = []
    if not isinstance(payload, dict):
        return out

    ran = payload.get("ran")
    if isinstance(ran, dict):
        for job, status in ran.items():
            if isinstance(status, str):
                out.append((str(job), status))
            elif isinstance(status, dict) and isinstance(status.get("status"), str):
                out.append((str(job), status["status"]))

    failures = payload.get("failures")
    if isinstance(failures, list):
        for item in failures:
            text = str(item)
            out.append((text.split(":", 1)[0].strip() or "?", "failed"))

    results = payload.get("results")
    if isinstance(results, dict):
        for job, status in results.items():
            if isinstance(status, str):
                out.append((str(job), status))
            elif isinstance(status, dict) and isinstance(status.get("status"), str):
                out.append((str(job), status["status"]))

    return out


def decide_tiers(now: datetime.datetime) -> list[tuple[str, str]]:
    """
    Given a UTC timestamp, return the list of (label, endpoint_path) to fire.

    Pure function — easy to unit-test.
    """
    fires: list[tuple[str, str]] = []
    hour = now.hour
    weekday = now.weekday()  # Mon=0 ... Sun=6
    day = now.day

    # Hot tier: every 6 hours
    if hour in (0, 6, 12, 18):
        fires.append(("hot_6h", "/api/cron/sync/hot-6h"))

    # Warm tier: every 12 hours (02 + 14 UTC, offset from hot tier)
    if hour in (2, 14):
        fires.append(("warm_12h", "/api/cron/sync/warm-12h"))

    # Registry FAST tier — the MEUB feeds the EU publishes intraday: News
    # (DG/EP/bespoke), My OJ, Votes (EP/Council). Runs sync_*_news.py etc. and
    # records freshness. ~every 6h on otherwise-light hours (no other tier fires
    # at 07/13/19/23). This is what keeps eu_news_items current.
    if hour in (7, 13, 19, 23):
        fires.append(("registry_fast", "/api/cron/sync/tier/fast"))

    # EP eMeeting committee documents: daily 08:00 UTC, alongside registry_warm.
    # 10:00 CEST, so the morning's EP publications are up, and clear of the
    # economy batches at 10/15/21. Added 26 Aug 2026: this sync had NO schedule
    # at all and had been frozen since mid-July while the EP published 17 new
    # agendas, six of them for the committee week starting 31 August.
    if hour == 8:
        fires.append(("ep_emeeting", "/api/cron/sync/ep-emeeting"))

    # Registry WARM tier — slower MEUB feeds: My EU Calendar, Transcripts,
    # Lobby Meetings, Parliamentary Questions. Twice a day on light hours.
    if hour in (8, 20):
        fires.append(("registry_warm", "/api/cron/sync/tier/warm"))

    # Legislative-journey AI precompute: 3x/day (01, 09, 17 UTC), throttled per
    # run (limit=8) so it backfills tracked dossiers gradually without a burst.
    if hour in (1, 9, 17):
        fires.append(("journey_precompute", "/api/cron/precompute-journeys?limit=8"))

    # Committee-transcript precompute: 2x/day (16, 22 UTC — otherwise-quiet
    # hours), free via Groq whisper-large-v3, tracked/PI committees first,
    # throttled (limit=3/run) so each run stays bounded.
    if hour in (16, 22):
        fires.append(("transcribe_precompute", "/api/cron/transcribe-pending?limit=3"))

    # Authority labels: 03:00 UTC daily
    if hour == 3:
        fires.append(("authority_labels", "/api/cron/sync/authority-labels"))

    # Daily tier: 04:00 UTC daily
    if hour == 4:
        fires.append(("daily", "/api/cron/sync/daily"))

    # Procedure-snapshot cube: 05:00 UTC daily. Builds one row per carriage (slow state +
    # 5 fast-signal counts) so the predictors gain count-trajectory features. Quiet hour
    # (only collides with the Sunday weekly tier, which uses a separate endpoint).
    if hour == 5:
        fires.append(("procedure_snapshots", "/api/cron/build-procedure-snapshots"))

    # Social posts — open tier (Bluesky/Mastodon/YouTube), TWICE daily, oldest-checked
    # first so it drips through the set. Robust keyless APIs.
    #
    # Raised from 150 once a day on 24 Aug 2026. Measured that morning: of 1,676
    # fetch-enabled accounts only 349 (21%) had been checked within two days and
    # 292 had not been checked for over a FORTNIGHT, the oldest frontier being 17
    # days. A feed described as "today's EU social pulse" was true of a fifth of
    # it. 510 open-tier accounts at 300 x 2 clears the set inside a day, and a
    # manual run of 200 accounts took about two minutes, so the cost is small.
    if hour in (6, 18):
        fires.append(("social_open", "/api/cron/fetch-social-posts?mode=open&limit=300"))

    # Social posts — X drip (paced, throttle-stop) every 4 hours. The public
    # syndication endpoint rate-limits, so the batch stays SMALL and slow and we
    # add slots rather than size: 6 x 40 = 240/day against 1,166 X accounts is
    # about five days per cycle, down from ten. Never add proxies or evasion to
    # beat the throttle.
    if hour in (1, 5, 9, 13, 17, 21):
        fires.append(("social_x_drip", "/api/cron/fetch-social-posts?mode=x&limit=40"))

    # Social posts — X TAIL window, once a day at 03:00 UTC (quiet hour: only the
    # authority-labels sync fires). Added 15 Sep 2026. The 4-hourly drip above
    # orders verified accounts first, and because every run hits the syndication
    # throttle within a handful of accounts it never reaches the unverified group:
    # 618 of 1,155 fetch-enabled X accounts (all unverified) were stale beyond 7
    # days, oldest last checked 12 Aug. This window reads the queue purely
    # oldest-checked-first, so it works that backlog. Same polite parameters as the
    # drip -- slower pace, smaller per-account pull, the same throttle-stop -- and a
    # larger cap that only matters on a night the endpoint is not throttling.
    # Worst case ~150 x (4s + fetch) is well inside the 1800s fire timeout. No
    # proxies, no evasion: when X throttles, the run stops.
    if hour == 3:
        fires.append(("social_x_tail",
                      "/api/cron/fetch-social-posts?mode=x&order=oldest&limit=150"
                      "&per_account=5&pace=4&empty_streak_stop=10"))

    # Economy folders (v2 institutional/agency/database endpoints backed by
    # economy_items: per-body news, events, publications, databases, tenders,
    # grants, calls, consultations). Daily, split into three batches on quiet
    # hours so ~34 EU sites aren't all scraped at once.
    if hour == 10:
        fires.append(("economy_b0", "/api/cron/sync/economy?batch=0"))
    if hour == 15:
        fires.append(("economy_b1", "/api/cron/sync/economy?batch=1"))
    if hour == 21:
        fires.append(("economy_b2", "/api/cron/sync/economy?batch=2"))

    # Brubru Brief: 11:00 UTC daily
    if hour == 11:
        fires.append(("daily_brief", "/api/cron/daily-brief"))

    # Weekly tier: Sunday 05:00 UTC
    if weekday == 6 and hour == 5:
        fires.append(("weekly", "/api/cron/sync/weekly"))

    # Commission heavy bulk datasets: Sunday 07:00 UTC. The 6 large commission
    # sub-types (CORDIS research / RASFF alerts / DG COMP state-aid / EBTI tariff
    # rulings / TARIC codes / FTS recipients) that no other tier covers -- bulk
    # reference universes that move slowly. Separate weekly slot so they never
    # collide with the daily economy batches (10/15/21) on the single worker.
    if weekday == 6 and hour == 7:
        fires.append(("commission_heavy", "/api/cron/sync/commission-heavy"))

    # Scraper-health detector: 23:00 UTC daily, after the last economy batch (21:00)
    # so freshly-synced bodies aren't flagged stale. Confirm mode (fetched_at scan +
    # live-confirm candidates); alerts only on 2 consecutive BROKEN runs.
    if hour == 23:
        fires.append(("scraper_health", "/api/cron/scraper-health"))

    # Monthly tier: 1st of month 02:00 UTC (offset to 02:30 conceptually but we wake on minute 0)
    # Avoid collision with warm-12h (also at 02:00) by using a different hour for monthly: 01.
    # Actually keep at 02 — let both fire in sequence. They use separate endpoints anyway.
    if day == 1 and hour == 2:
        fires.append(("monthly", "/api/cron/sync/monthly"))

    return fires


def main():
    if not CRON_SECRET:
        print("[ERROR] CRON_SECRET environment variable not set", flush=True)
        sys.exit(1)
    if not BACKEND_URL:
        print("[ERROR] BACKEND_URL environment variable not set", flush=True)
        sys.exit(1)

    now = datetime.datetime.utcnow()
    weekday_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][now.weekday()]
    print(
        f"[CRON-DISPATCH] {now.isoformat()}Z ({weekday_name} hour={now.hour:02d} day={now.day:02d})",
        flush=True,
    )

    # Liveness heartbeat — fire EVERY hour, before the no-tiers early-exit, so
    # /api/sync/health can confirm the hourly dispatcher itself is alive (vs the
    # app being up but the Railway cron not scheduled).
    _fire("/api/cron/heartbeat", timeout=60)

    fires = decide_tiers(now)
    if not fires:
        print(f"[CRON-DISPATCH] No tiers due at hour {now.hour:02d} UTC. Exiting.", flush=True)
        sys.exit(0)

    print(f"[CRON-DISPATCH] Firing {len(fires)} tier(s): {[label for label, _ in fires]}", flush=True)

    fired_at = time.time()
    results = {}
    for label, endpoint in fires:
        results[label] = _fire(endpoint, timeout=EDGE_TIMEOUT)

    # Summary line for log scraping
    succeeded = sum(1 for r in results.values() if r.get("status") == "success")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    detached = [label for label, r in results.items() if r.get("status") == DETACHED]

    # Per-job failures INSIDE a 200 response. The top-level count above is not
    # enough: `/api/cron/sync/tier/{tier}` returns {"tier":..., "ran": {...}} with
    # NO top-level "status" key at all, so a tier in which every single job failed
    # scored neither `succeeded` nor `failed` and the dispatcher printed a clean
    # summary. That is why the 19-22 September 2026 outage ran for 3.5 days with a
    # green Railway job every hour: the ingestion was dead and nothing here could
    # say so. Walk the payload.
    job_failures: list[str] = []
    # A tier whose connection was cut is judged from the ledger the container writes,
    # not from a response we never got.
    if detached:
        print(f"[CRON-DISPATCH] Detached: {detached}. Reading the ledger instead.", flush=True)
        detached_endpoints = [e for label, e in fires if results[label].get("status") == DETACHED]
        runs, unfinished = _wait_for_detached(fired_at, detached_endpoints)
        for path in unfinished:
            # The container was replaced (a deploy) or the work vanished: whatever was
            # recorded is a PART of the tier, never the tier.
            job_failures.append(f"{path}=did not reach its end")
        if runs is None:
            job_failures.append("runs-since=unreadable")
        elif not runs:
            job_failures.append(f"{','.join(detached)}=no runs recorded")
        else:
            for r in runs:
                if r.get("status") not in ("success", "ok", "skipped", "degraded"):
                    job_failures.append(f"{r.get('source_key')}={r.get('status')}")
            print(f"[CRON-DISPATCH] Ledger: {len(runs)} run(s), "
                  f"{len(job_failures)} failed", flush=True)
    for label, payload in results.items():
        for job, status in _iter_job_statuses(payload):
            # "degraded" = an AUDIT source found gaps (it exits non-zero to say
            # so). That is the auditor working, not a broken job, and counting it
            # would make the Railway job red on every single run for ever -- which
            # is how a red build stops meaning anything. It stays visible in
            # sync_runs and /api/sync/health.
            if status not in ("success", "ok", "skipped", "degraded"):
                job_failures.append(f"{label}/{job}={status}")

    print(
        f"[CRON-DISPATCH] Done. fired={len(fires)} succeeded={succeeded} failed={failed} "
        f"detached={len(detached)} job_failures={len(job_failures)}",
        flush=True,
    )
    if job_failures:
        print(f"[CRON-DISPATCH] FAILED JOBS: {', '.join(job_failures[:40])}", flush=True)

    # Exit NON-ZERO when anything failed, so Railway shows the job red.
    #
    # This used to be a hard `sys.exit(0)` with the comment "operator reads the
    # log". No operator reads a green log. Execution stays fail-soft -- one tier
    # failing still does not stop the next, which is what matters -- but the
    # REPORT is now honest. Set 22 September 2026.
    #
    # 23 September 2026: red also has to MEAN something. Every tier outlives
    # Railway's 300s edge timeout, so the cut connection was counted as a failed
    # tier and every single run went red and mailed a crash. A cut connection is
    # now `detached` and the verdict comes from the ledger the container writes.
    if failed or job_failures:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
