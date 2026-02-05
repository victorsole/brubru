#!/usr/bin/env python3
"""
Import HowTheyVote.eu EP Voting Data - Phase 1.1

Downloads and imports EP voting data from HowTheyVote.eu GitHub releases.

Usage:
    python scripts/import_howtheyvote.py                    # Full import
    python scripts/import_howtheyvote.py --skip-votes       # Skip member_votes (testing)
    python scripts/import_howtheyvote.py --members-only     # Only import members
    python scripts/import_howtheyvote.py --votes-only       # Only import votes
    python scripts/import_howtheyvote.py -v                 # Verbose output

Examples:
    # First-time full import (may take 10-20 minutes for member_votes)
    python scripts/import_howtheyvote.py

    # Quick test import without individual votes
    python scripts/import_howtheyvote.py --skip-votes

    # Update only member data
    python scripts/import_howtheyvote.py --members-only
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_import.howtheyvote_importer import HowTheyVoteImporter


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def progress_callback(current: int, total: int, message: str):
    """Print progress updates."""
    if total > 0:
        pct = current / total * 100
        print(f"\r  {message} ({pct:.1f}%)", end="", flush=True)
    else:
        print(f"\r  {message}", end="", flush=True)


async def main():
    parser = argparse.ArgumentParser(
        description="Import HowTheyVote.eu EP voting data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--skip-votes",
        action="store_true",
        help="Skip importing individual member votes (large file, ~16M records)"
    )

    parser.add_argument(
        "--members-only",
        action="store_true",
        help="Only import members and group memberships"
    )

    parser.add_argument(
        "--votes-only",
        action="store_true",
        help="Only import votes (requires members to exist)"
    )

    parser.add_argument(
        "--groups-only",
        action="store_true",
        help="Only import/update political groups"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test download without database import (not implemented)"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    print("=" * 60)
    print("HowTheyVote.eu EP Voting Data Import")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    importer = HowTheyVoteImporter()

    try:
        async with importer:
            if args.groups_only:
                print("[1/1] Importing political groups...")
                result = await importer.import_groups(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}, Errors: {result['errors']}")

            elif args.members_only:
                print("[1/3] Importing political groups...")
                result = await importer.import_groups(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}")

                print("[2/3] Importing MEPs...")
                result = await importer.import_members(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

                print("[3/3] Importing group memberships...")
                result = await importer.import_group_memberships(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

            elif args.votes_only:
                print("[1/2] Importing votes...")
                result = await importer.import_votes(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

                if not args.skip_votes:
                    print("[2/2] Importing member votes...")
                    result = await importer.import_member_votes(progress_callback)
                    print()
                    print(f"  Added: {result['added']}, Skipped: {result['skipped']}, "
                          f"Errors: {result['errors']}")

            else:
                # Full import
                print("[1/5] Importing political groups...")
                result = await importer.import_groups(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}")

                print("[2/5] Importing MEPs...")
                result = await importer.import_members(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

                print("[3/5] Importing group memberships...")
                result = await importer.import_group_memberships(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

                print("[4/5] Importing votes...")
                result = await importer.import_votes(progress_callback)
                print()
                print(f"  Added: {result['added']}, Updated: {result['updated']}, "
                      f"Skipped: {result['skipped']}")

                if not args.skip_votes:
                    print("[5/5] Importing member votes (this may take a while)...")
                    result = await importer.import_member_votes(progress_callback)
                    print()
                    print(f"  Added: {result['added']}, Skipped: {result['skipped']}, "
                          f"Errors: {result['errors']}")
                else:
                    print("[5/5] Skipping member votes (--skip-votes)")

        print()
        print("=" * 60)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        print(f"\n[ERROR] Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
