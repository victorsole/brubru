#!/usr/bin/env python3.12
"""
Warm the committee draft-agenda body cache.

Iterates `eu_calendar_events` rows with source='ep_committee_agenda' and an
agenda_url, fetches + parses the doceo agenda document, and caches body_txt +
body_html on the event's related_documents JSONB (see
services.scrapers.committee_agenda_body_extractor.ensure_agenda_body).

doceo is JS-WAF-walled to most hosts; run this from the deployment host
(Railway), the same place committee_minutes PDF extraction succeeds.

Usage:
    python3.12 -m scripts.backfill_committee_agenda_bodies               # all uncached
    python3.12 -m scripts.backfill_committee_agenda_bodies --committee LIBE
    python3.12 -m scripts.backfill_committee_agenda_bodies --limit 20 --recompute
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import func  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from models.eu_calendar import EUCalendarEvent  # noqa: E402
from services.scrapers.committee_agenda_body_extractor import (  # noqa: E402
    CACHE_TXT,
    extract_agenda_body,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Warm the committee agenda body cache.")
    ap.add_argument("--committee", help="Restrict to one committee code (e.g. LIBE).")
    ap.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = no cap).")
    ap.add_argument("--recompute", action="store_true", help="Re-fetch even if a body is already cached.")
    args = ap.parse_args()

    db = SessionLocal()
    stats = {"seen": 0, "fetched": 0, "empty": 0, "skipped": 0, "errors": 0}
    try:
        q = db.query(EUCalendarEvent).filter(
            EUCalendarEvent.source == "ep_committee_agenda",
            EUCalendarEvent.agenda_url.isnot(None),
        )
        if args.committee:
            q = q.filter(func.upper(EUCalendarEvent.ep_committee_code) == args.committee.upper())
        q = q.order_by(EUCalendarEvent.start_date.desc())
        if args.limit:
            q = q.limit(args.limit)

        for event in q.all():
            stats["seen"] += 1
            rd = event.related_documents or {}
            if rd.get(CACHE_TXT) and not args.recompute:
                stats["skipped"] += 1
                continue
            url = event.agenda_url or event.source_url
            try:
                txt, html = extract_agenda_body(url)
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                print(f"[ERROR] {event.ep_committee_code} {event.start_date}: {exc}")
                continue
            if not txt:
                stats["empty"] += 1
                continue
            new_rd = dict(rd)
            new_rd[CACHE_TXT] = txt
            new_rd["agenda_body_html"] = html
            from datetime import datetime

            new_rd["agenda_body_extracted_at"] = datetime.utcnow().isoformat()
            event.related_documents = new_rd
            db.commit()
            stats["fetched"] += 1
            print(f"[OK] {event.ep_committee_code} {event.start_date}: {len(txt)} chars")
    finally:
        db.close()

    print(
        f"[DONE] seen={stats['seen']} fetched={stats['fetched']} "
        f"empty={stats['empty']} skipped={stats['skipped']} errors={stats['errors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
