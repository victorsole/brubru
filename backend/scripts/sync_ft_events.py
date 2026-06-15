"""
Sync EU Funding & Tenders Portal events into eu_calendar_events (MEUB Calendar).

Mirrors the F&T Portal events feed already ingested into economy_items
(body_code='ftportal', item_type='event', via the API v2 /api/v2/funding/ft-events
layer) into the My EU Calendar aggregate so info days, webinars and conferences
show up in the calendar, filterable under the 'Funding & Tenders' institution.
Idempotent (dedup by source='ft_portal' + external_id). NO Anthropic.

Usage:
    python3.12 -m scripts.sync_ft_events
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text

from core.database import SessionLocal
from services.scrapers.eu_calendar_sync_service import EUCalendarSyncService


def _event_type(title: str, summary: str) -> str:
    """Map an F&T event to the calendar's event_type vocabulary."""
    hay = f"{title} {summary}".lower()
    if "webinar" in hay or "online info" in hay or "online information" in hay:
        return "webinar"
    if "workshop" in hay:
        return "workshop"
    if "training" in hay or "course" in hay:
        return "training"
    # Info days, brokerage events, conferences and fairs all read as conferences.
    return "conference"


def _rows(db):
    return db.execute(text(
        "SELECT id, title, summary, public_url, document_date "
        "FROM economy_items "
        "WHERE body_code = 'ftportal' AND item_type = 'event' AND title IS NOT NULL "
        "  AND document_date IS NOT NULL "
        "ORDER BY document_date DESC NULLS LAST, id DESC"
    )).mappings().all()


def main():
    svc = EUCalendarSyncService()
    db = SessionLocal()
    result = {"source": "ft_portal", "added": 0, "updated": 0, "skipped": 0, "errors": 0}
    try:
        rows = _rows(db)
        print(f"[ft_events] {len(rows)} ftportal event rows in economy_items")
        for r in rows:
            try:
                title = (r["title"] or "").strip()
                summary = (r.get("summary") or "").strip()
                event_data = {
                    "institution": "FUNDING",
                    "event_type": _event_type(title, summary),
                    "title": title[:500],
                    "description": summary or None,
                    "start_date": r["document_date"].date(),
                    "all_day": True,
                    "status": "scheduled",
                    "source_url": r.get("public_url"),
                    "source": "ft_portal",
                    "external_id": str(r["id"]),
                }
                svc._upsert_event(db, event_data, result)
            except Exception as e:
                db.rollback(); print(f"  upsert failed {r['id']}: {e}"); result["errors"] += 1
        db.commit()
    finally:
        db.close()
    print("[ft_events]", " ".join(f"{k}={v}" for k, v in result.items() if k != "source"))


if __name__ == "__main__":
    main()
