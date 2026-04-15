#!/usr/bin/env python3.12
"""
Ingest EU institutional publications from configured RSS feeds.

Usage:
    python3.12 scripts/ingest_publications.py                # all configs
    python3.12 scripts/ingest_publications.py ec_press ema_news   # subset
"""

import asyncio
import sys
from pathlib import Path

# Make backend/ importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.ingestion.rss_ingestor import ingest_all, list_configs


async def main() -> int:
    only = sys.argv[1:] or None
    configs = list_configs()
    total = len(configs)
    print(f"[ingest] {len(only or configs)} of {total} configs will run")
    results = await ingest_all(only=only)
    inserted_total = 0
    for slug, stats in results.items():
        status = "OK" if not stats.get("error") else "ERR"
        inserted_total += stats.get("inserted", 0)
        print(f"  [{status}] {slug:25s}  fetched={stats.get('fetched',0):3d}  inserted={stats.get('inserted',0):3d}  skipped={stats.get('skipped',0):3d}")
    print(f"[ingest] total new publications: {inserted_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
