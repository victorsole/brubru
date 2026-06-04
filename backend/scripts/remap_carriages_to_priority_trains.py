"""
Re-bucket legislative carriages to their correct EP Legislative-Train priority.

Bug being fixed: populate_carriages_fast.py / rescrape_carriages.py hardcoded
priority_number=1 and assigned EVERY carriage to Train 1, so 6 of the 7
von der Leyen priority trains showed "No legislative files found".

Authoritative source: the 7 EP theme pages (priority-1..7). Each lists the files
on that priority via `/legislative-train/theme-<x>/file-<slug>` links. We map
file slug -> priority and reassign carriages.train_id accordingly.

Safe / non-destructive of rows: only UPDATEs train_id on existing carriages.
- A carriage whose file_id matches a theme slug -> train_id = that priority's train.
- A carriage currently on a train but matching NO theme slug -> train_id = NULL
  (it is not on the current Schedule; it was mis-dumped into Train 1).
No new carriages are inserted (the carriages table is shared across features;
half-populated rows would pollute MTF / Comparator / search).

Usage:
    python3.12 -m backend.scripts.remap_carriages_to_priority_trains          # dry-run
    python3.12 -m backend.scripts.remap_carriages_to_priority_trains --apply  # persist
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from sqlalchemy import text as sqla_text
from core.database import SessionLocal
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper

_FILE_SLUG_RE = re.compile(r"/file-([a-z0-9-]+)")


async def _slug_to_priority() -> dict[str, int]:
    """Fetch the 7 theme pages and map each file slug -> priority number.

    First priority wins if a slug appears under more than one theme (rare).
    """
    scraper = LegislativeTrainScraper()
    mapping: dict[str, int] = {}
    for n in range(1, 8):
        slug_key = f"priority-{n}"
        url = f"{scraper.base_url}{scraper.theme_slugs[slug_key]}"
        try:
            html = await scraper._fetch(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  [priority-{n}] fetch error: {type(exc).__name__} {exc}")
            continue
        slugs = set(_FILE_SLUG_RE.findall(html or ""))
        for s in slugs:
            mapping.setdefault(s, n)
        print(f"  [priority-{n}] {len(slugs)} file slugs")
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-bucket carriages to priority trains.")
    parser.add_argument("--apply", action="store_true", help="Persist (default dry-run).")
    args = parser.parse_args()

    slug_priority = asyncio.run(_slug_to_priority())
    if not slug_priority:
        print("[ABORT] No theme slugs scraped; refusing to null out trains.")
        return
    print(f"[INFO] {len(slug_priority)} distinct file slugs across the 7 themes.")

    db = SessionLocal()
    try:
        # train id per priority
        train_ids = dict(
            db.execute(sqla_text("SELECT priority_number, id FROM legislative_trains")).fetchall()
        )
        missing = [n for n in range(1, 8) if n not in train_ids]
        if missing:
            print(f"[WARN] No train row for priorities {missing}; those files will be skipped.")

        # Bucket the matching slugs by priority
        by_priority: dict[int, list[str]] = {}
        for slug, pr in slug_priority.items():
            by_priority.setdefault(pr, []).append(slug)

        reassigned = {}
        for pr, slugs in sorted(by_priority.items()):
            tid = train_ids.get(pr)
            if not tid:
                continue
            n = db.execute(
                sqla_text(
                    "SELECT COUNT(*) FROM legislative_carriages WHERE file_id = ANY(:s)"
                ),
                {"s": slugs},
            ).scalar()
            reassigned[pr] = n
            if args.apply:
                db.execute(
                    sqla_text(
                        "UPDATE legislative_carriages SET train_id = :tid WHERE file_id = ANY(:s)"
                    ),
                    {"tid": tid, "s": slugs},
                )

        # Carriages currently on a train but not on ANY theme -> detach (train_id NULL)
        all_slugs = list(slug_priority.keys())
        detach_count = db.execute(
            sqla_text(
                "SELECT COUNT(*) FROM legislative_carriages "
                "WHERE train_id IS NOT NULL AND NOT (file_id = ANY(:s))"
            ),
            {"s": all_slugs},
        ).scalar()
        if args.apply:
            db.execute(
                sqla_text(
                    "UPDATE legislative_carriages SET train_id = NULL "
                    "WHERE train_id IS NOT NULL AND NOT (file_id = ANY(:s))"
                ),
                {"s": all_slugs},
            )
            db.commit()

        print(f"\n[{'APPLIED' if args.apply else 'DRY-RUN'}]")
        for pr in range(1, 8):
            print(f"  priority {pr}: {reassigned.get(pr, 0)} carriages matched")
        print(f"  detached from trains (not on Schedule): {detach_count}")
        if not args.apply:
            print("  re-run with --apply to persist")
    finally:
        db.close()


if __name__ == "__main__":
    main()
