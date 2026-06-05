"""Backfill / refresh the Council of the EU register cache (council_register_items).

Scrapes consilium.europa.eu (fresh Playwright context per URL) + the un-walled
data.consilium PDF store, composes bodies, and upserts into council_register_items
(migration 109). Backs the eight new Council-of-the-EU API endpoints.

Usage:
    cd backend
    python3.12 scripts/sync_council_register.py                 # all 8 content types
    python3.12 scripts/sync_council_register.py --type voting_result --type meeting
    python3.12 scripts/sync_council_register.py --limit 30 --enrich 8
    python3.12 scripts/sync_council_register.py --dry-run       # scrape + report, no write
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import SessionLocal
from models.council_register_item import CouncilRegisterItem
from services.scrapers.council_register_scraper import scrape, ALL_CONTENT_TYPES

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_council_register")


def upsert(db, item) -> bool:
    """Insert or update one ScrapedItem by item_key. Returns True if new."""
    key = item.item_key()
    row = db.query(CouncilRegisterItem).filter(CouncilRegisterItem.item_key == key).first()
    fields = dict(
        content_type=item.content_type,
        title=item.title,
        public_url=item.public_url,
        body_txt=item.body_txt,
        body_html=item.body_html,
        document_date=item.document_date,
        document_ref=item.document_ref,
        council_configuration=item.council_configuration,
        interinstitutional_ref=item.interinstitutional_ref,
        subject_matters=item.subject_matters or [],
        pdf_url=item.pdf_url,
        policy_areas=item.policy_areas or [],
        source_url=item.source_url,
        extra=item.extra or {},
    )
    if row is None:
        db.add(CouncilRegisterItem(item_key=key, **fields))
        return True
    for k, v in fields.items():
        setattr(row, k, v)
    return False


def main():
    ap = argparse.ArgumentParser(description="Backfill the Council register cache.")
    ap.add_argument("--type", action="append", dest="types",
                    help="content_type to scrape (repeatable). Default: all.")
    ap.add_argument("--limit", type=int, default=25, help="max items per content_type")
    ap.add_argument("--enrich", type=int, default=6,
                    help="how many meetings/press/research to deep-fetch for a rich body")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    content_types = args.types or ALL_CONTENT_TYPES
    log.info("[council-register] scraping %s (limit=%d, enrich=%d)",
             ", ".join(content_types), args.limit, args.enrich)

    items = scrape(content_types, limit=args.limit, enrich=args.enrich)
    log.info("[council-register] scraped %d items total", len(items))

    # Per-type summary + body-fill audit.
    by_type: dict = {}
    no_body = 0
    for it in items:
        by_type.setdefault(it.content_type, 0)
        by_type[it.content_type] += 1
        if not (it.body_txt and it.body_txt.strip()):
            no_body += 1
    for ct, n in sorted(by_type.items()):
        log.info("    %-18s %d", ct, n)
    if no_body:
        log.warning("    [WARN] %d items have empty body_txt", no_body)
    else:
        log.info("    [OK] every item has body_txt")

    if args.dry_run:
        log.info("[council-register] dry-run: nothing written")
        for it in items[:5]:
            log.info("    e.g. [%s] %s -> %s", it.content_type, it.title[:60], it.public_url)
        return

    db = SessionLocal()
    try:
        new = 0
        for it in items:
            if upsert(db, it):
                new += 1
        db.commit()
        log.info("[council-register] upserted %d items (%d new, %d updated)",
                 len(items), new, len(items) - new)
    finally:
        db.close()


if __name__ == "__main__":
    main()
