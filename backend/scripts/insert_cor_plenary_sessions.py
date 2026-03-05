"""
Insert Committee of the Regions (CoR) plenary sessions into EU Calendar.

Sources: cor.europa.eu/en/plenaries-events/plenary-sessions
         CoR Meetings Calendar 2025/2026 PDFs

Usage:
    python3.12 scripts/insert_cor_plenary_sessions.py [--dry-run] [--verbose]

Created: March 2026
"""

import argparse
import sys
import os
from datetime import date, datetime
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.eu_calendar import EUCalendarEvent, InstitutionEnum, EventTypeEnum, EventStatusEnum


COR_PLENARY_SESSIONS = [
    # 2025
    {
        "session": "167th",
        "start_date": date(2025, 7, 2),
        "end_date": date(2025, 7, 3),
        "status": EventStatusEnum.COMPLETED,
    },
    {
        "session": "168th",
        "start_date": date(2025, 10, 13),
        "end_date": date(2025, 10, 15),
        "description": "Coincides with EU Regions Week 2025.",
        "status": EventStatusEnum.COMPLETED,
    },
    {
        "session": "169th",
        "start_date": date(2025, 12, 10),
        "end_date": date(2025, 12, 11),
        "status": EventStatusEnum.COMPLETED,
    },
    # 2026
    {
        "session": "170th",
        "start_date": date(2026, 3, 4),
        "end_date": date(2026, 3, 5),
        "description": "14 opinions adopted. Key items: MFF post-2027 (Rautio), Water Resilience (Tutto/Moreno), European Competitiveness Fund (Granfalk), Single Market Strategy (Galligani), Chemical Industry Action Plan (Vermeulen), Enlargement Package (Coughlan/Molinoz), EU Grids Package (Colleran Molloy). Debates with EVP Sejourne and Commissioner Roswall. Adamowicz Award 5th edition.",
        "status": EventStatusEnum.CONFIRMED,
    },
    {
        "session": "171st",
        "start_date": date(2026, 6, 24),
        "end_date": date(2026, 6, 25),
        "status": EventStatusEnum.TENTATIVE,
    },
    {
        "session": "172nd",
        "start_date": date(2026, 10, 12),
        "end_date": date(2026, 10, 14),
        "description": "Expected to coincide with EU Regions Week 2026.",
        "status": EventStatusEnum.TENTATIVE,
    },
    {
        "session": "173rd",
        "start_date": date(2026, 12, 9),
        "end_date": date(2026, 12, 10),
        "status": EventStatusEnum.TENTATIVE,
    },
]


def insert_sessions(dry_run: bool = False, verbose: bool = False):
    """Insert CoR plenary sessions into eu_calendar_events."""
    session = SessionLocal()
    added = 0
    skipped = 0

    try:
        for item in COR_PLENARY_SESSIONS:
            external_id = f"cor_plenary_{item['session']}"
            title = f"CoR {item['session']} Plenary Session"

            existing = session.query(EUCalendarEvent).filter_by(
                source="cor_plenary",
                external_id=external_id,
            ).first()

            if existing:
                if verbose:
                    print(f"  [SKIP] {item['start_date']} - {title}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] {item['start_date']} - {title}")
                added += 1
                continue

            event = EUCalendarEvent(
                id=uuid4(),
                institution=InstitutionEnum.COR,
                event_type=EventTypeEnum.PLENARY_SESSION,
                title=title,
                description=item.get("description"),
                start_date=item["start_date"],
                end_date=item.get("end_date"),
                all_day=True,
                policy_areas=["cohesion"],
                status=item.get("status", EventStatusEnum.TENTATIVE),
                source="cor_plenary",
                source_url="https://cor.europa.eu/en/plenaries-events/plenary-sessions",
                external_id=external_id,
                scraped_at=datetime.now(),
                first_seen=datetime.now(),
                last_updated=datetime.now(),
            )
            session.add(event)
            added += 1

            if verbose:
                print(f"  [ADD] {item['start_date']} - {title}")

        if not dry_run:
            session.commit()
            print(f"\n[OK] Committed {added} events to database")
        else:
            print(f"\n[DRY-RUN] Would insert {added} events")

        print(f"  Added: {added}")
        print(f"  Skipped: {skipped}")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Insert CoR plenary sessions into EU Calendar"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("[START] Inserting CoR plenary sessions")
    print(f"  Sessions: {len(COR_PLENARY_SESSIONS)} (2025-2026)")
    print()

    insert_sessions(dry_run=args.dry_run, verbose=args.verbose)

    print("\n[STOP] Done")


if __name__ == "__main__":
    main()
