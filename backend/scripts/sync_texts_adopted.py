"""
CLI script to sync EP Texts Adopted to the database.

Usage:
    # Sync from RSS feed (recent texts)
    python scripts/sync_texts_adopted.py --rss

    # Sync specific parliamentary term
    python scripts/sync_texts_adopted.py --term 10

    # Sync all terms (full historical backfill)
    python scripts/sync_texts_adopted.py --all-terms

    # Limit dates per term
    python scripts/sync_texts_adopted.py --term 10 --max-dates 5

    # Dry run (test without database)
    python scripts/sync_texts_adopted.py --rss --dry-run

Created: February 2026
"""

import asyncio
import argparse
import logging
import sys
import os
import time

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def progress_callback(current: int, total: int, message: str):
    """Print progress updates."""
    print(f"  [{current}/{total}] {message}")


async def run_rss_sync(dry_run: bool = False):
    """Sync from RSS feed."""
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

    scraper = TextsAdoptedScraper()
    items = await scraper.fetch_rss()

    print(f"\n[INFO] Fetched {len(items)} items from RSS feed")

    for item in items[:10]:
        print(f"  - {item.ta_reference}: {item.title[:80]}")
        if item.procedure_ref:
            print(f"    Procedure: {item.procedure_ref}")
        print(f"    Type: {item.text_type}, Date: {item.adoption_date.strftime('%Y-%m-%d')}")

    if len(items) > 10:
        print(f"  ... and {len(items) - 10} more")

    if dry_run:
        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_rss(skip_existing=False)

    print(f"\n[OK] RSS sync complete:")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


async def run_dates_sync(dates, term: int = 10, dry_run: bool = False):
    """Backfill explicit plenary dates."""
    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    if dry_run:
        from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
        scraper = TextsAdoptedScraper()
        total = 0
        for d in dates:
            try:
                items = await scraper.scrape_toc_page(d, term)
            except Exception as exc:  # noqa: BLE001
                print(f"  [ERROR] {d}: {exc}")
                continue
            total += len(items)
            print(f"  [{d}] {len(items)} text(s)" + (f" e.g. {items[0].title[:60]}" if items else ""))
        print(f"\n[DRY RUN] {total} text(s) across {len(dates)} date(s); nothing written")
        return

    service = TextsAdoptedSyncService()
    result = await service.sync_dates(dates, term=term, skip_existing=True,
                                      progress_callback=progress_callback)
    print(f"\n[OK] added={result.get('added')} updated={result.get('updated')} "
          f"skipped={result.get('skipped')} errors={result.get('errors')}")
    empty = result.get("dates_with_no_texts") or []
    if empty:
        # Named, not swallowed: a date with no sitting and a date that failed to
        # fetch look identical in a count.
        print(f"[INFO] {len(empty)} date(s) yielded no texts: {', '.join(empty[:12])}")


async def run_term_sync(term: int, max_dates: int = None, dry_run: bool = False):
    """Sync a specific parliamentary term."""
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

    scraper = TextsAdoptedScraper()

    print(f"\n[INFO] Getting plenary dates for term {term}...")
    dates = await scraper.get_plenary_dates(term)
    print(f"[INFO] Found {len(dates)} plenary dates")

    if max_dates:
        dates = dates[:max_dates]
        print(f"[INFO] Limited to {max_dates} dates")

    items = await scraper.scrape_term(
        term=term,
        max_dates=max_dates,
        progress_callback=progress_callback
    )

    print(f"\n[INFO] Scraped {len(items)} items from term {term}")

    # Show sample
    for item in items[:5]:
        print(f"  - {item.ta_reference}: {item.title[:80]}")

    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

    if dry_run:
        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_term(
        term=term,
        max_dates=max_dates,
        skip_existing=True,
        progress_callback=progress_callback
    )

    print(f"\n[OK] Term {term} sync complete:")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


