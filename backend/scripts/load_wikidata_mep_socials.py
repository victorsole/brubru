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
from services.social.wikidata_mep_loader import (  # noqa: E402
    ep_display_name, fetch_ep_current, fetch_mep_socials, load, needs_name_fallback)


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
    ep_names = None
    if needs_name_fallback(bindings):
        # Some MEPs have no Wikidata label in any requested language: fall back to the EP
        # directory name via P1186. Never store a bare QID as a name.
        try:
            ep_names = {eid: ep_display_name(m) for eid, m in fetch_ep_current().items()}
            print(f"EP directory loaded for name fallback: {len(ep_names)} current MEPs")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] EP directory fetch failed ({type(exc).__name__}); "
                  "unlabelled MEPs will get entity_name NULL")
    db = SessionLocal()
    try:
        stats = load(db, bindings, dry_run=not args.apply, ep_names=ep_names)
    finally:
        db.close()
    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] MEPs={stats['meps']} accounts_written={stats['written']}")
    if stats["unnamed_meps"]:
        print(f"[ERROR] {len(stats['unnamed_meps'])} MEP(s) with no name anywhere "
              f"(entity_name NULL): {', '.join(stats['unnamed_meps'])}")
    print("by_platform:", dict(sorted(stats["by_platform"].items(), key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
