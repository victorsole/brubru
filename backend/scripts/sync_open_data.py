"""Backfill data.europa.eu open data (open_data_datasets + open_data_catalogues).

Pure-JSON integration with the data.europa.eu open search API (no auth/WAF).
Sweeps the catalogue across EU policy keywords + ingests every catalogue.

Usage:
    cd backend
    python3.12 scripts/sync_open_data.py                      # full sweep + catalogues
    python3.12 scripts/sync_open_data.py --per-keyword 300 --pages 2
    python3.12 scripts/sync_open_data.py --keyword energy --keyword climate
    python3.12 scripts/sync_open_data.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.database import engine
from models.open_data import OpenDataDataset, OpenDataCatalogue
from services.scrapers import open_data_ingest as oi

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_open_data")


def _bulk_upsert(table, rows: list, conflict_col: str, batch: int = 500) -> int:
    """Postgres bulk INSERT ... ON CONFLICT DO UPDATE in batches. Returns count."""
    if not rows:
        return 0
    cols = [c.name for c in table.columns
            if c.name not in ("id", "first_seen", "fetched_at")]
    done = 0
    for i in range(0, len(rows), batch):
        chunk = [{k: r.get(k) for k in cols} for r in rows[i:i + batch]]
        stmt = pg_insert(table).values(chunk)
        update = {c: getattr(stmt.excluded, c) for c in cols if c != conflict_col}
        stmt = stmt.on_conflict_do_update(index_elements=[conflict_col], set_=update)
        with engine.begin() as conn:
            conn.execute(stmt)
        done += len(chunk)
    return done


def main():
    ap = argparse.ArgumentParser(description="Backfill data.europa.eu open data.")
    ap.add_argument("--keyword", action="append", dest="keywords")
    ap.add_argument("--per-keyword", type=int, default=200)
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--skip-catalogues", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # 1. catalogues
    cats = [] if args.skip_catalogues else oi.fetch_catalogues()
    log.info("[open-data] catalogues fetched: %d", len(cats))

    # 2. datasets sweep
    rows = oi.fetch_datasets(per_keyword=args.per_keyword, pages=args.pages, keywords=args.keywords)
    hvd = sum(1 for r in rows if r["is_hvd"])
    no_body = sum(1 for r in rows if not (r["body_txt"] or "").strip())
    log.info("[open-data] datasets fetched: %d (HVD=%d)", len(rows), hvd)
    if no_body:
        log.warning("    [WARN] %d datasets have empty body", no_body)
    else:
        log.info("    [OK] every dataset has body_txt")

    if args.dry_run:
        log.info("[open-data] dry-run: nothing written")
        for r in rows[:4]:
            log.info("    [%s] %s hvd=%s formats=%s", r["catalogue"], r["title"][:50], r["is_hvd"], r["formats"][:3])
        return

    nc = _bulk_upsert(OpenDataCatalogue.__table__, cats, "catalogue_id")
    nd = _bulk_upsert(OpenDataDataset.__table__, rows, "dataset_id")
    log.info("[open-data] DONE: upserted %d catalogues + %d datasets", nc, nd)


if __name__ == "__main__":
    main()
