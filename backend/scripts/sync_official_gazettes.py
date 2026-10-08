#!/usr/bin/env python3.12
"""Daily BOE + DOGC sweep for the Terraqui / LIFE DPP-TEX watch.

Reads the last N days of the Spanish BOE and the Catalan DOGC open data, keeps the items
inside the client's remit (services/scrapers/official_gazettes.py) and upserts them into
official_gazette_items. Two sync_runs rows are written, `official_gazettes_boe` and
`official_gazettes_dogc`, which the client source ledger and dpp_watch read.

A run that READ nothing is a failure, not a quiet day (the repo's standing rule for jobs
that store nothing): the BOE publishes Monday to Saturday, so a multi-day window with no
issue at all, or a DOGC window with no norm at all, exits non-zero and records `failed`.
"Scanned many, matched none" is the healthy quiet state and exits 0.

Usage (from backend/):
    python3.12 scripts/sync_official_gazettes.py                 # dry run: read, classify, print
    python3.12 scripts/sync_official_gazettes.py --apply         # also upsert + record sync_runs
    python3.12 scripts/sync_official_gazettes.py --apply --days 30 --dogc-days 400   # backfill
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

logging.disable(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.official_gazettes import ScanResult, fetch_boe, fetch_dogc  # noqa: E402
from services.sync.freshness import record_run  # noqa: E402

# Windows shorter than this cannot be judged: a 2-day BOE window can legitimately hold a
# single issue, and a DOGC window of a week can hold no norm.
MIN_BOE_DAYS_TO_JUDGE = 3
MIN_DOGC_DAYS_TO_JUDGE = 14

_UPSERT = text("""
    INSERT INTO official_gazette_items
        (gazette, identifier, published_date, title, title_es, section, department, rank,
         url, pdf_url, match_tier, matched_terms)
    VALUES
        (:gazette, :identifier, :published_date, :title, :title_es, :section, :department, :rank,
         :url, :pdf_url, :match_tier, :matched_terms)
    ON CONFLICT (gazette, identifier) DO UPDATE SET
        title = EXCLUDED.title, title_es = EXCLUDED.title_es, section = EXCLUDED.section,
        department = EXCLUDED.department, rank = EXCLUDED.rank, url = EXCLUDED.url,
        pdf_url = EXCLUDED.pdf_url, match_tier = EXCLUDED.match_tier,
        matched_terms = EXCLUDED.matched_terms,
        scraped_at = NOW(), last_updated = NOW()
    RETURNING (xmax = 0) AS inserted
""")


def judge(res: ScanResult) -> tuple[str, str]:
    """('success' | 'failed', reason). Reading nothing is never success."""
    if res.gazette == "boe":
        if res.errors and res.days_with_issue == 0:
            return "failed", f"every request failed: {'; '.join(res.errors[:3])}"
        if res.days_requested >= MIN_BOE_DAYS_TO_JUDGE and res.days_with_issue == 0:
            return "failed", f"no BOE issue read in {res.days_requested} days"
    else:
        if res.errors and res.scanned == 0:
            return "failed", f"request failed: {'; '.join(res.errors[:3])}"
        if res.days_requested >= MIN_DOGC_DAYS_TO_JUDGE and res.scanned == 0:
            return "failed", f"no DOGC norm read in {res.days_requested} days"
    if res.errors:
        return "success", f"partial: {'; '.join(res.errors[:3])}"
    return "success", ""


def store(db, res: ScanResult) -> tuple[int, int]:
    inserted = updated = 0
    for it in res.items:
        row = db.execute(_UPSERT, {
            "gazette": it.gazette, "identifier": it.identifier, "published_date": it.published_date,
            "title": it.title[:1000], "title_es": (it.title_es or None), "section": it.section,
            "department": it.department, "rank": it.rank, "url": it.url or None,
            "pdf_url": it.pdf_url or None, "match_tier": it.tier, "matched_terms": it.matched,
        }).first()
        if row and row[0]:
            inserted += 1
        else:
            updated += 1
    db.commit()
    return inserted, updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=5, help="BOE window (default 5)")
    ap.add_argument("--dogc-days", type=int, default=30, help="DOGC window (default 30)")
    ap.add_argument("--apply", action="store_true", help="upsert and record sync_runs")
    a = ap.parse_args()

    results = [fetch_boe(a.days), fetch_dogc(a.dogc_days)]
    exit_code = 0
    db = SessionLocal() if a.apply else None
    try:
        for res in results:
            status, reason = judge(res)
            strict = sum(1 for i in res.items if i.tier == "strict")
            print(f"[{'OK' if status == 'success' else 'ERROR'}] {res.gazette.upper()}: "
                  f"window {res.days_requested}d, issues/days with items {res.days_with_issue}, "
                  f"scanned {res.scanned}, matched {len(res.items)} ({strict} strict), "
                  f"newest {res.newest_published}" + (f" | {reason}" if reason else ""))
            for it in res.items[:20]:
                print(f"    {it.published_date} {it.tier:<6} {it.section or '-':>2} {it.title[:100]}")
            if status != "success":
                exit_code = 1
            if db is not None:
                inserted = updated = 0
                if status == "success":
                    inserted, updated = store(db, res)
                    print(f"    stored: {inserted} new, {updated} refreshed")
                record_run(db, source_key=f"official_gazettes_{res.gazette}", tier="daily",
                           status=status, items_added=inserted,
                           error=(reason or None) if status != "success" else (reason or None))
    finally:
        if db is not None:
            db.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
