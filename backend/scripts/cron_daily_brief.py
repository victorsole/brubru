#!/usr/bin/env python3
"""
Railway Cron Job: Daily EU Brief

Runs as a Railway cron service (separate from the main backend).
Calls the backend's /api/cron/daily-brief endpoint and exits.

Railway cron schedule: 0 11 * * * (11:00 UTC = 12:00 CET)

This scrapes EU news portals, saves top headlines, and sends
the daily brief email to all subscribers (registered users + pre-users).

Usage:
    python scripts/cron_daily_brief.py
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

    url = f"{BACKEND_URL}/api/cron/daily-brief"
    headers = {"Authorization": f"Bearer {CRON_SECRET}"}

    print(f"[CRON] Calling {url}")

    try:
        response = requests.post(url, headers=headers, timeout=300)
        response.raise_for_status()

        data = response.json()
        print(f"[OK] Daily brief complete: {data}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Daily brief failed: {e}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
