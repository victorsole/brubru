"""Load the End-of-Life Vehicles Regulation's application ladder into My EU Calendar.

Every date below is read from Regulation (EU) 2026/1738 itself, mostly from
Article 59 and from the "from <date>" clause carried by the individual article.
The convention follows the existing `special_date` rows the Commission
factsheet loader writes: institution COMMISSION, event_type special_date, one
row per date, idempotent on external_id.

A regulation's phase-in is exactly the kind of thing a compliance team forgets
between the day it enters into force and the day it binds, which is why these
belong in the calendar and not only in a guide.

Usage:
  python3.12 -m scripts.seed_elv_calendar_milestones --dry-run
  python3.12 -m scripts.seed_elv_calendar_milestones --apply
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

SOURCE = "lawdrop_elv_2026"
SOURCE_URL = "http://publications.europa.eu/resource/eli/reg/2026/1738/oj"

# (date, title, description)
MILESTONES = [
    ("2026-08-13",
     "End-of-Life Vehicles Regulation enters into force",
     "Regulation (EU) 2026/1738 enters into force on the twentieth day after its "
     "publication in the Official Journal of 24 July 2026. Article 53 starts "
     "applying today: Annex I of the Batteries Regulation (EU) 2023/1542 is "
     "replaced, extending the mercury, cadmium and lead limits expressly to "
     "batteries incorporated in vehicles. Four heavy-metal exemptions in Annex II "
     "to Directive 2000/53/EC cease to apply on the same date."),
    ("2026-09-14",
     "Vehicle circularity: delegated-act empowerments start applying",
     "The delegated-act empowerments of Regulation (EU) 2026/1738 start applying, "
     "so the Commission can begin adopting the acts that will fill in the "
     "methodologies for recyclability, recycled content, the passport and fee "
     "modulation."),
    ("2028-09-01",
     "End-of-Life Vehicles Regulation becomes applicable",
     "The body of Regulation (EU) 2026/1738 applies from today, and Directive "
     "2000/53/EC is repealed with effect from the same date, though several of its "
     "provisions stay alive to 2029, 2030 and 2032 under Article 57."),
    ("2029-08-31",
     "Member State registers of vehicle producers must exist",
     "Each Member State establishes or designates its register of producers under "
     "Article 19 of Regulation (EU) 2026/1738, and the Commission publishes the "
     "website linking to all of them. Producers cannot register before this."),
    ("2029-09-01",
     "Vehicle producer responsibility and circularity strategies start",
     "Extended producer responsibility (Article 16), the manufacturer circularity "
     "strategy (Article 9), removal and replacement information for waste "
     "operators (Article 11), labelling duties on sellers of used and "
     "remanufactured parts (Article 31) and national penalty regimes (Article 49) "
     "all start applying. Special purpose M1 and N1 vehicles enter scope."),
    ("2030-01-01",
     "Vehicle reuse, recycling and recovery targets start applying",
     "From today producers, or their producer responsibility organisations, must "
     "ensure waste operators achieve reuse and recovery of at least 95 % and reuse "
     "and recycling of at least 85 % by average weight per vehicle per year, "
     "excluding batteries (Article 33)."),
    ("2030-08-14",
     "Third-country recyclate counts towards vehicle targets",
     "Recycled content recovered in an installation outside the Union may count "
     "towards the Article 6 targets from today, provided the installation meets "
     "Annex XIII and the audit requirements for material recycled in third "
     "countries."),
    ("2031-09-01",
     "Used-vehicle exports restricted to roadworthy vehicles",
     "From today a used vehicle may be exported from the Union only if it is not "
     "an end-of-life vehicle and is roadworthy when the export declaration is "
     "lodged, unless recognised as of special cultural interest (Article 39). "
     "Buses, lorries, trailers and L-category vehicles also enter scope."),
    ("2032-09-01",
     "Vehicle type-approval circularity and the vehicle passport",
     "For vehicle types type-approved from today: 85 % reusable or recyclable and "
     "95 % reusable or recoverable by mass (Article 4), a minimum 15 % recycled "
     "plastic content (Article 6), and a Digital Circularity Vehicle Passport for "
     "every vehicle placed on the market, interoperable with the battery passport "
     "and with Ecodesign product passports (Article 13)."),
    ("2036-09-01",
     "Recycled plastic in new vehicles rises to 25 %",
     "For vehicle types type-approved from today, the plastic in each new vehicle "
     "must contain at least 25 % recycled from post-consumer plastic waste, at "
     "least a fifth of it from end-of-life vehicles or parts removed during the "
     "use phase (Article 6)."),
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
            ext = f"elv-2026R1738-{date}"
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
                        ARRAY['Environment','Circular Economy','Automotive'],
                        ARRAY['2023/0284(COD)'])"""),
                {"t": title, "d": description, "s": date, "src": SOURCE,
                 "url": SOURCE_URL, "e": ext})
            added += 1

        print(f"\n=== PLAN === add {added}, already present {skipped}")
        if not apply:
            db.rollback()
            print("[DRY-RUN] nothing written. Re-run with --apply")
            return 0
        db.commit()
        n = db.execute(text("SELECT count(*) FROM eu_calendar_events WHERE source=:s"),
                       {"s": SOURCE}).scalar()
        print(f"[OK] committed. {n} ELV milestones in My EU Calendar.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
