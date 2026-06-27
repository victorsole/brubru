"""Backfill carriage policy_areas (Brubru Policy Interest) for unclassified carriages.

Runs the SAME classifier the OEIL sync uses (services.tracking.policy_area_classifier.classify)
over every carriage that has no policy_areas, and fills ONLY where it returns a real PI from
the title (+ committee when present). Carriages with no signal stay empty — never guessed
(no-hallucination). Idempotent and safe to re-run.

Run:  python3.12 scripts/backfill_carriage_policy_areas.py            # dry-run
      python3.12 scripts/backfill_carriage_policy_areas.py --apply
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

from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from models.legislative_train import LegislativeCarriage  # noqa: E402
from services.tracking.policy_area_classifier import classify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default dry-run)")
    args = ap.parse_args()

    db = SessionLocal()
    unclassified = (
        db.query(LegislativeCarriage)
        .filter((LegislativeCarriage.policy_areas.is_(None))
                | (LegislativeCarriage.policy_areas == []))
        .all()
    )
    filled = 0
    for c in unclassified:
        pis = classify(c.title or "", committee=c.lead_committee or None)
        if not pis:
            continue
        filled += 1
        if args.apply:
            c.policy_areas = pis

    if args.apply:
        db.commit()
    print(f"unclassified scanned: {len(unclassified)}")
    print(f"{'filled' if args.apply else 'WOULD fill'}: {filled}")
    print(f"still empty (honest gap): {len(unclassified) - filled}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
