"""Close calls whose deadline has passed but whose status still says otherwise.

Status arrives from the F&T portal at ingest time and is never revisited, so a
call ingested while open keeps saying "open" for ever. Thirty rows were inviting
applications to deadlines that had passed, one of them by four years
(ERASMUS-EDU-2022-ECHE-CERT-FP, closed 3 May 2022), and one of them a LIFE call.

This is the most damaging kind of wrong a funding feed can be. A stale "closed"
merely hides an opportunity; a stale "open" invites an organisation to spend
weeks writing a bid it cannot file.

Deliberately conservative: only rows with a deadline in the past are touched,
only the status column changes, and "forthcoming" is left alone because a call
can legitimately be announced with a provisional date that has slipped. Rows
with no deadline are never guessed at.

Run daily from the same cron as the ingest.
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

# table -> deadline column. Both tables carry the same status vocabulary.
# table -> (deadline column, label column). ft_calls_for_tenders has no
# topic_id, so its own id is the label.
TABLES = {
    "ft_calls_for_proposals": ("deadline", "topic_id"),
    "ft_calls_for_tenders": ("deadline", "id::text"),
    "funding_opportunities": ("deadline", "topic_id"),
}
STALE = ("open", "unknown")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        total = 0
        for table, (dl, label) in TABLES.items():
            rows = db.execute(text(
                f"SELECT {label} AS ref, title, {dl} AS deadline, status FROM {table} "
                f"WHERE status IN :stale AND {dl} IS NOT NULL AND {dl} < CURRENT_DATE "
                f"ORDER BY {dl}"), {"stale": STALE}).fetchall()
            print(f"=== {table}: {len(rows)} row(s) past deadline but not closed ===")
            for r in rows[:10]:
                print(f"  {str(r.deadline)[:10]}  {str(r.status):<8} "
                      f"{str(r.ref)[:34]:<34} {str(r.title)[:38]}")
            if len(rows) > 10:
                print(f"  ... and {len(rows) - 10} more")
            total += len(rows)
            if args.apply and rows:
                db.execute(text(
                    f"UPDATE {table} SET status = 'closed', last_updated = now() "
                    f"WHERE status IN :stale AND {dl} IS NOT NULL "
                    f"AND {dl} < CURRENT_DATE"), {"stale": STALE})
        print(f"\n  {total} row(s) affected")

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0
        db.commit()

        print("\n=== verification ===")
        for table, (dl, _label) in TABLES.items():
            left = db.execute(text(
                f"SELECT count(*) FROM {table} WHERE status IN :stale "
                f"AND {dl} IS NOT NULL AND {dl} < CURRENT_DATE"),
                {"stale": STALE}).scalar()
            print(f"  {table:<26} still open past deadline: {left} "
                  f"{'OK' if not left else 'FAIL'}")
            if left:
                rc = 1
            # and nothing in the future may have been closed by mistake
            future_closed = db.execute(text(
                f"SELECT count(*) FROM {table} WHERE status = 'closed' "
                f"AND {dl} > CURRENT_DATE AND last_updated > now() - interval '5 minutes'"
            )).scalar()
            print(f"  {table:<26} future calls wrongly closed: {future_closed} "
                  f"{'OK' if not future_closed else 'FAIL'}")
            if future_closed:
                rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
