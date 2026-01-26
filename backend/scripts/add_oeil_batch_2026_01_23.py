"""
Batch Add OEIL Procedures - January 23, 2026

Add new legislative files from OEIL XML feed.
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


# New procedures from OEIL XML feed (January 23, 2026)
NEW_PROCEDURES = [
    {
        "oeil_ref": "2026/0012(COD)",
        "title": "Simplification Measures and Alignment with Cybersecurity Act 2",
        "description": "Legislative proposal for simplification measures and alignment with the Proposal for the Cybersecurity Act 2, streamlining EU cybersecurity regulations.",
        "text_type": TextTypeEnum.LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Cybersecurity", "Digital single market", "Simplification"],
        "lead_committee": None,  # Not yet assigned
    },
    {
        "oeil_ref": "2026/0011(COD)",
        "title": "EU Cybersecurity Agency (ENISA) and ICT Cybersecurity Certification (Cybersecurity Act 2)",
        "description": "Proposal to strengthen ENISA's mandate and update the ICT cybersecurity certification framework. This is the Cybersecurity Act 2, modernising the EU's cybersecurity architecture.",
        "text_type": TextTypeEnum.LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Cybersecurity", "ENISA", "Certification", "Digital single market"],
        "lead_committee": "ITRE",  # Likely ITRE
    },
    {
        "oeil_ref": "2026/2006(INI)",
        "title": "Protection of EU's Financial Interests in Post-2027 MFF - Anti-Fraud Architecture Revision",
        "description": "Own-initiative report on protecting the Union's financial interests in the post-2027 multiannual financial framework through the revision of the anti-fraud architecture.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Budget", "Anti-fraud", "Financial interests", "MFF"],
        "lead_committee": "CONT",  # Budgetary Control
    },
    {
        "oeil_ref": "2026/2005(INI)",
        "title": "EU External Action on AI and Human Rights Challenges",
        "description": "Own-initiative report on shaping the EU's external action to address the human rights challenges posed by artificial intelligence.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Artificial intelligence", "Human rights", "External action", "Foreign affairs"],
        "lead_committee": "AFET",  # Foreign Affairs
    },
    {
        "oeil_ref": "2026/2004(INI)",
        "title": "EU Strategy to Protect International Justice System and Institutions",
        "description": "Own-initiative report towards an EU strategy to protect and strengthen the international justice system and its institutions, mechanisms and partners.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["International justice", "Rule of law", "Foreign affairs", "Human rights"],
        "lead_committee": "AFET",  # Foreign Affairs
    },
    {
        "oeil_ref": "2026/2003(INI)",
        "title": "Connecting Europe Through High-Speed Rail",
        "description": "Own-initiative report on connecting Europe through high-speed rail, examining infrastructure investment and cross-border connectivity.",
        "text_type": TextTypeEnum.NON_LEGISLATIVE,
        "status": CarriageStatusEnum.TABLED,
        "policy_areas": ["Transport", "Rail", "Infrastructure", "TEN-T", "Connectivity"],
        "lead_committee": "TRAN",  # Transport and Tourism
    },
]


async def add_procedures():
    """Add all new procedures from OEIL feed."""

    db = SessionLocal()
    scraper = OEILScraper()

    try:
        log("=" * 70)
        log("Batch Add OEIL Procedures - January 23, 2026")
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
                    # Generate file_id from OEIL ref
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

                if proc['lead_committee']:
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

                        # Update committee from OEIL if not set
                        if oeil_data.key_players and oeil_data.key_players.committee_responsible:
                            oeil_committee = oeil_data.key_players.committee_responsible.code
                            if oeil_committee and oeil_committee != "UNKNOWN" and not carriage.lead_committee:
                                carriage.lead_committee = oeil_committee
                                log(f"   Lead Committee: {carriage.lead_committee}")

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

                log(f"   [OK] Status: {carriage.current_status.value}, Committee: {carriage.lead_committee or 'TBD'}")

                # Commit after each to avoid losing progress
                db.commit()

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                log(f"   [ERROR] {str(e)[:60]}")
                db.rollback()
                errors += 1

        # Summary
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
