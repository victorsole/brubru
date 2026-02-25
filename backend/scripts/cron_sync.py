#!/usr/bin/env python3
"""
Railway Cron Job: OEIL + EUR-Lex Sync

Runs as a Railway cron service (separate from the main backend).
Calls the backend's /api/cron/sync/all endpoint and exits.

Railway cron schedule: 0 */6 * * * (every 6 hours)

Usage:
    python scripts/cron_sync.py
"""

import os
import sys
import requests

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://brubru-production.up.railway.app"
)
CRON_SECRET = os.environ.get("CRON_SECRET", "")


def main():
    if not CRON_SECRET:
        print("[ERROR] CRON_SECRET environment variable not set")
        sys.exit(1)

    url = f"{BACKEND_URL}/api/cron/sync/all"
    headers = {"Authorization": f"Bearer {CRON_SECRET}"}

    print(f"[CRON] Calling {url}")

    try:
        response = requests.post(url, headers=headers, params={"days": 7}, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"[OK] Sync complete: {data}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Sync failed: {e}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
