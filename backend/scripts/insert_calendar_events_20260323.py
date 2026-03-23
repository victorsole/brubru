"""
Insert EU Calendar events from 23 March 2026 morning routine.
EP committee meetings 23-25 March + remove incorrect plenary entries.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date
from uuid import uuid4
from sqlalchemy import text
from core.database import SessionLocal


EVENTS = [
    # PETI 23-24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "PETI Committee Meeting",
        "description": "Petitions Committee. Agenda: Public access to documents (Regulation 1049/2001 amendment), EU law application monitoring 2023-2025, Disability rights strategy post-2024, 2026 Budget, MFF 2028-2034, Budget Guidelines 2027, Petitions deliberations 2024, Ombudsman annual report 2024, EPSO competitions.",
        "start_date": date(2026, 3, 23), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "PETI",
        "source": "ep_committee_agenda", "external_id": "PETI_OJ(2026)03-23_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/peti/home",
    },
    # JURI 23-24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "JURI Committee Meeting",
        "description": "Legal Affairs Committee.",
        "start_date": date(2026, 3, 23), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "JURI",
        "source": "ep_committee_agenda", "external_id": "JURI_OJ(2026)03-23_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/juri/home",
    },
    # ECON 24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ECON Committee Meeting",
        "description": "Economic and Monetary Affairs Committee. Agenda: Banking Union 2nd reading -- SRM Regulation (Tinagli, A10-0067/2026), BRRD (Niedermayer, A10-0066/2026), DGSD deposit guarantee (Peter-Hansen, A10-0065/2026).",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "ECON",
        "source": "ep_committee_agenda", "external_id": "ECON_OJ(2026)03-24_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/econ/home",
    },
    # ENVI 24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ENVI Committee Meeting",
        "description": "Environment Committee. Agenda: Biocidal products data protection (Maran), joint ENVI/SANT session.",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "ENVI",
        "source": "ep_committee_agenda", "external_id": "ENVI_OJ(2026)03-24_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/envi/home",
    },
    # HOUS 24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "HOUS Special Committee Meeting",
        "description": "Special Committee on the Housing Crisis.",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "HOUS",
        "source": "ep_committee_agenda", "external_id": "HOUS_OJ(2026)03-24_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/hous/home",
    },
    # CONT 24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "CONT Committee Meeting",
        "description": "Budgetary Control Committee. Agenda: MFF 2028-2034 opinion (Protas).",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "CONT",
        "source": "ep_committee_agenda", "external_id": "CONT_OJ(2026)03-24_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/cont/home",
    },
    # EMPL/FEMM joint 24 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "EMPL + FEMM Joint Committee Meeting",
        "description": "Joint Employment and Women's Rights committees.",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "EMPL",
        "source": "ep_committee_agenda", "external_id": "CJ21_OJ(2026)03-24_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/empl/home",
    },
    # FEMM 24 March (separate session)
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "FEMM Committee Meeting",
        "description": "Women's Rights and Gender Equality Committee. Joint FEMM/SANT session.",
        "start_date": date(2026, 3, 24), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "FEMM",
        "source": "ep_committee_agenda", "external_id": "FEMM_OJ(2026)03-24_2",
        "source_url": "https://www.europarl.europa.eu/committees/en/femm/home",
    },
    # REGI 25 March
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "REGI Committee Meeting",
        "description": "Regional Development Committee. EVP Fitto visiting Austria on cohesion policy.",
        "start_date": date(2026, 3, 25), "end_date": date(2026, 3, 25),
        "all_day": True, "ep_committee_code": "REGI",
        "source": "ep_committee_agenda", "external_id": "REGI_OJ(2026)03-25_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/regi/home",
    },
]


def main():
    db = SessionLocal()
    try:
        # Remove incorrect plenary entries for this week (no plenary 23-26 March)
        result = db.execute(text("""
            DELETE FROM eu_calendar_events
            WHERE event_type = 'plenary_session'
            AND start_date >= '2026-03-23' AND start_date <= '2026-03-26'
        """))
        deleted = result.rowcount
        print(f"[OK] Removed {deleted} incorrect plenary entries for 23-26 March")

        added = 0
        skipped = 0
        for event in EVENTS:
            # Check for duplicates
            existing = db.execute(text(
                "SELECT id FROM eu_calendar_events WHERE external_id = :eid LIMIT 1"
            ), {"eid": event["external_id"]}).fetchone()

            if existing:
                skipped += 1
                print(f"[SKIP] {event['title']} ({event['start_date']})")
                continue

            db.execute(text("""
                INSERT INTO eu_calendar_events (
                    id, institution, event_type, title, description,
                    start_date, end_date, all_day, ep_committee_code,
                    source, external_id, source_url, scraped_at, first_seen, last_updated
                ) VALUES (
                    :id, :institution, :event_type, :title, :description,
                    :start_date, :end_date, :all_day, :ep_committee_code,
                    :source, :external_id, :source_url, NOW(), NOW(), NOW()
                )
            """), {
                "id": str(uuid4()),
                **event,
            })
            added += 1
            print(f"[OK] {event['title']} ({event['start_date']})")

        db.commit()
        print(f"\nSummary: {added} added, {skipped} skipped, {deleted} plenary entries removed")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
