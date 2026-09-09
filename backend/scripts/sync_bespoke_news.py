"""
Sync the bespoke-CMS EU bodies' news into eu_news_items (MEUB "News").

The holdouts with no RSS/ECL (Council, ECA, EIB, CoR, Ombudsman, ECHA, ENISA,
EUIPO, EUAA, Eurojust, FRA, EU-OSHA, ACER, ECDC, CEPOL, EIT, CPVO, CdT) —
rendered with Playwright + per-site link rules (bespoke_news_scraper.py).
One browser for the whole run. Resilient per source. Idempotent. NO Anthropic.

Usage:
    python3.12 -m scripts.sync_bespoke_news
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from core.database import SessionLocal
from models.eu_news_item import EuNewsItem
from services.news.fetch_anchor import stamp_fetched
from services.tracking.policy_area_classifier import classify
from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES, BespokeFetchError, scrape_bespoke, scrape_eeas
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher


def _upsert(db, it) -> str:
    existing = db.query(EuNewsItem).filter(EuNewsItem.entry_key == it["entry_key"]).first()
    if existing:
        changed = False
        for f in ("title", "news_date", "source_url", "item_type"):
            if it.get(f) and getattr(existing, f) != it.get(f):
                setattr(existing, f, it.get(f)); changed = True
        if changed:
            existing.policy_areas = classify(existing.title or "", existing.summary or "")
        return "updated" if changed else "skipped"
    db.add(EuNewsItem(
        entry_key=it["entry_key"], title=it["title"], summary=it.get("summary"),
        news_date=it.get("news_date"), institution=it["institution"], commission_dg=None,
        item_type=it.get("item_type", "news"), source_key=it.get("source_key"),
        image_url=it.get("image_url"), source_url=it.get("source_url"),
        policy_areas=classify(it["title"], it.get("summary") or ""),
    ))
    return "added"


def main():
    db = SessionLocal()
    counts = {"added": 0, "updated": 0, "skipped": 0, "sources": 0, "empty": 0,
              "errors": 0, "unreachable": 0}
    empty: list = []
    unreachable: list = []
    failed: list = []
    try:
        with WafBrowserFetcher(settle_ms=7000, networkidle_ms=18000) as fetcher:
            for cfg in BESPOKE_SOURCES:
                try:
                    items = scrape_bespoke(cfg, fetcher)
                except BespokeFetchError as e:
                    # UNREACHABLE, not empty. Named so stderr_tail identifies it.
                    print(f"  UNREACHABLE {cfg['institution']}: {e}", file=sys.stderr)
                    counts["unreachable"] += 1; unreachable.append(cfg["institution"]); continue
                except Exception as e:
                    print(f"  source failed {cfg['institution']}: {e}", file=sys.stderr)
                    counts["errors"] += 1; failed.append(cfg["institution"]); continue
                counts["sources"] += 1
                if not items:
                    counts["empty"] += 1
                    empty.append(cfg["institution"])
                print(f"  {cfg['institution']:10s} {len(items)} items")
                try:
                    for it in items:
                        counts[_upsert(db, it)] += 1
                    stamp_fetched(db, [i["entry_key"] for i in items])
                    db.commit()
                except Exception as e:
                    db.rollback(); print(f"  commit failed {cfg['institution']}: {e}"); counts["errors"] += 1

            # EEAS: dedicated card parser across all curated filter pages
            try:
                eeas_items = scrape_eeas(fetcher)
                counts["sources"] += 1
                if not eeas_items:
                    counts["empty"] += 1
                print(f"  {'EEAS':10s} {len(eeas_items)} items")
                for it in eeas_items:
                    counts[_upsert(db, it)] += 1
                stamp_fetched(db, [i["entry_key"] for i in eeas_items])
                db.commit()
            except Exception as e:
                db.rollback(); print(f"  source failed EEAS: {e}"); counts["errors"] += 1
        print("[bespoke_news] " + ", ".join(f"{k}={v}" for k, v in counts.items()))

        # A run that reaches nothing, or reaches a source it cannot fetch, is NOT a
        # success. This script returned None -- exit 0 -- whatever happened, so the
        # cron recorded `success` 352 consecutive times while COUNCIL news went 70
        # days without a row. The cron maps exit code only (0 = success, non-zero =
        # failed with stderr_tail), so the verdict has to be an exit code and the
        # culprits have to be on stderr to be visible at all.
        if unreachable:
            print(f"[bespoke_news] FAILED: unreachable sources: {', '.join(unreachable)}",
                  file=sys.stderr)
            return 1
        if failed:
            print(f"[bespoke_news] FAILED: errored sources: {', '.join(failed)}",
                  file=sys.stderr)
            return 1
        if counts["sources"] and counts["empty"] == counts["sources"]:
            print("[bespoke_news] FAILED: every source parsed to zero -- that is the "
                  "fetcher or the parser, not sixteen simultaneously quiet publishers",
                  file=sys.stderr)
            return 1
        if empty:
            # Degraded: some sources parsed nothing. Exit 0 (the run did land rows)
            # but name them, so a stale feed is traceable to a source and not just
            # to a silent aggregate.
            print(f"[bespoke_news] DEGRADED: parsed 0 items: {', '.join(empty)}",
                  file=sys.stderr)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
