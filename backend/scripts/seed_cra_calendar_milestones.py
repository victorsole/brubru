"""Load the Cyber Resilience Act's remaining dates into My EU Calendar, where
the law-drop radar (check D) reads it.

Every date is read from Regulation (EU) 2024/2847 and cited by article. Same convention as `seed_elv_calendar_milestones.py`: institution
COMMISSION, event_type special_date, one row per date, idempotent on external_id.
Passed dates are not loaded; the 11 Sep 2026 row (Article 14 applies) already exists from the Commission factsheet loader.

These are the dates the EU Canon page /eucanon/2024-2847_cra/ shows as
"Upcoming". When one passes, the radar's check E flags the page so its markers
are flipped; when one MOVES (a further omnibus, a corrigendum), change it here
and on the page together.

Usage:
  python3.12 -m scripts.seed_cra_calendar_milestones --dry-run
  python3.12 -m scripts.seed_cra_calendar_milestones --apply
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

SOURCE = "canon_cra_2024"
SOURCE_URL = "http://publications.europa.eu/resource/eli/reg/2024/2847/oj"
CANON_URL = "https://brubru.beresol.eu/eucanon/2024-2847_cra/index.html"

# (date, title, description)
MILESTONES = [
    ("2026-12-11",
     "Cyber Resilience Act: Member States should have enough notified bodies",
     "Article 35(2) of Regulation (EU) 2024/2847: Member States shall strive to ensure, by "
     "today, that there is a sufficient number of notified bodies in the Union to carry out "
     "conformity assessments, to avoid bottlenecks and hindrances to market entry. A "
     "best-efforts target for Member States, not an obligation on manufacturers."),
    ("2027-12-11",
     "Cyber Resilience Act applies",
     "Regulation (EU) 2024/2847 applies from today (Article 71(2)): the Annex I essential "
     "cybersecurity requirements, conformity assessment, CE marking, the support period and "
     "technical documentation. Products placed on the market before today are caught only "
     "after a substantial modification (Article 69(2)), except for the Article 14 reporting "
     "duties, which already apply to all of them. Consumer representative actions under "
     "Directive (EU) 2020/1828 also become available."),
    ("2028-06-11",
     "Cyber Resilience Act: transitional certificates and approvals stop being valid",
     "Article 69(1) of Regulation (EU) 2024/2847: EU type-examination certificates and "
     "approval decisions issued for cybersecurity requirements under other Union "
     "harmonisation legislation remain valid until today, unless they expire earlier or that "
     "other legislation says otherwise."),
    ("2028-09-11",
     "Cyber Resilience Act: Commission report on the single reporting platform due",
     "Article 70(2) of Regulation (EU) 2024/2847: by today the Commission, after consulting "
     "ENISA and the CSIRTs network, reports to the European Parliament and the Council on the "
     "effectiveness of the single reporting platform and on the effect of delaying the "
     "dissemination of notifications on cybersecurity-related grounds."),
    ("2030-12-11",
     "Cyber Resilience Act: first evaluation and review report due",
     "Article 70(1) of Regulation (EU) 2024/2847: by today, and every four years thereafter, "
     "the Commission submits a public report on the evaluation and review of the Regulation "
     "to the European Parliament and the Council."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    added = skipped = 0
    try:
        for date, title, description in MILESTONES:
            ext = f"cra-2024R2847-{date}"
            if db.execute(text("SELECT 1 FROM eu_calendar_events WHERE external_id=:e"),
                          {"e": ext}).scalar():
                print(f"  = {date}  already present")
                skipped += 1
                continue
            print(f"  + {date}  {title}")
            db.execute(text("""
                INSERT INTO eu_calendar_events
                    (institution, event_type, title, description, start_date,
                     all_day, status, source, source_url, external_id,
                     policy_areas, procedure_refs)
                VALUES ('COMMISSION', 'special_date', :t, :d, CAST(:s AS date),
                        true, 'scheduled', :src, :url, :e,
                        ARRAY['Digital Policy','Cybersecurity'],
                        ARRAY['2022/0272(COD)'])"""),
                {"t": title, "d": description + " Plain-language explainer: " + CANON_URL,
                 "s": date, "src": SOURCE, "url": SOURCE_URL, "e": ext})
            added += 1

        print(f"\n=== PLAN === add {added}, already present {skipped}")
        if not apply:
            db.rollback()
            print("(dry run: nothing written; pass --apply)")
            return
        db.commit()
        print("[OK] committed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
