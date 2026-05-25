#!/usr/bin/env python3.12
"""
Sync the LEGISSUM "Summaries of EU legislation" catalogue into
public.legissum_summaries (migration 086).

Catalogue-only (fast, ~32 chapter renders):
    python3.12 -m scripts.sync_legissum
Limit chapters (sampling / smoke):
    python3.12 -m scripts.sync_legissum --chapters 3
Full crawl incl. each summary's title/CELEX/body (SLOW — hours):
    python3.12 -m scripts.sync_legissum --fetch-text

Writes via DATABASE_URL (prod Supabase). Idempotent (upsert by slug).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from core.database import SessionLocal  # noqa: E402
from services.scrapers.legissum_scraper import enrich_pending, sync_legissum  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapters", type=int, default=None, help="Limit number of chapters (default: all ~32)")
    ap.add_argument("--fetch-text", action="store_true", help="Also fetch each summary's title/CELEX/body during the chapter crawl (slow)")
    ap.add_argument("--enrich", action="store_true", help="Resumable: enrich only rows with no body yet (text_fetched_at IS NULL)")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to enrich this run (with --enrich)")
    ap.add_argument("--sleep", type=float, default=0.5, help="Delay between summary page fetches")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.enrich:
            result = enrich_pending(db, limit=args.limit, sleep_s=args.sleep)
        else:
            result = sync_legissum(
                db,
                chapters_limit=args.chapters,
                fetch_text=args.fetch_text,
                sleep_s=args.sleep,
            )
    finally:
        db.close()
    print(f"[OK] LEGISSUM sync: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
