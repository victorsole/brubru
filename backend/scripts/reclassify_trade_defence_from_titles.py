"""Re-run the trade-defence classifiers over the STORED titles. No network.

`backfill_eu_trade_defence.py` classifies as it hydrates, so a classifier fix only
reaches the corpus when the full Cellar walk next passes a row: measured 24 September
2026, that walk moves at about 33 seconds per row (it re-fetches metadata for all 1,528
acts and a body for the 977 without one), so a one-line regex fix would take some nine
hours to land, and until then the rows that were never re-walked keep the old value.

Two defects were still in the corpus on that date, both of them in `target_country`:

  * 193 rows held the whole trailing clause, e.g. "People's Republic of China following
    an expiry review pursuant to Article 11(2) of Regulation (EC) No 384/96". The cut
    pattern that fixes this was added on 15 September; these rows predate it.
  * 715 China rows were split across two apostrophes, 403 curly against 312 straight,
    because the OJ uses both. That one is worse than it looks: the corpus reads as
    complete from either spelling, and a filter on the straight one returns 312 of 715
    measures while looking like the whole answer.

The classifiers are the SAME functions the walk uses, imported from it, so this cannot
drift from what the next hydration writes. Titles are left exactly as published.

Usage (from backend/):
    python3.12 scripts/reclassify_trade_defence_from_titles.py           # dry run
    python3.12 scripts/reclassify_trade_defence_from_titles.py --apply
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

# Import by path: the walk's filename is not an identifier and it must not be re-run.
_spec = importlib.util.spec_from_file_location(
    "_backfill_eu_trade_defence", BACKEND / "scripts" / "backfill_eu_trade_defence.py")
_walk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_walk)

FIELDS = ("target_country", "product", "measure_type", "duty_status")


def classify(title: str) -> dict:
    return {
        "target_country": _walk.extract_target_country(title),
        "product": _walk.extract_product(title),
        "measure_type": _walk.classify_measure_type(title),
        "duty_status": _walk.classify_duty_status(title),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT celex, title, target_country, product, measure_type, duty_status "
            "FROM eu_trade_defence_measures ORDER BY celex")).fetchall()
        print(f"[INFO] {len(rows):,} measures")

        changes, per_field = [], {f: 0 for f in FIELDS}
        untitled = 0
        for celex, title, *current in rows:
            if not title:
                untitled += 1          # nothing to reclassify from: leave it alone
                continue
            new = classify(title)
            old = dict(zip(FIELDS, current))
            diff = {f: new[f] for f in FIELDS if new[f] != old[f]}
            if diff:
                for f in diff:
                    per_field[f] += 1
                changes.append((celex, diff, old))

        print(f"[INFO] {len(changes):,} row(s) change; {untitled} without a stored title")
        for f in FIELDS:
            print(f"        {f:16} {per_field[f]:5}")
        for celex, diff, old in changes[:10]:
            for f, v in diff.items():
                print(f"   {celex} {f}: {str(old[f])[:52]!r} -> {str(v)[:52]!r}")
        if len(changes) > 10:
            print(f"   ... and {len(changes) - 10:,} more")

        if not args.apply:
            print("[DRY-RUN] re-run with --apply")
            return 0

        for celex, diff, _ in changes:
            sets = ", ".join(f"{f} = :{f}" for f in diff)
            db.execute(text(f"UPDATE eu_trade_defence_measures SET {sets}, updated_at = now() "
                            f"WHERE celex = :celex"), {**diff, "celex": celex})
        db.commit()
        print(f"[APPLIED] {len(changes):,} row(s) updated")

        # Verify from the database, not from the loop that just wrote it.
        messy = db.execute(text(
            "SELECT count(*) FROM eu_trade_defence_measures "
            "WHERE target_country ~* 'following|pursuant|review|expiry'")).scalar()
        curly = db.execute(text(
            "SELECT count(*) FROM eu_trade_defence_measures "
            "WHERE target_country LIKE '%' || chr(8217) || '%'")).scalar()
        print(f"[VERIFY] messy target_country: {messy}   curly apostrophes: {curly}")
        return 0 if (messy == 0 and curly == 0) else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
