"""Insert two EU Calendar events found in the 13 Oct 2026 /news run, each read from its source.

1. Implementation Dialogue on the Political Advertising Regulation, 4 Nov 2026, Brussels
   (Commission news item of 12 Oct 2026; hosted by Commissioner Michael McGrath).
2. Accession conferences with Albania, Moldova and Ukraine, 13 Oct 2026, Luxembourg
   (Council media advisory of 12 Oct 2026; approximate times only).

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
        "institution": "COMMISSION", "event_type": "conference",
        "title": "Implementation Dialogue on the application of the Political Advertising Regulation",
        "description": ("Hosted by Commissioner Michael McGrath in Brussels: stakeholders exchange views, share initial "
                        "experiences with Regulation (EU) 2024/900 and explore measures to support its application. "
                        "Announced in the Commission news item on the pilot European Repository for online political ads."),
        "start_date": date(2026, 11, 4), "end_date": date(2026, 11, 4), "all_day": True,
        "policy_areas": ["democracy", "digital"], "venue": "Brussels", "organiser": "European Commission",
        "external_id": "political_ads_implementation_dialogue_2026_11_04",
        "source_url": "https://commission.europa.eu/news-and-media/news/commission-launches-repository-transparency-information-online-political-ads-2026-10-12_en",
    },
    {
        "institution": "COUNCIL", "event_type": "council_meeting",
        "title": "Accession conferences with Albania, Moldova and Ukraine",
        "description": ("Luxembourg, after the General Affairs Council. Approximate times from the Council media advisory: "
                        "Albania about 17:00, Ukraine about 18:30, Moldova about 20:00, each with a press conference. "
                        "Outcomes are published by the Council afterwards."),
        "start_date": date(2026, 10, 13), "end_date": date(2026, 10, 13), "all_day": True,
        "policy_areas": ["enlargement"], "venue": "ECCL, Luxembourg", "organiser": "Council of the EU",
        "external_id": "accession_conferences_2026_10_13",
        "source_url": "https://www.consilium.europa.eu/en/press/press-releases/2026/10/12/media-advisory-general-affairs-council-and-accession-conferences-with-albania-the-republic-of-moldova-and-ukraine-of-13-october-2026/",
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
