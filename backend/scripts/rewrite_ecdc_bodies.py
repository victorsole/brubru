#!/usr/bin/env python3.12
"""Rewrite the ECDC procedure bodies that state a rejected date or an escaped link.

API audit, 16 Oct 2026 (step 2, ECDC): 28 bodies said "Published: 2017-07-27" (the
site-migration day the date field rejects) and 3 carried Funding & Tenders links with
"&amp;". The writer is fixed, but the nightly run re-opens only the two newest listing
pages and the open procedures, so these old pages are re-read once here and their body
and date rewritten by the writer. Backup first; one row per transaction; ECDC is paced
(2 s between requests, backoff on 429). Dry run by default; --apply writes.

    python3.12 -m backend.scripts.rewrite_ecdc_bodies [--apply]
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
from services.scrapers import agency_procurement as ap  # noqa: E402

BACKUPS = _REPO_ROOT / "backend" / "data" / "backups"

_SELECT = text("""
    SELECT id, title, public_url, document_date, deadline, tender_reference, body_txt
      FROM economy_items
     WHERE body_code = 'ecdc' AND item_type = 'tender'
       AND (body_txt ~ 'Published: 2017-07-27' OR body_txt ~ '&amp;')
     ORDER BY id""")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write the rewritten bodies (default: dry run)")
    a = p.parse_args()
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(_SELECT)]
    print(f"[INFO] {len(rows)} ECDC rows with a rejected date or an escaped link in their body")
    if not rows:
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"ecdc_bodies_before_rewrite_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M')}.json"
    backup.write_text(json.dumps(rows, default=str, indent=1))
    print(f"[INFO] backup: {backup}")
    now = datetime.now(timezone.utc)
    plan, failed = [], 0
    for r in rows:
        try:
            detail = ap._ecdc_detail(r["public_url"])
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {r['id']} {r['public_url']}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        kind = "ex-ante publicity" if "ex-ante" in (r["body_txt"] or "").lower() else "call for tender"
        row = {"title": r["title"], "url": r["public_url"], "reference": r["tender_reference"] or "",
               "kind": kind, "deadline": r["deadline"]}
        item = ap._ecdc_item(row, detail, now)
        plan.append((r, item))
        print(f"  {r['id']:>8} date {str(r['document_date'])[:10]:<10} -> "
              f"{item.document_date.date().isoformat() if item.document_date else 'NULL':<10} "
              f"body {len(r['body_txt'] or '')} -> {len(item.body_txt or '')}  "
              f"stamp={'Published: 2017-07-27' in item.body_txt}  amp={'&amp;' in item.body_txt}  {r['title'][:40]}")
    print(f"[INFO] planned: {len(plan)} rows, {failed} pages unreadable (left as they are)")
    if not a.apply:
        print("[INFO] dry run; re-run with --apply to write")
        return 1 if failed else 0
    written = 0
    for r, it in plan:
        with engine.begin() as c:   # one row per transaction
            written += c.execute(text(
                # The writer's vetted date replaces the stored one even when it is NULL:
                # 5778517 held the 2017-07-27 stamp with a deadline after it.
                "UPDATE economy_items SET body_txt = :bt, body_html = :bh, "
                "document_date = :d WHERE id = :id"),
                {"bt": it.body_txt, "bh": it.body_html, "d": it.document_date, "id": r["id"]}).rowcount
    with engine.connect() as c:
        left = c.execute(_SELECT).fetchall()
    print(f"[OK] {written} of {len(plan)} rows rewritten; still flagged: {len(left)}")
    return 0 if written == len(plan) and not left and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
