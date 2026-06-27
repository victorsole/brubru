"""Step (c), local phase: backfill real titles for CELEX-only-title carriages from the
local eu_laws cache, then re-classify Policy Interest.

These carriages are corrigenda whose title was ingested as the bare CELEX string
('CELEX:32010L0045R(05)'); the base act's real title is already in eu_laws. Copy the REAL
title (never invented), then run the same classifier. No network. No fabrication.

Run:  python3.12 scripts/backfill_669_local_titles.py            # dry-run
      python3.12 scripts/backfill_669_local_titles.py --apply
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from services.tracking.policy_area_classifier import classify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()

    rows = db.execute(text("""
        SELECT c.id, c.celex_numbers,
               (SELECT l.title FROM eu_laws l
                WHERE l.celex = ANY(c.celex_numbers)
                  AND l.title IS NOT NULL AND l.title <> '' AND l.title NOT LIKE 'CELEX:%'
                ORDER BY length(l.title) DESC LIMIT 1) AS real_title
        FROM legislative_carriages c
        WHERE (c.policy_areas IS NULL OR array_length(c.policy_areas,1) IS NULL)
          AND c.title LIKE 'CELEX:%'
    """)).mappings().all()

    titled = classified = 0
    for r in rows:
        if not r["real_title"]:
            continue
        titled += 1
        pis = classify(r["real_title"])
        if args.apply:
            stmt = "UPDATE legislative_carriages SET title=:t" + (", policy_areas=:p" if pis else "") + " WHERE id=:i"
            params = {"t": r["real_title"], "i": r["id"]}
            if pis:
                params["p"] = pis
            db.execute(text(stmt), params)
        if pis:
            classified += 1

    if args.apply:
        db.commit()
    print(f"CELEX-only rows scanned: {len(rows)}")
    print(f"{'titled' if args.apply else 'WOULD title'} from eu_laws: {titled}")
    print(f"of those, classified a PI: {classified}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
