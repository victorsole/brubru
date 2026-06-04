"""
Backfill committee_work_items.procedure_type, relevance_score and status.

Why: the procedure_type column used to be a native PG enum with only five labels
(COD/APP/CNS/NLE/INI), so the scraper collapsed every other OEIL type to INI.
Migration 093 converted the column to varchar; this script populates the real
type from the procedure-reference suffix and recomputes relevance.

Status: the scraped status_text turned out to be noise (mostly a mis-captured
committee code, e.g. "ECON"), so there is nothing reliable to map from. The data
source is the EP "Work in Progress" feed, where every listed procedure is, by
definition, currently sitting in a committee. We therefore set status to
IN_COMMITTEE wherever it is still the bare UNKNOWN default (a provenance-based
fact, not a fabricated one) and clear the junk committee-code status_text.

Usage:
    python3.12 -m backend.scripts.backfill_committee_procedure_status          # dry-run
    python3.12 -m backend.scripts.backfill_committee_procedure_status --apply   # persist
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from models.committee_work import CommitteeWorkItem
from knowledge_base.ep_committees import EP_COMMITTEE_CODES

SUFFIX_RE = re.compile(r"\(([A-Z]{2,4})\)")

# Substantive legislative work ranks highest; technical scrutiny / housekeeping
# lowest. Mirrors CommitteeWorkInProgressScraper.RELEVANCE_SCORES.
RELEVANCE = {
    "COD": 100, "INL": 90, "APP": 80, "CNS": 70, "ACI": 65, "BUD": 60,
    "GBD": 60, "BUI": 58, "DEC": 58, "NLE": 50, "RSP": 45, "RSO": 42,
    "INI": 40, "COS": 40, "DCE": 38, "DEA": 30, "RPS": 30, "REG": 25, "IMM": 15,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill committee_work_items type/status.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default dry-run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.query(CommitteeWorkItem).all()
        committee_codes = set(EP_COMMITTEE_CODES)

        type_changed = relevance_changed = status_changed = text_cleared = 0
        type_hist: dict[str, int] = {}

        for r in rows:
            m = SUFFIX_RE.search(r.procedure_ref or "")
            suffix = m.group(1) if m else None

            if suffix:
                type_hist[suffix] = type_hist.get(suffix, 0) + 1
                if r.procedure_type != suffix:
                    type_changed += 1
                    if args.apply:
                        r.procedure_type = suffix
                new_score = RELEVANCE.get(suffix, 40)
                if r.relevance_score != new_score:
                    relevance_changed += 1
                    if args.apply:
                        r.relevance_score = new_score

            # Clear junk status_text that is just a committee code.
            if r.status_text and r.status_text.strip().upper() in committee_codes:
                text_cleared += 1
                if args.apply:
                    r.status_text = None

            # Provenance default: work-in-progress feed => in committee.
            status_val = getattr(r.status, "value", r.status)
            if str(status_val) in ("unknown", "UNKNOWN", "CommitteeWorkStatusEnum.UNKNOWN"):
                status_changed += 1
                if args.apply:
                    r.status = "IN_COMMITTEE"

        if args.apply:
            db.commit()

        print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] {len(rows)} rows scanned")
        print(f"  procedure_type set/changed : {type_changed}")
        print(f"  relevance_score recomputed : {relevance_changed}")
        print(f"  status -> IN_COMMITTEE      : {status_changed}")
        print(f"  junk status_text cleared   : {text_cleared}")
        print("  type distribution          : " +
              ", ".join(f"{k}={v}" for k, v in sorted(type_hist.items(), key=lambda x: -x[1])))
        if not args.apply:
            print("  re-run with --apply to persist")
    finally:
        db.close()


if __name__ == "__main__":
    main()
