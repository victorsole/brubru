#!/usr/bin/env python3
"""Bridge the EU institutions' own contract notices into the Tenderator.

The Tenderator matcher reads ONE table, `tenders`, filled from TED. The EU
institutions' own eTendering notices live in `ft_calls_for_tenders` and never
reached it. Measured 29 Sep 2026 over the open rows of that table:

    TED-numbered re-listings (e.g. 00868326-2025)   385, all 385 already in tenders
    institution contract notices (-CN)              211, NONE in tenders
    prior information notices (-PIN)                 76, advance notice, not biddable

So 211 open, biddable EU tenders were invisible to every profile, among them
Frontex's EUR 12 million Dynamic Purchasing System for Standing Corps equipment,
open until 2032 and promoted by Frontex on 28 Sep.

This copies each open -CN row into `tenders` with source='ft_portal', keyed on
its own reference (publication_number 'FT-<reference>', unique index), so the
existing matcher, digest and Tenderator screens pick it up unchanged. A row that
is no longer open on the portal is closed here too. TED-numbered rows are never
copied: they are TED notices and TED already delivers them under their number.

    python3.12 scripts/bridge_ft_tenders_to_tenders.py            # dry run
    python3.12 scripts/bridge_ft_tenders_to_tenders.py --apply
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

NATURE = {"services": "services", "supplies": "supplies", "works": "works"}

OPEN_CN = """
    SELECT id, tender_reference, contracting_authority, title, description, contract_type,
           estimated_value, value_currency, deadline, source_url, documents_url,
           cpv_codes, published_at
    FROM ft_calls_for_tenders
    WHERE tender_reference ~ '-CN$'
      AND status = 'open'
      AND (deadline IS NULL OR deadline > now())
      AND NOT COALESCE(is_test, false)
      AND title IS NOT NULL AND title <> ''
    ORDER BY id
"""

UPSERT = """
    INSERT INTO tenders (publication_number, notice_id, title, description, official_name,
                         contract_nature, estimated_value, estimated_value_currency,
                         publication_date, submission_deadline, cpv_codes, cpv_main,
                         documents_url, submission_url, ted_url, status, source, created_at, updated_at)
    VALUES (:pub, :ref, :title, :description, :official_name, :nature, :value, :currency,
            :published, :deadline, :cpv, :cpv_main, :documents_url, :submission_url, :submission_url,
            'open', 'ft_portal', now(), now())
    ON CONFLICT (publication_number) DO UPDATE SET
        title = EXCLUDED.title,
        description = COALESCE(NULLIF(EXCLUDED.description, ''), tenders.description),
        official_name = EXCLUDED.official_name,
        contract_nature = EXCLUDED.contract_nature,
        estimated_value = COALESCE(EXCLUDED.estimated_value, tenders.estimated_value),
        estimated_value_currency = COALESCE(EXCLUDED.estimated_value_currency, tenders.estimated_value_currency),
        submission_deadline = EXCLUDED.submission_deadline,
        cpv_codes = COALESCE(EXCLUDED.cpv_codes, tenders.cpv_codes),
        documents_url = EXCLUDED.documents_url,
        submission_url = EXCLUDED.submission_url,
        -- the screens open ted_url as "the notice"; for a portal notice that is its portal page
        ted_url = EXCLUDED.ted_url,
        status = 'open'
    -- updated_at is NOT set here: trg_tenders_touch owns it and moves it only when
    -- the row really changed, so a daily re-run does not re-stamp every row.
    WHERE tenders.source = 'ft_portal'
    RETURNING (xmax = 0) AS inserted
"""

# A bridged tender whose portal row is no longer open (closed, awarded, past its
# deadline, or gone) is closed here as well, so no profile keeps matching it.
CLOSE_STALE = """
    UPDATE tenders t SET status = 'closed'
    WHERE t.source = 'ft_portal' AND t.status = 'open'
      AND NOT EXISTS (
          SELECT 1 FROM ft_calls_for_tenders f
          WHERE 'FT-' || f.tender_reference = t.publication_number
            AND f.status = 'open' AND (f.deadline IS NULL OR f.deadline > now())
      )
"""


def to_row(r) -> dict:
    cpv = [c for c in (r["cpv_codes"] or []) if c] or None
    url = r["source_url"] or r["documents_url"]
    return {
        "pub": f"FT-{r['tender_reference']}",
        "ref": r["tender_reference"],
        "title": r["title"].strip(),
        "description": (r["description"] or "").strip() or None,
        "official_name": r["contracting_authority"],
        "nature": NATURE.get((r["contract_type"] or "").strip().lower()),
        "value": r["estimated_value"],
        "currency": r["value_currency"],
        "published": r["published_at"],
        "deadline": r["deadline"],
        "cpv": cpv,
        "cpv_main": cpv[0] if cpv else None,
        "documents_url": r["documents_url"] or url,
        "submission_url": url,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text(OPEN_CN)).mappings().all()
        if not rows:
            # A job that stores nothing must say so: 211 were open on 29 Sep 2026,
            # so an empty read means the portal ingest has broken, not that the
            # institutions stopped buying.
            print("[ERROR] no open institution contract notices in ft_calls_for_tenders", flush=True)
            return 1
        inserted = updated = 0
        for r in rows:
            row = to_row(r)
            if not args.apply:
                continue
            res = db.execute(text(UPSERT), row).first()
            if res is None:
                continue  # publication_number owned by another source: never overwrite it
            if res.inserted:
                inserted += 1
            else:
                updated += 1
        closed = 0
        if args.apply:
            closed = db.execute(text(CLOSE_STALE)).rowcount
            db.commit()
        open_now = db.execute(text(
            "SELECT count(*) FROM tenders WHERE source = 'ft_portal' AND status = 'open'")).scalar()
        print(f"[OK] open institution contract notices: {len(rows)} | inserted {inserted} | "
              f"refreshed {updated} | closed {closed} | bridged and open now: {open_now}"
              f"{'' if args.apply else ' (dry run)'}", flush=True)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
