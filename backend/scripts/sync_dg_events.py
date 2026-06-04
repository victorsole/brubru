"""
Sync European Commission DG + executive-agency events into My EU Calendar.

Scrapes the ~50 DG/agency event-page URLs in dg_events_sources.py (ECL "What's on"
markup; SPA fallback) and upserts them into eu_calendar_events tagged
institution=COMMISSION + commission_dg=<code>, so they're filterable by department
and by the user's Policy Interests. NO LLM / NO Anthropic.

Usage:
    python3.12 -m scripts.sync_dg_events
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


def main():
    svc = EUCalendarSyncService()
    res = svc.sync_dg_events()
    print("[dg_events]",
          f"sources={res['sources']}", f"empty={res['sources_empty']}",
          f"added={res['added']}", f"updated={res['updated']}",
          f"skipped={res['skipped']}", f"errors={res['errors']}",
          f"({res['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
