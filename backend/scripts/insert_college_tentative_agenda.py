"""
Insert Commission College tentative agenda items into EU Calendar.

Source: SEC(2026)2556 (25 February 2026)
"Liste des points prevus pour figurer a l'ordre du jour des prochaines
reunions de la Commission" -- 4 March to 27 May 2026.

Usage:
    python3.12 scripts/insert_college_tentative_agenda.py [--dry-run] [--verbose]

Created: March 2026
"""

import argparse
import asyncio
import logging
import sys
import os
from datetime import date, datetime
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.eu_calendar import EUCalendarEvent, InstitutionEnum, EventTypeEnum, EventStatusEnum


# ============================================================================
# SEC(2026)2556 -- Tentative agenda items, 4 Mar - 27 May 2026
# ============================================================================

TENTATIVE_ITEMS = [
    # 4 March 2026
    {
        "start_date": date(2026, 3, 4),
        "title": "College of Commissioners: Industrial Accelerator Act",
        "description": "Industrial Accelerator Act (COM(2026)100). Responsible: EVP Sejourne.",
        "policy_areas": ["industry", "internal_market"],
        "related_documents": {"com_ref": "COM(2026)100", "sec_ref": "SEC(2026)2556"},
    },
    {
        "start_date": date(2026, 3, 4),
        "title": "College of Commissioners: EU Industrial Maritime Strategy",
        "description": "EU industrial maritime strategy. Responsible: EVP Sejourne / Fitto.",
        "policy_areas": ["industry", "transport"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    {
        "start_date": date(2026, 3, 4),
        "title": "College of Commissioners: EU Ports Strategy",
        "description": "EU ports strategy. Responsible: Fitto.",
        "policy_areas": ["transport"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    {
        "start_date": date(2026, 3, 4),
        "title": "College of Commissioners: Gender Equality Strategy 2026-2030",
        "description": "Gender equality strategy 2026-2030. Responsible: Minzatu.",
        "policy_areas": ["employment_social"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    {
        "start_date": date(2026, 3, 4),
        "title": "College of Commissioners: Intergenerational Fairness Strategy",
        "description": "Intergenerational fairness strategy. Responsible: Minzatu.",
        "policy_areas": ["employment_social"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 6 March 2026
    {
        "start_date": date(2026, 3, 6),
        "title": "College of Commissioners: Orientation Debate on Energy Prices",
        "description": "Orientation debate on energy prices. Responsible: President. Visit of Fatih Birol (IEA Executive Director).",
        "policy_areas": ["energy"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 10 March 2026 (Strasbourg)
    {
        "start_date": date(2026, 3, 10),
        "title": "College of Commissioners: Energy Package (SMRs, Clean Energy Investment, Citizens Energy)",
        "description": "Energy package: (1) Small modular reactors (Ribera/Sejourne), (2) Clean energy investment strategy (Ribera), (3) Citizens energy package (Ribera). Strasbourg meeting during EP Plenary 9-12 March.",
        "policy_areas": ["energy", "environment"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 18 March 2026
    {
        "start_date": date(2026, 3, 18),
        "title": "College of Commissioners: Merger Guidelines Review + 28th Regime + European Innovation Act",
        "description": "Orientation debate on merger guidelines review (President). 28th Regime (Virkkunen). European Innovation Act (Sejourne). European Council 19-20 March.",
        "policy_areas": ["competition", "internal_market", "research"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 25 March 2026
    {
        "start_date": date(2026, 3, 25),
        "title": "College of Commissioners: Defence (Military Edge + AGILE) + Wildfire Risk Management",
        "description": "Qualitative Military Edge programme (Virkkunen). AGILE - Instrument for Agile and Rapid Defence Innovation (Virkkunen). Integrated Wildfire Risk Management communication (Minzatu).",
        "policy_areas": ["defence", "civil_protection"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 13 April 2026
    {
        "start_date": date(2026, 4, 13),
        "title": "College of Commissioners: Orientation Debate on EU-China Relations",
        "description": "Orientation debate on EU-China relations. Responsible: President. Security College.",
        "policy_areas": ["foreign_affairs", "trade"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 15 April 2026
    {
        "start_date": date(2026, 4, 15),
        "title": "College of Commissioners: RepowerEU -- Phase Out Russian Oil Imports",
        "description": "RepowerEU proposal to phase out remaining Russian oil imports. Responsible: Ribera.",
        "policy_areas": ["energy", "foreign_affairs"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 23-24 April 2026 (Informal Leaders' meeting in Cyprus)
    {
        "start_date": date(2026, 4, 23),
        "end_date": date(2026, 4, 24),
        "title": "College of Commissioners: Tech Sovereignty Package (Cloud/AI Act, Chips Act 2, Open Source)",
        "description": "Tech Sovereignty Package: (1) Strategic Roadmap for Digitalisation & AI in Energy (Ribera), (2) Cloud and AI Development Act (Virkkunen), (3) Chips Act 2 (Virkkunen), (4) Open Source strategy (Virkkunen). Coincides with Informal Leaders' meeting in Cyprus.",
        "policy_areas": ["digital", "industry", "energy"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 28 April 2026 (Strasbourg)
    {
        "start_date": date(2026, 4, 28),
        "title": "College of Commissioners: Better Regulation and Enforcement",
        "description": "Communication on better regulation and enforcement. Responsible: President / Dombrovskis. Strasbourg meeting during EP Plenary 27-30 April.",
        "policy_areas": ["institutional"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 6 May 2026
    {
        "start_date": date(2026, 5, 6),
        "title": "College of Commissioners: Social Package (Anti-Poverty, Child Guarantee, Housing, Disability)",
        "description": "Social package: (1) Anti-poverty strategy, (2) Strengthening Child Guarantee, (3) Council Recommendation on fighting housing exclusion, (4) Enhancing disability rights strategy to 2030. Responsible: Minzatu. Also: Strategy on sustainable tourism (Fitto). 9 May Europe Day.",
        "policy_areas": ["employment_social", "tourism"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 13 May 2026
    {
        "start_date": date(2026, 5, 13),
        "title": "College of Commissioners: Mobility Package (Digital Mobility, Ticketing, Rail Rights)",
        "description": "Mobility package: (1) Multimodal Digital Mobility Services, (2) Single Digital Booking and Ticketing, (3) Revision of rail passengers' rights Regulation. Responsible: Fitto.",
        "policy_areas": ["transport", "digital"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 19 May 2026 (Strasbourg)
    {
        "start_date": date(2026, 5, 19),
        "title": "College of Commissioners: Energy Package (Security, Electrification, Heating & Cooling)",
        "description": "Energy package: (1) Strengthening energy security, (2) Electrification action plan, (3) Heating and cooling strategy. Responsible: Ribera. Strasbourg meeting during EP Plenary 18-21 May.",
        "policy_areas": ["energy"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
    # 27 May 2026
    {
        "start_date": date(2026, 5, 27),
        "title": "College of Commissioners: Global Health + Humanitarian Aid + Outermost Regions",
        "description": "Global health resilience initiative (Kallas). Communication on humanitarian aid (Kallas). Strategy for outermost regions (Fitto).",
        "policy_areas": ["health", "development", "regional"],
        "related_documents": {"sec_ref": "SEC(2026)2556"},
    },
]


def insert_items(dry_run: bool = False, verbose: bool = False):
    """Insert tentative agenda items into eu_calendar_events."""
    session = SessionLocal()
    added = 0
    skipped = 0

    try:
        for item in TENTATIVE_ITEMS:
            external_id = f"sec2026_2556_{item['start_date'].isoformat()}_{hash(item['title']) % 100000}"

            # Check if already exists
            existing = session.query(EUCalendarEvent).filter_by(
                source="ec_tentative_agenda",
                external_id=external_id,
            ).first()

            if existing:
                if verbose:
                    print(f"  [SKIP] {item['start_date']} - {item['title'][:60]}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] {item['start_date']} - {item['title'][:80]}")
                added += 1
                continue

            event = EUCalendarEvent(
                id=uuid4(),
                institution=InstitutionEnum.COMMISSION,
                event_type=EventTypeEnum.COMMISSION_COLLEGE_MEETING,
                title=item["title"],
                description=item.get("description"),
                start_date=item["start_date"],
                end_date=item.get("end_date"),
                all_day=True,
                policy_areas=item.get("policy_areas", []),
                status=EventStatusEnum.TENTATIVE,
                source="ec_tentative_agenda",
                source_url="https://ec.europa.eu/transparency/documents-register/detail?ref=SEC(2026)2556&lang=en",
                external_id=external_id,
                related_documents=item.get("related_documents", {}),
                scraped_at=datetime.now(),
                first_seen=datetime.now(),
                last_updated=datetime.now(),
            )
            session.add(event)
            added += 1

            if verbose:
                print(f"  [ADD] {item['start_date']} - {item['title'][:60]}")

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
        description="Insert Commission College tentative agenda items (SEC(2026)2556)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("[START] Inserting College tentative agenda items")
    print(f"  Source: SEC(2026)2556 (25 February 2026)")
    print(f"  Period: 4 March - 27 May 2026")
    print(f"  Items:  {len(TENTATIVE_ITEMS)}")
    print()

    insert_items(dry_run=args.dry_run, verbose=args.verbose)

    print("\n[STOP] Done")


if __name__ == "__main__":
    main()
