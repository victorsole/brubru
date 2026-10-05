"""Load the Cyber Solidarity Act's remaining dates into My EU Calendar, where
the law-drop radar (check D) reads it.

The dates are read from Regulation (EU) 2025/38 and cited by article. Same convention as `seed_elv_calendar_milestones.py`: institution
COMMISSION, event_type special_date, one row per date, idempotent on external_id.
Passed dates are not loaded.

These are the dates the EU Canon page /eucanon/2025-38_cybersolidarity/ shows as
"Upcoming". When one passes, the radar's check E flags the page so its markers
are flipped; when one MOVES (an amendment, a corrigendum), change it here
and on the page together.

Usage:
  python3.12 -m scripts.seed_cybersolidarity_calendar_milestones --dry-run
  python3.12 -m scripts.seed_cybersolidarity_calendar_milestones --apply
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

SOURCE = "canon_cybersolidarity_2025"
SOURCE_URL = "http://publications.europa.eu/resource/eli/reg/2025/38/oj"
CANON_URL = "https://brubru.beresol.eu/eucanon/2025-38_cybersolidarity/index.html"

# (date, title, description)
MILESTONES = [
    ("2027-02-05",
     "Cyber Solidarity Act: first Commission evaluation report due",
     "Article 25(1) of Regulation (EU) 2025/38: by today, and at least every 4 years "
     "thereafter, the Commission evaluates the functioning of the European Cybersecurity "
     "Alert System, the Cybersecurity Emergency Mechanism (including the EU Cybersecurity "
     "Reserve) and the incident review mechanism, and reports to the European Parliament and "
     "the Council, with a legislative proposal where appropriate."),
    ("2030-02-05",
     "Cyber Solidarity Act: first five-year delegation period ends",
     "Article 23(2) of Regulation (EU) 2025/38: the Commission's power to adopt delegated acts "
     "specifying the types and number of EU Cybersecurity Reserve response services runs for 5 "
     "years from 5 February 2025 and is tacitly extended unless the European Parliament or the "
     "Council objects no later than 3 months before the end of the period. The Commission's "
     "report on the delegation is due no later than 9 months before that end."),
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
            ext = f"cybersolidarity-2025R0038-{date}"
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
                        ARRAY['2023/0109(COD)'])"""),
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
