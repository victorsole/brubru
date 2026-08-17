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

Fail-soft: one tier failing doesn't stop the next. The dispatcher logs and
continues. Exit code 0 even on partial failure — the operator reads the log.

Usage:
    BACKEND_URL=https://brubru-production.up.railway.app \\
    CRON_SECRET=... \\
    python scripts/cron_dispatch.py
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request


BACKEND_URL = os.environ.get("BACKEND_URL", "https://brubru-production.up.railway.app")
CRON_SECRET = os.environ.get("CRON_SECRET", "")


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
        print(f"[ERR]  {endpoint_path} → HTTP {e.code}: {e.reason}", flush=True)
        return {"status": "failed", "http_code": e.code, "reason": str(e.reason)}
    except urllib.error.URLError as e:
        print(f"[ERR]  {endpoint_path} → URL error: {e.reason}", flush=True)
        return {"status": "failed", "error": str(e.reason)}
    except Exception as e:
        print(f"[ERR]  {endpoint_path} → {type(e).__name__}: {e}", flush=True)
        return {"status": "failed", "error": str(e)}


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

    # Social posts — open tier (Bluesky/Mastodon/YouTube), 06:00 UTC daily, oldest-checked
    # first so it drips through the set. Robust keyless APIs.
    if hour == 6:
        fires.append(("social_open", "/api/cron/fetch-social-posts?mode=open&limit=150"))

    # Social posts — X drip (paced, throttle-stop) at 01/09/17 UTC. Public syndication endpoint
    # rate-limits, so small slow batches rotate through the 978 X accounts over ~days.
    if hour in (1, 9, 17):
        fires.append(("social_x_drip", "/api/cron/fetch-social-posts?mode=x&limit=40"))

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

    results = {}
    for label, endpoint in fires:
        results[label] = _fire(endpoint)

    # Summary line for log scraping
    succeeded = sum(1 for r in results.values() if r.get("status") == "success")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    print(
        f"[CRON-DISPATCH] Done. fired={len(fires)} succeeded={succeeded} failed={failed}",
        flush=True,
    )

    # Exit 0 even on partial failure — operator reads the log
    sys.exit(0)


if __name__ == "__main__":
    main()
