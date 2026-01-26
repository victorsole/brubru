#!/usr/bin/env python3
"""
Sync EPRS "EU Legislation in Progress" to Database

Scrapes the curated list from epthinktank.eu (~184 procedures)
and creates carriages in the database with source='oeil_direct'.

These will then appear in the "Track a Legislative File" modal.

Usage:
    cd backend
    python -m scripts.sync_eprs_legislation_in_progress

Options:
    --dry-run    Show what would be synced without making changes
    --force      Re-sync even if procedures already exist
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage,
    CarriageSourceEnum,
    CarriageStatusEnum,
)
from services.eprs.legislation_in_progress_scraper import LegislationInProgressScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def sync_legislation_in_progress(
    dry_run: bool = False,
    force: bool = False
) -> dict:
    """
    Sync EPRS curated procedures to database.

    Args:
        dry_run: If True, don't make database changes
        force: If True, update existing records

    Returns:
        Statistics dict
    """
    stats = {
        'total_scraped': 0,
        'created': 0,
        'skipped_existing': 0,
        'skipped_no_ref': 0,
        'errors': []
    }

    # Initialize scraper
    scraper = LegislationInProgressScraper()

    try:
        # Scrape the page
        logger.info("Scraping epthinktank.eu/eu-legislation-in-progress/...")
        procedures = await scraper.get_procedures(force_refresh=True)
        stats['total_scraped'] = len(procedures)
        logger.info(f"Found {len(procedures)} procedures")

        if dry_run:
            logger.info("DRY RUN - showing first 10 procedures:")
            for proc in procedures[:10]:
                logger.info(f"  - {proc['procedure_ref']}: {proc['title'][:60]}...")
            logger.info(f"  ... and {len(procedures) - 10} more")
            return stats

        # Get database session
        db: Session = SessionLocal()

        try:
            for proc in procedures:
                procedure_ref = proc.get('procedure_ref')

                if not procedure_ref:
                    stats['skipped_no_ref'] += 1
                    continue

                try:
                    # Check if already exists
                    existing = db.query(LegislativeCarriage).filter(
                        LegislativeCarriage.oeil_procedure_ref == procedure_ref
                    ).first()

                    if existing:
                        if force:
                            # Update with EPRS info
                            if not existing.eprs_matched_briefings:
                                existing.eprs_matched_briefings = []

                            # Add EPRS briefing if not already present
                            eprs_urls = [b.get('url') for b in existing.eprs_matched_briefings]
                            if proc.get('eprs_url') and proc['eprs_url'] not in eprs_urls:
                                existing.eprs_matched_briefings.append({
                                    'url': proc['eprs_url'],
                                    'title': proc['title'],
                                    'source': 'legislation_in_progress',
                                    'policy_area': proc.get('policy_area')
                                })
                                logger.debug(f"Updated EPRS briefing for {procedure_ref}")
                        else:
                            stats['skipped_existing'] += 1
                            continue
                    else:
                        # Create new carriage
                        file_id = f"lip-{procedure_ref.replace('/', '-').replace('(', '-').replace(')', '')}"

                        carriage = LegislativeCarriage(
                            file_id=file_id,
                            title=proc['title'],
                            oeil_procedure_ref=procedure_ref,
                            source=CarriageSourceEnum.OEIL_DIRECT,
                            current_status=CarriageStatusEnum.TABLED,  # Default status
                            eprs_matched_briefings=[{
                                'url': proc.get('eprs_url'),
                                'title': proc['title'],
                                'source': 'legislation_in_progress',
                                'policy_area': proc.get('policy_area')
                            }] if proc.get('eprs_url') else [],
                            policy_areas=[proc['policy_area']] if proc.get('policy_area') else [],
                        )

                        db.add(carriage)
                        stats['created'] += 1
                        logger.info(f"Created: {procedure_ref} - {proc['title'][:50]}...")

                except Exception as e:
                    error_msg = f"Error processing {procedure_ref}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # Commit all changes
            db.commit()
            logger.info(f"Committed {stats['created']} new carriages to database")

        except Exception as e:
            db.rollback()
            logger.error(f"Database error: {str(e)}")
            stats['errors'].append(f"Database error: {str(e)}")
        finally:
            db.close()

    finally:
        await scraper.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Sync EPRS "EU Legislation in Progress" to database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be synced without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Update existing records with EPRS info'
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("EPRS Legislation in Progress Sync")
    logger.info("=" * 60)

    stats = asyncio.run(sync_legislation_in_progress(
        dry_run=args.dry_run,
        force=args.force
    ))

    logger.info("")
    logger.info("=" * 60)
    logger.info("SYNC COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total scraped:     {stats['total_scraped']}")
    logger.info(f"Created:           {stats['created']}")
    logger.info(f"Skipped (exists):  {stats['skipped_existing']}")
    logger.info(f"Skipped (no ref):  {stats['skipped_no_ref']}")
    logger.info(f"Errors:            {len(stats['errors'])}")

    if stats['errors']:
        logger.info("")
        logger.info("Errors:")
        for error in stats['errors'][:10]:
            logger.info(f"  - {error}")
        if len(stats['errors']) > 10:
            logger.info(f"  ... and {len(stats['errors']) - 10} more")

    return 0 if not stats['errors'] else 1


if __name__ == '__main__':
    sys.exit(main())
