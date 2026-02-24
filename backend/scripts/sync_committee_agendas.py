"""
Sync EP Committee Draft Agendas to Calendar Events.

CLI script to scrape draft agendas from EP committee latest-documents
pages and create calendar events with cross-referenced procedure refs.

Usage:
    python scripts/sync_committee_agendas.py
    python scripts/sync_committee_agendas.py --committees LIBE ITRE ENVI
    python scripts/sync_committee_agendas.py --verbose

Created: February 2026
"""

import argparse
import asyncio
import logging
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scrapers.committee_agenda_sync_service import CommitteeAgendaSyncService


def main():
    parser = argparse.ArgumentParser(
        description="Sync EP committee draft agendas to calendar events"
    )
    parser.add_argument(
        "--committees",
        nargs="+",
        help="Committee codes to sync (e.g. LIBE ITRE). Default: all 26.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed progress",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("[START] Syncing EP committee draft agendas...")

    service = CommitteeAgendaSyncService()
    result = asyncio.run(
        service.sync_committee_agendas(
            committee_codes=args.committees,
            verbose=args.verbose,
        )
    )

    print(f"\n[OK] Sync complete:")
    print(f"  Added:   {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors:  {result['errors']}")
    print(f"  Duration: {result.get('duration_seconds', 0):.1f}s")


if __name__ == "__main__":
    main()
