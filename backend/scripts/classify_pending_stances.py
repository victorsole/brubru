"""Classify consultation responses still waiting for a stance, for the Stakeholder Map.

Why (28 Sep 2026): 10,947 substantive responses to Commission consultations sat at
stance = 'pending'. The extractor's hosted lanes had no key (Qwen direct) or no
credits (Hugging Face), and neither local model loads in the Railway container, so
nothing ever classified them and the Stakeholder Map could colour none of the
respondents it shows. The extractor now also has the chat chain's open-model lanes;
this job drains the backlog in the order the map needs it.

Order: per consultation, round-robin across respondent types (as the map picks its
18 nodes), Transparency-Register-matched organisations first, newest first. Only
the stored excerpt (<= 600 characters) exists, so the classification and its
one-line summary are grounded in that excerpt.

Verdict: exit 1 when rows are waiting and not one could be classified (every lane
failed); `[SYNC_STATUS] degraded` while a backlog remains; 0 when it is clear.

    python3.12 scripts/classify_pending_stances.py --limit 200 --free-only --apply   # scheduled form
    python3.12 scripts/classify_pending_stances.py --limit 3000 --apply              # a paid catch-up
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
# Hugging Face is out of credits: skip it rather than paying a 402 round trip per row.
os.environ.setdefault("SKIP_HF_STANCE", "1")

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.positions.stance_extractor import extract_stance  # noqa: E402

MIN_TEXT = 120   # same floor as the feedback sync: below it a response is boilerplate


def _queue(db, limit: int) -> list:
    return db.execute(text("""
        WITH ranked AS (
            SELECT id, organisation, consultation_title, feedback_excerpt,
                   row_number() OVER (
                       PARTITION BY initiative_id, coalesce(user_type, 'OTHER')
                       ORDER BY (transparency_register_id IS NULL), feedback_date DESC NULLS LAST, id
                   ) AS rank_in_type,
                   initiative_id
            FROM consultation_feedback
            WHERE stance = 'pending' AND length(coalesce(feedback_excerpt, '')) >= :min_text
        )
        SELECT id, organisation, consultation_title, feedback_excerpt
        FROM ranked
        ORDER BY rank_in_type, initiative_id, id
        LIMIT :limit
    """), {"min_text": MIN_TEXT, "limit": limit}).fetchall()


def _backlog(db) -> int:
    return db.execute(text(
        "SELECT count(*) FROM consultation_feedback WHERE stance = 'pending' "
        "AND length(coalesce(feedback_excerpt, '')) >= :m"), {"m": MIN_TEXT}).scalar()


def _save(fid, r) -> None:
    """Write one result as soon as it exists, so a run that dies keeps its work."""
    db = SessionLocal()
    try:
        db.execute(text(
            "UPDATE consultation_feedback SET stance = :s, stance_summary = :sum, last_updated = now() "
            "WHERE id = :id AND stance = 'pending'"),
            {"s": r["stance"], "sum": r.get("summary"), "id": fid})
        db.commit()
    finally:
        db.close()


async def _classify(rows, allow_paid: bool, concurrency: int, deadline: float, apply: bool):
    sem = asyncio.Semaphore(concurrency)
    out = {}

    async def one(r):
        if time.monotonic() > deadline:
            return
        async with sem:
            res = await extract_stance(r.feedback_excerpt, r.organisation or "",
                                       r.consultation_title, allow_paid=allow_paid, local=False)
            out[r.id] = res
            if apply and res.get("stance") not in (None, "pending"):
                await asyncio.to_thread(_save, r.id, res)
            if len(out) % 50 == 0:
                print(f"[stance] {len(out)} processed", flush=True)

    await asyncio.gather(*(one(r) for r in rows))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--free-only", action="store_true", help="never use the paid lane (Scaleway)")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--max-seconds", type=int, default=420)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rows = _queue(db, args.limit)
    backlog = _backlog(db)
    db.close()
    print(f"[stance] backlog {backlog}; this run takes {len(rows)} "
          f"({'free lanes only' if args.free_only else 'free lanes, then paid'})")
    if not rows:
        print("[OK] no pending stances")
        return 0

    deadline = time.monotonic() + args.max_seconds
    results = asyncio.run(_classify(rows, not args.free_only, args.concurrency, deadline, args.apply))

    done = {i: r for i, r in results.items() if r.get("stance") not in (None, "pending")}
    engines = {}
    stances = {}
    for r in done.values():
        engines[r.get("engine", "other")] = engines.get(r.get("engine", "other"), 0) + 1
        stances[r["stance"]] = stances.get(r["stance"], 0) + 1
    print(f"[stance] classified {len(done)} of {len(rows)} | by stance {stances} | by engine {engines}")

    if not args.apply:
        print("[DRY RUN] nothing written; pass --apply")

    left = backlog - (len(done) if args.apply else 0)
    if not done:
        print(f"[ERROR] {len(rows)} row(s) waiting and none classified: every lane failed")
        return 1
    if left > 0:
        print(f"[SYNC_STATUS] degraded: {left} consultation response(s) still pending a stance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
