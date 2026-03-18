#!/usr/bin/env python3
"""
Railway Cron Job: OEIL + EUR-Lex Sync

Runs as a Railway cron service (separate from the main backend).
Calls the backend's /api/cron/sync/all endpoint and exits.

Railway cron schedule: 0 */6 * * * (every 6 hours)

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
        with urllib.request.urlopen(req, timeout=300) as resp:
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
