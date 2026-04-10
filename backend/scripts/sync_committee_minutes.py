#!/usr/bin/env python3
"""
Sync EP Committee Minutes to database.

Usage:
    python3.12 scripts/sync_committee_minutes.py              # Sync all (5 pages)
    python3.12 scripts/sync_committee_minutes.py --max-pages 10  # More pages
    python3.12 scripts/sync_committee_minutes.py --stats        # Show DB stats
    python3.12 scripts/sync_committee_minutes.py --dry-run      # Scrape only, don't save

Created: April 2026
"""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


def show_stats():
    """Show current committee minutes statistics."""
    from core.database import SessionLocal
    from models.committee_minutes import CommitteeMinutes
    from sqlalchemy import func

    db = SessionLocal()
    total = db.query(func.count(CommitteeMinutes.id)).scalar()
    with_text = db.query(func.count(CommitteeMinutes.id)).filter(CommitteeMinutes.has_full_text == True).scalar()
    committees = db.query(
        CommitteeMinutes.committee_code,
        func.count(CommitteeMinutes.id),
        func.max(CommitteeMinutes.meeting_date),
    ).group_by(CommitteeMinutes.committee_code).order_by(CommitteeMinutes.committee_code).all()

    print(f"\nCommittee Minutes Database Stats:")
    print(f"  Total records: {total}")
    print(f"  With full text: {with_text}")
    print(f"\n  By committee:")
    for code, count, latest in committees:
        latest_str = latest.strftime('%Y-%m-%d') if latest else 'N/A'
        print(f"    {code:6s}: {count:3d} minutes (latest: {latest_str})")

    db.close()


async def main():
    parser = argparse.ArgumentParser(description='Sync EP Committee Minutes')
    parser.add_argument('--max-pages', type=int, default=5, help='Max pages to scrape (default: 5)')
    parser.add_argument('--stats', action='store_true', help='Show database stats')
    parser.add_argument('--dry-run', action='store_true', help='Scrape only, print results')
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.dry_run:
        from services.scrapers.committee_minutes_scraper import CommitteeMinutesScraper
        scraper = CommitteeMinutesScraper()
        items = await scraper.scrape_all_minutes(max_pages=args.max_pages)
        print(f"\n[OK] Scraped {len(items)} minutes entries (dry run)")
        for item in items:
            end = f" - {item.meeting_date_end.strftime('%Y-%m-%d')}" if item.meeting_date_end else ""
            print(f"  {item.committee_code:6s} {item.meeting_date.strftime('%Y-%m-%d')}{end}  {item.title[:60]}")
        return

    # Create table if needed
    from core.database import engine
    from models.committee_minutes import CommitteeMinutes
    CommitteeMinutes.__table__.create(engine, checkfirst=True)

    from services.scrapers.committee_minutes_sync_service import CommitteeMinutesSyncService
    service = CommitteeMinutesSyncService()
    result = await service.sync_all(max_pages=args.max_pages)

    print(f"\n[OK] Committee minutes sync complete:")
    print(f"  Added:   {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors:  {result['errors']}")


if __name__ == '__main__':
    asyncio.run(main())
