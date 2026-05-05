#!/usr/bin/env python3
"""
Railway Cron Job: OEIL + EUR-Lex + Committee Work + Texts Adopted + Commission Docs sync

Runs as a Railway cron service (separate from the main backend).
Calls the backend's /api/cron/sync/all endpoint and exits.

Railway cron schedule: 0 0 * * * (daily at 00:00 UTC).

Server-side `/api/cron/sync/all` runs 5 syncs sequentially (OEIL, EUR-Lex,
Committee Work for 26 EP committees, Texts Adopted, Commission Documents);
realistic total runtime is 6-12 minutes. Client timeout below is set to 30
minutes to leave headroom for a slow night. Bumped from 300s -> 1800s on
5 May 2026 after the 4 May 00:03 UTC run timed out and was marked CRASHED
by Railway (the backend work likely completed; only the client gave up).

The proper fix (deferred): make the endpoint return 202 immediately and run
syncs as FastAPI BackgroundTasks so the cron client never blocks.

Usage:
    python scripts/cron_sync.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://brubru-production.up.railway.app"
)
CRON_SECRET = os.environ.get("CRON_SECRET", "")


def main():
    if not CRON_SECRET:
        print("[ERROR] CRON_SECRET environment variable not set")
        sys.exit(1)

    params = urllib.parse.urlencode({"days": 7})
    url = f"{BACKEND_URL}/api/cron/sync/all?{params}"
    headers = {"Authorization": f"Bearer {CRON_SECRET}"}

    print(f"[CRON] Calling {url}")

    try:
        req = urllib.request.Request(url, method="POST", headers=headers)
        # 1800s (30 min) client timeout. Server runs 5 syncs sequentially;
        # 6-12 min is normal, 30 min is the slow-night ceiling. See module docstring.
        with urllib.request.urlopen(req, timeout=1800) as resp:
            data = json.loads(resp.read().decode())
            print(f"[OK] Sync complete: {data}")

    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Connection failed: {e.reason}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
