"""
Audit script for amendator_featured_examples table.

Read-only — never modifies the database. Run manually to inspect the state
of the Amendator 'Hot files this week' list before deciding whether to apply
migration 043 (stale sweep).

Usage:
    cd backend && python3.12 scripts/audit_amendator_examples.py
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal

STALE_DAYS = 30
NEWS_ROTATION_THRESHOLD = 8   # >=8 news-sourced adds in 14 days → recurring monthly
STALE_THRESHOLD = 3           # >3 stale items → recurring monthly


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_audit() -> None:
    db = SessionLocal()
    try:
        now = _now()
        stale_cutoff = now - timedelta(days=STALE_DAYS)
        window_cutoff = now - timedelta(days=14)

        # --- totals ---
        total = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples"
        )).scalar() or 0

        active = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples WHERE is_active = TRUE"
        )).scalar() or 0

        stale_active = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples "
            "WHERE is_active = TRUE AND added_at < :cutoff"
        ), {"cutoff": stale_cutoff}).scalar() or 0

        # stale active items not manually pinned (source != 'manual')
        stale_non_manual = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples "
            "WHERE is_active = TRUE AND added_at < :cutoff AND source != 'manual'"
        ), {"cutoff": stale_cutoff}).scalar() or 0

        # --- counts by source ---
        source_rows = db.execute(text(
            "SELECT COALESCE(source, 'unknown'), COUNT(*) "
            "FROM amendator_featured_examples "
            "GROUP BY COALESCE(source, 'unknown') "
            "ORDER BY COUNT(*) DESC"
        )).fetchall()

        # --- counts by document_type ---
        dtype_rows = db.execute(text(
            "SELECT COALESCE(document_type, 'NULL (unset)'), COUNT(*) "
            "FROM amendator_featured_examples "
            "GROUP BY COALESCE(document_type, 'NULL (unset)') "
            "ORDER BY COUNT(*) DESC"
        )).fetchall()

        # --- oldest active item ---
        oldest = db.execute(text(
            "SELECT title, added_at, source, document_type "
            "FROM amendator_featured_examples "
            "WHERE is_active = TRUE "
            "ORDER BY added_at ASC LIMIT 1"
        )).first()

        # --- manual items (must never be auto-deactivated) ---
        manual_rows = db.execute(text(
            "SELECT title, celex, added_at, is_active "
            "FROM amendator_featured_examples "
            "WHERE source = 'manual' "
            "ORDER BY added_at ASC"
        )).fetchall()

        # --- news-sourced additions in last 14 days ---
        news_in_window = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples "
            "WHERE source = 'news' AND added_at >= :cutoff"
        ), {"cutoff": window_cutoff}).scalar() or 0

        # --- stale active non-manual detail (for display) ---
        stale_detail = db.execute(text(
            "SELECT title, celex, added_at, source, document_type "
            "FROM amendator_featured_examples "
            "WHERE is_active = TRUE AND added_at < :cutoff AND source != 'manual' "
            "ORDER BY added_at ASC"
        ), {"cutoff": stale_cutoff}).fetchall()

        # --- items with NULL document_type (API filter concern) ---
        null_dtype_active = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples "
            "WHERE is_active = TRUE AND document_type IS NULL"
        )).scalar() or 0

        # ------------------------------------------------------------------ #
        #  Print report                                                        #
        # ------------------------------------------------------------------ #
        print("=" * 70)
        print("AMENDATOR FEATURED EXAMPLES — AUDIT REPORT")
        print(f"  Run date : {now.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  Stale    : items with added_at < {stale_cutoff.strftime('%Y-%m-%d')} "
              f"(>{STALE_DAYS} days old)")
        print("=" * 70)

        print(f"\n[INFO] Total rows (all-time): {total}")
        print(f"[INFO] Active rows          : {active}")
        print(f"[INFO] Active + stale       : {stale_active}  (source='manual' protected)")
        print(f"[INFO] Stale non-manual     : {stale_non_manual}  (would be deactivated by mig 043)")

        print("\n[INFO] Count by source:")
        for src, cnt in source_rows:
            print(f"       {src:<12} {cnt}")

        print("\n[INFO] Count by document_type:")
        for dt, cnt in dtype_rows:
            print(f"       {dt:<30} {cnt}")

        if null_dtype_active:
            print(f"\n[WARN] {null_dtype_active} active item(s) have NULL document_type.")
            print("       The API passes these through because the filter is "
                  "'document_type IS NULL OR ...'.")
            print("       This means non-amendable docs (Communications, agreements, etc.)")
            print("       may be shown to users. Consider a follow-up to backfill document_type.")

        if oldest:
            age_days = (now - oldest[1].replace(tzinfo=timezone.utc)).days
            print(f"\n[INFO] Oldest active item  : '{oldest[0]}'")
            print(f"       added_at            : {oldest[1].strftime('%Y-%m-%d')}  ({age_days} days ago)")
            print(f"       source              : {oldest[2]}")
            print(f"       document_type       : {oldest[3] or 'NULL (unset)'}")

        print(f"\n[INFO] News-sourced additions in last 14 days: {news_in_window}")

        print("\n[INFO] Manually pinned items (source='manual' — NEVER auto-deactivate):")
        if manual_rows:
            for row in manual_rows:
                status = "ACTIVE" if row[3] else "inactive"
                print(f"       [{status}] {row[0]}  (celex={row[1]}, added={row[2].strftime('%Y-%m-%d')})")
        else:
            print("       (none)")

        if stale_detail:
            print(f"\n[WARN] Stale active non-manual items (would be deactivated by mig 043):")
            for row in stale_detail:
                print(f"       - {row[0]}")
                print(f"         celex={row[1]}  added={row[2].strftime('%Y-%m-%d')}  "
                      f"source={row[3]}  dtype={row[4] or 'NULL'}")
        else:
            print("\n[OK]  No stale active non-manual items found "
                  f"(threshold: >{STALE_DAYS} days).")
            print("      Migration 043 would be a no-op for deactivations.")

        # ------------------------------------------------------------------ #
        #  Recommendation                                                      #
        # ------------------------------------------------------------------ #
        print("\n" + "=" * 70)
        print("RECOMMENDATION")
        print("=" * 70)

        reasons = []
        if news_in_window >= NEWS_ROTATION_THRESHOLD:
            reasons.append(
                f"/news added {news_in_window} items in 14 days "
                f"(threshold: >={NEWS_ROTATION_THRESHOLD})"
            )
        if stale_non_manual > STALE_THRESHOLD:
            reasons.append(
                f"{stale_non_manual} stale non-manual items "
                f"(threshold: >{STALE_THRESHOLD})"
            )

        if news_in_window == 0:
            print("[ACTION REQUIRED] Zero /news rotations in 14 days.")
            print("  Investigate why /news isn't surfacing new amendable files.")
            print("  The rotation may need a feeder script in /news Step 3.2.")
            print("  Cadence: Keep as ad-hoc (no data to justify monthly sweep yet).")
        elif reasons:
            print(f"[RESULT] Convert to recurring monthly sweep.")
            for r in reasons:
                print(f"  - {r}")
        else:
            print("[RESULT] Keep as ad-hoc.")
            print(f"  - /news rotations in 14 days: {news_in_window} (threshold: >={NEWS_ROTATION_THRESHOLD})")
            print(f"  - Stale non-manual items    : {stale_non_manual} (threshold: >{STALE_THRESHOLD})")

        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_audit()
