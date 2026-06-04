"""
Backfill legislative_carriages.lead_committee from already-cached OEIL data.

For carriages that have an OEIL procedure reference and cached oeil_procedure_data
but an empty lead_committee, read the responsible committee code out of
oeil_procedure_data.key_players.committee_responsible.code and set lead_committee.

This is NOT a scrape: it only reads JSON we already hold (no network calls). It
lifts committee coverage of the OEIL subset (~55% -> ~67%), which is what My
Tracked Files filters on when auto-populating from Policy Interests.

Usage:
    python3.12 -m backend.scripts.backfill_committee_from_oeil_cache            # dry-run
    python3.12 -m backend.scripts.backfill_committee_from_oeil_cache --apply
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage

SKIP_CODES = {"", "UNKNOWN", "NONE", "NULL"}


def _extract_code(carriage: LegislativeCarriage) -> str | None:
    data = carriage.oeil_procedure_data
    if not isinstance(data, dict):
        return None
    kp = data.get("key_players")
    if not isinstance(kp, dict):
        return None
    cr = kp.get("committee_responsible")
    if not isinstance(cr, dict):
        return None
    code = (cr.get("code") or "").strip().upper()
    if code in SKIP_CODES:
        return None
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill lead_committee from cached OEIL data.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is dry-run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = (
            db.query(LegislativeCarriage)
            .filter(
                LegislativeCarriage.oeil_procedure_ref.isnot(None),
                LegislativeCarriage.oeil_procedure_data.isnot(None),
                (LegislativeCarriage.lead_committee.is_(None))
                | (LegislativeCarriage.lead_committee == ""),
            )
            .all()
        )
        print(f"[INFO] {len(rows)} committee-less OEIL carriages to inspect.")

        updated = Counter()
        changed = 0
        for c in rows:
            code = _extract_code(c)
            if not code:
                continue
            if args.apply:
                c.lead_committee = code
            updated[code] += 1
            changed += 1

        print(f"[INFO] Recoverable committees: {changed}")
        for code, n in updated.most_common():
            print(f"    {code:6} {n}")

        if not args.apply:
            print("[DRY-RUN] No changes written. Re-run with --apply.")
            return
        db.commit()
        print(f"[OK] Backfilled lead_committee on {changed} carriages.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
