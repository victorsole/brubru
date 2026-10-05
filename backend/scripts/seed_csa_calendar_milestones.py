"""Load the Cybersecurity Act's remaining date into My EU Calendar, where
the law-drop radar (check D) reads it.

The date is read from Regulation (EU) 2019/881 and cited by article. Same convention as `seed_elv_calendar_milestones.py`: institution
COMMISSION, event_type special_date, one row per date, idempotent on external_id.
Passed dates are not loaded.

These are the dates the EU Canon page /eucanon/2019-881_csa/ shows as
"Upcoming". When one passes, the radar's check E flags the page so its markers
are flipped; when one MOVES (the Cybersecurity Act 2 repeals the Regulation, a corrigendum), change it here
and on the page together.

Usage:
  python3.12 -m scripts.seed_csa_calendar_milestones --dry-run
  python3.12 -m scripts.seed_csa_calendar_milestones --apply
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

SOURCE = "canon_csa_2019"
SOURCE_URL = "http://publications.europa.eu/resource/eli/reg/2019/881/oj"
CANON_URL = "https://brubru.beresol.eu/eucanon/2019-881_csa/index.html"

# (date, title, description)
MILESTONES = [
    ("2029-06-28",
     "Cybersecurity Act: next Commission evaluation and review report due",
     "Article 67 of Regulation (EU) 2019/881: by 28 June 2024, and every five years "
     "thereafter, the Commission evaluates the impact, effectiveness and efficiency of ENISA "
     "and of the certification framework (Title III) and reports to the European Parliament, "
     "the Council and ENISA's Management Board. The next report is due by today. The "
     "Commission's January 2026 proposal for a Cybersecurity Act 2 (2026/0011(COD)) would "
     "repeal the Regulation; this date holds only while Regulation (EU) 2019/881 stays in force."),
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
            ext = f"csa-2019R0881-{date}"
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
                        ARRAY['2017/0225(COD)'])"""),
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
