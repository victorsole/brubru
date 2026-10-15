"""Insert five EU Calendar events found in the 15 Oct 2026 /news run, each read from its source.

1-2. Return Regulation (EU) 2026/2280 (OJ L 15 Oct 2026), Article 50: in force 16 Oct 2026 (first set of articles,
     incl. Article 14, apply the same day); remaining provisions apply from 17 Oct 2027 (Article 50(3)).
3. CAM gas network code revision (Regulation (EU) 2017/459): call for feedback closes 10 Nov 2026 (DG ENER, 14 Oct).
4. Water Resilience Investment Accelerator: Green Assist applications "by the end of October" 2026 (DG ENV, 14 Oct).
5. EESC plenary session 21-22 Oct 2026 (EESC announcement on its official account, 14 Oct).

Dry-run by default; --apply writes. Idempotent on (source, external_id).
"""
import argparse
import os
import sys
from datetime import date
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402

SOURCE = "manual_news_review"
EVENTS = [
    {
        "institution": "COUNCIL", "event_type": "special_date",
        "title": "Return Regulation (EU) 2026/2280 enters into force (Article 14 and a first set of articles apply)",
        "description": ("Regulation (EU) 2026/2280 establishing a common system for the return of third-country nationals staying "
                        "illegally in the Union, published in the OJ on 15 October 2026, enters into force the day after publication. "
                        "Articles 1, 2(1)-(3), 3(3), 4, 5(13) and (15), 14, 15, 16, 34, 35, 41, 43 and 47-49 apply from this date; "
                        "the remaining provisions apply from 17 October 2027."),
        "start_date": date(2026, 10, 16), "end_date": date(2026, 10, 16), "all_day": True,
        "policy_areas": ["Migration", "Justice and Home Affairs"], "venue": None, "organiser": "European Parliament and Council",
        "external_id": "return_regulation_2026_2280_in_force_2026_10_16",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202602280",
    },
    {
        "institution": "COUNCIL", "event_type": "special_date",
        "title": "Return Regulation (EU) 2026/2280: remaining provisions apply; Return Directive 2008/115/EC repealed",
        "description": ("Article 50(3): all provisions not listed in Article 50(2) apply from 17 October 2027. Article 49: Directive "
                        "2008/115/EC, Directive 2001/40/EC and Decision 2004/191/EC are repealed for the Member States bound by "
                        "the Regulation with effect from this date."),
        "start_date": date(2027, 10, 17), "end_date": date(2027, 10, 17), "all_day": True,
        "policy_areas": ["Migration", "Justice and Home Affairs"], "venue": None, "organiser": "European Parliament and Council",
        "external_id": "return_regulation_2026_2280_full_application_2027_10_17",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202602280",
    },
    {
        "institution": "COMMISSION", "event_type": "special_date",
        "title": "CAM gas network code revision: call for feedback closes",
        "description": ("Draft implementing regulation revising Regulation (EU) 2017/459 on capacity allocation mechanisms in gas "
                        "transmission systems (CAM network code); 4-week call for feedback opened 14 October 2026. A comitology "
                        "vote follows; formal adoption expected in 2027."),
        "start_date": date(2026, 11, 10), "end_date": date(2026, 11, 10), "all_day": True,
        "policy_areas": ["Energy"], "venue": None, "organiser": "European Commission (DG ENER)",
        "external_id": "cam_network_code_feedback_deadline_2026_11_10",
        "source_url": "https://energy.ec.europa.eu/news/cross-border-gas-network-code-commission-launches-call-feedback-revision-rules-2026-10-14_en",
    },
    {
        "institution": "COMMISSION", "event_type": "special_date",
        "title": "Water Resilience Investment Accelerator: Green Assist applications close (end of October)",
        "description": ("Projects on water efficiency, nature-based solutions or clean water seeking free advisory support under the "
                        "EU Water Resilience Investment Accelerator (Green Assist, InvestEU, LIFE-funded; 20 pilot projects) apply "
                        "to the CINEA Green Assist mailbox by the end of October 2026."),
        "start_date": date(2026, 10, 31), "end_date": date(2026, 10, 31), "all_day": True,
        "policy_areas": ["Environment"], "venue": None, "organiser": "European Commission (DG ENV, CINEA)",
        "external_id": "water_resilience_accelerator_green_assist_deadline_2026_10_31",
        "source_url": "https://environment.ec.europa.eu/news/commission-presents-water-resilience-investment-accelerator-2026-10-14_en",
    },
    {
        "institution": "EESC", "event_type": "plenary_session",
        "title": "EESC plenary session (Single Market, AI and digital sovereignty opinions)",
        "description": ("European Economic and Social Committee plenary session; announced agenda includes opinions on the Single "
                        "Market and on AI and digital sovereignty. The flagship conference 'Eradicating Poverty by 2050' runs alongside."),
        "start_date": date(2026, 10, 21), "end_date": date(2026, 10, 22), "all_day": True,
        "policy_areas": ["Single Market", "Digital Policy"], "venue": "Brussels", "organiser": "EESC",
        "external_id": "eesc_plenary_2026_10_21",
        "source_url": "https://bsky.app/profile/eesc.bsky.social/post/3mxtaa7d4e22r",
    },
]


def main(apply: bool) -> int:
    db = SessionLocal()
    added = skipped = 0
    try:
        for e in EVENTS:
            exists = db.execute(text("SELECT 1 FROM eu_calendar_events WHERE source=:s AND external_id=:x"),
                                {"s": SOURCE, "x": e["external_id"]}).first()
            if exists:
                skipped += 1
                print(f"  [SKIP] {e['start_date']} {e['title'][:60]}")
                continue
            if apply:
                db.execute(text("""
                    INSERT INTO eu_calendar_events
                      (id, institution, event_type, title, description, start_date, end_date, all_day,
                       policy_areas, source, external_id, source_url, venue, organiser)
                    VALUES (:id, :institution, :event_type, :title, :description, :start_date, :end_date, :all_day,
                            :policy_areas, :source, :external_id, :source_url, :venue, :organiser)"""),
                    {**{k: e[k] for k in ("institution", "event_type", "title", "description", "start_date",
                                          "end_date", "all_day", "policy_areas", "external_id", "source_url",
                                          "venue", "organiser")},
                     "id": str(uuid4()), "source": SOURCE})
            added += 1
            print(f"  [{'ADD' if apply else 'WOULD ADD'}] {e['start_date']} {e['title'][:60]}")
        if apply:
            db.commit()
        print(f"added {added}, skipped {skipped}, apply={apply}")
        return 0
    except Exception as ex:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {ex}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
