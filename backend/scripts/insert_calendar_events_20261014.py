"""Insert three EU Calendar events found in the 14 Oct 2026 /news run, each read from its source.

1. EHDS Stakeholder Forum: application deadline 10 Dec 2026 (Commission call page, read 14 Oct 2026).
2. UNECE WP.29 200th session, 17-20 Nov 2026 (COM(2026) 548 final, section 2.3: "WP.29 plans to vote on these
   proposals at its meeting of 17 to 20 November 2026").
3. Implementing Regulation (EU) 2026/2266 on mobile driving licences enters into force on 3 Nov 2026
   (published in the OJ on 14 Oct 2026; Article 10: the twentieth day following publication).

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
        "institution": "COMMISSION", "event_type": "special_date",
        "title": "EHDS Stakeholder Forum: deadline to apply for membership",
        "description": ("The Commission invites organisations and public entities other than Member State authorities to apply "
                        "to become members of the European Health Data Space Stakeholder Forum (about 80 members). "
                        "Applications: cover letter, classification form and selection criteria form."),
        "start_date": date(2026, 12, 10), "end_date": date(2026, 12, 10), "all_day": True,
        "policy_areas": ["health", "digital_ai"], "venue": None, "organiser": "European Commission (DG SANTE)",
        "external_id": "ehds_stakeholder_forum_application_deadline_2026_12_10",
        "source_url": "https://health.ec.europa.eu/ehealth-digital-health-and-care/ehds-action/ehds-stakeholder-forum_en",
    },
    {
        "institution": "THIRD_PARTY", "event_type": "conference",
        "title": "UNECE WP.29, 200th session (EU position proposed in COM(2026) 548)",
        "description": ("World Forum for Harmonization of Vehicle Regulations of the UN Economic Commission for Europe. "
                        "WP.29 plans to vote on amendments to UN Regulations, UN GTRs and UN resolutions; the Commission "
                        "proposed the EU position on 13 October 2026 (Council Decision under Article 218(9) TFEU)."),
        "start_date": date(2026, 11, 17), "end_date": date(2026, 11, 20), "all_day": True,
        "policy_areas": ["Transport", "Automotive"], "venue": None, "organiser": "UNECE",
        "external_id": "unece_wp29_200th_session_2026_11_17",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:2026:548:FIN",
    },
    {
        "institution": "COMMISSION", "event_type": "special_date",
        "title": "Mobile driving licences: Implementing Regulation (EU) 2026/2266 enters into force",
        "description": ("Commission Implementing Regulation (EU) 2026/2266 of 13 October 2026 on mobile driving licences "
                        "(Directive (EU) 2025/2205), published in the OJ on 14 October 2026, enters into force on the "
                        "twentieth day following publication."),
        "start_date": date(2026, 11, 3), "end_date": date(2026, 11, 3), "all_day": True,
        "policy_areas": ["Transport", "Digital Policy"], "venue": None, "organiser": "European Commission",
        "external_id": "mobile_driving_licence_regulation_2026_2266_in_force_2026_11_03",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202602266",
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
