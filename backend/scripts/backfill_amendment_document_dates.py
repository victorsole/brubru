"""Give amendment documents (and their amendments) the date EP holds for them.

Discovery builds document stubs from identifiers alone and never sees a date, and the
document upsert did not carry document_date through ON CONFLICT, so a row created before
the date was resolvable kept NULL however often it was re-synced. Measured 28 Sep 2026:
1,145 of 1,365 amendment_documents and 5,678 of 5,695 newly stored amendments had no date.

/parliament/amendments and /parliament/ep-documents filter published_from and
published_to on that column, so an undated row is invisible to every date query, and
document_date is one of the five datapoints each item must carry.

The date comes from EP Open Data's own record for the document. AM documents are not in
/committee-documents (it holds PR, PA, AD, AL and AG), so they keep NULL rather than an
invented date: unknown stays unknown.

Run:
    python3.12 scripts/backfill_amendment_document_dates.py            # dry-run, 20 rows
    python3.12 scripts/backfill_amendment_document_dates.py --apply --limit 0
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.api_clients.ep_open_data_client import EPOpenDataClient  # noqa: E402

_DATE_KEYS = ("date", "document_date", "date_document", "activity_date")


def _parse(value) -> datetime | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value)[:len(fmt.replace("%Y", "2026")
                                                    .replace("%m", "01")
                                                    .replace("%d", "01")
                                                    .replace("%H:%M:%S", "00:00:00"))], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value)[:19])
    except ValueError:
        return None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=20, help="0 = every undated document")
    ap.add_argument("--max-seconds", type=int, default=900)
    args = ap.parse_args()

    db = SessionLocal()
    client = EPOpenDataClient()
    started = time.time()
    filled = no_record = still_unknown = blocked = 0
    try:
        sql = ("SELECT ep_identifier, pe_reference FROM amendment_documents "
               "WHERE document_date IS NULL AND ep_identifier IS NOT NULL "
               "ORDER BY scraped_at DESC")
        if args.limit:
            sql += f" LIMIT {args.limit}"
        rows = db.execute(text(sql)).fetchall()
        due = db.execute(text("SELECT count(*) FROM amendment_documents "
                              "WHERE document_date IS NULL AND ep_identifier IS NOT NULL")).scalar()
        print(f"[INFO] {len(rows)} of {due} undated document(s) this run (apply={args.apply})")

        for i, row in enumerate(rows, 1):
            if time.time() - started > args.max_seconds:
                print(f"[INFO] budget reached after {i - 1} document(s)")
                break
            # A 404 means the document genuinely is not in this endpoint (AM documents
            # are not). Anything else is a wall, and calling it "no record" is how 973
            # PR documents were written off on the first run while EP was answering 429:
            # they are all in the endpoint, and the count said otherwise.
            detail = None
            for attempt in range(1, 4):
                try:
                    detail = await client.get_document_detail(
                        row.ep_identifier, endpoint="committee-documents")
                    break
                except Exception as exc:  # noqa: BLE001
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status == 404:
                        no_record += 1
                        break
                    if attempt == 3:
                        blocked += 1
                        break
                    await asyncio.sleep(5.0 * attempt)
            if detail is None:
                continue
            when = None
            for key in _DATE_KEYS:
                when = _parse(detail.get(key) if isinstance(detail, dict) else None)
                if when:
                    break
            if not when:
                still_unknown += 1
                continue
            filled += 1
            if args.apply:
                db.execute(text("UPDATE amendment_documents SET document_date = :d "
                                "WHERE ep_identifier = :i AND document_date IS NULL"),
                           {"d": when, "i": row.ep_identifier})
                # The amendments carry their own copy, joined by PE reference.
                db.execute(text("UPDATE mep_amendments SET document_date = :d "
                                "WHERE pe_reference = :p AND document_date IS NULL"),
                           {"d": when, "p": row.pe_reference})
                db.commit()
            if i % 50 == 0:
                print(f"  [{i}/{len(rows)}] filled={filled} no_record={no_record}", flush=True)

        print(f"[DONE] filled={filled}  not in the endpoint (404)={no_record}  "
              f"blocked or failed={blocked}  record without a date={still_unknown}"
              f"{'' if args.apply else '  (DRY-RUN)'}")
        left = max(0, (due or 0) - filled) if args.apply else 0
        if left:
            print(f"[SYNC_STATUS] degraded: {left} document(s) still undated, resumes next run")
        if rows and filled == 0 and blocked >= len(rows) / 2:
            print("[ERROR] EP refused most requests (rate limit or outage): this run "
                  "read nothing, and the documents it skipped are NOT dateless")
            return 1
        if rows and filled == 0 and no_record == len(rows):
            print("[ERROR] not one document had an EP record: the endpoint or the "
                  "identifier format has changed")
            return 1
        return 0
    finally:
        await client.close()
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
