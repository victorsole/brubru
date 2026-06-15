"""
Sync EU Funding & Tenders Portal news into eu_news_items (MEUB "News").

Mirrors the F&T Portal news feed already ingested into economy_items
(body_code='ftportal', item_type='news', via the API v2 /api/v2/funding/ft-news
layer) into the MEUB News aggregate so it shows up in the News tab alongside the
institutional feed, PI-filterable and facet-able. Idempotent. NO Anthropic.

Tagged institution='FUNDING' + source_key='F&T Portal'; the News-tab facet picks
the new institution up automatically.

Usage:
    python3.12 -m scripts.sync_ft_news
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text

from core.database import SessionLocal
from models.eu_news_item import EuNewsItem
from services.tracking.policy_area_classifier import classify


def _rows(db):
    return db.execute(text(
        "SELECT id, title, summary, public_url, document_date "
        "FROM economy_items "
        "WHERE body_code = 'ftportal' AND item_type = 'news' AND title IS NOT NULL "
        "ORDER BY document_date DESC NULLS LAST, id DESC"
    )).mappings().all()


def _upsert(db, r) -> str:
    entry_key = f"ft_portal_news:{r['id']}"
    news_date = r["document_date"].date() if r.get("document_date") else None
    existing = db.query(EuNewsItem).filter(EuNewsItem.entry_key == entry_key).first()
    if existing:
        changed = False
        for f, v in (("title", r["title"]), ("summary", r.get("summary")),
                     ("news_date", news_date), ("source_url", r.get("public_url"))):
            if v is not None and getattr(existing, f) != v:
                setattr(existing, f, v); changed = True
        if changed:
            existing.policy_areas = classify(existing.title or "", existing.summary or "")
        return "updated" if changed else "skipped"
    db.add(EuNewsItem(
        entry_key=entry_key, title=r["title"], summary=r.get("summary"),
        news_date=news_date, institution="FUNDING", commission_dg=None,
        item_type="news", source_key="F&T Portal",
        image_url=None, source_url=r.get("public_url"),
        policy_areas=classify(r["title"], r.get("summary") or ""),
    ))
    return "added"


def main():
    db = SessionLocal()
    counts = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    try:
        rows = _rows(db)
        print(f"[ft_news] {len(rows)} ftportal news rows in economy_items")
        for r in rows:
            try:
                counts[_upsert(db, r)] += 1
            except Exception as e:
                db.rollback(); print(f"  upsert failed {r['id']}: {e}"); counts["errors"] += 1
        db.commit()
    finally:
        db.close()
    print("[ft_news]", " ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
