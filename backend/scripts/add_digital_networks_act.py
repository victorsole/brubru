"""
Add Digital Networks Act (DNA) Legislative File

Status: ANNOUNCED
Source: EC Legislative Train Schedule

References:
- EC Digital Strategy: https://digital-strategy.ec.europa.eu/en/policies/digital-networks-act
- Legislative Train: https://www.europarl.europa.eu/legislative-train/theme-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness/file-digital-networks-act-(dna)
"""

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
    LegislativePackage,
    CarriageStatusEnum,
    TextTypeEnum,
    CarriageSourceEnum
)


def log(msg):
    """Print and flush immediately."""
    print(msg, flush=True)


def add_digital_networks_act():
    """Add Digital Networks Act carriage to the database."""

    db = SessionLocal()

    # Carriage data from Legislative Train
    DNA_DATA = {
        "file_id": "digital-networks-act-dna",
        "title": "Digital Networks Act (DNA)",
        "description": (
            "The Digital Networks Act aims to modernise EU telecoms rules to boost investment "
            "in digital infrastructure, simplify regulations, and ensure Europe's competitiveness "
            "in the global digital economy. It will address the need for massive investments in "
            "very high-capacity networks (fibre and 5G) and support the EU's digital decade targets."
        ),
        "current_status": CarriageStatusEnum.ANNOUNCED,
        "source": CarriageSourceEnum.LEGISLATIVE_TRAIN,
        "text_type": TextTypeEnum.LEGISLATIVE,

        # URLs
        "url": "https://www.europarl.europa.eu/legislative-train/theme-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness/file-digital-networks-act-(dna)",
        "legal_text_url": "https://digital-strategy.ec.europa.eu/en/policies/digital-networks-act",

        # Committees (expected)
        "lead_committee": "ITRE",  # Industry, Research and Energy

        # Policy areas
        "policy_areas": [
            "Digital single market",
            "Telecommunications",
            "Digital infrastructure",
            "5G/6G networks",
            "Fibre deployment"
        ],

        # Related themes
        "related_themes": [
            "Digital decade",
            "Connectivity",
            "Competitiveness"
        ],

        # EC priorities
        "ec_priority_ids": ["competitiveness"],  # A new plan for Europe's sustainable prosperity and competitiveness

        # Package slug (from Legislative Train URL)
        "package_slug": "package-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness",
    }

    try:
        log("=" * 60)
        log("Add Digital Networks Act (DNA) Legislative File")
        log("=" * 60)

        # Step 1: Check if carriage already exists
        log("\n1. Checking for existing carriage...")

        existing = db.query(LegislativeCarriage).filter(
            or_(
                LegislativeCarriage.file_id == DNA_DATA["file_id"],
                LegislativeCarriage.title.ilike('%digital networks act%'),
                LegislativeCarriage.title.ilike('%DNA%telecommunications%'),
            )
        ).first()

        if existing:
            log(f"   [WARN] Carriage already exists!")
            log(f"      Title: {existing.title}")
            log(f"      Status: {existing.current_status.value}")
            log(f"      File ID: {existing.file_id}")
            log("\n   Updating existing carriage instead of creating new one...")
            carriage = existing
        else:
            log("   [OK] No existing carriage found. Creating new one...")
            carriage = LegislativeCarriage(
                id=uuid.uuid4(),
                file_id=DNA_DATA["file_id"],
            )
            db.add(carriage)

        # Step 2: Find the parent package
        log("\n2. Finding parent package...")

        package = db.query(LegislativePackage).filter(
            or_(
                LegislativePackage.slug == DNA_DATA["package_slug"],
                LegislativePackage.name.ilike('%competitiveness%'),
                LegislativePackage.name.ilike('%prosperity%'),
            )
        ).first()

        if package:
            log(f"   [OK] Found package: {package.name}")
            carriage.package_id = package.id
            carriage.train_id = package.train_id
        else:
            log("   [WARN] No matching package found. Carriage will be unassigned.")

        # Step 3: Set carriage data
        log("\n3. Setting carriage data...")

        carriage.title = DNA_DATA["title"]
        log(f"   Title: {carriage.title}")

        carriage.description = DNA_DATA["description"]
        log(f"   Description: {carriage.description[:60]}...")

        carriage.current_status = DNA_DATA["current_status"]
        log(f"   Status: {carriage.current_status.value}")

        carriage.source = DNA_DATA["source"]
        log(f"   Source: {carriage.source.value}")

        carriage.text_type = DNA_DATA["text_type"]
        log(f"   Text Type: {carriage.text_type.value}")

        carriage.url = DNA_DATA["url"]
        log(f"   URL: {carriage.url}")

        carriage.legal_text_url = DNA_DATA["legal_text_url"]
        log(f"   Legal Text URL: {carriage.legal_text_url}")

        carriage.lead_committee = DNA_DATA["lead_committee"]
        log(f"   Lead Committee: {carriage.lead_committee}")

        carriage.policy_areas = DNA_DATA["policy_areas"]
        log(f"   Policy Areas: {len(carriage.policy_areas)} areas")

        carriage.related_themes = DNA_DATA["related_themes"]
        log(f"   Related Themes: {carriage.related_themes}")

        carriage.ec_priority_ids = DNA_DATA["ec_priority_ids"]
        log(f"   EC Priority IDs: {carriage.ec_priority_ids}")

        carriage.package_slug = DNA_DATA["package_slug"]
        log(f"   Package Slug: {carriage.package_slug}")

        # Timestamps
        now = datetime.now(timezone.utc)
        carriage.scraped_at = now
        carriage.first_seen = now
        carriage.last_updated = now

        # Step 4: Commit
        log("\n4. Committing to database...")
        db.commit()
        log("   [OK] Changes committed!")

        # Step 5: Verify
        log("\n5. Verifying...")
        db.refresh(carriage)

        log(f"   ID: {carriage.id}")
        log(f"   File ID: {carriage.file_id}")
        log(f"   Title: {carriage.title}")
        log(f"   Status: {carriage.current_status.value}")
        log(f"   Lead Committee: {carriage.lead_committee}")
        log(f"   Package ID: {carriage.package_id}")

        log("\n" + "=" * 60)
        log("[OK] Digital Networks Act added successfully!")
        log("=" * 60)

    except Exception as e:
        log(f"\n[ERROR] Failed to add carriage: {str(e)}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    add_digital_networks_act()
