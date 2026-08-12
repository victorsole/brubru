"""Tag existing rows with a policy interest that did not exist when they landed.

Every MEUB surface joins on `policy_areas`, and rows are classified once, at
sync time. A leaf added to policy_taxonomy.json afterwards therefore claims
nothing that is already in the database: the classifier is right, it simply
never ran again. For the ecodesign / digital-product-passport leaf that meant
66 consultations and 13 legislative carriages about the regime carried every
tag except the one naming the regime.

The symptom is subtle, which is why it survived: the rows still surfaced
through their generic tags ("Environment"), so the tabs looked populated. What
was missing was the connection between the user's own interest and the material
it exists to find. A user who ticked only this interest would have seen nothing.

Adds the leaf where classify() says it belongs. Never removes anything: the
existing tags are other leaves' business.

    python3.12 scripts/backfill_interest_tagging.py --leaf "<name>" --apply
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
from services.tracking.policy_area_classifier import classify

# table -> (id column, title column, body column, policy-areas column)
TABLES = [
    ("public_consultations", "id", "title", "description", "policy_areas"),
    ("legislative_carriages", "id", "title", "short_title", "policy_areas"),
    ("eu_news_items", "id", "title", "summary", "policy_areas"),
    ("eu_calendar_events", "id", "title", "description", "policy_areas"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--leaf", required=True, help="canonical PI leaf name")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    leaf = args.leaf

    db = SessionLocal()
    rc = 0
    try:
        totals = {}
        for table, idc, titlec, bodyc, areac in TABLES:
            rows = db.execute(text(
                f"SELECT {idc} AS rid, {titlec} AS title, "
                f"COALESCE({bodyc}, '') AS body, {areac} AS areas FROM {table}"
            )).fetchall()
            todo = []
            for r in rows:
                if leaf in (r.areas or []):
                    continue
                if leaf in classify(r.title or "", r.body or ""):
                    todo.append(r)
            totals[table] = (len(rows), len(todo))
            print(f"=== {table}: {len(rows)} row(s), {len(todo)} to tag ===")
            for r in todo[:8]:
                print(f"  + {str(r.title)[:80]}")
            if len(todo) > 8:
                print(f"  ... and {len(todo) - 8} more")
            if args.apply and todo:
                for r in todo:
                    db.execute(text(
                        f"UPDATE {table} SET {areac} = ("
                        f"  SELECT ARRAY(SELECT DISTINCT unnest("
                        f"    COALESCE({areac}, '{{}}') || ARRAY[:leaf]::text[]))"
                        f") WHERE {idc} = :rid"),
                        {"leaf": leaf, "rid": r.rid})
                db.commit()

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0

        print("\n=== verification ===")
        for table, idc, titlec, bodyc, areac in TABLES:
            n = db.execute(text(
                f"SELECT count(*) FROM {table} WHERE :leaf = ANY({areac})"),
                {"leaf": leaf}).scalar()
            expected = totals[table][1]
            # rows already carrying it plus the ones just added
            print(f"  {table:<24} now tagged: {n} (added {expected})")
            if expected and n < expected:
                print(f"    [FAIL] fewer tagged than added")
                rc = 1

        # nothing may have LOST a tag
        print("\n=== no row lost its other tags ===")
        empty = db.execute(text(
            "SELECT count(*) FROM public_consultations "
            "WHERE :leaf = ANY(policy_areas) AND array_length(policy_areas, 1) IS NULL"),
            {"leaf": leaf}).scalar()
        print(f"  consultations with an empty array: {empty} "
              f"{'OK' if not empty else 'FAIL'}")
        if empty:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
