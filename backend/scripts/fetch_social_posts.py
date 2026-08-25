"""Phase 4.2 CLI — fetch recent posts from open-tier accounts (Bluesky/Mastodon/YouTube).

Usage:
  python3.12 scripts/fetch_social_posts.py --limit 20            # dry-run, first 20 accounts
  python3.12 scripts/fetch_social_posts.py --limit 20 --apply
  python3.12 scripts/fetch_social_posts.py --apply               # all content_fetch_enabled
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from services.social.post_fetcher import run, OPEN_TIER  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="cap accounts (testing)")
    ap.add_argument("--per-account", type=int, default=10)
    ap.add_argument("--platforms", help="comma list (default Bluesky/Mastodon/YouTube)")
    ap.add_argument("--pace", type=float, default=0.4, help="seconds between accounts")
    ap.add_argument("--empty-streak-stop", type=int, help="stop after N consecutive empties (X throttle)")
    # action="append", never nargs="+": a repeated flag with nargs silently
    # overwrites its earlier values (three confirmed incidents in this repo).
    ap.add_argument("--handle", action="append",
                    help="fetch this handle regardless of when it was last checked; repeatable")
    ap.add_argument("--prioritise-verified", action="store_true",
                    help="verified accounts first, then oldest-first (use on throttled platforms)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    plats = tuple(args.platforms.split(",")) if args.platforms else OPEN_TIER
    db = SessionLocal()
    try:
        stats = run(db, platforms=plats, limit_accounts=args.limit, per_account=args.per_account,
                    pace=args.pace, empty_streak_stop=args.empty_streak_stop, dry_run=not args.apply,
                    handles=args.handle,
                    prioritise_verified=args.prioritise_verified)
    finally:
        db.close()
    print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] accounts={stats['accounts']} "
          f"fetched_ok={stats['fetched_ok']} skipped={stats['skipped']} posts={stats['posts_written']}")
    print("by_platform:", stats["by_platform"])
    print("skips:", stats["skips"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
