"""
EFPIA pharma/health scraper - CLI driver.

Source catalogue: backend/data/efpia_brief/sources.json (83 sources).
Storage: efpia_scraped_items (migration 092).
Engine:  backend/services/efpia_scraper.py.

Usage:
    # Scrape the tier-1 priority sources (default, ~15 daily URLs).
    python3.12 -m scripts.scrape_efpia_sources --tier1

    # Scrape every source in the catalogue (long-running, daily/weekly/monthly).
    python3.12 -m scripts.scrape_efpia_sources --all

    # Scrape one or more specific sources by id.
    python3.12 -m scripts.scrape_efpia_sources --source-ids ema_news ep_sant_press_releases

    # Print what would be inserted, without DB writes.
    python3.12 -m scripts.scrape_efpia_sources --tier1 --dry-run

    # Force Playwright for hard cases (WAF / JavaScript-heavy pages).
    python3.12 -m scripts.scrape_efpia_sources --source-ids ep_sant_highlights --force-playwright

Per memory/feedback_send_script_dotenv_required.md, load_dotenv() runs at
import time before any database service touches MISTRAL_API_KEY / DATABASE_URL.

Created 28 May 2026.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from core.database import SessionLocal  # noqa: E402
from services import efpia_scraper  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("efpia_scraper.cli")


def _resolve_sources(args: argparse.Namespace) -> List[dict]:
    catalogue = efpia_scraper.load_sources().get("sources", [])
    if args.all:
        return catalogue
    if args.tier1:
        wanted = set(efpia_scraper.tier1_source_ids())
        return [s for s in catalogue if s.get("id") in wanted]
    if args.source_ids:
        wanted = set(args.source_ids)
        return [s for s in catalogue if s.get("id") in wanted]
    return []


def main() -> int:
    p = argparse.ArgumentParser(description="EFPIA pharma/health source scraper.")
    p.add_argument("--tier1", action="store_true", help="Run the tier-1 daily priority sources (default if no selector given).")
    p.add_argument("--all", action="store_true", help="Run every source in the catalogue.")
    p.add_argument("--source-ids", nargs="*", help="Specific source ids to run.")
    p.add_argument("--dry-run", action="store_true", help="Parse but do not write to DB.")
    p.add_argument("--force-playwright", action="store_true", help="Skip the requests path and use Playwright everywhere.")
    p.add_argument("--limit-per-source", type=int, default=None, help="Cap items per source (for diagnostics).")
    args = p.parse_args()

    if not (args.tier1 or args.all or args.source_ids):
        # Default to tier1 -- the most common daily-morning invocation.
        args.tier1 = True

    sources = _resolve_sources(args)
    if not sources:
        logger.error("no sources matched the selectors. Aborting.")
        return 2

    logger.info("Running %d sources (%s)", len(sources), "DRY RUN" if args.dry_run else "LIVE WRITE")
    started = datetime.now(timezone.utc)

    db = None if args.dry_run else SessionLocal()
    try:
        total_items = 0
        per_source_summary = []
        for s in sources:
            t0 = time.monotonic()
            try:
                items = efpia_scraper.scrape_source(s, force_playwright=args.force_playwright)
            except Exception as exc:  # noqa: BLE001
                logger.warning("source %s raised: %s", s.get("id"), exc)
                items = []

            if args.limit_per_source is not None:
                items = items[: args.limit_per_source]

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            written = 0
            if not args.dry_run and items:
                try:
                    written = efpia_scraper.save_items(db, items)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning("DB save failed for source %s: %s", s.get("id"), exc)

            total_items += len(items)
            per_source_summary.append(
                {
                    "source_id": s.get("id"),
                    "institution": s.get("institution"),
                    "items_parsed": len(items),
                    "items_written": written,
                    "elapsed_ms": elapsed_ms,
                }
            )
            logger.info(
                "%-32s items=%-3d written=%-3d %5d ms %s",
                s.get("id"),
                len(items),
                written,
                elapsed_ms,
                "" if items else "(empty)",
            )
    finally:
        if db is not None:
            db.close()

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info("=" * 60)
    logger.info("Scrape complete: %d sources, %d items parsed in %.1fs",
                len(sources), total_items, duration)

    if args.dry_run:
        logger.info("(dry run; no DB writes performed)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
