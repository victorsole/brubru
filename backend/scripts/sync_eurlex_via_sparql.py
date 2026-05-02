#!/usr/bin/env python3
"""
SPARQL-driven EUR-Lex delta sync.

Drop-in companion to scripts/sync_eurlex_feeds.py. Replaces the RSS-feed
discovery layer with direct Cellar SPARQL queries — covering the full
3.79M-work corpus rather than only items in the recent RSS window.

This script:
  1. Reads a watermark (the latest known publication date in
     legislative_carriages, source=EURLEX_RSS).
  2. Queries Cellar SPARQL for acts published since the watermark.
  3. Upserts new acts into legislative_carriages.

Default is dry-run. Pass --apply to write to the DB.

Usage:
    python3.12 backend/scripts/sync_eurlex_via_sparql.py [--days N] [--apply]

Options:
    --days N       Lookback window when no watermark exists (default: 7)
    --sectors X    CELEX sectors to include (default: 3,5)
    --apply        Actually write to the DB. Default is dry-run.
    --limit N      Max acts to ingest in this run (default: 200)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import desc

from core.database import SessionLocal  # noqa: E402
from models.legislative_train import (  # noqa: E402
    CarriageSourceEnum,
    CarriageStatusEnum,
    LegislativeCarriage,
    TextTypeEnum,
)
from services.discovery.cellar_helpers import stream_oj_delta  # noqa: E402
from services.api_clients.immc_client import IMMCClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sparql-sync")

CELEX_TYPE_LETTERS = {
    "R": ("Regulation", TextTypeEnum.LEGISLATIVE),
    "L": ("Directive", TextTypeEnum.LEGISLATIVE),
    "D": ("Decision", TextTypeEnum.LEGISLATIVE),
    "H": ("Recommendation", TextTypeEnum.NON_LEGISLATIVE),
    "C": ("Declaration", TextTypeEnum.NON_LEGISLATIVE),
    "B": ("Budget", TextTypeEnum.NON_LEGISLATIVE),
    "M": ("Merger Decision", TextTypeEnum.NON_LEGISLATIVE),
    "A": ("Agreement", TextTypeEnum.LEGISLATIVE),
    "X": ("Other", TextTypeEnum.UNKNOWN),
}

# CELEX format: <sector><year><type-letter><serial>
# e.g. 32016R0679 -> sector=3, year=2016, type=R, serial=0679
_CELEX_RE = re.compile(r"^(\d)(\d{4})([A-Z]{1,2})(\d+)")


def parse_celex(celex: str) -> dict:
    m = _CELEX_RE.match(celex)
    if not m:
        return {"sector": None, "year": None, "type_letter": None, "serial": None}
    sector, year, type_letter, serial = m.groups()
    label, text_type = CELEX_TYPE_LETTERS.get(type_letter[0], ("Unknown", TextTypeEnum.UNKNOWN))
    return {
        "sector": sector,
        "year": int(year),
        "type_letter": type_letter,
        "serial": serial,
        "doc_type": label,
        "text_type": text_type,
    }


def get_watermark(session) -> Optional[date]:
    """Read the latest known SPARQL-source carriage publication date."""
    latest = (
        session.query(LegislativeCarriage)
        .filter(LegislativeCarriage.source == CarriageSourceEnum.EURLEX)
        .order_by(desc(LegislativeCarriage.scraped_at))
        .first()
    )
    if latest and latest.scraped_at:
        return latest.scraped_at.date()
    return None


def existing_celex_set(session, candidates: List[str]) -> set:
    """Return the subset of `candidates` already present in legislative_carriages."""
    if not candidates:
        return set()
    rows = (
        session.query(LegislativeCarriage.celex_numbers)
        .filter(LegislativeCarriage.celex_numbers.overlap(candidates))
        .all()
    )
    found: set = set()
    for (numbers,) in rows:
        if numbers:
            for n in numbers:
                if n in candidates:
                    found.add(n)
    return found


async def run(
    days: int,
    sectors: List[str],
    limit: int,
    apply_writes: bool,
) -> int:
    log.info(
        f"Starting SPARQL sync: days={days}, sectors={sectors}, limit={limit}, apply={apply_writes}"
    )

    session = SessionLocal()
    try:
        watermark = get_watermark(session)
        if watermark:
            since = watermark - timedelta(days=1)  # 1-day overlap for safety
            log.info(f"Watermark: {watermark.isoformat()} -> querying since {since.isoformat()}")
        else:
            since = date.today() - timedelta(days=days)
            log.info(f"No watermark — first run, looking back {days} days from today: since {since.isoformat()}")

        log.info("Querying Cellar SPARQL for delta...")
        rows = await stream_oj_delta(
            since=since,
            until=date.today(),
            sectors=sectors,
            limit=limit,
        )
        log.info(f"Cellar returned {len(rows)} candidate acts")

        if not rows:
            log.info("Nothing to do.")
            return 0

        # De-dup against existing carriages
        candidate_celex = [r["celex"] for r in rows if r.get("celex")]
        existing = existing_celex_set(session, candidate_celex)
        new_rows = [r for r in rows if r.get("celex") and r["celex"] not in existing]
        log.info(f"  already in DB: {len(existing)}  |  new: {len(new_rows)}")

        if not new_rows:
            log.info("All candidates are already known. Done.")
            return 0

        if not apply_writes:
            log.info("DRY-RUN — would insert these new acts:")
            for r in new_rows[:20]:
                log.info(
                    f"  [{r.get('celex')}] ({r.get('date')}) {(r.get('title') or '')[:80]}"
                )
            if len(new_rows) > 20:
                log.info(f"  ... and {len(new_rows) - 20} more")
            return 0

        # Phase 5 — fetch IMMC tags in parallel batches (one SPARQL per CELEX).
        # We tolerate per-row failure: an IMMC fetch error must not block the
        # insert of the carriage row.
        log.info(f"Fetching IMMC tags for {len(new_rows)} new carriages...")
        immc_by_celex: dict[str, dict] = {}
        async with IMMCClient(timeout=30) as immc:
            for r in new_rows:
                celex = r.get("celex")
                if not celex:
                    continue
                try:
                    immc_by_celex[celex] = await immc.fetch_events_for_celex(celex)
                except Exception as e:  # noqa: BLE001
                    log.warning(f"  IMMC fetch failed for {celex}: {e}")
                    immc_by_celex[celex] = {"events": [], "error": str(e)[:200]}

        # Real insert
        added = 0
        for r in new_rows:
            celex = r["celex"]
            parsed = parse_celex(celex)
            doc_date_str = r.get("date") or ""
            try:
                doc_date = datetime.fromisoformat(doc_date_str.split("T")[0])
                doc_date = doc_date.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                doc_date = datetime.now(timezone.utc)

            carriage = LegislativeCarriage(
                file_id=f"sparql-{celex.lower()}",
                source=CarriageSourceEnum.EURLEX,  # reuse enum until SPARQL-specific value lands
                title=(r.get("title") or f"EU act {celex}")[:500],
                description=f"Discovered via Cellar SPARQL on {date.today().isoformat()}.",
                current_status=CarriageStatusEnum.ADOPTED if parsed["sector"] == "3" else CarriageStatusEnum.PROPOSED,
                text_type=parsed["text_type"],
                celex_numbers=[celex],
                eurlex_documents=[
                    {
                        "celex": celex,
                        "doc_type": parsed["doc_type"],
                        "date": doc_date_str,
                        "title": r.get("title"),
                        "eurlex_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
                    }
                ],
                scraped_at=doc_date,
                first_seen=doc_date,
                last_updated=datetime.now(timezone.utc),
                immc_tags=immc_by_celex.get(celex) or {"events": []},
            )
            session.add(carriage)
            added += 1
        session.commit()
        log.info(f"Inserted {added} new carriages.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPARQL-driven EUR-Lex delta sync")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--sectors", default="3,5", help="Comma-separated CELEX sectors")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--apply", action="store_true", help="Actually write to DB")
    args = parser.parse_args()
    sectors = [s.strip() for s in args.sectors.split(",") if s.strip()]
    sys.exit(asyncio.run(run(args.days, sectors, args.limit, args.apply)))
