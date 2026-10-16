#!/usr/bin/env python3.12
"""Date the undated ECHA procedures from the TED notice their body cites.

API audit, 16 Oct 2026 (step 2, ECHA): 97 of 106 tenders carried no publication date.
ECHA publishes none; 79 bodies cite a TED notice number (the OJ S publication), and TED's
search API gives the publication date for notices from 2016 on (47 of the 79). The writer
now does this on every page it reads, but the nightly run re-opens only the current calls,
so the stored rows are dated once here: the earliest cited notice published on or before
the deadline. Rows whose notices TED no longer indexes stay empty. Backup first; one row
per transaction. Dry run by default; --apply writes.

    python3.12 -m backend.scripts.repair_echa_dates_from_ted [--apply]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
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
    SELECT id, title, deadline, document_date, body_txt
      FROM economy_items
     WHERE body_code = 'echa' AND item_type IN ('tender', 'eoi_call')
       AND document_date IS NULL AND body_txt ~ 'ted\\.europa\\.eu'
     ORDER BY id""")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="write the dates (default: dry run)")
    a = p.parse_args()
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(_SELECT)]
    print(f"[INFO] {len(rows)} undated ECHA procedures cite a TED notice")
    if not rows:
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"echa_dates_before_ted_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M')}.json"
    backup.write_text(json.dumps([{k: v for k, v in r.items() if k != "body_txt"} for r in rows],
                                 default=str, indent=1))
    print(f"[INFO] backup: {backup}")
    links = {r["id"]: re.findall(r"https?://ted\.europa\.eu\S+", r["body_txt"] or "") for r in rows}
    ap._ted_publication_dates(sorted({n for ls in links.values() for n in ap._ted_notice_numbers(ls)}))
    plan = []
    for r in rows:
        notice, d = ap._ted_published(links[r["id"]], r["deadline"])
        nums = ap._ted_notice_numbers(links[r["id"]])
        print(f"  {r['id']:>8} {d.date().isoformat() if d else 'no date':<10} notice {notice or '-':<12} "
              f"cited {len(nums)} ({nums[0][-4:] if nums else ''})  deadline {str(r['deadline'])[:10]}  {r['title'][:40]}")
        if d:
            plan.append((r, d))
    print(f"[INFO] planned: {len(plan)} of {len(rows)} get a date; {len(rows) - len(plan)} cite only notices TED no longer indexes")
    if not a.apply:
        print("[INFO] dry run; re-run with --apply to write")
        return 0
    written = 0
    for r, d in plan:
        with engine.begin() as c:   # one row per transaction
            written += c.execute(text("UPDATE economy_items SET document_date = :d "
                                      "WHERE id = :id AND document_date IS NULL"),
                                 {"d": d, "id": r["id"]}).rowcount
    with engine.connect() as c:
        left = c.execute(_SELECT).fetchall()
    print(f"[OK] {written} of {len(plan)} rows dated; undated ECHA rows citing TED now: {len(left)}")
    return 0 if written == len(plan) else 1


if __name__ == "__main__":
    sys.exit(main())
