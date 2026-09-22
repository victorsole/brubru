"""Sync Who is Who (who_is_who_departments + who_is_who_officials). Daily cron job.

Runs the EU Whoiswho SPARQL query and bulk-upserts departments + officials.

Since 22 Sep 2026 (migration 234) it also:
* refreshes `fetched_at` on every row it sees (it was set once, on 5 June, and never again);
* marks officials who are no longer in the directory (`removed_at`) and clears the mark if
  they come back, so /who-is-who/officials can tell an incremental sync about departures.
  It refuses to mark more than MAX_REMOVED_SHARE of the listed officials in one run: a
  truncated SPARQL answer must not read as a mass departure;
* records a sync_runs row (`who_is_who`), failed runs included.

Usage:
    cd backend
    python3.12 scripts/sync_who_is_who.py
    python3.12 scripts/sync_who_is_who.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.database import engine
from models.who_is_who import WhoIsWhoDepartment, WhoIsWhoOfficial
from services.scrapers import who_is_who_ingest as wi

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_who_is_who")


def _bulk(table, rows, conflict_col, batch=500) -> int:
    if not rows:
        return 0
    # content_updated_at is the trigger's (migration 234); removed_at is written by
    # _mark_departures, except that a row seen again is no longer removed.
    managed = ("id", "first_seen", "fetched_at", "content_updated_at", "removed_at")
    cols = [c.name for c in table.columns if c.name not in managed]
    has_removed = "removed_at" in table.columns
    done = 0
    for i in range(0, len(rows), batch):
        chunk = [{k: r.get(k) for k in cols} for r in rows[i:i + batch]]
        stmt = pg_insert(table).values(chunk)
        set_ = {c: getattr(stmt.excluded, c) for c in cols if c != conflict_col}
        set_["fetched_at"] = func.now()
        if has_removed:
            set_["removed_at"] = None
        stmt = stmt.on_conflict_do_update(index_elements=[conflict_col], set_=set_)
        with engine.begin() as conn:
            conn.execute(stmt)
        done += len(chunk)
    return done


MAX_REMOVED_SHARE = 0.10


def _mark_departures(seen_keys: set[str], max_share: float = MAX_REMOVED_SHARE) -> int:
    """Mark listed officials absent from this run as removed. Returns how many."""
    with engine.begin() as conn:
        listed = conn.execute(text(
            "SELECT official_key FROM who_is_who_officials WHERE removed_at IS NULL")).scalars().all()
        gone = [k for k in listed if k not in seen_keys]
        if listed and len(gone) > max_share * len(listed):
            raise RuntimeError(
                f"{len(gone)} of {len(listed)} listed officials are missing from this run "
                f"(> {max_share:.0%}); refusing to mark them removed. A partial "
                f"directory answer is the likelier cause than a mass departure.")
        for i in range(0, len(gone), 1000):
            conn.execute(text(
                "UPDATE who_is_who_officials SET removed_at = now() "
                "WHERE removed_at IS NULL AND official_key = ANY(:keys)"), {"keys": gone[i:i + 1000]})
    return len(gone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-removed-share", type=float, default=MAX_REMOVED_SHARE,
                    help="Only for a catch-up after a long gap. An official is keyed by person + "
                         "department + position, so a job change retires one record and adds another.")
    args = ap.parse_args()
    if args.dry_run:
        return _run(dry_run=True)
    started = datetime.now(timezone.utc)
    error, upserted = None, None
    try:
        upserted = _run(dry_run=False, max_share=args.max_removed_share)
    except Exception as e:  # recorded, then a failing exit
        error = f"{type(e).__name__}: {e}"
        log.error("[who-is-who] [ERROR] %s", error)
    finally:
        try:
            from core.database import SessionLocal
            from services.sync.freshness import record_run
            s = SessionLocal()
            record_run(s, source_key="who_is_who", tier="daily", status="failed" if error else "success",
                       items_added=upserted, error=error, started_at=started,
                       finished_at=datetime.now(timezone.utc))
            s.close()
        except Exception as e:  # noqa: BLE001
            log.warning("[who-is-who] [WARN] could not record the run: %s: %s", type(e).__name__, e)
    return 1 if error else 0


def _run(dry_run: bool, max_share: float = MAX_REMOVED_SHARE):
    depts, officials = wi.build()
    if not officials:
        raise RuntimeError("the directory returned no officials")
    no_body = sum(1 for r in depts + officials if not (r["body_txt"] or "").strip())
    if no_body:
        log.warning("[who-is-who] [WARN] %d rows missing body_txt", no_body)
    else:
        log.info("[who-is-who] [OK] every department + official has body_txt")

    if dry_run:
        log.info("[who-is-who] dry-run: %d departments + %d officials (nothing written)", len(depts), len(officials))
        for o in officials[:4]:
            log.info("    %s | %s | %s", o["name"], o.get("position"), o.get("department"))
        return

    nd = _bulk(WhoIsWhoDepartment.__table__, depts, "dept_key")
    no = _bulk(WhoIsWhoOfficial.__table__, officials, "official_key")
    removed = _mark_departures({o["official_key"] for o in officials}, max_share)
    log.info("[who-is-who] DONE: %d departments + %d officials upserted, %d marked removed", nd, no, removed)
    return no


if __name__ == "__main__":
    sys.exit(main())
