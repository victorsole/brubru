"""
Sync the all-EU bodies' events into My EU Calendar (the non-ECL, non-RSS bodies).

Council (future-meetings) + CoR, EMA, CEPOL, EU-OSHA, EIT, FRA, Eurofound, EEAS —
each via bespoke_events_scraper.py. One browser for the whole run. Upcoming only.
Idempotent (dedup by source+external_id; Council also deduped cross-source). NO Anthropic.

Usage:
    python3.12 -m scripts.sync_bespoke_events
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


def main():
    svc = EUCalendarSyncService()
    res = svc.sync_bespoke_events()
    print("[bespoke_events]",
          f"sources={res['sources']}", f"empty={res['sources_empty']}",
          f"added={res['added']}", f"updated={res['updated']}",
          f"skipped={res['skipped']}", f"errors={res['errors']}",
          f"({res['elapsed_seconds']}s)")


if __name__ == "__main__":
    main()
