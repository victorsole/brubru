"""Surface the /api/v2/dpp news and events in My EU Bubble.

The DPP folder holds the Commission's passport news and events, but MEUB News
reads eu_news_items and My EU Calendar reads eu_calendar_events. Neither knew
about them, so a user whose whole remit is the digital product passport saw
nothing about it in either tab.

Both tables filter on policy_areas against the user's ticked interests, so the
route in is to publish these items tagged with the new interest,
"Ecodesign of sustainable products / Digital product passport". That means they
reach ANY user who ticks it, not just Terraqui: the same tick that drives the
filters drives this.

Idempotent: news on entry_key, events on (title, start_date).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

INTEREST = "Ecodesign of sustainable products / Digital product passport"
# Environment is kept alongside so the items also reach the broader audience the
# taxonomy already routes there.
AREAS = [INTEREST, "Environment"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        # ---------------- news ----------------
        news = db.execute(
            text("SELECT title, summary, public_url, document_date "
                 "FROM economy_items WHERE body_code = 'dpp' AND item_type = 'news' "
                 "ORDER BY document_date DESC")
        ).fetchall()
        print(f"=== news: {len(news)} item(s) in the DPP folder ===")
        added = 0
        for n in news:
            key = f"dpp:{n.public_url.rstrip('/').rsplit('/', 1)[-1][:100]}"
            exists = db.execute(
                text("SELECT count(*) FROM eu_news_items WHERE entry_key = :k"), {"k": key}
            ).scalar()
            if exists:
                print(f"  [OK]  {n.title[:62]}")
                continue
            added += 1
            print(f"  [ADD] {str(n.document_date)} {n.title[:56]}")
            if args.apply:
                db.execute(
                    text("""INSERT INTO eu_news_items
                        (entry_key, title, summary, news_date, institution,
                         commission_dg, item_type, source_key, policy_areas,
                         source_url, scraped_at, created_at)
                        VALUES (:k, :t, :s, :d, 'COMMISSION', 'GROW', 'news',
                                'dpp', :pa, :u, now(), now())"""),
                    {"k": key, "t": n.title, "s": n.summary, "d": n.document_date,
                     "pa": AREAS, "u": n.public_url},
                )

        # ---------------- events ----------------
        events = db.execute(
            text("SELECT title, summary, public_url, document_date "
                 "FROM economy_items WHERE body_code = 'dpp' AND item_type = 'event' "
                 "ORDER BY document_date DESC")
        ).fetchall()
        print(f"\n=== events: {len(events)} item(s) in the DPP folder ===")
        added_ev = 0
        for ev in events:
            if not ev.document_date:
                print(f"  [SKIP] no date: {ev.title[:56]}")
                continue
            exists = db.execute(
                text("SELECT count(*) FROM eu_calendar_events "
                     "WHERE title = :t AND start_date = :d"),
                {"t": ev.title, "d": ev.document_date},
            ).scalar()
            if exists:
                # It was already scraped generically, so it carries whatever
                # policy areas that scrape assigned and NOT the DPP interest,
                # which means the user whose remit this is would still not see
                # it. Add the tag rather than skip.
                print(f"  [TAG] already present, adding the interest: {ev.title[:44]}")
                if args.apply:
                    db.execute(
                        text("UPDATE eu_calendar_events SET policy_areas = ("
                             "  SELECT ARRAY(SELECT DISTINCT unnest("
                             "    COALESCE(policy_areas, '{}') || CAST(:pa AS text[]))))"
                             " WHERE title = :t AND start_date = :d"),
                        {"pa": AREAS, "t": ev.title, "d": ev.document_date},
                    )
                continue
            added_ev += 1
            print(f"  [ADD] {ev.document_date} {ev.title[:56]}")
            if args.apply:
                db.execute(
                    text("""INSERT INTO eu_calendar_events
                        (institution, event_type, title, description, start_date,
                         all_day, commission_dg, policy_areas, status, source_url,
                         source, scraped_at)
                        VALUES ('COMMISSION', 'conference', :t, :d, :sd,
                                true, 'GROW', :pa, :st, :u, 'dpp', now())"""),
                    {"t": ev.title, "d": ev.summary, "sd": ev.document_date,
                     "pa": AREAS, "u": ev.public_url,
                     # anything already past is completed, not scheduled
                     "st": "completed" if str(ev.document_date) < "2026-08-12"
                           else "scheduled"},
                )

        if args.apply:
            db.commit()
            print("\n=== verification ===")
            n = db.execute(
                text("SELECT count(*) FROM eu_news_items WHERE source_key = 'dpp'")
            ).scalar()
            e = db.execute(
                text("SELECT count(*) FROM eu_calendar_events "
                     "WHERE :i = ANY(policy_areas)"), {"i": INTEREST}
            ).scalar()
            print(f"  eu_news_items tagged dpp     : {n}/{len(news)} "
                  f"{'OK' if n == len(news) else 'FAIL'}")
            print(f"  eu_calendar_events tagged dpp: {e}/{len(events)} "
                  f"{'OK' if e == len(events) else 'FAIL'}")
            # do they carry the interest that makes them reachable?
            bad = db.execute(
                text("SELECT count(*) FROM eu_news_items WHERE source_key = 'dpp' "
                     "AND NOT (:i = ANY(policy_areas))"), {"i": INTEREST}
            ).scalar()
            print(f"  news missing the interest tag: {bad} "
                  f"{'OK' if bad == 0 else 'FAIL'}")
            if n != len(news) or e != len(events) or bad:
                rc = 1
        else:
            print(f"\n[DRY-RUN] would add {added} news, {added_ev} events")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
