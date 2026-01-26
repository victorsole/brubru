"""
Update Digital Networks Act (DNA) with OEIL Data

The DNA was tabled on January 23, 2026 with OEIL reference 2026/0013(COD).
Update status from ANNOUNCED to TABLED and enrich with OEIL data.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from sqlalchemy import or_
from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage, CarriageStatusEnum
from services.scrapers.oeil_scraper import OEILScraper


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


async def update_dna_oeil():
    """Update Digital Networks Act with OEIL data."""

    db = SessionLocal()
    scraper = OEILScraper()

    # Target data from OEIL XML feed
    OEIL_REF = "2026/0013(COD)"
    NEW_STATUS = CarriageStatusEnum.TABLED
    OEIL_TITLE = "Digital Networks Act"

    try:
        log("=" * 60)
        log("Update Digital Networks Act (DNA) with OEIL Data")
        log("=" * 60)
        log(f"OEIL Reference: {OEIL_REF}")
        log(f"New Status: {NEW_STATUS.value}")
        log("=" * 60)

        # Step 1: Find the DNA carriage
        log("\n1. Finding Digital Networks Act carriage...")

        carriage = db.query(LegislativeCarriage).filter(
            or_(
                LegislativeCarriage.file_id == "digital-networks-act-dna",
                LegislativeCarriage.title.ilike('%digital networks act%'),
                LegislativeCarriage.oeil_procedure_ref == OEIL_REF,
            )
        ).first()

        if not carriage:
            log("   [ERROR] Digital Networks Act carriage not found!")
            return

        log(f"   [OK] Found carriage:")
        log(f"      Title: {carriage.title}")
        log(f"      Current Status: {carriage.current_status.value}")
        log(f"      Current OEIL Ref: {carriage.oeil_procedure_ref or 'None'}")

        # Step 2: Fetch OEIL data
        log(f"\n2. Fetching OEIL procedure data for {OEIL_REF}...")

        oeil_data = None
        try:
            oeil_data = await scraper.get_procedure_full(OEIL_REF)
            log("   [OK] OEIL data fetched successfully")

            if oeil_data.basic_info:
                log(f"      Title: {oeil_data.basic_info.title or 'N/A'}")
                log(f"      Status: {oeil_data.basic_info.status or 'N/A'}")
                log(f"      Procedure Type: {oeil_data.basic_info.procedure_type or 'N/A'}")

            if oeil_data.key_players:
                if oeil_data.key_players.committee_responsible:
                    log(f"      Lead Committee: {oeil_data.key_players.committee_responsible.code}")
                    if oeil_data.key_players.committee_responsible.rapporteur:
                        log(f"      Rapporteur: {oeil_data.key_players.committee_responsible.rapporteur.name}")
                if oeil_data.key_players.commission_dg:
                    log(f"      Commission DG: {oeil_data.key_players.commission_dg}")

            if oeil_data.key_events and oeil_data.key_events.events:
                log(f"      Key Events: {len(oeil_data.key_events.events)} found")

        except Exception as e:
            log(f"   [WARN] Failed to fetch OEIL data: {str(e)}")
            log("   Continuing with basic update...")

        # Step 3: Update carriage
        log(f"\n3. Updating carriage...")

        old_status = carriage.current_status.value
        old_oeil_ref = carriage.oeil_procedure_ref

        # Update status
        carriage.current_status = NEW_STATUS
        log(f"   Status: {old_status} -> {NEW_STATUS.value}")

        # Update OEIL reference
        carriage.oeil_procedure_ref = OEIL_REF
        log(f"   OEIL Ref: {old_oeil_ref or 'None'} -> {OEIL_REF}")

        # Update with OEIL data if available
        if oeil_data:
            # Update key events
            if oeil_data.key_events and oeil_data.key_events.events:
                events_json = [
                    {
                        'date': e.date.isoformat() if e.date else None,
                        'event_type': e.event_type,
                        'description': e.description
                    }
                    for e in oeil_data.key_events.events
                ]
                carriage.oeil_key_events = events_json
                log(f"   Key Events: Updated ({len(events_json)} events)")

            # Update lead committee from OEIL if available
            if oeil_data.key_players and oeil_data.key_players.committee_responsible:
                oeil_committee = oeil_data.key_players.committee_responsible.code
                if oeil_committee and oeil_committee != "UNKNOWN":
                    carriage.lead_committee = oeil_committee
                    log(f"   Lead Committee: {carriage.lead_committee}")

            # Store full OEIL procedure data (use mode='json' for proper serialization)
            carriage.oeil_procedure_data = oeil_data.model_dump(mode='json')
            log(f"   OEIL Procedure Data: Stored")

            # Update enrichment timestamp
            carriage.enriched_at = datetime.now(timezone.utc)
            carriage.enrichment_quality = "high"

        # Update last modified
        carriage.last_updated = datetime.now(timezone.utc)

        # Commit changes
        db.commit()
        log("\n   [OK] Changes committed to database")

        # Step 4: Verify
        log(f"\n4. Verifying update...")
        db.refresh(carriage)
        log(f"   Title: {carriage.title}")
        log(f"   Status: {carriage.current_status.value}")
        log(f"   OEIL Ref: {carriage.oeil_procedure_ref}")
        log(f"   Lead Committee: {carriage.lead_committee}")
        log(f"   Last Updated: {carriage.last_updated}")

        log("\n" + "=" * 60)
        log("[OK] Digital Networks Act updated successfully!")
        log("=" * 60)

    except Exception as e:
        log(f"\n[ERROR] Update failed: {str(e)}")
        db.rollback()
        raise

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(update_dna_oeil())
