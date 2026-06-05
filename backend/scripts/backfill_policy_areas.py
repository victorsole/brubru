"""
Backfill canonical PI policy_areas onto MEUB surfaces.

Tags eu_news_items and legislative_carriages with canonical PI leaf names using
the deterministic classifier (services/tracking/policy_area_classifier.py), so
PI filtering becomes a direct policy_areas overlap everywhere.

Usage:
    python3.12 scripts/backfill_policy_areas.py --target all            # dry-run report
    python3.12 scripts/backfill_policy_areas.py --target news --apply   # write
    python3.12 scripts/backfill_policy_areas.py --target carriages --apply --limit 500
"""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.INFO)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tracking.policy_area_classifier import classify  # noqa: E402

TARGETS = {
    "news": {
        "table": "eu_news_items",
        "select": "SELECT id, title, summary, commission_dg FROM eu_news_items",
        "classify": lambda r: classify(r["title"], r.get("summary") or "", dg=r.get("commission_dg")),
    },
    "carriages": {
        "table": "legislative_carriages",
        "select": "SELECT id, title, description, lead_committee FROM legislative_carriages",
        "classify": lambda r: classify(r["title"], r.get("description") or "", committee=r.get("lead_committee")),
    },
}


def run(target: str, apply: bool, limit: int | None):
    cfg = TARGETS[target]
    db = SessionLocal()
    sql = cfg["select"]
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = db.execute(text(sql)).mappings().all()

    before = db.execute(
        text(f"SELECT count(*) FROM {cfg['table']} WHERE policy_areas IS NOT NULL AND array_length(policy_areas,1)>0")
    ).scalar()

    dist = Counter()
    tag_counts = Counter()
    blanks = 0
    updated = 0
    for r in rows:
        leaves = cfg["classify"](r)
        if not leaves:
            blanks += 1
        tag_counts[len(leaves)] += 1
        for lf in leaves:
            dist[lf] += 1
        if apply:
            db.execute(
                text(f"UPDATE {cfg['table']} SET policy_areas = :pa WHERE id = :id"),
                {"pa": leaves, "id": r["id"]},
            )
            updated += 1
    if apply:
        db.commit()

    after = db.execute(
        text(f"SELECT count(*) FROM {cfg['table']} WHERE policy_areas IS NOT NULL AND array_length(policy_areas,1)>0")
    ).scalar() if apply else None

    n = len(rows)
    tagged = n - blanks
    print(f"\n=== {target} ({cfg['table']}) — {'APPLIED' if apply else 'DRY-RUN'} ===")
    print(f"rows processed:      {n}")
    print(f"tagged:              {tagged} ({100*tagged//max(n,1)}%)   blank: {blanks}")
    print(f"populated before:    {before}" + (f"   after: {after}" if apply else ""))
    avg = sum(k*v for k, v in tag_counts.items()) / max(tagged, 1)
    print(f"avg leaves/tagged:   {avg:.2f}")
    print(f"tag-count histogram: " + ", ".join(f"{k}:{tag_counts[k]}" for k in sorted(tag_counts)))
    print("top leaves:          " + ", ".join(f"{lf}={c}" for lf, c in dist.most_common(12)))
    db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["news", "carriages", "all"], required=True)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    targets = ["news", "carriages"] if args.target == "all" else [args.target]
    for tgt in targets:
        run(tgt, args.apply, args.limit)


if __name__ == "__main__":
    main()
