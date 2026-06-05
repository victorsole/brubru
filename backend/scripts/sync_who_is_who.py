"""Backfill Who is Who (who_is_who_departments + who_is_who_officials).

Runs the EU Whoiswho SPARQL query and bulk-upserts departments + officials.

Usage:
    cd backend
    python3.12 scripts/sync_who_is_who.py
    python3.12 scripts/sync_who_is_who.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.database import engine
from models.who_is_who import WhoIsWhoDepartment, WhoIsWhoOfficial
from services.scrapers import who_is_who_ingest as wi

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_who_is_who")


def _bulk(table, rows, conflict_col, batch=500) -> int:
    if not rows:
        return 0
    cols = [c.name for c in table.columns if c.name not in ("id", "first_seen", "fetched_at")]
    done = 0
    for i in range(0, len(rows), batch):
        chunk = [{k: r.get(k) for k in cols} for r in rows[i:i + batch]]
        stmt = pg_insert(table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[conflict_col],
            set_={c: getattr(stmt.excluded, c) for c in cols if c != conflict_col})
        with engine.begin() as conn:
            conn.execute(stmt)
        done += len(chunk)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    depts, officials = wi.build()
    no_body = sum(1 for r in depts + officials if not (r["body_txt"] or "").strip())
    if no_body:
        log.warning("[who-is-who] [WARN] %d rows missing body_txt", no_body)
    else:
        log.info("[who-is-who] [OK] every department + official has body_txt")

    if args.dry_run:
        log.info("[who-is-who] dry-run: %d departments + %d officials (nothing written)", len(depts), len(officials))
        for o in officials[:4]:
            log.info("    %s | %s | %s", o["name"], o.get("position"), o.get("department"))
        return

    nd = _bulk(WhoIsWhoDepartment.__table__, depts, "dept_key")
    no = _bulk(WhoIsWhoOfficial.__table__, officials, "official_key")
    log.info("[who-is-who] DONE: %d departments + %d officials upserted", nd, no)


if __name__ == "__main__":
    main()
