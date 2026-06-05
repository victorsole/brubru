"""
Normalize users.policy_interests to canonical PI leaf names.

12/21 users carry legacy/granular interest strings ("Trade", "Vaccines", "HTA")
that are NOT canonical leaves, so PI filtering matches nothing for them. This
maps each non-canonical value to its canonical leaf (legacy alias map +
classifier), ADDITIVELY and non-destructively: canonical values are kept,
mappable ones gain their leaf, and unmappable ones are kept as-is (never lost).

Usage:
    python3.12 scripts/normalize_user_interests.py            # dry-run (per-user diff)
    python3.12 scripts/normalize_user_interests.py --apply
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.INFO)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tracking.policy_area_classifier import classify  # noqa: E402

# Legacy short forms the keyword classifier can't infer from a bare token.
LEGACY = {
    "Trade": "Trade and Economic Security",
    "Trade and IP": "Trade and Economic Security",
    "Digital": "Digital Policy and Digital Economy",
    "Digital Policy": "Digital Policy and Digital Economy",
    "Migration": "Migration and Home Affairs",
    "Cohesion": "Regional Policy",
    "Finance": "Economic and Financial Affairs",
    "Economics": "Economic and Financial Affairs",
    "Public Health": "Health",
}


def _canon_set():
    tax = json.load(open(Path(__file__).resolve().parents[1] / "knowledge_base" / "policy_taxonomy.json", encoding="utf-8"))
    return {p["name"] for c in tax["categories"] for p in c["policy_areas"]}


def _normalize(vals, canon):
    out, seen = [], set()
    def add(x):
        if x and x not in seen:
            seen.add(x); out.append(x)
    for v in vals:
        if v in canon:
            add(v)
        else:
            leaf = LEGACY.get(v) or (classify(v) or [None])[0]
            if leaf:
                add(leaf)
            else:
                add(v)  # keep unmapped value, never drop the user's intent
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    canon = _canon_set()
    db = SessionLocal()
    rows = db.execute(text("SELECT id, email, policy_interests FROM users WHERE policy_interests IS NOT NULL")).mappings().all()
    changed = 0
    for r in rows:
        try:
            vals = json.loads(r["policy_interests"]) if isinstance(r["policy_interests"], str) else r["policy_interests"]
        except Exception:
            continue
        if not isinstance(vals, list) or not vals:
            continue
        new = _normalize(vals, canon)
        if new != vals:
            changed += 1
            print(f"  {r['email']}:\n    - {vals}\n    + {new}")
            if args.apply:
                db.execute(text("UPDATE users SET policy_interests = :pi WHERE id = :id"),
                           {"pi": json.dumps(new), "id": r["id"]})
    if args.apply:
        db.commit()
    print(f"\n{'APPLIED' if args.apply else 'DRY-RUN'}: {changed} users would change")
    db.close()


if __name__ == "__main__":
    main()
