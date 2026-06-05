"""
Aggregate EU institutional news into eu_news_items (MEUB "News").

Scrapes the Commission hub + every DG / agency newsroom (dg_news_sources.py),
parses the ECL news cards (image + date + summary), and upserts into eu_news_items
tagged institution=COMMISSION + commission_dg, so the feed is filterable by
department and by the user's Policy Interests. Also the store the /news skill reads.
NO LLM / NO Anthropic.

Usage:
    python3.12 -m scripts.sync_dg_news
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.database import SessionLocal
from models.eu_news_item import EuNewsItem
from services.tracking.policy_area_classifier import classify
from services.scrapers.dg_news_sources import DG_NEWS_SOURCES, EU_BODY_FEEDS, OUTLET_FEEDS
from services.scrapers.dg_news_scraper import scrape_source

ALL_SOURCES = DG_NEWS_SOURCES + EU_BODY_FEEDS + OUTLET_FEEDS


def _upsert(db, it) -> str:
    existing = db.query(EuNewsItem).filter(EuNewsItem.entry_key == it["entry_key"]).first()
    if existing:
        changed = False
        for f in ("title", "summary", "news_date", "image_url", "source_url", "item_type"):
            if it.get(f) and getattr(existing, f) != it.get(f):
                setattr(existing, f, it.get(f)); changed = True
        if changed:
            existing.policy_areas = classify(existing.title or "", existing.summary or "",
                                             dg=existing.commission_dg)
        return "updated" if changed else "skipped"
    db.add(EuNewsItem(
        entry_key=it["entry_key"], title=it["title"], summary=it.get("summary"),
        news_date=it.get("news_date"), institution=it.get("institution", "COMMISSION"),
        commission_dg=it.get("commission_dg"), item_type=it.get("item_type", "news"),
        source_key=it.get("source_key"), image_url=it.get("image_url"),
        source_url=it.get("source_url"),
        policy_areas=classify(it["title"], it.get("summary") or "", dg=it.get("commission_dg")),
    ))
    return "added"


def main():
    db = SessionLocal()
    counts = {"added": 0, "updated": 0, "skipped": 0, "sources": 0, "empty": 0, "errors": 0}
    try:
        for src in ALL_SOURCES:
            try:
                items = scrape_source(src)
            except Exception as e:
                print(f"  source failed {src['url']}: {e}"); counts["errors"] += 1; continue
            counts["sources"] += 1
            if not items:
                counts["empty"] += 1
            # Commit per source; a transient Supabase drop rolls back THIS source
            # only (NullPool hands a fresh connection next use) and we continue.
            try:
                for it in items:
                    counts[_upsert(db, it)] += 1
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"  source commit failed {src['url']}: {e}")
                counts["errors"] += 1
        print("[dg_news] " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    finally:
        db.close()


if __name__ == "__main__":
    main()
