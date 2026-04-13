"""
Insert EU Calendar events from 13 April 2026 morning routine.
EP committee meetings 14-17 April, COREPER I, Council, Informal EUCO.

Source: EP weekly agenda Week 16 (13-19 April 2026), Council Forward Look.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import date
from uuid import uuid4
from sqlalchemy import text
from core.database import SessionLocal


EVENTS = [
    # ----- EP COMMITTEE MEETINGS (14-17 April 2026) -----

    # SEDE 14 April (full day)
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "SEDE Committee Meeting",
        "description": "Security and Defence Subcommittee. Full day session (09:00-18:30), ANTALL 4Q1.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 14),
        "all_day": True, "ep_committee_code": "SEDE",
        "source": "ep_committee_agenda", "external_id": "SEDE_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/sede/home",
    },
    # LIBE 14-15 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "LIBE Committee Meeting",
        "description": "Civil Liberties, Justice and Home Affairs. Votes: UN Convention against Cybercrime (2025/0231(NLE), consent, Rapporteur Moritz Korner). Commission Rule of Law Report 2025 (2025/2239(INI), draft report adoption, Rapporteur Konstantinos Arvanitis).",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 15),
        "all_day": True, "ep_committee_code": "LIBE",
        "policy_areas": ["justice", "rule_of_law", "cybercrime"],
        "procedure_refs": ["2025/0231(NLE)", "2025/2239(INI)"],
        "source": "ep_committee_agenda", "external_id": "LIBE_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/libe/home",
    },
    # REGI 14-15 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "REGI Committee Meeting",
        "description": "Regional Development Committee. Exchange of views on future of cross-border cooperation within post-2027 MFF with Joris Bengevoord (President AEBR, Chair Brabant Delta Water Board). Study presentation: Flexibility and Simplification in Cohesion Policy under 2028-2034 MFF (Policy Dept for Regional Development, Agriculture and Fisheries). NRP Fund and ERDF/Interreg/Cohesion Fund legislative proposals.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 15),
        "all_day": True, "ep_committee_code": "REGI",
        "policy_areas": ["cohesion", "regional_development", "mff"],
        "source": "ep_committee_agenda", "external_id": "REGI_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/regi/home",
    },
    # SANT (Public Health) 14 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "SANT Committee Meeting",
        "description": "Public Health Subcommittee. Europe's Beating Cancer Plan (2025/2139(INI), consideration of draft report, Rapporteur Vlad Vasile-Voiculescu). Medical devices simplification (2025/0404(COD), presentation by Commissioner Varhelyi, Rapporteur Oliver Schenk).",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 14),
        "all_day": True, "ep_committee_code": "SANT",
        "policy_areas": ["health", "cancer", "medical_devices"],
        "procedure_refs": ["2025/2139(INI)", "2025/0404(COD)"],
        "source": "ep_committee_agenda", "external_id": "SANT_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/sant/home",
    },
    # DEVE 14 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "DEVE Committee Meeting",
        "description": "Development Committee. Debate on humanitarian situation in Lebanon in context of Israel's ongoing assault, with WFP and Lebanon Humanitarian and Development Forum (online) + EU Commission representatives.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 14),
        "all_day": True, "ep_committee_code": "DEVE",
        "policy_areas": ["development", "humanitarian", "middle_east"],
        "source": "ep_committee_agenda", "external_id": "DEVE_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/deve/home",
    },
    # BUDG 14-16 April (press conference Tue, vote Wed)
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "BUDG Committee Meeting -- MFF 2028-2034 Position Adoption",
        "description": "Budgets Committee. MAJOR: Adoption of EP position on MFF 2028-2034 (Wednesday 16 April). This constitutes the EP negotiating mandate for long-term budget negotiations with Council. Press conference with co-rapporteurs on Tuesday 15 April at 10:30.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 16),
        "all_day": True, "ep_committee_code": "BUDG",
        "policy_areas": ["budget", "mff"],
        "source": "ep_committee_agenda", "external_id": "BUDG_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/budg/home",
    },
    # AFET + Iran delegation 16 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "AFET Committee + Iran Delegation -- Iran Opposition Debate",
        "description": "Foreign Affairs Committee joint with Iran Delegation. Discussion with advocates for a free Iran. Speakers: Shirin Ebadi (Sakharov and Nobel Peace Prize laureate, online), Mustafa Hijri (Democratic Party of Iranian Kurdistan), Saeed Bashirtash (7 Aban Front), Abdullah Mohtadi (Komala Party, online), Sanaz Behzadi (Open Society journalist).",
        "start_date": date(2026, 4, 16), "end_date": date(2026, 4, 16),
        "all_day": True, "ep_committee_code": "AFET",
        "policy_areas": ["foreign_affairs", "iran", "human_rights"],
        "source": "ep_committee_agenda", "external_id": "AFET_OJ(2026)04-16_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/afet/home",
    },
    # EMPL 14-15 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "EMPL Committee Meeting -- Occupational Health Vote",
        "description": "Employment and Social Affairs Committee. Vote on update of EU rules protecting workers from exposure to hazardous chemicals (lead, diisocyanates). Carcinogens and Mutagens Directive revision.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 15),
        "all_day": True, "ep_committee_code": "EMPL",
        "policy_areas": ["employment_social", "health_safety"],
        "source": "ep_committee_agenda", "external_id": "EMPL_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/empl/home",
    },
    # IMCO 17 April -- Temu hearing
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "IMCO Committee Meeting -- Temu Hearing",
        "description": "Internal Market and Consumer Protection Committee. Hearing with Temu representatives on adherence to EU rules on product safety, consumer protection, and digital platforms. Follows previous hearings with SHEIN and AliExpress.",
        "start_date": date(2026, 4, 17), "end_date": date(2026, 4, 17),
        "all_day": True, "ep_committee_code": "IMCO",
        "policy_areas": ["consumer_protection", "product_safety", "digital"],
        "source": "ep_committee_agenda", "external_id": "IMCO_OJ(2026)04-17_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/imco/home",
    },
    # HOUS 14-15 April
    {
        "institution": "EP", "event_type": "committee_meeting",
        "title": "HOUS Special Committee Meeting",
        "description": "Special Committee on the Housing Crisis in the EU. Full agenda session (10:00-17:15), SPINELLI 1G3.",
        "start_date": date(2026, 4, 14), "end_date": date(2026, 4, 15),
        "all_day": True, "ep_committee_code": "HOUS",
        "policy_areas": ["housing", "social"],
        "source": "ep_committee_agenda", "external_id": "HOUS_OJ(2026)04-14_1",
        "source_url": "https://www.europarl.europa.eu/committees/en/hous/home",
    },

    # ----- COUNCIL EVENTS -----

    # COREPER I 15 April
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "COREPER I -- Transport, Agriculture, Middle East",
        "description": "Permanent Representatives Committee (Part 1). Agenda: Transport Council 21 April preparation (air passenger rights conciliation), Agriculture and Fisheries Council 27 April preparation (wildfire prevention, sustainable forest management), Middle East crisis coordination in transport sector, energy impacts of geopolitical crisis.",
        "start_date": date(2026, 4, 15), "end_date": date(2026, 4, 15),
        "all_day": True,
        "policy_areas": ["transport", "agriculture", "foreign_affairs"],
        "source": "council_agenda", "external_id": "COREPER1_2026-04-15_CM2340",
        "source_url": "https://data.consilium.europa.eu/doc/document/CM-2340-2026-INIT/en/pdf",
    },
    # Antici Group Simplification 17 April
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "Antici Group -- Simplification",
        "description": "Meeting of the Antici Group (Simplification). Justus Lipsius building, 10:00.",
        "start_date": date(2026, 4, 17), "end_date": date(2026, 4, 17),
        "all_day": True,
        "policy_areas": ["institutional", "better_regulation"],
        "source": "council_agenda", "external_id": "ANTICI_SIMPLIFICATION_2026-04-17_CM2332",
        "source_url": "https://data.consilium.europa.eu/doc/document/CM-2332-2026-INIT/en/pdf",
    },
    # Working Party on Shipping 17 April
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "Working Party on Shipping",
        "description": "Working Party on Shipping. Justus Lipsius building, 10:00.",
        "start_date": date(2026, 4, 17), "end_date": date(2026, 4, 17),
        "all_day": True,
        "policy_areas": ["transport"],
        "source": "council_agenda", "external_id": "WP_SHIPPING_2026-04-17_364866",
    },
    # FAC 21 April
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "Foreign Affairs Council (FAC)",
        "description": "Foreign Affairs Council meeting, 21 April 2026.",
        "start_date": date(2026, 4, 21), "end_date": date(2026, 4, 21),
        "all_day": True,
        "policy_areas": ["foreign_affairs"],
        "source": "council_agenda", "external_id": "FAC_2026-04-21",
        "source_url": "https://www.consilium.europa.eu/en/meetings/fac/2026/04/21/",
    },
    # Transport Council 21 April (informal videoconference)
    {
        "institution": "COUNCIL", "event_type": "informal_meeting",
        "title": "Transport Council -- Informal Videoconference",
        "description": "Informal videoconference of Ministers of Transport, 21 April 2026. Agenda: air passenger rights conciliation, Middle East crisis transport sector impact.",
        "start_date": date(2026, 4, 21), "end_date": date(2026, 4, 21),
        "all_day": True,
        "policy_areas": ["transport"],
        "source": "council_agenda", "external_id": "TTE_TRANSPORT_2026-04-21",
        "source_url": "https://www.consilium.europa.eu/en/meetings/tte/2026/04/21/",
    },

    # ----- EUROPEAN COUNCIL -----

    # Informal EUCO 23-24 April
    {
        "institution": "EUROPEAN_COUNCIL", "event_type": "informal_meeting",
        "title": "Informal Meeting of Heads of State or Government",
        "description": "Informal European Council meeting, 23-24 April 2026.",
        "start_date": date(2026, 4, 23), "end_date": date(2026, 4, 24),
        "all_day": True,
        "policy_areas": ["foreign_affairs", "defence", "economy"],
        "source": "council_agenda", "external_id": "EUCO_INFORMAL_2026-04-23",
        "source_url": "https://www.consilium.europa.eu/en/meetings/european-council/2026/04/23-24/",
    },
]


def insert_events(dry_run=False):
    session = SessionLocal()
    added = 0
    skipped = 0

    try:
        for item in EVENTS:
            existing = session.execute(
                text("SELECT id FROM eu_calendar_events WHERE source = :s AND external_id = :e"),
                {"s": item["source"], "e": item["external_id"]},
            ).first()

            if existing:
                print(f"  [SKIP] {item['start_date']} {item['title'][:60]}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY]  {item['start_date']} {item['title'][:60]}")
                added += 1
                continue

            session.execute(
                text("""
                    INSERT INTO eu_calendar_events
                    (id, institution, event_type, title, description, start_date, end_date,
                     all_day, ep_committee_code, policy_areas, procedure_refs, status,
                     source, external_id, source_url, scraped_at, first_seen, last_updated)
                    VALUES
                    (:id, :institution, :event_type, :title, :description, :start_date, :end_date,
                     :all_day, :ep_committee_code, :policy_areas, :procedure_refs, 'scheduled',
                     :source, :external_id, :source_url, NOW(), NOW(), NOW())
                """),
                {
                    "id": str(uuid4()),
                    "institution": item["institution"],
                    "event_type": item["event_type"],
                    "title": item["title"],
                    "description": item.get("description"),
                    "start_date": item["start_date"],
                    "end_date": item.get("end_date"),
                    "all_day": item.get("all_day", True),
                    "ep_committee_code": item.get("ep_committee_code"),
                    "policy_areas": item.get("policy_areas", []),
                    "procedure_refs": item.get("procedure_refs", []),
                    "source": item["source"],
                    "external_id": item["external_id"],
                    "source_url": item.get("source_url"),
                },
            )
            added += 1
            print(f"  [ADD]  {item['start_date']} {item['title'][:60]}")

        if not dry_run:
            session.commit()
            print(f"\n[OK] Committed {added} events")
        else:
            print(f"\n[DRY-RUN] Would insert {added} events")

        print(f"  Added: {added}, Skipped: {skipped}")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Insert week 16 calendar events (13-19 April 2026)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[START] Week 16 calendar events (13-19 April 2026)")
    print(f"  EP committee meetings: 10")
    print(f"  Council events: 5")
    print(f"  EUCO: 1")
    print(f"  Total: {len(EVENTS)}")
    print()

    insert_events(dry_run=args.dry_run)
    print("\n[STOP] Done")
