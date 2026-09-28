"""feedback_count for every Commission consultation: the sum over its publications.

WHY THIS WAS REWRITTEN (28 Sep 2026)
------------------------------------
The previous version asked `allFeedback?publicationId=<initiative_id>`, on the
assumption that a consultation's publication id equals its initiative id ("verified
for 13693, 15912, 13174"). It does not: the two are separate number series that
overlap, so every count it stored belonged to SOME OTHER publication. Measured:

    initiative            stored (old)   real (sum of its publications)
    14674 EU Inc.               61              2,518
    13693 cooker labels         19                 51
    15912 labour mobility       39                205
    13174 food systems          86              2,899

and only 24 of 4,124 Commission consultations carried any count, so the
consultation tab, the chat's "most-answered" ranking and the feedback sync's
selection (`WHERE feedback_count > 0`) all read nothing or the wrong thing.

HOW IT COUNTS NOW
-----------------
One call per initiative to the Better Regulation initiative detail (the same one
the feedback sync uses): it lists every publication (call for evidence, public
consultation, draft act...) with its own `totalFeedback`. The count is their sum.

WHAT A RUN DOES
---------------
1. Refreshes every Commission consultation still collecting feedback or closed in
   the last 30 days (their counts still move).
2. Drains the rest in initiative-id order, keeping its place in `job_cursors`
   (migration 244) so each run continues where the last stopped and wraps round.
Agency consultations (source = 'agency', synthetic '99...' ids) are never sent to
Have Your Say.

This script is the ONE writer of public_consultations.feedback_count for
Commission rows; the list sync sets it only when it creates a row.

Verdict: exit 1 when the portal answers nothing at all; `[SYNC_STATUS] degraded`
while the first full pass is unfinished; 0 otherwise.

    python3.12 scripts/backfill_consultations_feedback_count.py --apply                 # scheduled form
    python3.12 scripts/backfill_consultations_feedback_count.py --initiative 14674      # one, dry run
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.hys_feedback_scraper import fetch_initiative  # noqa: E402

JOB_KEY = "consultation_feedback_count"


def total_feedback(initiative: dict) -> int:
    """Sum of totalFeedback over every publication of the initiative."""
    return sum(int(p.get("totalFeedback") or 0) for p in (initiative.get("publications") or []))


def _cursor(db) -> tuple[int, bool]:
    row = db.execute(text("SELECT cursor_value, note FROM job_cursors WHERE job_key = :k"),
                     {"k": JOB_KEY}).first()
    if not row:
        return 0, False
    return int(row[0] or 0), bool(row[1] and "full pass done" in row[1])


def _save_cursor(db, value: int, full_pass_done: bool) -> None:
    db.execute(text("""
        INSERT INTO job_cursors (job_key, cursor_value, note, updated_at)
        VALUES (:k, :v, :n, now())
        ON CONFLICT (job_key) DO UPDATE SET cursor_value = EXCLUDED.cursor_value,
            note = EXCLUDED.note, updated_at = now()
    """), {"k": JOB_KEY, "v": str(value),
           "n": "full pass done" if full_pass_done else "first full pass in progress"})
    db.commit()


def _update(db, row_id, iid: str, total: int, apply: bool) -> bool:
    if apply:
        db.execute(text("UPDATE public_consultations SET feedback_count = :c WHERE id = :id"),
                   {"c": total, "id": row_id})
        db.commit()
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-seconds", type=int, default=420)
    ap.add_argument("--initiative", action="append", default=[], help="count just these ids (repeatable)")
    ap.add_argument("--pace", type=float, default=0.15, help="seconds between portal calls")
    args = ap.parse_args()

    deadline = time.monotonic() + args.max_seconds
    db = SessionLocal()
    asked = answered = changed = failed = 0
    try:
        if args.initiative:
            rows = db.execute(text(
                "SELECT id, initiative_id, feedback_count FROM public_consultations "
                "WHERE source = 'commission' AND initiative_id = ANY(:ids)"),
                {"ids": args.initiative}).fetchall()
            hot, drain = rows, []
        else:
            hot = db.execute(text("""
                SELECT id, initiative_id, feedback_count FROM public_consultations
                WHERE source = 'commission' AND initiative_id ~ '^[0-9]+$'
                  AND (status::text ILIKE 'open%' OR end_date >= current_date - 30)
                ORDER BY initiative_id::bigint""")).fetchall()
            start, _ = _cursor(db)
            drain = db.execute(text("""
                SELECT id, initiative_id, feedback_count FROM public_consultations
                WHERE source = 'commission' AND initiative_id ~ '^[0-9]+$'
                  AND initiative_id::bigint > :start
                ORDER BY initiative_id::bigint"""), {"start": start}).fetchall()

        def count(row) -> bool:
            nonlocal asked, answered, changed, failed
            asked += 1
            init = fetch_initiative(str(row.initiative_id))
            time.sleep(args.pace)
            if not init:
                failed += 1
                return False
            answered += 1
            total = total_feedback(init)
            if total != (row.feedback_count or 0):
                changed += 1
                print(f"  {row.initiative_id}: {row.feedback_count or 0} -> {total}")
                _update(db, row.id, str(row.initiative_id), total, args.apply)
            return True

        for row in hot:
            if time.monotonic() > deadline:
                break
            count(row)

        last = None
        wrapped = False
        for row in drain:
            if time.monotonic() > deadline:
                break
            count(row)
            last = int(row.initiative_id)
            if args.apply and asked % 25 == 0:
                _save_cursor(db, last, _cursor(db)[1])
        if args.apply and not args.initiative:
            if drain and last == int(drain[-1].initiative_id):
                _save_cursor(db, 0, True)          # end of the register: wrap round
                wrapped = True
            elif last is not None:
                _save_cursor(db, last, _cursor(db)[1])

        full_done = _cursor(db)[1] if not args.initiative else True
    finally:
        db.close()

    print(f"[count] asked {asked}, answered {answered}, changed {changed}, failed {failed}"
          f"{' (applied)' if args.apply else ' (dry run)'}")
    if asked and not answered:
        print("[ERROR] the Have Your Say portal answered nothing")
        return 1
    if not args.initiative and not full_done:
        print("[SYNC_STATUS] degraded: the first full pass over Commission consultations is not finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
