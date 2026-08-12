"""Merge the DPP carriage rows that duplicate a pre-existing file.

Creating one carriage per act keyed on the lowercase CELEX collided with rows
that already existed keyed on the PROCEDURE: lip-2020-0353-COD for batteries,
lip-2023-0290-COD for toys, 2023-0124-cod for detergents. That is a duplicate
legislative file in a shared table, and the detergents original is the one
holding the Legislative Train summary, so keeping mine would have hidden it.

The procedure-keyed row wins: it is older, it is what the OEIL and Legislative
Train syncs write to, and a future sync would keep enriching it while my copy
went stale. Anything my row had and the keeper lacked (the description, the
OEIL key events fetched today) is copied over first, then the tracks are
repointed and the duplicate is deleted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

# procedure ref -> (my duplicate file_id, the pre-existing keeper file_id)
DUPES = {
    "2020/0353(COD)": ("32023r1542", "lip-2020-0353-COD"),
    "2023/0290(COD)": ("32025r2509", "lip-2023-0290-COD"),
    "2023/0124(COD)": ("32026r0405", "2023-0124-cod"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        for proc, (mine_fid, keep_fid) in DUPES.items():
            mine = db.execute(
                text("SELECT id, description, oeil_key_events, celex_numbers, url "
                     "FROM legislative_carriages WHERE file_id = :f"), {"f": mine_fid}
            ).fetchone()
            keep = db.execute(
                text("SELECT id, title, description, oeil_key_events, celex_numbers, "
                     "legislative_train_summary FROM legislative_carriages "
                     "WHERE file_id = :f"), {"f": keep_fid}
            ).fetchone()
            if not mine or not keep:
                print(f"  [SKIP] {proc}: one side missing "
                      f"(mine={bool(mine)} keeper={bool(keep)})")
                continue

            n_tracks = db.execute(
                text("SELECT count(*) FROM user_carriage_tracks WHERE carriage_id = :c"),
                {"c": mine.id},
            ).scalar()
            keep_events = len(keep.oeil_key_events or [])
            mine_events = len(mine.oeil_key_events or [])

            print(f"\n=== {proc} ===")
            print(f"  keeper : {keep_fid}  {keep.title[:44]}")
            print(f"           events={keep_events} train="
                  f"{bool(keep.legislative_train_summary)} "
                  f"description={'yes' if keep.description else 'no'}")
            print(f"  mine   : {mine_fid}  events={mine_events} "
                  f"tracks pointing at it={n_tracks}")

            if args.apply:
                # carry across anything the keeper lacks
                db.execute(
                    text("""
                        UPDATE legislative_carriages SET
                            description = COALESCE(NULLIF(description, ''), :descr),
                            oeil_key_events = CASE
                                WHEN oeil_key_events IS NULL
                                  OR json_array_length(oeil_key_events) = 0
                                THEN CAST(:ev AS json) ELSE oeil_key_events END,
                            celex_numbers = (
                                SELECT ARRAY(SELECT DISTINCT unnest(
                                    COALESCE(celex_numbers, '{}') || COALESCE(:cx, '{}')))),
                            current_status = 'ADOPTED',
                            last_updated = now()
                        WHERE id = :id
                    """),
                    {"descr": mine.description,
                     "ev": __import__("json").dumps(mine.oeil_key_events or []),
                     "cx": mine.celex_numbers or [], "id": keep.id},
                )
                # repoint the tracks, then drop the duplicate
                db.execute(
                    text("UPDATE user_carriage_tracks SET carriage_id = :keep "
                         "WHERE carriage_id = :mine"),
                    {"keep": keep.id, "mine": mine.id},
                )
                db.execute(
                    text("DELETE FROM legislative_carriages WHERE id = :id"),
                    {"id": mine.id},
                )
                print("  [MERGED] tracks repointed, duplicate deleted")

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            for proc, (mine_fid, keep_fid) in DUPES.items():
                n = db.execute(
                    text("SELECT count(*) FROM legislative_carriages "
                         "WHERE oeil_procedure_ref = :p"), {"p": proc}).scalar()
                gone = db.execute(
                    text("SELECT count(*) FROM legislative_carriages WHERE file_id = :f"),
                    {"f": mine_fid}).scalar()
                print(f"  {proc}: {n} row(s) {'OK' if n == 1 else 'FAIL'}, "
                      f"duplicate {'removed' if gone == 0 else 'STILL PRESENT'}")
                if n != 1 or gone:
                    rc = 1
            for email, uid in (("jcastella@terraqui.com", "e6337400-6c0c-4842-9007-26db3f59a3fb"),
                               ("joana-demo@demo.invalid", "96788e72-5890-4b2f-bd35-00bedc98e721")):
                n = db.execute(
                    text("SELECT count(DISTINCT carriage_id) FROM user_carriage_tracks "
                         "WHERE user_id = :u AND archived_at IS NOT NULL"), {"u": uid}).scalar()
                print(f"  {email}: {n} distinct archived files")
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
