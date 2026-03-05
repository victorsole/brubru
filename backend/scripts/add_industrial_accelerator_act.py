#!/usr/bin/env python3
"""
Add the Industrial Accelerator Act (COM(2026)100) to the legislative database.

Creates a LegislativeCarriage record and tracks it for all test users.
This is a one-time script for a newly published Commission proposal.

Usage:
    python3.12 -m scripts.add_industrial_accelerator_act
    python3.12 -m scripts.add_industrial_accelerator_act --dry-run
"""

import argparse
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, text
from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage,
    CarriageStatusEnum,
    CarriageSourceEnum,
    TextTypeEnum,
    UserCarriageTrack,
)


IAA_DATA = {
    "file_id": "industrial-accelerator-act-com-2026-100",
    "title": "Industrial Accelerator Act",
    "description": (
        "Proposal for a Regulation establishing measures for industrial capacity "
        "and decarbonisation in strategic sectors. Part of the Clean Industrial Deal "
        "package. Covers permitting acceleration, low-carbon product labels, "
        "public procurement criteria, and lead markets for EU-made clean products."
    ),
    "current_status": CarriageStatusEnum.TABLED,
    "source": CarriageSourceEnum.EURLEX,
    "text_type": TextTypeEnum.LEGISLATIVE,

    # Cross-references (OEIL ref TBD -- just published 4 March 2026)
    "oeil_procedure_ref": None,
    "celex_numbers": ["52026PC0100"],
    "lead_committee": "ITRE",
    "opinion_committees": ["ENVI", "IMCO"],
    "committees": ["ITRE", "ENVI", "IMCO"],
    "policy_areas": [
        "industrial policy",
        "decarbonisation",
        "internal market",
        "clean technology",
        "public procurement",
    ],
    "spotlight_tags": ["Clean Industrial Deal", "Competitiveness"],
    "related_themes": [
        "a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness"
    ],

    # URLs
    "url": "https://www.europarl.europa.eu/legislative-train/theme-a-new-plan-for-europe-s-sustainable-prosperity-and-competitiveness/file-industrial-decarbonisation-accelerator-act",
    "legal_text_url": "https://single-market-economy.ec.europa.eu/publications/industrial-accelerator-act_en",

    # Enrichment data
    "oeil_procedure_data": {
        "com_reference": "COM(2026)100",
        "swd_references": ["SWD(2026)70", "SWD(2026)71", "SWD(2026)72"],
        "responsible_dg": "DG GROW",
        "responsible_commissioner": "Stephane Sejourne",
        "legal_basis": "Article 114 TFEU, Article 192 TFEU",
        "proposal_date": "2026-03-04",
        "related_procedures": [
            {"ref": "2025/2656(RSP)", "title": "Resolution on the Clean Industrial Deal", "type": "related_resolution"}
        ],
        "related_documents": [
            {"ref": "COM(2025)85", "title": "Clean Industrial Deal Communication"},
            {"ref": "COM(2025)30", "title": "Competitiveness Compass"},
            {"ref": "COM(2025)378", "title": "Delivering on the Clean Industrial Deal I"},
        ],
    },
    "eurlex_documents": [
        {
            "celex": "52026PC0100",
            "title": "Proposal for a Regulation establishing measures for industrial capacity and decarbonisation in strategic sectors",
            "type": "proposal",
            "date": "2026-03-04",
        }
    ],

    # AI summary
    "ai_summary": (
        "The Industrial Accelerator Act (COM(2026)100) proposes a Regulation to "
        "accelerate industrial decarbonisation in strategic sectors including steel, "
        "cement, chemicals, and clean technology manufacturing. Key measures include "
        "streamlined permitting procedures, low-carbon product labels (starting with "
        "steel and cement), public procurement criteria favouring clean products, and "
        "the creation of lead markets for EU-made clean industrial technologies. "
        "The proposal complements the Net-Zero Industry Act by addressing demand-side "
        "measures and permitting bottlenecks beyond NZIA scope."
    ),

    "first_seen": datetime(2026, 3, 4),
    "last_updated": datetime(2026, 3, 4),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Check if already exists
        existing = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.file_id == IAA_DATA["file_id"]
        ).first()
        if existing:
            print("[INFO] Industrial Accelerator Act already exists in database")
            return

        if args.dry_run:
            print("[DRY RUN] Would create carriage:")
            print(f"  Title: {IAA_DATA['title']}")
            print(f"  File ID: {IAA_DATA['file_id']}")
            print(f"  Status: {IAA_DATA['current_status'].value}")
            print(f"  CELEX: {IAA_DATA['celex_numbers']}")
            print(f"  Committee: {IAA_DATA['lead_committee']}")
            return

        # Create carriage
        carriage = LegislativeCarriage(**IAA_DATA)
        db.add(carriage)
        db.flush()
        print(f"[OK] Created carriage: {carriage.id}")

        # Track for all test users
        test_users = db.execute(
            text("""
                SELECT id, email FROM users
                WHERE email LIKE '%@brubru.eu'
                   OR email LIKE '%@beresol.eu'
                LIMIT 20
            """)
        ).fetchall()

        tracked_count = 0
        for user_id, email in test_users:
            track = UserCarriageTrack(
                user_id=user_id,
                carriage_id=carriage.id,
            )
            db.add(track)
            tracked_count += 1

        db.commit()
        print(f"[OK] Tracked for {tracked_count} users")
        print(f"[OK] Carriage ID: {carriage.id}")
        print(f"[OK] File ID: {IAA_DATA['file_id']}")
        print("[INFO] When OEIL assigns a procedure ref, update with:")
        print(f"  UPDATE legislative_carriages SET oeil_procedure_ref = '2026/XXXX(COD)' WHERE file_id = '{IAA_DATA['file_id']}';")
    finally:
        db.close()


if __name__ == "__main__":
    main()
