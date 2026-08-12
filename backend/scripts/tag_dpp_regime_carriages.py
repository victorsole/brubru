"""Tag the DPP regime's acts from the regime's own legal framework, not from words.

A keyword classifier reads titles. Four of the acts that create digital product
passport obligations do not say so in their titles: the Critical Raw Materials
Act, the Construction Products Regulation, the textile EPR Directive and the
PPWR. Their membership of the regime is a legal fact established by Commission
Implementing Regulation (EU) 2026/1778 Article 1, not a lexical one, so no
amount of keyword tuning would ever find them, and loosening the keywords to
reach them is what produced the insurance false positives in the first place.

/api/v2/dpp/legal-framework is that list. Read it, match each act to its
carriage by CELEX, and tag it. Authority comes from the regime, the classifier
keeps its precision, and the two never have to be traded against each other.

Idempotent; adds only, never removes.
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

LEAF = "Ecodesign of sustainable products / Digital product passport"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        # The folder is the regime's legal framework: read it from the same
        # rows /api/v2/dpp/legal-framework serves.
        # economy_items has no identifier column: the CELEX is the tail of the
        # Cellar public_url, which is how the folder addresses each act.
        acts = db.execute(text(
            "SELECT DISTINCT UPPER(right(public_url, 10)) AS identifier, title "
            "FROM economy_items "
            "WHERE body_code = 'dpp' AND item_type = 'law' "
            "  AND public_url ILIKE '%celex:%' ORDER BY 1")).fetchall()
        print(f"=== the regime's legal framework: {len(acts)} act(s) ===")
        if not acts:
            print("  [FAIL] the DPP folder holds no legal acts; nothing to tag")
            return 1

        tagged = already = nocard = 0
        for a in acts:
            celex = (a.identifier or "").upper()
            row = db.execute(text(
                "SELECT id, file_id, title, policy_areas FROM legislative_carriages "
                "WHERE UPPER(file_id) = :c OR celex_numbers::text ILIKE :like "
                "ORDER BY (UPPER(file_id) = :c) DESC LIMIT 1"),
                {"c": celex, "like": f"%{celex}%"}).fetchone()
            if not row:
                nocard += 1
                print(f"  [NO CARD] {celex}  {a.title[:58]}")
                continue
            if LEAF in (row.policy_areas or []):
                already += 1
                print(f"  [OK]      {celex}  already tagged")
                continue
            tagged += 1
            print(f"  [TAG]     {celex}  {row.file_id:<16} {row.title[:46]}")
            if args.apply:
                db.execute(text(
                    "UPDATE legislative_carriages SET policy_areas = ("
                    "  SELECT ARRAY(SELECT DISTINCT unnest("
                    "    COALESCE(policy_areas, '{}') || ARRAY[:l]::text[]))"
                    ") WHERE id = :id"), {"l": LEAF, "id": row.id})

        print(f"\n  tagged {tagged}, already {already}, no card {nocard}")
        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0
        db.commit()

        print("\n=== verification: every act of the regime carries the interest ===")
        for a in acts:
            celex = (a.identifier or "").upper()
            row = db.execute(text(
                "SELECT file_id, policy_areas FROM legislative_carriages "
                "WHERE UPPER(file_id) = :c OR celex_numbers::text ILIKE :like "
                "ORDER BY (UPPER(file_id) = :c) DESC LIMIT 1"),
                {"c": celex, "like": f"%{celex}%"}).fetchone()
            if not row:
                print(f"  SKIP {celex}: no carriage exists")
                continue
            ok = LEAF in (row.policy_areas or [])
            print(f"  {'OK ' if ok else 'FAIL'} {celex}  {row.file_id}")
            if not ok:
                rc = 1
        total = db.execute(text(
            "SELECT count(*) FROM legislative_carriages WHERE :l = ANY(policy_areas)"),
            {"l": LEAF}).scalar()
        print(f"\n  carriages carrying the interest: {total}")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
