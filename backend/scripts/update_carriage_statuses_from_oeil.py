"""
Update Legislative Carriage Statuses Based on OEIL Key Events

This script fetches OEIL data for carriages with procedure refs and updates
their status based on key events detected on the OEIL procedure page.

Status inference rules (strongest signal wins):
  - "Final act signed" or "Final act published" or "Entry into force" -> ADOPTED
  - "Act adopted by Council" or "Decision by Parliament" (both present) -> COMPLETED
  - "Act adopted by Council" alone -> COMPLETED
  - "Vote in committee" or "Committee report" -> CLOSE_TO_ADOPTION (only if currently ANNOUNCED/TABLED)
  - "Legislative proposal" or "Committee referral" -> TABLED (only if currently ANNOUNCED)
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


# Status progression order (higher index = further along)
STATUS_RANK = {
    CarriageStatusEnum.ANNOUNCED: 0,
    CarriageStatusEnum.LEGISLATIVE_INITIATIVE: 1,
    CarriageStatusEnum.TABLED: 2,
    CarriageStatusEnum.CLOSE_TO_ADOPTION: 3,
    CarriageStatusEnum.COMPLETED: 4,
    CarriageStatusEnum.ADOPTED: 5,
    # BLOCKED and WITHDRAWN are not in the progression
}


def infer_status_from_events(events) -> CarriageStatusEnum | None:
    """
    Infer the most advanced status from a list of OEIL key events.
    Returns None if no status can be inferred.
    """
    event_types_lower = [(e.event_type or '').lower() for e in events]

    # Strongest signal: final act
    if any('final act signed' in et for et in event_types_lower):
        return CarriageStatusEnum.ADOPTED
    if any('final act published' in et for et in event_types_lower):
        return CarriageStatusEnum.ADOPTED
    if any('entry into force' in et for et in event_types_lower):
        return CarriageStatusEnum.ADOPTED

    # Strong signal: adopted by Council
    if any('act adopted by council' in et for et in event_types_lower):
        return CarriageStatusEnum.COMPLETED

    # Medium signal: both Parliament decision and committee report
    has_parliament_decision = any('decision by parliament' in et for et in event_types_lower)
    has_committee_report = any('committee report' in et for et in event_types_lower)
    has_vote_in_committee = any('vote in committee' in et for et in event_types_lower)

    if has_parliament_decision:
        return CarriageStatusEnum.COMPLETED

    if has_committee_report or has_vote_in_committee:
        return CarriageStatusEnum.CLOSE_TO_ADOPTION

    # Weak signal: at least tabled
    if any('legislative proposal' in et for et in event_types_lower):
        return CarriageStatusEnum.TABLED
    if any('committee referral' in et for et in event_types_lower):
        return CarriageStatusEnum.TABLED

    return None


async def update_statuses():
    """Update carriage statuses based on OEIL key events."""

    db = SessionLocal()
    scraper = OEILScraper()

    try:
        log("=" * 60)
        log("Update Carriage Statuses from OEIL Key Events")
        log("=" * 60)

        # Get all carriages with OEIL procedure refs that are not already ADOPTED
        carriages = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref != None,
            LegislativeCarriage.oeil_procedure_ref != '',
            LegislativeCarriage.current_status != CarriageStatusEnum.ADOPTED,
            LegislativeCarriage.current_status != CarriageStatusEnum.WITHDRAWN
        ).all()

        log(f"\n1. Found {len(carriages)} carriages to check")

        updated_count = 0
        updated_key_events = 0
        errors = 0
        status_changes = []

        for i, carriage in enumerate(carriages):
            procedure_ref = carriage.oeil_procedure_ref
            log(f"\n[{i+1}/{len(carriages)}] {procedure_ref}: {carriage.title[:50]}...")

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

                    # Infer status from events
                    inferred = infer_status_from_events(data.key_events.events)

                    if inferred:
                        current_rank = STATUS_RANK.get(carriage.current_status, -1)
                        inferred_rank = STATUS_RANK.get(inferred, -1)

                        # Only advance status forward, never regress
                        if inferred_rank > current_rank:
                            old_status = carriage.current_status.value
                            carriage.current_status = inferred
                            carriage.last_updated = datetime.now(timezone.utc)
                            updated_count += 1
                            status_changes.append(f"{procedure_ref}: {old_status} -> {inferred.value}")
                            log(f"   -> Status updated: {old_status} -> {inferred.value}")
                        else:
                            log(f"   -> Status already at {carriage.current_status.value} (inferred: {inferred.value})")
                    else:
                        log(f"   -> No status signal from events")
                else:
                    log(f"   -> No key events found")

                # Commit after each successful update to avoid losing progress
                db.commit()

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                log(f"   -> ERROR: {str(e)[:80]}")
                errors += 1
                db.rollback()

        log("\n" + "=" * 60)
        log("Summary:")
        log(f"  Total checked: {len(carriages)}")
        log(f"  Key events updated: {updated_key_events}")
        log(f"  Status changes: {updated_count}")
        log(f"  Errors: {errors}")

        if status_changes:
            log("\nAll status changes:")
            for change in status_changes:
                log(f"  {change}")

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
