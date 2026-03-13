"""
Insert EU Calendar events from 13 March 2026 morning routine.
21 EP committee meetings (16-24 March) + 1 Energy Council.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date, datetime
from uuid import uuid4
from sqlalchemy import text
from core.database import SessionLocal


EVENTS = [
    # C1: AFET
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "AFET Committee Meeting",
        "description": "Foreign Affairs Committee. Agenda: Bosnia and Herzegovina 2025 report (Kolar), Serbia report (Picula), Kosovo report (Terras), North Macedonia amendments (Waitz), Switzerland bilateral (Grudler).",
        "start_date": date(2026, 3, 16), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "AFET",
        "source": "ep_committee_agenda", "external_id": "AFET_OJ(2026)03-16_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/afet/home",
    },
    # C2: DEVE
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "DEVE Committee Meeting",
        "description": "Development Committee. Agenda: Cook Islands fisheries protocol opinion (Goerens).",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "DEVE",
        "source": "ep_committee_agenda", "external_id": "DEVE_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/deve/home",
    },
    # C3: DEVE + ENVI joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "DEVE + ENVI Joint Committee Meeting",
        "description": "Joint Development and Environment committees.",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "DEVE",
        "source": "ep_committee_agenda", "external_id": "CJ37_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/deve/home",
    },
    # C4: ENVI
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ENVI Committee Meeting",
        "description": "Environment Committee. Agenda: Water Framework Directive 2nd reading (Lopez), Market Stability Reserve amendments (Nerudova), Civil Protection + Health Emergency (Pajin/Veryga).",
        "start_date": date(2026, 3, 16), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "ENVI",
        "source": "ep_committee_agenda", "external_id": "ENVI_OJ(2026)03-16_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/envi/home",
    },
    # C5: ENVI + TRAN joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ENVI + TRAN Joint Committee Meeting",
        "description": "Joint Environment and Transport committees.",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "ENVI",
        "source": "ep_committee_agenda", "external_id": "CJ46_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/envi/home",
    },
    # C6: BUDG
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "BUDG Committee Meeting",
        "description": "Budgets Committee. Agenda: Parliament 2027 estimates (Hadjipantela, deadline 20 Mar), EGF Belgium/Liberty (Ecke, deadline 20 Mar), Civil Protection budgetary assessment (Stefanuta).",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "BUDG",
        "source": "ep_committee_agenda", "external_id": "BUDG_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/budg/home",
    },
    # C7: REGI
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "REGI Committee Meeting",
        "description": "Regional Development Committee.",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "REGI",
        "source": "ep_committee_agenda", "external_id": "REGI_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/regi/home",
    },
    # C8: EUDS
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "EUDS Special Committee Meeting (European Democracy Shield)",
        "description": "Special Committee on European Democracy Shield.",
        "start_date": date(2026, 3, 17), "end_date": date(2026, 3, 17),
        "all_day": True, "ep_committee_code": "EUDS",
        "source": "ep_committee_agenda", "external_id": "EUDS_OJ(2026)03-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/euds/home",
    },
    # C9: DROI
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "DROI Subcommittee Meeting (Human Rights)",
        "description": "Subcommittee on Human Rights.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "DROI",
        "source": "ep_committee_agenda", "external_id": "DROI_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/droi/home",
    },
    # C10: AFCO
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "AFCO Committee Meeting",
        "description": "Constitutional Affairs Committee. Agenda: IIA budgetary discipline, Electoral Act proxy voting (pregnancy), Common European Defence Union (institutional), Framework Agreement EP-Commission, Rules of Procedure Rule 135, Article 19 TEU.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "AFCO",
        "source": "ep_committee_agenda", "external_id": "AFCO_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/afco/home",
    },
    # C11: INTA
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "INTA Committee Meeting",
        "description": "International Trade Committee.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "INTA",
        "source": "ep_committee_agenda", "external_id": "INTA_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/inta/home",
    },
    # C12: ECON
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ECON Committee Meeting",
        "description": "Economic and Monetary Affairs Committee. Agenda: Tobacco excise recast (Kubin, deadline 13 Apr), SRB Regulation 2nd reading (Tinagli), BRRD 2nd reading (Niedermayer), Deposit Guarantee Schemes 2nd reading (Peter-Hansen), Switzerland bilateral opinion amendments (Ferber).",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "ECON",
        "source": "ep_committee_agenda", "external_id": "ECON_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/econ/home",
    },
    # C13: LIBE + CONT joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "LIBE + CONT Joint Committee Meeting",
        "description": "Joint Civil Liberties and Budgetary Control committees.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "LIBE",
        "source": "ep_committee_agenda", "external_id": "LIBE_OJ(2026)03-18_2",
        "source_url": "https://www.europarl.europa.eu/committees/en/libe/home",
    },
    # C14: LIBE + AFCO + EUDS joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "LIBE + AFCO + EUDS Joint Committee Meeting",
        "description": "Joint Civil Liberties, Constitutional Affairs and European Democracy Shield committees.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "LIBE",
        "source": "ep_committee_agenda", "external_id": "LIBE_OJ(2026)03-18_3",
        "source_url": "https://www.europarl.europa.eu/committees/en/libe/home",
    },
    # C15: IMCO + LIBE joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "IMCO + LIBE Joint Committee Meeting",
        "description": "Joint Internal Market and Civil Liberties committees.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "IMCO",
        "source": "ep_committee_agenda", "external_id": "CJ40_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/imco/home",
    },
    # C16: SANT
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "SANT Committee Meeting",
        "description": "Public Health Committee. Agenda: Mission report Cyprus (16-18 Feb 2026).",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "SANT",
        "source": "ep_committee_agenda", "external_id": "SANT_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/sant/home",
    },
    # C17: ITRE + SANT joint
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "ITRE + SANT Joint Committee Meeting",
        "description": "Joint Industry/Research/Energy and Public Health committees.",
        "start_date": date(2026, 3, 19), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "ITRE",
        "source": "ep_committee_agenda", "external_id": "CJ53_OJ(2026)03-19_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/itre/home",
    },
    # C18: TRAN
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "TRAN Committee Meeting",
        "description": "Transport and Tourism Committee.",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "TRAN",
        "source": "ep_committee_agenda", "external_id": "TRAN_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/tran/home",
    },
    # C19: AGRI
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "AGRI Committee Meeting",
        "description": "Agriculture and Rural Development Committee. Agenda: MFF 2028-2034 opinion (Bonaccini).",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 19),
        "all_day": True, "ep_committee_code": "AGRI",
        "source": "ep_committee_agenda", "external_id": "AGRI_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/agri/home",
    },
    # C20: CULT
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "CULT Committee Meeting",
        "description": "Culture and Education Committee. Agenda: Media literacy and digital learning report (Ros Sempere, deadline 30 Mar), Youth Guarantee opinion (Petrov, deadline 24 Mar).",
        "start_date": date(2026, 3, 18), "end_date": date(2026, 3, 18),
        "all_day": True, "ep_committee_code": "CULT",
        "source": "ep_committee_agenda", "external_id": "CULT_OJ(2026)03-18_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/cult/home",
    },
    # C21: IMCO (next week)
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "IMCO Committee Meeting",
        "description": "Internal Market and Consumer Protection Committee. Agenda: Single Market and Customs Programme 2028-2034 report (Dibrani, deadline 26 Mar).",
        "start_date": date(2026, 3, 23), "end_date": date(2026, 3, 24),
        "all_day": True, "ep_committee_code": "IMCO",
        "source": "ep_committee_agenda", "external_id": "IMCO_OJ(2026)03-23_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/imco/home",
    },
    # C22: Energy Council
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "Energy Council (TTE): European Grids Package debate",
        "description": "Transport, Telecommunications and Energy Council (Energy configuration). Political debate on the European Grids Package: cross-border grid integration, TEN-E revision, national operator cost sharing.",
        "start_date": date(2026, 3, 16), "end_date": date(2026, 3, 16),
        "all_day": True, "council_configuration": "TTE",
        "source": "manual_news_scrape", "external_id": "council_tte_energy_20260316",
        "source_url": "https://www.consilium.europa.eu/en/meetings/tte/2026/03/16/",
        "policy_areas": ["energy", "internal market"],
    },
]


def main():
    db = SessionLocal()
    try:
        inserted = 0
        skipped = 0
        for event in EVENTS:
            # Check if event already exists by external_id
            result = db.execute(
                text("SELECT id FROM eu_calendar_events WHERE external_id = :eid"),
                {"eid": event["external_id"]}
            ).fetchone()
            if result:
                print(f"  [SKIP] {event['title']} (already exists)")
                skipped += 1
                continue

            event_id = uuid4()
            now = datetime.utcnow()

            db.execute(
                text("""
                    INSERT INTO eu_calendar_events (
                        id, institution, event_type, title, description,
                        start_date, end_date, all_day,
                        ep_committee_code, council_configuration,
                        policy_areas, source, external_id, source_url,
                        status, scraped_at, first_seen, last_updated
                    ) VALUES (
                        :id, :institution, :event_type, :title, :description,
                        :start_date, :end_date, :all_day,
                        :ep_committee_code, :council_configuration,
                        :policy_areas, :source, :external_id, :source_url,
                        'confirmed', :now, :now, :now
                    )
                """),
                {
                    "id": str(event_id),
                    "institution": event["institution"],
                    "event_type": event["event_type"],
                    "title": event["title"],
                    "description": event.get("description", ""),
                    "start_date": event["start_date"],
                    "end_date": event.get("end_date", event["start_date"]),
                    "all_day": event.get("all_day", True),
                    "ep_committee_code": event.get("ep_committee_code"),
                    "council_configuration": event.get("council_configuration"),
                    "policy_areas": event.get("policy_areas"),
                    "source": event.get("source", "manual_news_scrape"),
                    "external_id": event["external_id"],
                    "source_url": event.get("source_url"),
                    "now": now,
                }
            )
            print(f"  [OK] {event['title']} ({event['start_date']})")
            inserted += 1

        db.commit()
        print(f"\n[DONE] Inserted: {inserted}, Skipped: {skipped}")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
