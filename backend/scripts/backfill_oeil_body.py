"""
backfill_oeil_body — populate legislative_carriages.{oeil_html_body, oeil_text_body}
                     for every carriage that has an oeil_procedure_ref.

Run modes:
  python3.12 backend/scripts/backfill_oeil_body.py --limit 5 --dry-run
  python3.12 backend/scripts/backfill_oeil_body.py --limit 100
  python3.12 backend/scripts/backfill_oeil_body.py --refresh-older-than 30  # days

After the run, the v1 /committees/{code}/work-items endpoint will serve
the cached OEIL body via body_txt / body_html.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")

from services.scrapers.oeil_body_scraper import fetch_many  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-oeil-body")


def _candidates(engine, *, limit: int, refresh_older_than_days: int | None):
    """Return list of oeil_procedure_refs that need a body fetch."""
    where = []
    if refresh_older_than_days is None:
        # First-pass: only rows where we never fetched the body.
        where.append("oeil_body_fetched_at IS NULL")
    else:
        cutoff = datetime.utcnow() - timedelta(days=refresh_older_than_days)
        where.append(f"(oeil_body_fetched_at IS NULL OR oeil_body_fetched_at < '{cutoff.isoformat()}')")
    where.append("oeil_procedure_ref IS NOT NULL")
    sql = text(f"""
        SELECT oeil_procedure_ref
        FROM legislative_carriages
        WHERE {' AND '.join(where)}
        ORDER BY oeil_procedure_ref
        LIMIT :lim
    """)
    with engine.connect() as c:
        return [r[0] for r in c.execute(sql, {"lim": limit}).fetchall()]


async def _run(engine, refs: list[str], dry_run: bool, concurrency: int):
    log.info("Fetching %d OEIL pages with concurrency=%d", len(refs), concurrency)
    results = await fetch_many(refs, concurrency=concurrency)
    ok = sum(1 for v in results.values() if v is not None)
    log.info("Fetched OK: %d / %d", ok, len(results))
    if dry_run:
        log.info("[DRY] not writing to DB. First 3 successful fetches:")
        shown = 0
        for ref, body in results.items():
            if body is None:
                continue
            log.info("  %s -> html=%d chars, text=%d chars; preview: %r",
                     ref, len(body.html_body), len(body.text_body), body.text_body[:120])
            shown += 1
            if shown >= 3:
                break
        return ok

    now = datetime.utcnow()
    written = 0
    with engine.begin() as c:
        for ref, body in results.items():
            if body is None:
                # Still stamp the row so we don't re-try on every pass — set
                # fetched_at but leave body cols null. Refresh mode will retry.
                c.execute(text("""
                    UPDATE legislative_carriages
                    SET oeil_body_fetched_at = :now
                    WHERE oeil_procedure_ref = :ref
                """), {"now": now, "ref": ref})
                continue
            c.execute(text("""
                UPDATE legislative_carriages
                SET oeil_html_body       = :html,
                    oeil_text_body       = :txt,
                    oeil_body_fetched_at = :now
                WHERE oeil_procedure_ref = :ref
            """), {"html": body.html_body, "txt": body.text_body, "now": now, "ref": ref})
            written += 1
    log.info("Wrote %d rows.", written)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50, help="Max procedures per run (default 50).")
    ap.add_argument("--concurrency", type=int, default=4, help="Parallel HTTP fetches (default 4).")
    ap.add_argument("--refresh-older-than", type=int, default=None,
                    help="Also refresh rows whose body was last fetched > N days ago. "
                         "Default: only fetch rows with no body yet.")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + parse but don't write to DB.")
    ap.add_argument("--refs", nargs="+", default=None,
                    help="Explicit oeil_procedure_refs to fetch (overrides --limit query).")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        log.error("DATABASE_URL is not set."); sys.exit(1)
    eng = create_engine(db_url)

    if args.refs:
        refs = args.refs
    else:
        refs = _candidates(eng, limit=args.limit, refresh_older_than_days=args.refresh_older_than)
    if not refs:
        log.info("Nothing to fetch.")
        return
    asyncio.run(_run(eng, refs, dry_run=args.dry_run, concurrency=args.concurrency))


if __name__ == "__main__":
    main()
