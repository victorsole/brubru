"""
Fill status, deadline and tender_reference on the EU bodies' own procurement items that have none.

Until 26 Oct 2026 most agency writers put the status and the deadline only into the text, so 388
items (tenders, grants, calls, framework contracts) had no status and no deadline. The writers now fill the columns
(services/funding/agency_status.py), but each reads only what its body still lists; this fills
the items already stored, from what each row already holds, in this order:
  - the lines our writers composed from the listing ("Status: Open", "Deadline: 2026-08-31",
    "Reference: ...") and the summary they composed ("<ref> · <status> · <date>",
    "<programme> · <status> · deadline <date>");
  - the item's own page as stored: the facts it labels ("Status Upcoming", "Deadline date 15 October
    2026", "Deadline for submission of tenders: 27/11/2026").
Nothing is guessed: a row whose text labels neither a status nor a deadline keeps NULL. The
reference comes from `guid` only where the writer stored the body's reference there (never ERA's
URL slug, never a URL).

Run: python3.12 -m scripts.backfill_agency_status [--apply] [--backup-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.funding.agency_status import ITEM_TYPES, from_source, page_facts  # noqa: E402

_LINE = re.compile(r"^(Status|Deadline|Reference):\s*(.+?)\s*$", re.M)
_ISO = re.compile(r"(?:^|deadline\s)(\d{4}-\d{2}-\d{2})$")
# Writers whose `guid` is the body's own reference (agency_procurement._build: guid = reference or url).
_GUID_IS_REFERENCE = {"euda_procurement", "euaa_procurement", "eurojust_procurement", "sedia"}
# Writers that labelled their whole listing "Open" whatever each item said (ETF's pages say
# "Tender status Closed" under it): that word is ours, not the body's, so only the dates count.
_LABEL_ONLY = {"etf", "euaa", "euda"}


def _iso(s: str):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def derive(row, today: date):
    """(status, deadline, tender_reference, where) for one stored row."""
    def known(w):  # a status word the rule reads (not a description that happens to sit there)
        return w if w and from_source(w, None, today) is not None else None

    body = row.body_txt or ""
    label_only = row.body_code in _LABEL_ONLY
    lines = {k: v for k, v in _LINE.findall(body)}
    parts = [p.strip() for p in (row.summary or "").split(" · ") if p.strip()]
    m = _ISO.search(parts[-1]) if parts else None
    # The summary is rewritten every run and the body only when a longer one comes, so the
    # summary holds the latest listing's deadline (EUDA/2026/OP/0006: 2 Dec, the body 16 Nov).
    deadline = _iso(m.group(1)) if m else None
    where = "the composed summary" if deadline else "no deadline"
    if deadline is None and lines.get("Deadline"):
        deadline, where = _iso(lines["Deadline"]), "the composed lines"
    page_word, page_ref, page_deadline = page_facts(_LINE.sub("", body) if label_only else body)
    if deadline is None and page_deadline is not None:
        deadline, where = page_deadline, "the page's labelled facts"
    word = page_word
    if word is None and not label_only:
        word = known(lines.get("Status")) or next((known(p) for p in parts if known(p)), None)
    ref = None
    if row.source_kind in _GUID_IS_REFERENCE and row.guid and not row.guid.startswith("http"):
        ref = row.guid
    elif row.body_code not in ("eeas", "era"):   # EEAS prints no common reference; ERA's is our slug
        ref = page_ref
    return from_source(word, deadline, today), deadline, ref, where


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run).")
    ap.add_argument("--backup-dir", default=None, help="Write the rows' current values here first.")
    args = ap.parse_args(argv)
    today = datetime.now(timezone.utc).date()
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, body_code, item_type, source_kind, guid, summary, body_txt, status, deadline, "
            "tender_reference, updated_at FROM economy_items "
            "WHERE item_type = ANY(CAST(:types AS text[])) AND status IS NULL ORDER BY body_code, id"),
            {"types": list(ITEM_TYPES)}).fetchall()
        plan, tally = [], Counter()
        for r in rows:
            status, deadline, ref, where = derive(r, today)
            tally[(r.body_code, r.item_type, status or "(none)", "deadline" if deadline else "-",
                   "ref" if ref else "-")] += 1
            if status or deadline or ref:
                plan.append({"id": r.id, "status": status, "deadline": deadline, "ref": ref})
        for k, n in sorted(tally.items()):
            print(f"  {k[0]:<10} {k[1]:<9} {k[2]:<12} {k[3]:<9} {k[4]:<4} {n}")
        print(f"[{'OK' if args.apply else 'DRY-RUN'}] {len(rows)} item(s) without a status; "
              f"{len(plan)} {'filled' if args.apply else 'would be filled'}; "
              f"{len(rows) - len(plan)} keep NULL (their text labels neither)")
        if args.apply and plan:
            if args.backup_dir:
                out = Path(args.backup_dir) / f"economy_items_status_before_{datetime.now():%Y%m%d_%H%M}.csv"
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open("w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["id", "status", "deadline", "tender_reference", "updated_at"])
                    for r in rows:
                        w.writerow([r.id, r.status, r.deadline, r.tender_reference, r.updated_at])
                print(f"[OK] backup {out}")
            db.execute(text(
                "UPDATE economy_items SET status = COALESCE(status, :status), "
                "deadline = COALESCE(deadline, :deadline), "
                "tender_reference = COALESCE(tender_reference, :ref) WHERE id = :id"), plan)
            db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
