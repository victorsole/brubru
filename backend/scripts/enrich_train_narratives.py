"""
Enrich legislative_carriages with EP Legislative Train "state of play" narratives.

Usage:
    # single file (test)
    python3.12 -m backend.scripts.enrich_train_narratives --url "https://www.europarl.europa.eu/legislative-train/spotlight-MFF/file-common-agricultural-policy-2028-2034"
    # discover + enrich every Train file that matches a carriage
    python3.12 -m backend.scripts.enrich_train_narratives --all          # dry-run
    python3.12 -m backend.scripts.enrich_train_narratives --all --apply
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from services.scrapers.legislative_train_scraper import LegislativeTrainScraper
from services.scrapers.legislative_train_narrative import (
    discover_file_urls,
    enrich_carriage_from_url,
)


async def _run(urls, apply: bool, detach_thin: bool = False) -> None:
    from sqlalchemy import text as sqla_text
    s = LegislativeTrainScraper()
    db = SessionLocal()
    try:
        counts = {"enriched": 0, "no_carriage": 0, "no_oeil_ref": 0, "no_narrative": 0}
        placed = 0
        for i, url in enumerate(urls, 1):
            res = await enrich_carriage_from_url(db, url, scraper=s, apply=apply)
            counts[res["status"]] = counts.get(res["status"], 0) + 1
            if res["status"] == "enriched":
                if res.get("train_id"):
                    placed += 1
                print(f"  [{i}/{len(urls)}] {res['oeil_ref']} <- {res['chars']} chars"
                      f"{' [train]' if res.get('train_id') else ''}")
            await asyncio.sleep(0.4)
        print(f"\n[{'APPLIED' if apply else 'DRY-RUN'}] "
              + ", ".join(f"{k}={v}" for k, v in counts.items())
              + f", placed_on_train={placed}")

        # Detach the thin theme-slug duplicates: trains should hold the rich OEIL
        # carriages only, so modals are full and linked to MTF.
        if detach_thin:
            n = db.execute(sqla_text(
                "SELECT COUNT(*) FROM legislative_carriages "
                "WHERE train_id IS NOT NULL AND oeil_procedure_ref IS NULL"
            )).scalar()
            if apply:
                db.execute(sqla_text(
                    "UPDATE legislative_carriages SET train_id = NULL "
                    "WHERE train_id IS NOT NULL AND oeil_procedure_ref IS NULL"
                ))
                db.commit()
            print(f"  detached thin (no OEIL ref) carriages from trains: {n}")
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Enrich carriages with Legislative Train narratives.")
    p.add_argument("--url", help="Enrich a single Train file URL.")
    p.add_argument("--all", action="store_true", help="Discover + enrich every Train file.")
    p.add_argument("--apply", action="store_true", help="Persist (default dry-run for --all).")
    args = p.parse_args()

    if args.url:
        asyncio.run(_run([args.url], apply=True))
    elif args.all:
        urls = asyncio.run(discover_file_urls())
        print(f"[INFO] discovered {len(urls)} Train file URLs")
        asyncio.run(_run(urls, apply=args.apply, detach_thin=True))
    else:
        p.error("provide --url <url> or --all")


if __name__ == "__main__":
    main()
