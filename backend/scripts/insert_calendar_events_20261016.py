"""Insert two EU Calendar events found in the 16 Oct 2026 /news run, each read from its source.

1. GM maize Bt11 x MIR162 x MON 89034 x NK603 (application GMFF-2025-33624): public consultation on the EFSA
   opinion (15 Oct 2026) closes 15 Nov 2026 (DG SANTE GMO public consultations page, read 16 Oct).
2. Horizon Europe Nature and Bridging calls (extra EUR 500 million to 2027): REA brokerage event 19 Oct 2026
   (REA news of 9 Oct 2026).

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
        "title": "GM maize Bt11 x MIR162 x MON 89034 x NK603: public consultation on the EFSA opinion closes",
        "description": ("Scientific comments on EFSA's opinion of 15 October 2026 on genetically modified maize "
                        "Bt11 x MIR162 x MON 89034 x NK603 and its sub-combinations, for food and feed uses under "
                        "Regulation (EC) No 1829/2003 (application GMFF-2025-33624). Comments go to EFSA, which checks "
                        "their impact on its opinion."),
        "start_date": date(2026, 11, 15), "end_date": date(2026, 11, 15), "all_day": True,
        "policy_areas": ["Food Safety", "Agriculture"], "venue": None, "organiser": "European Commission (DG SANTE)",
        "external_id": "gm_maize_gmff_2025_33624_consultation_closes_2026_11_15",
        "source_url": "https://food.ec.europa.eu/food-safety/genetically-modified-organisms/public-consultations_en",
    },
    {
        "institution": "COMMISSION", "event_type": "special_date",
        "title": "Horizon Europe Nature and Bridging calls: REA brokerage event",
        "description": ("Brokerage event for the new Horizon Europe Nature actions (EUR 41.45 million and EUR 108 million, "
                        "opened 13 October) and Bridging actions (EUR 32.5 million and EUR 20 million, opening 20 October), "
                        "funded by the extra EUR 500 million the Commission allocated to Horizon Europe on 29 September 2026."),
        "start_date": date(2026, 10, 19), "end_date": date(2026, 10, 19), "all_day": True,
        "policy_areas": ["Research and Innovation"], "venue": None, "organiser": "European Research Executive Agency (REA)",
        "external_id": "horizon_europe_nature_bridging_brokerage_2026_10_19",
        "source_url": "https://rea.ec.europa.eu/news/horizon-europes-horizontal-actions-2027-extra-funding-nature-innovation-and-competitiveness-2026-10-09_en",
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
