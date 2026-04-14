#!/usr/bin/env python3.12
"""
Precompute recital-article maps for tracked EU laws.

Runs link_recitals_to_articles for every CELEX currently tracked in the
Legislative Train (or an explicit list) and stores the result in
eu_laws.extra_metadata.recital_article_map.

Usage
-----
    # Every CELEX tracked by any user
    python3.12 scripts/precompute_recital_article_maps.py --tracked

    # Explicit CELEX list (space-separated)
    python3.12 scripts/precompute_recital_article_maps.py --celex 32016R0679 32024R1689

    # Every law in eu_laws that is flagged primary
    python3.12 scripts/precompute_recital_article_maps.py --primary-only --limit 200
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from sqlalchemy import text as sqla_text

from core.database import SessionLocal
from services.parsers.recital_article_store import get_or_compute_map, CURRENT_VERSION, VERSION_KEY


def iter_tracked(db) -> Iterable[str]:
    rows = db.execute(
        sqla_text(
            """
            SELECT DISTINCT celex_number
              FROM legislative_tracking
             WHERE celex_number IS NOT NULL
            """
        )
    ).fetchall()
    for (celex,) in rows:
        if celex:
            yield celex


def iter_primary(db, limit: int) -> Iterable[str]:
    rows = db.execute(
        sqla_text(
            """
            SELECT celex
              FROM eu_laws
             WHERE is_primary_legislation = true
               AND celex IS NOT NULL
               AND xml_path IS NOT NULL
             ORDER BY date DESC NULLS LAST
             LIMIT :limit
            """
        ),
        {"limit": limit},
    ).fetchall()
    for (celex,) in rows:
        yield celex


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--tracked", action="store_true", help="All CELEX in legislative_tracking")
    src.add_argument("--celex", nargs="+", help="Explicit CELEX numbers")
    src.add_argument("--primary-only", action="store_true", help="All primary laws (regulations, directives)")
    ap.add_argument("--limit", type=int, default=500, help="Limit for --primary-only")
    ap.add_argument("--force", action="store_true", help="Recompute even if cached")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.celex:
            targets = list(args.celex)
        elif args.tracked:
            targets = list(iter_tracked(db))
        else:
            targets = list(iter_primary(db, args.limit))

        print(f"[INFO] {len(targets)} CELEX to process")
        ok = skipped = failed = 0
        for i, celex in enumerate(targets, 1):
            try:
                mapping = get_or_compute_map(db, celex, force_recompute=args.force)
            except Exception as exc:
                failed += 1
                print(f"[{i:>4}/{len(targets)}] ERROR {celex}: {exc}")
                continue
            if mapping is None:
                skipped += 1
                print(f"[{i:>4}/{len(targets)}] skip {celex} (no xml_path)")
            else:
                ok += 1
                linked = sum(1 for v in mapping.values() if v)
                total = sum(len(v) for v in mapping.values())
                print(f"[{i:>4}/{len(targets)}] {celex}: {linked}/{len(mapping)} articles, {total} links")

        print(f"\n[SUMMARY] ok={ok} skipped={skipped} failed={failed}")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