async def run_all_terms_sync(max_dates: int = None, dry_run: bool = False):
    """Sync all parliamentary terms."""
    if dry_run:
        from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
        from schemas.scrapers.texts_adopted_schemas import PARLIAMENTARY_TERMS

        scraper = TextsAdoptedScraper()

        for term in sorted(PARLIAMENTARY_TERMS.keys(), reverse=True):
            print(f"\n--- Term {term} ({PARLIAMENTARY_TERMS[term]['years']}) ---")
            dates = await scraper.get_plenary_dates(term)
            print(f"  Plenary dates: {len(dates)}")
            if dates:
                print(f"  Latest: {dates[0]}, Earliest: {dates[-1]}")

        print("\n[DRY RUN] No database changes made")
        return

    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    service = TextsAdoptedSyncService()
    result = await service.sync_all(
        max_dates_per_term=max_dates,
        skip_existing=True,
        progress_callback=progress_callback
    )

    print(f"\n[OK] All terms sync complete:")
    print(f"  Terms synced: {result['terms_synced']}")
    print(f"  Added: {result['added']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Errors: {result['errors']}")


def main():
    parser = argparse.ArgumentParser(description="Sync EP Texts Adopted to database")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--rss', action='store_true', help='Sync from RSS feed (recent texts)')
    group.add_argument('--term', type=int, choices=range(4, 11), help='Sync specific term (4-10)')
    group.add_argument('--all-terms', action='store_true', help='Sync all terms (historical backfill)')
    group.add_argument('--dates', nargs='+', metavar='YYYY-MM-DD',
                       help='Sync explicit plenary dates. The texts-adopted index lists '
                            'only the CURRENT year, so earlier sittings can only be '
                            'reached this way (TOC urls are deterministic).')
    group.add_argument('--date-range', nargs=2, metavar=('FROM', 'TO'),
                       help='Sync every Mon-Thu between two dates (plenary sittings fall '
                            'on those days). Dates with no sitting are reported, not hidden.')
    group.add_argument('--recent-days', type=int, metavar='N',
                       help='Rolling window for cron: re-walk the last N days of '
                            'Mon-Thu sittings. Idempotent (existing texts are skipped), '
                            'so a run that overlaps the previous one is harmless and a '
                            'sitting published late is still picked up.')

    parser.add_argument('--max-dates', type=int, help='Max plenary dates to scrape per term')
    parser.add_argument('--dry-run', action='store_true', help='Test without database writes')
    parser.add_argument('--term-for-dates', type=int, default=10,
                        help='Parliamentary term the --dates belong to (default 10)')

    args = parser.parse_args()

    start_time = time.time()

    if args.rss:
        print("[START] Syncing Texts Adopted from RSS feed...")
        asyncio.run(run_rss_sync(dry_run=args.dry_run))
    elif args.term:
        print(f"[START] Syncing Texts Adopted for term {args.term}...")
        asyncio.run(run_term_sync(args.term, max_dates=args.max_dates, dry_run=args.dry_run))
    elif args.dates or args.date_range or args.recent_days:
        dates = args.dates
        if args.recent_days:
            from datetime import date as _d, timedelta as _td
            _to = _d.today()
            _from = _to - _td(days=args.recent_days)
            args.date_range = [_from.isoformat(), _to.isoformat()]
        if args.date_range:
            from datetime import date as _d, timedelta as _td
            a = _d.fromisoformat(args.date_range[0]); b = _d.fromisoformat(args.date_range[1])
            dates = []
            cur = a
            while cur <= b:
                if cur.weekday() < 4:      # Mon-Thu; plenary does not sit Fri-Sun
                    dates.append(cur.isoformat())
                cur += _td(days=1)
        print(f"[START] Syncing {len(dates)} explicit date(s)...")
        asyncio.run(run_dates_sync(dates, term=args.term_for_dates,
                                   dry_run=args.dry_run))
    elif args.all_terms:
        print("[START] Syncing Texts Adopted for ALL terms...")
        asyncio.run(run_all_terms_sync(max_dates=args.max_dates, dry_run=args.dry_run))

    duration = time.time() - start_time
    print(f"\n[DONE] Completed in {duration:.1f}s")


if __name__ == "__main__":
    main()
