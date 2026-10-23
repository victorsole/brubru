#!/usr/bin/env python3.12
"""Set eu_laws.date to the date a corrigendum gave the act's title (register O65).

23 Oct 2026: on 20 Oct we reported to the EUR-Lex helpdesk 136 acts whose Cellar work_date_document differed from the
date in their title. The helpdesk corrected Cellar, "except in a few cases where a corrigendum has been published to
correct the date in the original title" (32006D0635, corrected by 32006D0635R(01): "for: 4 April 2006, read: 4 April
2005"). Re-read that day: 106 now match the title; in 26 a corrigendum corrected the title, and the signature, to
Cellar's date. eu_laws held the uncorrected title date for those 26, because leg_folder.act_date (20 Oct) prefers the
title and never reads corrigenda.

A row changes only when three readings agree: the stored date is the one a corrigendum of the act corrects ("for:"),
that corrigendum's "read:" date differs from it, and Cellar's work_date_document today is the "read:" date. Anything
else is reported and left. The corrigenda are read from the LEG_2026-10 folders (Formex) of their eu_laws rows.
Each write is skipped when another writer changed the date since it was read; updated_at moves (a corrected date
partners should receive). Dry run unless --apply.

Usage (from backend/):
    python3.12 scripts/fix_eu_laws_corrigendum_dates.py [--apply] [--backup] [--dump PATH] [CELEX ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))  # production runs with PYTHONPATH=/app (the backend folder)

# The 26 acts of register O65, each read by hand on 23 Oct 2026 (the corrigendum's "read:" date is Cellar's).
O65 = ["32006D0635", "32007D0360", "32007R0580", "32008D0373", "32010D0183", "32010L0089", "32011R0683", "32016D1790",
       "32019D1798", "32020D0422(01)", "32020D1188", "32020R0730", "32021D0357", "32021D0486", "32021D0856",
       "32022D1313", "32022D2417", "32022D2435", "32022D2571", "32022L2523", "32022R0363", "32022R0364",
       "32023D0804(02)", "32023D1598", "32023R1593", "32023R1803"]

def decide(stored, pairs, cellar):
    """(new date, None) when the three readings agree, else (None, why)."""
    news = {c[1] for c in pairs if c[0] == stored}
    if not news:
        return None, f"no corrigendum corrects {stored} (pairs {pairs[:3]})"
    if len(news) > 1:
        return None, f"corrigenda disagree: {sorted(news)}"
    new = news.pop()
    if cellar != [new]:
        return None, f"corrigendum reads {new}, Cellar says {cellar}"
    return new, None


def _main_checkout() -> Path:
    """The main checkout, which holds the untracked .env, docs/LEG_2026-10 and data/backups, when run from a worktree."""
    out = subprocess.run(["git", "-C", str(BACKEND), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                         capture_output=True, text=True).stdout.strip()
    return Path(out).parent if out else BACKEND.parent


def main() -> int:
    main_tree = _main_checkout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("celex", nargs="*", help="acts to check (default: the 26 of register O65)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", action="store_true", help="write the replaced dates to backend/data/backups first")
    ap.add_argument("--dump", default=str(main_tree / "docs/LEG_2026-10"), help="the LEG_2026-10 folders")
    a = ap.parse_args()
    import logging
    from dotenv import load_dotenv
    load_dotenv(BACKEND.parent / ".env" if (BACKEND.parent / ".env").exists() else main_tree / ".env")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    from sqlalchemy import text
    from core.database import SessionLocal
    from scripts.fix_eu_laws_dates import cellar_dates
    from scripts.leg_folder import corrigendum_text, title_date_corrections
    dump = Path(a.dump)
    if not dump.is_dir():
        print(f"[ERROR] no LEG_2026-10 folders at {dump}", file=sys.stderr)
        return 2
    acts = a.celex or O65

    db = SessionLocal()
    try:
        rows = {r[1]: r for r in db.execute(text("SELECT id, celex, date::text FROM eu_laws WHERE celex = ANY(:c)"),
                                            {"c": acts}).fetchall()}
        corr = db.execute(text("SELECT celex, uuid FROM eu_laws WHERE celex ~ '^3.*R\\(\\d\\d\\)$' "
                               "AND regexp_replace(celex, 'R\\(\\d\\d\\)$', '') = ANY(:c)"), {"c": acts}).fetchall()
        db.rollback()
        corr_of: dict[str, list] = {}
        for celex, uuid in corr:
            corr_of.setdefault(re.sub(r"R\(\d\d\)$", "", celex), []).append((celex, uuid))
        cellar = {c: [d] for c, d in cellar_dates(acts).items()}
        changes, left = [], []
        for c in acts:
            if c not in rows:
                left.append((c, "not in eu_laws"))
                continue
            i, _, stored = rows[c]
            pairs = []
            for k, uuid in sorted(corr_of.get(c, [])):
                if uuid and (dump / uuid).is_dir():
                    pairs += title_date_corrections(corrigendum_text(dump / uuid), c)
            new, why = decide(stored, pairs, cellar.get(c, []))
            if new:
                changes.append((i, c, stored, new))
            else:
                left.append((c, why))
        print(f"[INFO] {len(acts)} acts | to change: {len(changes)} | left: {len(left)}")
        for c in changes:
            print(f"[INFO]   {c[1]}: {c[2]} -> {c[3]}")
        for c, why in left:
            print(f"[INFO]   left {c}: {why}")
        if not a.apply:
            print("[DRY-RUN] nothing written")
            return 0
        if a.backup and changes:
            path = main_tree / f"backend/data/backups/eu_laws_corrigendum_dates_before_{dt.datetime.now():%Y%m%d_%H%M}.json"
            path.parent.mkdir(parents=True, exist_ok=True)  # untracked: absent from a fresh checkout
            path.write_text(json.dumps({"columns": ["id", "celex", "date_before", "date_after"], "rows": changes,
                                        "restore": "set date back to date_before by id"}))
            print(f"[OK] backup of {len(changes)} rows -> {path}")
        done = []
        for i, c, old, new in changes:
            got = db.execute(text("UPDATE eu_laws SET date = CAST(:new AS date) WHERE id = :i "
                                  "AND date IS NOT DISTINCT FROM CAST(:old AS date) RETURNING id"),
                             {"new": new, "i": i, "old": old}).fetchall()
            db.commit()
            done += [c] if got else []
        after = dict(db.execute(text("SELECT celex, date::text FROM eu_laws WHERE celex = ANY(:c)"),
                                {"c": [c[1] for c in changes]}).fetchall())
        db.rollback()
        right = sum(after.get(c[1]) == c[3] for c in changes)
        print(f"[OK] written: {len(done)} of {len(changes)} (a row another writer changed meanwhile is left)")
        print(f"[VERIFY] re-read: {right} of {len(changes)} hold the corrected date")
        return 0 if right == len(changes) else 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
