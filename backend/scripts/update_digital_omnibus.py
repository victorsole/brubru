"""
Update Digital Omnibus Legislative File

Updates the Digital Omnibus (Digital Fairness Omnibus) carriage:
- Status: ANNOUNCED -> TABLED
- OEIL Procedure Reference: 2025/0359(COD)
- Enriches with full OEIL data

EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52025PC0837
OEIL: https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0359(COD)
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


async def update_digital_omnibus():
    """Update Digital Omnibus carriage with OEIL data."""

    db = SessionLocal()
    scraper = OEILScraper()

    # Target data
    OEIL_REF = "2025/0359(COD)"
    CELEX = "52025PC0837"
    NEW_STATUS = CarriageStatusEnum.TABLED

    try:
        log("=" * 60)
        log("Update Digital Omnibus Legislative File")
        log("=" * 60)
        log(f"OEIL Reference: {OEIL_REF}")
        log(f"CELEX Number: {CELEX}")
        log(f"Target Status: {NEW_STATUS.value}")
        log("=" * 60)

        # Step 1: Find the carriage
        log("\n1. Searching for Digital Omnibus carriage...")

        # Search by multiple criteria
        carriage = db.query(LegislativeCarriage).filter(
            or_(
                LegislativeCarriage.oeil_procedure_ref == OEIL_REF,
                LegislativeCarriage.title.ilike('%digital omnibus%'),
                LegislativeCarriage.title.ilike('%digital fairness%'),
                LegislativeCarriage.celex_numbers.contains([CELEX]),
            )
        ).first()

        if not carriage:
            log("   [WARN] Carriage not found. Searching by partial title match...")
            # Try broader search
            carriages = db.query(LegislativeCarriage).filter(
                or_(
                    LegislativeCarriage.title.ilike('%omnibus%'),
                    LegislativeCarriage.title.ilike('%consumer protection%digital%'),
                    LegislativeCarriage.title.ilike('%unfair commercial practices%'),
                )
            ).all()

            if carriages:
                log(f"   Found {len(carriages)} potential matches:")
                for c in carriages:
                    log(f"      - {c.title[:60]}... (status: {c.current_status.value})")
                    log(f"        OEIL: {c.oeil_procedure_ref or 'None'}")

                # Use the first match if it's the only one
                if len(carriages) == 1:
                    carriage = carriages[0]
                    log(f"\n   Using the only match found.")
                else:
                    log("\n   [ERROR] Multiple matches found. Please specify which one to update.")
                    return
            else:
                log("   [ERROR] No carriage found matching Digital Omnibus criteria.")
                log("   You may need to create the carriage first or check the title.")
                return

        log(f"\n   [OK] Found carriage:")
        log(f"      Title: {carriage.title}")
        log(f"      Current Status: {carriage.current_status.value}")
        log(f"      Current OEIL Ref: {carriage.oeil_procedure_ref or 'None'}")
        log(f"      File ID: {carriage.file_id}")

        # Step 2: Fetch OEIL data
        log(f"\n2. Fetching OEIL procedure data for {OEIL_REF}...")

        try:
            oeil_data = await scraper.get_procedure_full(OEIL_REF)
            log("   [OK] OEIL data fetched successfully")

            if oeil_data.basic_info:
                log(f"      Title from OEIL: {oeil_data.basic_info.title or 'N/A'}")
                log(f"      Status from OEIL: {oeil_data.basic_info.status or 'N/A'}")
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
            log(f"   [ERROR] Failed to fetch OEIL data: {str(e)}")
            oeil_data = None

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

        # Update CELEX numbers
        if CELEX not in (carriage.celex_numbers or []):
            carriage.celex_numbers = (carriage.celex_numbers or []) + [CELEX]
            log(f"   CELEX: Added {CELEX}")

        # Update with OEIL data if available
        if oeil_data:
            # Only update title if OEIL has a meaningful one (not just "Procedure File: X")
            if oeil_data.basic_info and oeil_data.basic_info.title:
                oeil_title = oeil_data.basic_info.title
                # Don't use generic OEIL titles like "Procedure File: 2025/0359(COD)"
                is_generic_title = oeil_title.startswith("Procedure File:") or oeil_title.startswith("20")
                if len(oeil_title) > 10 and oeil_title != carriage.title and not is_generic_title:
                    log(f"   Title: Updated from OEIL")
                    carriage.title = oeil_title
                else:
                    log(f"   Title: Kept existing (OEIL title is generic)")

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

            # Update lead committee
            if oeil_data.key_players and oeil_data.key_players.committee_responsible:
                carriage.lead_committee = oeil_data.key_players.committee_responsible.code
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
        log(f"   CELEX: {carriage.celex_numbers}")
        log(f"   Lead Committee: {carriage.lead_committee}")
        log(f"   Last Updated: {carriage.last_updated}")

        log("\n" + "=" * 60)
        log("[OK] Digital Omnibus update complete!")
        log("=" * 60)

    except Exception as e:
        log(f"\n[ERROR] Update failed: {str(e)}")
        db.rollback()
        raise

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(update_digital_omnibus())
