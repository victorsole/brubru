"""
Repair `tenders.submission_deadline` from each row's OWN stored XML.

Measured 28 Oct 2026 (O98): 228 TED notices said "open" with no deadline. 173 had their notice
XML stored, and in 163 of them the deadline sat in it (`cac:TenderSubmissionDeadlinePeriod`, or
the legacy forms' date for receipt of tenders): 97 had passed, so those calls for competition were
served as open after they closed. Most predate the 7 Aug 2026 fix of the eForms date parser, which
dropped every deadline whose date carried an offset; two were published after it (17 Sep, 13 Oct)
and lost theirs too, cause not yet found. The repair parses the stored XML with today's parser:
no network, no guessing (since 29 Oct 2026 a call for expressions of interest's own deadline too:
the end of its period for expressions of interest). A notice whose XML states no deadline is left alone, and the status rule
(services/tenders/status.py) serves it as `unknown`.

Runs in the daily tier before the status job, so a deadline the fetch drops is filled the next day.
It reads the XML only of rows without a deadline whose XML names one.

Run:
    python3.12 backend/scripts/repair_tender_deadline.py            # dry run
    python3.12 backend/scripts/repair_tender_deadline.py --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tenders.eforms_parser import EFormsParser  # noqa: E402

# The ids first, without the XML; then the XML in small batches.
_TODO = text("""SELECT id, publication_number, status FROM tenders
    WHERE submission_deadline IS NULL AND xml_content IS NOT NULL
      AND (xml_content LIKE '%TenderSubmissionDeadlinePeriod%' OR xml_content LIKE '%DT_DATE_FOR_SUBMISSION%'
           OR xml_content LIKE '%DATE_RECEIPT_TENDERS%' OR xml_content LIKE '%InterestExpressionReceptionPeriod%')
    ORDER BY id""")
_XML = text("SELECT id, xml_content FROM tenders WHERE id = ANY(:ids)")
_SET = text("UPDATE tenders SET submission_deadline = :d WHERE id = :id AND submission_deadline IS NULL")
_BATCH = 50
_LISTED = 20


def deadline_from_xml(parser: EFormsParser, xml: str | None) -> datetime | None:
    """The deadline the notice states, timezone-aware, or None."""
    if not xml:
        return None
    d = parser.parse(xml).get("submission_deadline")
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def repair(db, *, apply: bool) -> tuple[int, int]:
    """(filled, left without a deadline)."""
    todo = db.execute(_TODO).all()
    parser = EFormsParser()
    filled = left = 0
    for start in range(0, len(todo), _BATCH):
        chunk = todo[start:start + _BATCH]
        xml_by_id = {r.id: r.xml_content for r in db.execute(_XML, {"ids": [r.id for r in chunk]}).all()}
        for row in chunk:
            try:
                d = deadline_from_xml(parser, xml_by_id.get(row.id))
            except Exception as e:  # one unreadable notice never stops the others; it is listed
                d = None
                print(f"  [leave] {row.publication_number}: XML not readable ({type(e).__name__})")
            if d is None:
                left += 1
                continue
            filled += 1
            if filled <= _LISTED:
                print(f"  [fill]  {row.publication_number} ({row.status}): deadline {d.isoformat()}")
            if apply:
                db.execute(_SET, {"d": d, "id": row.id})
        if apply:
            db.commit()
    if filled > _LISTED:
        print(f"  [fill]  ...and {filled - _LISTED} more")
    return filled, left


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        filled, left = repair(db, apply=args.apply)
        print(f"\n[{'OK' if args.apply else 'DRY-RUN'}] {filled} deadline(s) "
              f"{'filled' if args.apply else 'would be filled'} from the notice's own XML; "
              f"{left} notice(s) name none")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
