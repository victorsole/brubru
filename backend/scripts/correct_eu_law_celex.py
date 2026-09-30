"""Correct eu_laws CELEX values that the Publications Office does not have.

GovClipping checked the CELEX values we serve and found 9.8% that do not exist in Cellar;
our own audit of all 19,081 distinct values found 1,897 (9.9%). The cause is
`derive_celex()` in the OJ scraper, which BUILDS a CELEX from the OJ number and a letter
looked up from the parsed act type, so a Directive read as a Regulation becomes
32023R2413 (the real RED III is 32023L2413) and a corrigendum's OJ number becomes a CELEX
that never existed.

A correction is only written when three independent checks agree:

  1. Cellar HAS the candidate (same year and number, different document-type letter, or
     year and number transposed), and it is the ONLY candidate that exists.
  2. The candidate is not already in eu_laws. 27 were, and inspecting them showed why this
     matters: our 32005L0649 is a Commission Decision of 13 September 2005, while Cellar's
     32005D0649 is Decision No 649/2005/EC of the Parliament and Council. Applying it
     would have merged two unrelated laws.
  3. Cellar's title for the candidate MATCHES our stored title. This rejected 88 more:
     our 31049D2001 is an EU-OSHA Administrative Board decision and Cellar's 32001R1049 is
     the Regulation on public access to documents. Existence is not identity.

115 of 1,189 candidates failed a check and are left alone. The 360 ambiguous and 348
unresolved are not touched either: reported, not guessed.

Because a changed CELEX reads to a client as a new record, every change is written to an
old -> new mapping file to hand over, and eu_laws.id (now exposed on /laws) is the
identifier that does not move.

Usage (from backend/):
    python3.12 scripts/correct_eu_law_celex.py --input <verified.json>           # dry run
    python3.12 scripts/correct_eu_law_celex.py --input <verified.json> --apply
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="celex_verified.json from the audit")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    confirmed = {bad: v["to"] for bad, v in payload["confirmed"].items()}
    # The ROW each correction belongs to. Keying an UPDATE on the old CELEX alone is
    # unsafe after an ordered swap: the value one row vacates is the value another row
    # is corrected into, so a second run would move the wrong row onto an occupied
    # target. The collision check happens to stop it; the row id makes it impossible.
    row_of = {bad: v.get("row_id") for bad, v in payload["confirmed"].items()}
    print(f"[INFO] {len(confirmed):,} title-confirmed correction(s)")

    # Two different wrong values must not be corrected onto the same CELEX.
    targets: dict[str, list[str]] = {}
    for bad, good in confirmed.items():
        targets.setdefault(good, []).append(bad)
    clashes = {g: b for g, b in targets.items() if len(b) > 1}
    if clashes:
        print(f"[INFO] {len(clashes)} target(s) claimed by more than one row; skipping those")
        for g in clashes:
            for b in targets[g]:
                confirmed.pop(b, None)

    db = SessionLocal()
    try:
        # Re-check against the live table, not against the audit's snapshot.
        existing = {r[0] for r in db.execute(text(
            "SELECT DISTINCT celex FROM eu_laws WHERE celex IS NOT NULL")).fetchall()}

        # A target held by a row that is ITSELF moving is not a collision, it is an
        # ORDERED SWAP: move the holder first and the target frees up. Treating it as a
        # collision silently dropped all four pairs GovClipping flagged on 29 Sep 2026.
        # 32011L0061 is held by the Israel adequacy Decision and wanted by AIFMD, which
        # sits on 32011R0061 -- a CELEX that belongs to a real, unrelated Regulation.
        moving = set(confirmed)

        # Three states, not two. On a SECOND run every old value is gone, so every
        # correction looks like a collision and the script reported "1,098 skipped,
        # 4 will be applied" for a database that was already entirely correct. A run
        # that has nothing to do must say so, or the next person reads a finished job
        # as a broken one.
        done = [b for b in confirmed if b not in existing]
        for b in done:
            confirmed.pop(b)
        if done:
            print(f"[INFO] {len(done):,} correction(s) already applied; nothing to do for them")

        hard = [b for b, g in confirmed.items() if g in existing and g not in moving]
        for b in hard:
            confirmed.pop(b)
        if hard:
            print(f"[INFO] {len(hard)} correction(s) collide with a row that is NOT moving; skipped")
        swaps = [b for b, g in confirmed.items() if g in existing]
        if swaps:
            print(f"[INFO] {len(swaps)} correction(s) are ordered swaps; the holder moves first")
        if not confirmed:
            print("[OK] nothing left to correct")
            return 0
        print(f"[INFO] {len(confirmed):,} correction(s) will be applied")

        if not args.apply:
            for b, g in list(confirmed.items())[:8]:
                print(f"   {b} -> {g}")
            print("[DRY-RUN] re-run with --apply")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = db.execute(text(
            "SELECT id, celex, left(coalesce(title,''),200) FROM eu_laws WHERE celex = ANY(:c)"),
            {"c": list(confirmed)}).fetchall()
        mapping = [{"id": r[0], "old_celex": r[1], "new_celex": confirmed[r[1]], "title": r[2]}
                   for r in rows]
        out = BACKUP_DIR / f"eu_laws_celex_corrections_{stamp}.json"
        out.write_text(json.dumps(mapping, indent=1), encoding="utf-8")
        print(f"[BACKUP] {len(mapping):,} row(s) recorded in {out}")

        # Repeated passes rather than one: a correction is applied only when its target
        # is free, so an ordered swap resolves on the pass after its holder has moved.
        applied_ids: dict[str, str] = {}
        pending = dict(confirmed)
        changed = 0
        for pass_no in range(1, 11):
            taken = {r[0] for r in db.execute(text(
                "SELECT celex FROM eu_laws WHERE celex IS NOT NULL")).fetchall()}
            ready = {b: g for b, g in pending.items() if g not in taken}
            if not ready:
                break
            for bad, good in ready.items():
                rid = row_of.get(bad)
                if rid:
                    res = db.execute(text(
                        "UPDATE eu_laws SET celex = :good, updated_at = now() "
                        "WHERE id = :rid AND celex = :bad RETURNING id"),
                        {"good": good, "bad": bad, "rid": int(rid)}).fetchall()
                else:
                    res = db.execute(text(
                        "UPDATE eu_laws SET celex = :good, updated_at = now() "
                        "WHERE celex = :bad RETURNING id"), {"good": good, "bad": bad}).fetchall()
                for row in res:
                    applied_ids[str(row[0])] = good
                changed += len(res)
                pending.pop(bad)
            db.commit()
            print(f"[PASS {pass_no}] applied {len(ready)}, {len(pending)} still waiting")
        if pending:
            print(f"[WARN] {len(pending)} correction(s) never became applicable: "
                  f"{list(pending)[:5]}")
        print(f"[APPLIED] {changed:,} row(s) re-celexed")

        # Records with no CELEX of their own: drafts, association-council acts, EEA
        # declarations, annex fragments. NULL, never a fabricated identifier.
        nulled = 0
        for rec in payload.get("to_null", []):
            nulled += db.execute(text(
                "UPDATE eu_laws SET celex = NULL, updated_at = now() "
                "WHERE id = :i AND celex = :c"),
                {"i": int(rec["id"]), "c": rec["celex"]}).rowcount
        db.commit()
        print(f"[NULLED] {nulled} record(s) that have no CELEX of their own")

        # The row id is the identifier that does not move; record what each row now holds
        # so the acceptance suite can prove no row was created or replaced.
        payload["applied_ids"] = applied_ids
        Path(args.input).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                    encoding="utf-8")

        left = db.execute(text(
            "SELECT count(*) FROM eu_laws WHERE celex = ANY(:c)"), {"c": list(confirmed)}).scalar()
        dupes = db.execute(text(
            "SELECT count(*) FROM (SELECT celex FROM eu_laws WHERE celex IS NOT NULL "
            "GROUP BY celex HAVING count(*) > 1) z")).scalar()
        print(f"[VERIFY] old CELEX values still present: {left}   "
              f"CELEX values now held by >1 row: {dupes}")
        return 0 if left == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
