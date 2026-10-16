#!/usr/bin/env python3.12
"""Repair Cedefop procedures whose stored publication date is after their own deadline.

API audit, 16 Oct 2026 (step 2, Cedefop): 92 rows (88 tenders, 4 calls) carried an
"Official Publication Date" later than their closing date: 77 the site-migration stamp
(27/11/2009), 15 with day and month swapped on the page. The writer now vets that date
(agency_procurement._cedefop_published), but the nightly run re-reads only the two newest
listing pages and the live procedures, and the upsert never regresses document_date to
NULL, so the stored rows must be repaired once, from the source.

Each affected page is re-read and the date recomputed by the writer's own rule; the new
value (a date or NULL) replaces the stored one, one row per transaction. Rows are backed
up first to backend/data/backups/. Dry run by default; --apply writes.

    python3.12 -m backend.scripts.repair_cedefop_publication_dates [--apply]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))
sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402
from services.scrapers import agency_procurement as ap  # noqa: E402

BACKUPS = _REPO_ROOT / "backend" / "data" / "backups"

_SELECT = text("""
    SELECT id, title, public_url, document_date, deadline, item_type
      FROM economy_items
     WHERE body_code = 'cedefop' AND item_type IN ('tender', 'eoi_call')
       AND document_date IS NOT NULL AND deadline IS NOT NULL
       AND document_date > deadline
     ORDER BY id""")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write the repaired dates (default: dry run)")
    a = p.parse_args()
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(_SELECT)]
    print(f"[INFO] {len(rows)} Cedefop rows published after their deadline")
    if not rows:
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M")
    backup = BACKUPS / f"cedefop_publication_dates_before_repair_{stamp}.json"
    backup.write_text(json.dumps(rows, default=str, indent=1))
    print(f"[INFO] backup: {backup}")

    plan, failed = [], 0
    for r in rows:
        try:
            detail = ap._cedefop_detail(r["public_url"])
        except Exception as exc:  # noqa: BLE001 - one unreadable page must not stop the rest
            print(f"[ERROR] {r['id']} {r['public_url']}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        extended = ap._parse_date(detail.get("Extended closing date", ""))
        closing = ap._parse_date(detail.get("Closing date", "")) or r["deadline"]
        deadline = extended or closing
        new = ap._cedefop_published(detail, deadline)
        plan.append((r, detail.get("Official Publication Date", ""), new))
        print(f"  {r['id']:>8} {str(r['document_date'])[:10]} -> {new.date().isoformat() if new else 'NULL':<10} "
              f"deadline {str(r['deadline'])[:10]}  page says {detail.get('Official Publication Date', '')!r:<12} "
              f"{r['title'][:50]}")
        time.sleep(0.8)
    dated = sum(1 for _r, _p, n in plan if n)
    print(f"[INFO] planned: {len(plan)} rows, {dated} get an OJ date, {len(plan) - dated} become NULL, "
          f"{failed} pages unreadable (left as they are)")
    if not a.apply:
        print("[INFO] dry run; re-run with --apply to write")
        return 1 if failed else 0

    written = 0
    for r, _page, new in plan:
        with engine.begin() as c:   # one row per transaction
            res = c.execute(text("UPDATE economy_items SET document_date = :d "
                                 "WHERE id = :id AND document_date = :old"),
                            {"d": new, "id": r["id"], "old": r["document_date"]})
            written += res.rowcount
    print(f"[OK] {written} of {len(plan)} rows repaired")
    with engine.connect() as c:
        left = c.execute(_SELECT).fetchall()
    print(f"[INFO] rows still published after their deadline: {len(left)}")
    return 0 if written == len(plan) and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
