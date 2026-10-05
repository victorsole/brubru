"""Load the Digital Omnibus on AI's application ladder into My EU Calendar, where
the law-drop radar (check D) reads it.

Every date is read from Regulation (EU) 2026/1744 (OJ 24 July 2026) and cited by
article. Same convention as `seed_elv_calendar_milestones.py`: institution
COMMISSION, event_type special_date, one row per date, idempotent on external_id.
Passed dates (27 July and 2 August 2026) are deliberately not loaded.

These are the dates the EU Canon page /eucanon/2026-1744_aiomnibus/ shows as
"Upcoming". When one passes, the radar's check E flags the page so its markers
are flipped; when one MOVES (a further omnibus, a corrigendum), change it here
and on the page together.

Usage:
  python3.12 -m scripts.seed_ai_omnibus_calendar_milestones --dry-run
  python3.12 -m scripts.seed_ai_omnibus_calendar_milestones --apply
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

SOURCE = "canon_ai_omnibus_2026"
SOURCE_URL = "http://publications.europa.eu/resource/eli/reg/2026/1744/oj"
CANON_URL = "https://brubru.beresol.eu/eucanon/2026-1744_aiomnibus/index.html"

# (date, title, description)
MILESTONES = [
    ("2026-12-02",
     "AI Act: new prohibitions and synthetic-content marking transition",
     "Article 5(1)(ba) and (bb) of the AI Act, added by Regulation (EU) 2026/1744, "
     "start applying: AI systems generating non-consensual intimate imagery or "
     "child sexual abuse material are prohibited. Providers of AI systems that "
     "generate synthetic audio, image, video or text content and placed them on the "
     "market before 2 August 2026 must also comply with Article 50(2) marking by "
     "today (Article 111(4))."),
    ("2027-08-01",
     "AI Act: Commission guidelines on combining AI Act and sectoral requirements due",
     "Article 96(1)(g) of the AI Act, as amended by Regulation (EU) 2026/1744: the "
     "Commission publishes guidelines on the practical implementation of Article "
     "8(2), Article 9(10) and Article 17(3) for high-risk systems in Annex I "
     "Section A products, by today."),
    ("2027-08-02",
     "AI Act: national AI regulatory sandboxes and equivalent-protection delegated acts due",
     "Each Member State must have at least one national AI regulatory sandbox "
     "operational (Article 57(1)), and the Commission adopts the delegated acts "
     "specifying which requirements for Annex I Section A high-risk systems may be "
     "limited where sectoral law gives equivalent protection (Article 2(13)), by "
     "today."),
    ("2027-09-02",
     "AI Act: Commission guidance and template on the post-market monitoring plan due",
     "Article 72(3) of the AI Act, as amended by Regulation (EU) 2026/1744: the "
     "Commission adopts guidance, including a voluntary template, on the "
     "post-market monitoring plan by today."),
    ("2027-12-02",
     "AI Act: Annex III high-risk AI rules start applying",
     "Chapter III Sections 1, 2 and 3 of the AI Act apply from today to AI systems "
     "classified as high-risk under Article 6(2) and Annex III (Article 113(c)(i) "
     "as amended by Regulation (EU) 2026/1744). The original date was 2 August 2026."),
    ("2028-01-28",
     "AI Act: notified bodies under Annex I Section A law must have applied for designation",
     "Notified bodies already designated under the Union harmonisation legislation "
     "in Annex I Section A that assess high-risk AI systems must apply for "
     "designation under the AI Act by today (Article 43(3) as amended by Regulation "
     "(EU) 2026/1744; recital 56 describes 18 months from 27 July 2026)."),
    ("2028-08-02",
     "AI Act: Annex I product high-risk AI rules start applying",
     "Chapter III Sections 1, 2 and 3 of the AI Act apply from today to AI systems "
     "classified as high-risk under Article 6(1) and Annex I (Article 113(c)(ii) as "
     "amended by Regulation (EU) 2026/1744). The delegated acts amending Annex III "
     "to the Machinery Regulation (EU) 2023/1230 also apply by today (Article 8 of "
     "that Regulation, as amended)."),
    ("2030-08-02",
     "AI Act: high-risk AI intended for use by public authorities must comply",
     "Providers and deployers of high-risk AI systems intended to be used by public "
     "authorities that were placed on the market or put into service before the "
     "application date must take the necessary steps to comply by today (Article "
     "111(2) as amended by Regulation (EU) 2026/1744)."),
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
            ext = f"aiomnibus-2026R1744-{date}"
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
                        ARRAY['Digital Policy','Artificial Intelligence'],
                        ARRAY['2025/0359(COD)'])"""),
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
