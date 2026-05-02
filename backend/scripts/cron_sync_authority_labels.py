#!/usr/bin/env python3
"""
Railway Cron Job: EU Authority-Label Sync

Runs as a Railway cron service. Calls the backend's
/api/cron/sync/authority-labels endpoint and exits.

Recommended Railway cron schedule: 0 3 * * *  (daily 03:00 UTC)

The schedule is daily (not every-6-hours like the OEIL/EUR-Lex sync)
because (a) authority labels barely change, (b) the upstream Cellar
SPARQL endpoint is occasionally down, and a single retry per day is
enough to backfill within the week.

Idempotent: re-running yields the same DB state.

Usage:
    python scripts/cron_sync_authority_labels.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://brubru-production.up.railway.app",
)
CRON_SECRET = os.environ.get("CRON_SECRET", "")


def main():
    if not CRON_SECRET:
        print("[ERROR] CRON_SECRET environment variable not set")
        sys.exit(1)

    url = f"{BACKEND_URL}/api/cron/sync/authority-labels"
    headers = {"Authorization": f"Bearer {CRON_SECRET}"}

    print(f"[CRON] Calling {url}")

    try:
        req = urllib.request.Request(url, method="POST", headers=headers)
        # 30 minutes — full 12 NALs × 6 langs takes ~10-15 min when Cellar is healthy
        with urllib.request.urlopen(req, timeout=1800) as resp:
            data = json.loads(resp.read().decode())
            print(f"[OK] Authority-label sync result: {data}")

    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Connection failed: {e.reason}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
