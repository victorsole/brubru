"""
Batch Add OEIL Procedures - Additional

Add Detergents regulation and Human Rights annual report.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import uuid

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from sqlalchemy import or_
from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage,
    CarriageStatusEnum,
    TextTypeEnum,
    CarriageSourceEnum
)
from services.scrapers.oeil_scraper import OEILScraper


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


# New procedures from OEIL XML feed
NEW_PROCEDURES = [
    {
        "oeil_ref": "2023/0124(COD)",
        "title": "Detergents and Surfactants Regulation",
        "description": "Legislative proposal on detergents and surfactants, updating EU rules on the environmental and health aspects of cleaning products.",
        "text_type": TextTypeEnum.LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,  # From 2023, likely in progress
        "policy_areas": ["Environment", "Consumer protection", "Single market", "Chemicals"],
        "lead_committee": "ENVI",
        "rapporteur": "SBAI Majdouline (Greens/EFA)",
    },
    {
        "oeil_ref": "2025/2166(INI)",
        "title": "Human Rights and Democracy in the World – Annual Report 2025",
        "description": "Own-initiative annual report on Human Rights and Democracy in the world and the European Union's policy on the matter for 2025.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Human rights", "Democracy", "Foreign affairs", "External action"],
        "lead_committee": "AFET",
        "rapporteur": "ASSIS Francisco (S&D)",
    },
]


async def add_procedures():
    """Add all new procedures from OEIL feed."""

    db = SessionLocal()
    scraper = OEILScraper()

    try:
        log("=" * 70)
        log("Batch Add OEIL Procedures - Additional")
        log("=" * 70)
        log(f"Procedures to add: {len(NEW_PROCEDURES)}")
        log("=" * 70)

        added = 0
        updated = 0
        errors = 0

        for i, proc in enumerate(NEW_PROCEDURES):
            log(f"\n[{i+1}/{len(NEW_PROCEDURES)}] {proc['oeil_ref']}: {proc['title'][:50]}...")

            try:
                # Check if already exists
                existing = db.query(LegislativeCarriage).filter(
                    or_(
                        LegislativeCarriage.oeil_procedure_ref == proc['oeil_ref'],
                        LegislativeCarriage.title.ilike(f"%{proc['title'][:30]}%"),
                    )
                ).first()

                if existing:
                    log(f"   [EXISTS] Updating existing carriage...")
                    carriage = existing
                    updated += 1
                else:
                    log(f"   [NEW] Creating new carriage...")
                    file_id = proc['oeil_ref'].lower().replace('/', '-').replace('(', '-').replace(')', '')
                    carriage = LegislativeCarriage(
                        id=uuid.uuid4(),
                        file_id=file_id,
                    )
                    db.add(carriage)
                    added += 1

                # Set basic data
                carriage.title = proc['title']
                carriage.description = proc['description']
                carriage.current_status = proc['status']
                carriage.text_type = proc['text_type']
                carriage.oeil_procedure_ref = proc['oeil_ref']
                carriage.source = CarriageSourceEnum.OEIL_DIRECT
                carriage.policy_areas = proc['policy_areas']
                carriage.lead_committee = proc['lead_committee']

                # Fetch OEIL data for enrichment
                log(f"   Fetching OEIL data...")
                try:
                    oeil_data = await scraper.get_procedure_full(proc['oeil_ref'])

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
                            log(f"   Key Events: {len(events_json)} found")

                        # Store full OEIL data
                        carriage.oeil_procedure_data = oeil_data.model_dump(mode='json')
                        carriage.enriched_at = datetime.now(timezone.utc)
                        carriage.enrichment_quality = "high"

                except Exception as e:
                    log(f"   [WARN] OEIL fetch failed: {str(e)[:50]}")

                # Set timestamps
                now = datetime.now(timezone.utc)
                if not existing:
                    carriage.first_seen = now
                    carriage.scraped_at = now
                carriage.last_updated = now

                # Build OEIL URL
                carriage.url = f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={proc['oeil_ref']}"

                log(f"   [OK] Status: {carriage.current_status.value}, Committee: {carriage.lead_committee}")
                log(f"   Rapporteur: {proc.get('rapporteur', 'N/A')}")

                db.commit()
                await asyncio.sleep(0.5)

            except Exception as e:
                log(f"   [ERROR] {str(e)[:60]}")
                db.rollback()
                errors += 1

        log("\n" + "=" * 70)
        log("Summary:")
        log(f"   Added: {added}")
        log(f"   Updated: {updated}")
        log(f"   Errors: {errors}")
        log("=" * 70)

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    asyncio.run(add_procedures())
