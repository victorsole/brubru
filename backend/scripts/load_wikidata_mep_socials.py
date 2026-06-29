"""Phase 4.2.1 CLI — load current MEPs' social handles from Wikidata.

Usage:
  python3.12 scripts/load_wikidata_mep_socials.py            # dry-run
  python3.12 scripts/load_wikidata_mep_socials.py --apply
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
from services.social.wikidata_mep_loader import fetch_mep_socials, load  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cache", help="cache file: load bindings from it if present, else fetch + save")
    args = ap.parse_args()
    if args.cache and Path(args.cache).exists():
        bindings = json.load(open(args.cache))
        print(f"loaded {len(bindings)} bindings from cache {args.cache}")
    else:
        print("querying Wikidata for current (term-10) MEP socials...")
        bindings = fetch_mep_socials()
        if args.cache:
            json.dump(bindings, open(args.cache, "w"))
            print(f"cached {len(bindings)} bindings -> {args.cache}")
    db = SessionLocal()
    try:
        stats = load(db, bindings, dry_run=not args.apply)
    finally:
        db.close()
    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] MEPs={stats['meps']} accounts_written={stats['written']}")
    print("by_platform:", dict(sorted(stats["by_platform"].items(), key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
