"""
Update Legislative Carriage Statuses Based on OEIL Key Events

This script fetches OEIL data for carriages with procedure refs and updates
their status to COMPLETED if "Act adopted by Council" is in key events.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage, CarriageStatusEnum
from services.scrapers.oeil_scraper import OEILScraper


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


async def update_statuses():
    """Update carriage statuses based on OEIL key events."""

    db = SessionLocal()
    scraper = OEILScraper()

    try:
        log("=" * 60)
        log("Update Carriage Statuses from OEIL Key Events")
        log("=" * 60)

        # Get all carriages with OEIL procedure refs that are not COMPLETED
        carriages = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref != None,
            LegislativeCarriage.oeil_procedure_ref != '',
            LegislativeCarriage.current_status != CarriageStatusEnum.COMPLETED,
            LegislativeCarriage.current_status != CarriageStatusEnum.ADOPTED
        ).all()

        log(f"\n1. Found {len(carriages)} carriages to check")

        updated_to_completed = 0
        updated_key_events = 0
        errors = 0

        for i, carriage in enumerate(carriages):
            procedure_ref = carriage.oeil_procedure_ref
            log(f"\n[{i+1}/{len(carriages)}] {procedure_ref}: {carriage.title[:40]}...")

            try:
                # Fetch OEIL data
                data = await scraper.get_procedure_full(procedure_ref)

                if data and data.key_events and data.key_events.events:
                    # Convert events to JSON-serializable format
                    events_json = [
                        {
                            'date': e.date.isoformat() if e.date else None,
                            'event_type': e.event_type,
                            'description': e.description
                        }
                        for e in data.key_events.events
                    ]

                    # Update oeil_key_events
                    carriage.oeil_key_events = events_json
                    updated_key_events += 1

                    # Check for "Act adopted by Council"
                    council_adopted = any(
                        'act adopted by council' in (e.event_type or '').lower()
                        for e in data.key_events.events
                    )

                    if council_adopted:
                        old_status = carriage.current_status.value
                        carriage.current_status = CarriageStatusEnum.COMPLETED
                        carriage.last_updated = datetime.now(timezone.utc)
                        updated_to_completed += 1
                        log(f"   -> Status updated: {old_status} -> COMPLETED")
                    else:
                        log(f"   -> No 'Act adopted by Council' found")
                else:
                    log(f"   -> No key events found")

                # Commit after each successful update to avoid losing progress
                db.commit()

                # Rate limiting - be nice to OEIL servers
                await asyncio.sleep(0.5)

            except Exception as e:
                log(f"   -> ERROR: {str(e)[:80]}")
                errors += 1
                # Rollback failed transaction and continue
                db.rollback()

        log("\n" + "=" * 60)
        log("Summary:")
        log(f"  Total checked: {len(carriages)}")
        log(f"  Key events updated: {updated_key_events}")
        log(f"  Status updated to COMPLETED: {updated_to_completed}")
        log(f"  Errors: {errors}")

        # Final stats
        log("\n" + "=" * 60)
        log("Current status distribution:")
        for status in CarriageStatusEnum:
            count = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.current_status == status
            ).count()
            log(f"  {status.value}: {count}")

        log("=" * 60)

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(update_statuses())
