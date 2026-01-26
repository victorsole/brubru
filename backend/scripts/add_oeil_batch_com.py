"""
Batch Add Commission Documents from OEIL - January 23, 2026

Add COM documents including SAFE programme, BEREC/ENISA evaluations, etc.
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


# Commission documents from OEIL XML feed
NEW_PROCEDURES = [
    # SAFE Programme - Security Action for Europe
    {
        "oeil_ref": "COM(2026)0031",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Cyprus",
        "description": "Council implementing decision making SAFE financial assistance available to Cyprus for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Cyprus"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0030",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Croatia",
        "description": "Council implementing decision making SAFE financial assistance available to Croatia for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Croatia"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0029",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Belgium",
        "description": "Council implementing decision making SAFE financial assistance available to Belgium for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Belgium"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0028",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Denmark",
        "description": "Council implementing decision making SAFE financial assistance available to Denmark for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Denmark"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0027",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Spain",
        "description": "Council implementing decision making SAFE financial assistance available to Spain for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Spain"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0026",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Romania",
        "description": "Council implementing decision making SAFE financial assistance available to Romania for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Romania"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0025",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Bulgaria",
        "description": "Council implementing decision making SAFE financial assistance available to Bulgaria for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Bulgaria"],
        "lead_committee": "SEDE",
    },
    {
        "oeil_ref": "COM(2026)0024",
        "title": "Security Action for Europe (SAFE) – Financial Assistance to Portugal",
        "description": "Council implementing decision making SAFE financial assistance available to Portugal for defence and security investments.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Defence", "Security", "SAFE programme", "Portugal"],
        "lead_committee": "SEDE",
    },
    # Evaluations and other documents
    {
        "oeil_ref": "COM(2026)0034",
        "title": "Evaluation of BEREC and the BEREC Office",
        "description": "Commission evaluation of the Body of European Regulators for Electronic Communications (BEREC) and its Office.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Telecommunications", "Digital single market", "Regulatory bodies"],
        "lead_committee": "ITRE",
    },
    {
        "oeil_ref": "COM(2026)0009",
        "title": "Evaluation of ENISA and the European Cybersecurity Certification Framework",
        "description": "Commission evaluation of the European Union Agency for Cybersecurity (ENISA) and the European Cybersecurity Certification Framework.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Cybersecurity", "ENISA", "Certification", "Digital single market"],
        "lead_committee": "ITRE",
    },
    {
        "oeil_ref": "COM(2026)0033",
        "title": "Austria – National Escape Clause Activation under Regulation (EU) 2024/1263",
        "description": "Recommendation for a Council Recommendation allowing Austria to deviate from maximum growth rates of net expenditure (activation of national escape clause).",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Economic governance", "Fiscal policy", "Austria"],
        "lead_committee": "ECON",
    },
    {
        "oeil_ref": "COM(2026)0008",
        "title": "WTO – Adoption of Several Decisions (EU Position)",
        "description": "EU position for the World Trade Organization regarding the envisaged adoption of several decisions.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["International trade", "WTO", "Trade policy"],
        "lead_committee": "INTA",
    },
]


async def add_procedures():
    """Add Commission documents from OEIL feed."""

    db = SessionLocal()
    scraper = OEILScraper()

    try:
        log("=" * 70)
        log("Batch Add Commission Documents - January 23, 2026")
        log("=" * 70)
        log(f"Documents to add: {len(NEW_PROCEDURES)}")
        log("=" * 70)

        added = 0
        updated = 0
        errors = 0

        for i, proc in enumerate(NEW_PROCEDURES):
            log(f"\n[{i+1}/{len(NEW_PROCEDURES)}] {proc['oeil_ref']}: {proc['title'][:45]}...")

            try:
                # Check if already exists
                existing = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.oeil_procedure_ref == proc['oeil_ref']
                ).first()

                if existing:
                    log(f"   [EXISTS] Updating existing carriage...")
                    carriage = existing
                    updated += 1
                else:
                    log(f"   [NEW] Creating new carriage...")
                    file_id = proc['oeil_ref'].lower().replace('(', '-').replace(')', '')
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

                # Set timestamps
                now = datetime.now(timezone.utc)
                if not existing:
                    carriage.first_seen = now
                    carriage.scraped_at = now
                carriage.last_updated = now

                # Build OEIL URL
                carriage.url = f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={proc['oeil_ref']}"

                log(f"   [OK] Status: {carriage.current_status.value}, Committee: {carriage.lead_committee}")

                db.commit()

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
