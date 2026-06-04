"""
Sync European Parliament news into eu_news_items (MEUB "News").

EP press room + all committees (press-releases) + all delegations (communiques).
JS-rendered EP pages -> Playwright (one browser for the whole run). NO Anthropic.
Resilient per source (rolls back on transient Supabase drop). Idempotent.

Usage:
    python3.12 -m scripts.sync_ep_news
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.database import SessionLocal
from models.eu_news_item import EuNewsItem
from services.scrapers.ep_news_scraper import ep_sources, scrape_ep_source
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher


def _upsert(db, it) -> str:
    existing = db.query(EuNewsItem).filter(EuNewsItem.entry_key == it["entry_key"]).first()
    if existing:
        changed = False
        for f in ("title", "news_date", "source_url", "item_type"):
            if it.get(f) and getattr(existing, f) != it.get(f):
                setattr(existing, f, it.get(f)); changed = True
        return "updated" if changed else "skipped"
    db.add(EuNewsItem(
        entry_key=it["entry_key"], title=it["title"], summary=it.get("summary"),
        news_date=it.get("news_date"), institution="EP", commission_dg=None,
        item_type=it.get("item_type", "press"), source_key=it.get("source_key"),
        image_url=it.get("image_url"), source_url=it.get("source_url"), policy_areas=[],
    ))
    return "added"


def main():
    db = SessionLocal()
    counts = {"added": 0, "updated": 0, "skipped": 0, "sources": 0, "empty": 0, "errors": 0}
    srcs = ep_sources()
    try:
        with WafBrowserFetcher(settle_ms=7000, networkidle_ms=18000) as fetcher:
            for src in srcs:
                try:
                    items = scrape_ep_source(src, fetcher)
                except Exception as e:
                    print(f"  source failed {src['url']}: {e}"); counts["errors"] += 1; continue
                counts["sources"] += 1
                if not items:
                    counts["empty"] += 1
                try:
                    for it in items:
                        counts[_upsert(db, it)] += 1
                    db.commit()
                except Exception as e:
                    db.rollback(); print(f"  commit failed {src['url']}: {e}"); counts["errors"] += 1
        print("[ep_news] " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    finally:
        db.close()


if __name__ == "__main__":
    main()
