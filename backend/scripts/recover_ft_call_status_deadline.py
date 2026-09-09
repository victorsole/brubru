#!/usr/bin/env python3.12
"""Recover `status` and `deadline` on ft_calls_for_proposals rows that have neither.

The problem
-----------
Measured 9 September 2026: **772 of 1,881 calls (41%) sat at `status='unknown'`**, and
**771 of those had no deadline** -- one population, not two defects. Only **76 of
1,881 (4%)** carried a future deadline at all, so a caller could not answer "what can
I still apply to" by either field.

764 of the 772 have a proper topic identifier (`HORIZON-...`, `LIFE-...`); the
remaining 8 are UUID- or numeric-keyed rows that are a separate question.

What is and is not recoverable, measured rather than assumed
-----------------------------------------------------------
The SEDIA *search* API answers this for **roughly a quarter** of them. Sampling 8
real-topic-id rows: `ISF-2024-TF2-AG-COP` came back closed with deadline 2024-10-08
and `LIFE-2021-CET-HOMERENO` closed with 2022-01-12, while the other six carry
`status=None` and `deadlineDate=None` in the search record itself. The richer values
live behind the portal's `topicDetails` endpoint, which is keyed by an INTERNAL id
(`.../topicDetails/3725COMPETITIV...`), not the topic identifier -- and the statusless
search records do not carry that id, so this script cannot reach it. Guessing the URL
was tried and 404s; per `feedback_ep_url_no_guessing` it is not retried here.

So this script is deliberately partial and says so. It recovers what the publisher
actually exposes and leaves the rest honestly `unknown` rather than inventing a
status, which is the whole point of having an `unknown` value
([[feedback_backfill_no_hallucination]]).

English is preferred among the language variants because they DISAGREE: for one
topic the `en` record reported `31094503` (closed) while `sv` and `fr` reported
`31094501` (forthcoming). Taking whichever arrived first is how a wrong status gets
stored.

Usage
-----
    python3.12 -m backend.scripts.recover_ft_call_status_deadline --dry-run
    python3.12 -m backend.scripts.recover_ft_call_status_deadline --apply
    python3.12 -m backend.scripts.recover_ft_call_status_deadline --apply --limit 50
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
from collections import Counter

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND), str(_BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from ingest_funding_sedia import (  # noqa: E402
    STATUS_MAP, fetch_sedia_page, first_or_none, parse_iso_date,
)

DELAY = 0.6
# Small on purpose. Each candidate costs a SEDIA round trip and only a minority
# recover, so a 40-row batch meant the first commit landed ~200 lookups in --
# long enough that a healthy run looked indistinguishable from a stuck one, and I
# killed a working job over it. Frequent commits make progress observable and cap
# what an interruption loses.
BATCH = 10

# Rows with a real topic identifier. UUID/numeric-keyed rows are excluded because
# they are not topics and would only add noise to the outcome counts.
CANDIDATE_SQL = """
SELECT topic_id, status, deadline, title
FROM ft_calls_for_proposals
WHERE topic_id ~ '^[A-Z0-9]+-'
  AND (status = 'unknown' OR status IS NULL OR deadline IS NULL)
ORDER BY topic_id
"""


def counts(db) -> dict:
    r = db.execute(text(
        "SELECT count(*) AS rows, "
        "count(*) FILTER (WHERE status = 'unknown' OR status IS NULL) AS unknown_status, "
        "count(*) FILTER (WHERE deadline IS NULL) AS no_deadline, "
        "count(*) FILTER (WHERE deadline > now()) AS future_deadline "
        "FROM ft_calls_for_proposals"
    )).mappings().one()
    return dict(r)


def sedia_lookup(topic_id: str):
    """(status, deadline) for one topic from the SEDIA search API, English preferred.

    Returns (None, None) when SEDIA's search record genuinely carries neither, which
    is the majority case and is not an error.
    """
    j = fetch_sedia_page(1, page_size=40, text=topic_id)
    matched = [r for r in (j.get("results") or [])
               if first_or_none((r.get("metadata") or {}).get("identifier")) == topic_id]
    if not matched:
        return None, None
    english = [m for m in matched
               if (first_or_none((m.get("metadata") or {}).get("language")) or "").lower() == "en"]
    md = (english or matched)[0].get("metadata") or {}
    code = str(first_or_none(md.get("status")))
    status = STATUS_MAP.get(code)          # None when absent or unmapped
    deadline = parse_iso_date(first_or_none(md.get("deadlineDate")))
    return status, deadline


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = counts(db)
        print(f"[INFO] before: {before}")

        sql = CANDIDATE_SQL + (f" LIMIT {int(args.limit)}" if args.limit else "")
        rows = db.execute(text(sql)).mappings().all()
        print(f"[INFO] candidates (real topic ids, missing status or deadline): {len(rows)}")
        if not rows:
            print("[OK] nothing to do")
            return 0

        out = Counter()
        pending = []
        for n, r in enumerate(rows, 1):
            tid = r["topic_id"]
            try:
                status, deadline = sedia_lookup(tid)
            except Exception as exc:  # noqa: BLE001
                out[f"lookup_error:{type(exc).__name__}"] += 1
                time.sleep(DELAY)
                continue

            # Only write a value we actually obtained, and never downgrade a value
            # the row already holds.
            new_status = status if (status and (r["status"] in (None, "unknown"))) else None
            new_deadline = deadline if (deadline and r["deadline"] is None) else None
            if new_status or new_deadline:
                pending.append({"tid": tid,
                                "s": new_status or r["status"],
                                "d": new_deadline or r["deadline"]})
                out["recovered_status" if new_status else "recovered_deadline_only"] += 1
            else:
                out["not_in_sedia_search"] += 1
            time.sleep(DELAY)

            if args.apply and len(pending) >= BATCH:
                db.execute(text("UPDATE ft_calls_for_proposals "
                                "SET status = :s, deadline = :d, last_updated = now() "
                                "WHERE topic_id = :tid"), pending)
                db.commit()
                print(f"[INFO] committed {len(pending)}  ({n}/{len(rows)})  {dict(out)}")
                pending = []
            elif n % 100 == 0:
                print(f"[INFO] {n}/{len(rows)} looked up  {dict(out)}")

        if args.apply and pending:
            db.execute(text("UPDATE ft_calls_for_proposals "
                            "SET status = :s, deadline = :d, last_updated = now() "
                            "WHERE topic_id = :tid"), pending)
            db.commit()
            print(f"[INFO] committed final {len(pending)}")

        print(f"[INFO] outcomes: {dict(out)}")
        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        after = counts(db)
        print(f"[INFO] after : {after}")
        print(f"[INFO] unknown_status {before['unknown_status']} -> {after['unknown_status']}, "
              f"no_deadline {before['no_deadline']} -> {after['no_deadline']}, "
              f"future_deadline {before['future_deadline']} -> {after['future_deadline']}")
        left = after["unknown_status"]
        if left:
            print(f"[INFO] {left} row(s) remain 'unknown'. That is the honest state: the "
                  "SEDIA search record carries no status for them, and the richer "
                  "topicDetails endpoint is keyed by an internal id these records do "
                  "not expose. Not a failure of this script -- do not invent a status.")
        print("[OK] recovery pass complete")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
