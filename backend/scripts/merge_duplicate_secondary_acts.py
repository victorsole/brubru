"""One EU act, one record: merge secondary_acts rows that share a CELEX.

GovClipping identifies acts by CELEX, so an act stored twice means whichever record they
process last wins, and the loser was usually the one with the full text: 64 delegated and
7 implementing acts inside their sync window, 783 CELEX values across the whole table.

The extra row is almost always a cascade stub. `backfill_regulatory_cascade.py` writes the
CELEX itself into `reference` and upserts ON CONFLICT (reference), so an act already stored
under its Commission document number (C(2013)9763 for 32014R0241) did not collide and was
inserted again, with no text_body and a 128-character "Derived from ..." description.

Merging is not deleting. Measured before writing anything: 729 pairs agree on
parent_celex, 22 have it ONLY on the stub, and 28 name two different and equally real
parents (32017R1569 supplements Regulation (EU) 536/2014 AND Directive 2001/20/EC, and the
column holds one). Four more pairs are two real rows sharing a CELEX under different
Commission document numbers. So the survivor absorbs the losers into `merged_from` and
inherits a parent it was missing, and every deleted row is written to a backup file first.

Survivor: most body text, then the row whose reference is NOT its own CELEX (a real
register entry beats a derived stub), then the earliest first_seen.

A second wave of 80 duplicates arrived on 30 September 2026, from the same root cause in
a different script: ingest_regdel_acts.py also upserted ON CONFLICT (reference). That is
now fixed at the source and migration 258 adds a partial unique index on celex, so the
database itself refuses a second row for one act. This script stays for the cleanup, and
gained two guards on that run:

  * --rehearse applies the whole merge inside a transaction, checks the invariants and
    rolls back, so the plan can be proven before anything is written.
  * the invariants are checked BEFORE the commit, not after. A merge that loses a
    character of body text, a distinct CELEX, or an unexpected row is rolled back. On
    the 30 September wave 32 of 73 pairs held their full text on the row being deleted
    (32024R0870: 120,902 characters there, none on the survivor), which rank() handles
    correctly -- but "already correct" is not "proven correct on this run".

Usage (from backend/):
    python3.12 scripts/merge_duplicate_secondary_acts.py            # dry run
    python3.12 scripts/merge_duplicate_secondary_acts.py --rehearse # apply, check, undo
    python3.12 scripts/merge_duplicate_secondary_acts.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

BACKUP_DIR = BACKEND.parent / "docs" / "backups"

_FETCH = """
SELECT id::text, celex, reference, act_type::text, parent_celex,
       coalesce(length(text_body), 0) AS text_len,
       first_seen, description
FROM secondary_acts
WHERE celex IS NOT NULL
  AND celex IN (SELECT celex FROM secondary_acts WHERE celex IS NOT NULL
                GROUP BY celex HAVING count(*) > 1)
