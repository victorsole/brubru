#!/usr/bin/env python3.12
"""Retype Cedefop's calls for proposals from 'tender' to 'grant'.

API audit, 16 Oct 2026 (step 2, Cedefop): 89 procedures whose page states
"Procurement type: Call for proposals" were stored as tenders. The writer now types them
grant and /funding/cedefop-grants serves them, but the nightly run re-opens only the
newest pages, and a re-read could not move a row anyway: item_type is part of the
upsert's conflict key, so a grant item would be INSERTED beside the tender row. The
stored rows are therefore retyped once, before the new writer runs.

The rows keep their ids and their procurement_documents (linked by economy_item_id;
the documents writer selects by source_kind, not type). Backup first; one row per
transaction. Dry run by default; --apply writes.

    python3.12 -m backend.scripts.repair_cedefop_grant_type [--apply]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402

BACKUPS = _REPO_ROOT / "backend" / "data" / "backups"

_SELECT = text("""
    SELECT id, item_type, title, public_url, tender_reference
      FROM economy_items
     WHERE body_code = 'cedefop' AND item_type <> 'grant'
       AND body_txt ~ 'Procurement type: Call for proposals'
     ORDER BY id""")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write the new type (default: dry run)")
    a = p.parse_args()
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(_SELECT)]
        clash = c.execute(text(
            "SELECT count(*) FROM economy_items g JOIN economy_items t ON t.body_code = g.body_code "
            "AND t.public_url = g.public_url WHERE g.body_code = 'cedefop' AND g.item_type = 'grant' "
            "AND t.item_type <> 'grant'")).scalar()
    print(f"[INFO] {len(rows)} Cedefop calls for proposals stored as "
          f"{sorted({r['item_type'] for r in rows})}; {clash} would clash with an existing grant row")
    for r in rows[:5]:
        print(f"  {r['id']:>8} {r['item_type']:<8} {r['tender_reference'] or '':<32} {r['title'][:50]}")
    if clash:
        print("[ERROR] a grant row already exists for a page to retype: resolve by hand first")
        return 2
    if not rows:
        return 0
    if not a.apply:
        print("[INFO] dry run; re-run with --apply to write")
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"cedefop_grant_type_before_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M')}.json"
    backup.write_text(json.dumps(rows, default=str, indent=1))
    print(f"[INFO] backup: {backup}")
    written = 0
    for r in rows:
        with engine.begin() as c:   # one row per transaction
            written += c.execute(text("UPDATE economy_items SET item_type = 'grant' "
                                      "WHERE id = :id AND item_type = :old"),
                                 {"id": r["id"], "old": r["item_type"]}).rowcount
    with engine.connect() as c:
        left = c.execute(_SELECT).fetchall()
        n = c.execute(text("SELECT count(*) FROM economy_items WHERE body_code = 'cedefop' "
                           "AND item_type = 'grant'")).scalar()
    print(f"[OK] {written} of {len(rows)} rows retyped; cedefop grants now {n}; still mistyped: {len(left)}")
    return 0 if written == len(rows) and not left else 1


if __name__ == "__main__":
    sys.exit(main())
