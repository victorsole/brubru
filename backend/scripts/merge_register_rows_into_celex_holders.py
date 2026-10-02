"""Merge a bodyless register row into the row that already holds its act under the CELEX.

backfill_secondary_act_celex_from_cellar.py reads each register row's CELEX from Cellar
by its Commission document number. For 63 rows the CELEX it read is already held by
another secondary_acts row (the OJ copy, with full text), so the register row is a
second record of one act. ux_secondary_acts_celex refuses to give both rows the CELEX,
which is why merge_duplicate_secondary_acts.py (it groups rows that SHARE a CELEX)
cannot see these pairs.

Same rules as that script: the row with the text survives, the register row is
absorbed into its merged_from (with its reference, so C(2021)2449 still resolves to the
act), a missing parent_celex is inherited, every deleted row is backed up in full
first, and the invariants (no text lost, no CELEX lost, row count) are checked before
the commit.

Input: backend/data/secondary_act_duplicates.json, written by the Cellar backfill.

    python3.12 scripts/merge_register_rows_into_celex_holders.py --rehearse
    python3.12 scripts/merge_register_rows_into_celex_holders.py --apply
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

PAIRS = BACKEND / "data" / "secondary_act_duplicates.json"
BACKUP_DIR = BACKEND.parent / "docs" / "backups"


def _snapshot(db) -> dict:
    r = db.execute(text("""
        SELECT count(*), coalesce(sum(length(text_body)), 0), coalesce(sum(length(body_html)), 0),
               count(DISTINCT celex) FILTER (WHERE celex IS NOT NULL)
          FROM secondary_acts""")).fetchone()
    return {"rows": r[0], "text": r[1], "html": r[2], "celex": r[3]}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    pairs = json.loads(PAIRS.read_text())
    db = SessionLocal()
    try:
        before = _snapshot(db)
        plan = []
        for p in pairs:
            loser = db.execute(text(
                "SELECT row_to_json(s) FROM secondary_acts s WHERE id::text = :i"),
                {"i": p["bodyless_id"]}).scalar()
            holder = db.execute(text(
                "SELECT id::text, celex, parent_celex, merged_from, coalesce(length(text_body),0) "
                "FROM secondary_acts WHERE id::text = :i"), {"i": p["held_by_id"]}).fetchone()
            if not loser or not holder or holder[1] != p["celex"]:
                print(f"   skip {p['reference']}: pair no longer as recorded")
                continue
            if (loser.get("text_body") or "") and len(loser["text_body"]) > holder[4]:
                print(f"   skip {p['reference']}: the register row holds more text")
                continue
            plan.append((p, loser, holder))
        print(f"[INFO] pairs to merge: {len(plan)} of {len(pairs)}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backup = BACKUP_DIR / f"secondary_acts_register_merged_{stamp}.json"
        backup.write_text(json.dumps([l for _, l, _ in plan], indent=1, default=str))
        print(f"[BACKUP] {len(plan)} row(s) written to {backup.name}")

        for p, loser, (hid, celex, parent, merged, _) in plan:
            absorbed = list(merged or []) if isinstance(merged, list) else (
                json.loads(merged) if merged else [])
            absorbed.append({"id": loser["id"], "reference": loser["reference"],
                             "parent_celex": loser.get("parent_celex"),
                             "first_seen": loser.get("first_seen"), "source": "register"})
            db.execute(text(
                "UPDATE secondary_acts SET merged_from = :m, parent_celex = :pc, "
                "last_updated = now() WHERE id::text = :id"),
                {"m": json.dumps(absorbed, default=str),
                 "pc": parent or loser.get("parent_celex"), "id": hid})
            db.execute(text("DELETE FROM secondary_acts WHERE id::text = :i"), {"i": loser["id"]})

        after = _snapshot(db)
        problems = []
        if after["text"] < before["text"]:
            problems.append(f"text_body lost {before['text'] - after['text']:,} chars")
        if after["html"] < before["html"]:
            problems.append(f"body_html lost {before['html'] - after['html']:,} chars")
        if after["celex"] != before["celex"]:
            problems.append(f"distinct CELEX moved {before['celex']} -> {after['celex']}")
        if after["rows"] != before["rows"] - len(plan):
            problems.append(f"rows {after['rows']}, expected {before['rows'] - len(plan)}")
        if problems:
            db.rollback()
            print("[ROLLED BACK]", "; ".join(problems))
            return 1
        print(f"[VERIFY] rows {before['rows']} -> {after['rows']}, no text or CELEX lost")
        if args.rehearse:
            db.rollback()
            print("[REHEARSAL] rolled back")
            return 0
        db.commit()
        print(f"[APPLIED] merged {len(plan)} register row(s) into their CELEX holder")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
