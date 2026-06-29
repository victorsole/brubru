"""Phase 4.1 CLI — load the EU social-media directory into social_accounts.

Usage:
  python3.12 scripts/load_eu_social_directory.py --first-subset            # dry-run, step-1 subset
  python3.12 scripts/load_eu_social_directory.py --first-subset --apply
  python3.12 scripts/load_eu_social_directory.py --from-cache <path> --first-subset --apply
  python3.12 scripts/load_eu_social_directory.py --apply                   # full directory (later)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from services.social.eu_directory_loader import fetch_directory, load  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache", help="load records from a cached JSON file instead of live fetch")
    ap.add_argument("--first-subset", action="store_true", help="only central-account, single clean institution")
    ap.add_argument("--agencies", action="store_true", help="only the lumped agency rows (resolved to economy_bodies)")
    ap.add_argument("--office", action="store_true", help="office wave: local_office + subdivision, all institutions")
    ap.add_argument("--apply", action="store_true", help="write (default dry-run)")
    args = ap.parse_args()

    if args.from_cache:
        records = json.load(open(args.from_cache))
        print(f"loaded {len(records)} records from cache")
    else:
        print("fetching directory live (paced)...")
        records = fetch_directory()
        print(f"fetched {len(records)} records")

    db = SessionLocal()
    try:
        atypes = {"local_office", "subdivision"} if args.office else None
        stats = load(db, records, only_central_clean=args.first_subset,
                     only_agency=args.agencies, account_types=atypes, dry_run=not args.apply)
    finally:
        db.close()
    print(f"\n[{'APPLIED' if args.apply else 'DRY-RUN'}] {{'input':{stats['input']}, 'written':{stats['written']}, "
          f"'skipped':{stats['skipped']}, 'person':{stats['person']}, 'unresolved_agency':{stats['unresolved_agency']}}}")
    print("by_platform:", dict(sorted(stats["by_platform"].items(), key=lambda x: -x[1])))
    print("by_entity:", dict(sorted(stats["by_entity"].items(), key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