ORDER BY celex
"""


def rank(row: dict) -> tuple:
    """Lower sorts first: the survivor. Text wins, then a real reference, then age."""
    is_stub = row["reference"] == row["celex"]
    return (-row["text_len"], 1 if is_stub else 0, row["first_seen"] or datetime.max)


def _snapshot(db) -> dict:
    """What must not change when rows are merged away.

    Added 30 Sep 2026 after a second wave of 80 duplicates. The merge deletes rows, and
    the thing most worth losing is text: on that wave 32 of 73 pairs held their full body
    on the row being deleted (32024R0870 had 120,902 characters there and none on the
    survivor). The rank() below already prefers the row with the most text, so the body
    is kept, but "already correct" is not the same as "proven correct on this run".
    """
    r = db.execute(text("""
        SELECT count(*),
               coalesce(sum(length(text_body)), 0),
               coalesce(sum(length(body_html)), 0),
               count(DISTINCT celex) FILTER (WHERE celex IS NOT NULL),
               count(*) FILTER (WHERE celex IS NULL)
        FROM secondary_acts""")).fetchone()
    return {"rows": r[0], "text": r[1], "html": r[2], "celex": r[3], "no_celex": r[4]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rehearse", action="store_true",
                    help="apply inside a transaction, check the invariants, then ROLL BACK")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = _snapshot(db)
        rows = [dict(r._mapping) for r in db.execute(text(_FETCH)).fetchall()]
        groups: dict[str, list] = {}
        for r in rows:
            groups.setdefault(r["celex"], []).append(r)
        print(f"[INFO] {len(groups):,} CELEX values with more than one row "
              f"({len(rows):,} rows)")

        plan, inherited, parents_kept = [], 0, 0
        for celex, members in groups.items():
            members.sort(key=rank)
            survivor, losers = members[0], members[1:]
            absorbed = [{
                "id": l["id"], "reference": l["reference"], "parent_celex": l["parent_celex"],
                "first_seen": l["first_seen"].isoformat() if l["first_seen"] else None,
                "source": "cascade_stub" if l["reference"] == l["celex"] else "register",
            } for l in losers]
            new_parent = survivor["parent_celex"]
            if not new_parent:
                for l in losers:
                    if l["parent_celex"]:
                        new_parent = l["parent_celex"]; inherited += 1
                        break
            # Only a genuine conflict: the survivor already had a parent and the loser
            # names a different one. Both are real (an act can supplement two acts), and
            # the column holds one, so the other survives in merged_from.
            if survivor["parent_celex"] and any(
                    l["parent_celex"] and l["parent_celex"] != survivor["parent_celex"]
                    for l in losers):
                parents_kept += 1
            plan.append((celex, survivor, losers, absorbed, new_parent))

        print(f"[INFO] {sum(len(p[2]) for p in plan):,} row(s) would be merged away")
        print(f"[INFO] {inherited} survivor(s) inherit a parent_celex they were missing")
        print(f"[INFO] {parents_kept} group(s) keep a second, different parent in merged_from")
        for celex, s, losers, _, np in plan[:5]:
            print(f"   {celex}: keep {s['reference']} ({s['text_len']:,} chars, parent {np}) "
                  f"<- drop {', '.join(l['reference'] for l in losers)}")

        if not (args.apply or args.rehearse):
            body_on_loser = sum(
                1 for _, s, losers, _, _ in plan
                if any(l["text_len"] > s["text_len"] for l in losers))
            if body_on_loser:
                print(f"[WARN] {body_on_loser} group(s) hold more text on a row that would "
                      f"be deleted than on the survivor; rank() should prevent this")
            print("[DRY-RUN] re-run with --rehearse to apply and roll back, "
                  "or --apply to commit")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup = BACKUP_DIR / f"secondary_acts_merged_{stamp}.json"
        # Every row about to be deleted, in full, before anything is written.
        doomed = [l["id"] for _, _, losers, _, _ in plan for l in losers]
        full = db.execute(text(
            "SELECT row_to_json(s) FROM secondary_acts s WHERE id::text = ANY(:ids)"),
            {"ids": doomed}).scalars().all()
        backup.write_text(json.dumps(full, indent=1, default=str), encoding="utf-8")
        print(f"[BACKUP] {len(full):,} row(s) written to {backup}")
        if len(full) != len(doomed):
            print(f"[ERROR] backed up {len(full)} of {len(doomed)}: refusing to delete")
            return 1

        for celex, survivor, losers, absorbed, new_parent in plan:
            db.execute(text(
                "UPDATE secondary_acts SET merged_from = :m, parent_celex = :p, "
                "last_updated = now() WHERE id::text = :id"),
                {"m": json.dumps(absorbed), "p": new_parent, "id": survivor["id"]})
            db.execute(text("DELETE FROM secondary_acts WHERE id::text = ANY(:ids)"),
                       {"ids": [l["id"] for l in losers]})
        # Verify from the database, not from the loop that just wrote it -- and BEFORE the
        # commit, so a merge that broke an invariant can still be rolled back. Checking
        # after committing only tells you what you have already lost.
        after = _snapshot(db)
        deleted = sum(len(p[2]) for p in plan)
        problems = []
        if after["text"] < before["text"]:
            problems.append(f"text_body lost {before['text'] - after['text']:,} characters")
        if after["html"] < before["html"]:
            problems.append(f"body_html lost {before['html'] - after['html']:,} characters")
        if after["celex"] != before["celex"]:
            problems.append(f"distinct CELEX moved {before['celex']} -> {after['celex']}")
        if after["no_celex"] != before["no_celex"]:
            problems.append(f"rows without a CELEX moved "
                            f"{before['no_celex']} -> {after['no_celex']}")
        if after["rows"] != before["rows"] - deleted:
            problems.append(f"row count is {after['rows']}, expected "
                            f"{before['rows'] - deleted}")
        left = db.execute(text(
            "SELECT count(*) FROM (SELECT celex FROM secondary_acts WHERE celex IS NOT NULL "
            "GROUP BY celex HAVING count(*) > 1) z")).scalar()
        if left:
            problems.append(f"{left} duplicate CELEX still present")

        if problems:
            db.rollback()
            print("\n[ROLLED BACK] the merge broke an invariant and nothing was written:")
            for p in problems:
                print(f"   - {p}")
            return 1

        kept = db.execute(text(
            "SELECT count(*) FROM secondary_acts WHERE merged_from IS NOT NULL")).scalar()
        print(f"[VERIFY] duplicate CELEX remaining: {left}   rows carrying merged_from: {kept}")
        print(f"[VERIFY] no text lost ({after['text']:,} chars), no CELEX lost "
              f"({after['celex']:,}), {deleted} row(s) removed as planned")

        if args.rehearse:
            db.rollback()
            print("[REHEARSAL] rolled back; the database is untouched")
            return 0

        db.commit()
        print(f"[APPLIED] merged {len(plan):,} group(s)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
