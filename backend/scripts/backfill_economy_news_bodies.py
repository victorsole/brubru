#!/usr/bin/env python3.12
"""Ensure every `economy_items` news row carries body_txt AND body_html.

Why
---
The v2 five-datapoint contract requires a body on every item. Measured 8 September
2026: of 12,509 news rows, **621 had no body_txt** and 601 no body_html, spread
across 34 bodies. `f4e` had none at all (157/157). Eleven of them are self-inflicted:
`dedup_ombudsman_news.py` correctly NULLed bodies that were really 404 pages,
unrendered templates or pure site chrome, which removed false data and left a real
gap. The other 610 are item-page fetches that failed at scrape time and were never
retried.

Two-stage, in this order
------------------------
1. **Re-fetch the item's own page.** A scraped article is the real body, so try that
   first. `fetch_detail_dated` also returns the publication date, which is filled in
   when the row lacks one (a free win while we are here).
2. **Compose, and SAY SO.** Where the page cannot be fetched or yields only an error
   page, render title + summary + provenance into a readable body and set
   `source_kind = 'composed'`. `economy_items` has no `body_source` column, so
   `source_kind` is the honesty marker: a consumer can tell a composed body from a
   scraped one.

Never invent prose. A composed body contains only fields the row already holds, and
`error_body_reason` keeps a 404 page or a page-builder shortcode dump from being
stored as content (feedback_backfill_no_hallucination).

Usage
-----
    python3.12 -m backend.scripts.backfill_economy_news_bodies --dry-run
    python3.12 -m backend.scripts.backfill_economy_news_bodies --apply
    python3.12 -m backend.scripts.backfill_economy_news_bodies --apply --body f4e
    python3.12 -m backend.scripts.backfill_economy_news_bodies --apply --limit 50
    python3.12 -m backend.scripts.backfill_economy_news_bodies --apply --compose-only

`--compose-only` skips the network entirely and composes from stored fields; use it
when the remaining rows are known-unfetchable and you just want the contract met.

Reports rows PERSISTED by re-reading after the commit, never attempts.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time
from collections import Counter

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.news.body_composer import compose_news_body  # noqa: E402
from services.scrapers.economy_common import (  # noqa: E402
    error_body_reason, fetch_detail_dated,
)

BATCH = 40
DELAY = 0.35

MISSING = ("(body_txt IS NULL OR btrim(body_txt) = '' "
           " OR body_html IS NULL OR btrim(body_html) = '')")


def _counts(db):
    r = db.execute(text(
        "SELECT count(*) AS rows, "
        f"count(*) FILTER (WHERE {MISSING}) AS missing, "
        "count(*) FILTER (WHERE source_kind = 'composed') AS composed "
        "FROM economy_items WHERE item_type IN ('news','press_release')"
    )).mappings().one()
    return dict(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--body")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--compose-only", action="store_true",
                    help="Skip the network; compose from stored fields.")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = _counts(db)
        print(f"[INFO] before: {before}")

        sql = ("SELECT id, body_code, title, summary, public_url, document_date, "
               "       body_txt, body_html "
               "FROM economy_items "
               "WHERE item_type IN ('news','press_release') AND " + MISSING)
        params = {}
        if args.body:
            sql += " AND body_code = :b"
            params["b"] = args.body
        sql += " ORDER BY body_code, id"
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = db.execute(text(sql), params).mappings().all()
        print(f"[INFO] candidates: {len(rows)}")
        if not rows:
            print("[OK] nothing to do")
            return 0

        outcomes = Counter()
        pending = []
        done = 0
        for r in rows:
            done += 1
            txt = htm = None
            kind = None
            doc_dt = None

            if not args.compose_only and r["public_url"]:
                try:
                    t, h, k, dt, _c = fetch_detail_dated(r["public_url"])
                except Exception as exc:  # noqa: BLE001
                    t = h = k = dt = None
                    outcomes[f"fetch_error:{type(exc).__name__}"] += 1
                if t and not error_body_reason(t):
                    txt, htm, doc_dt = t, h, dt
                    kind = k or "html"
                    outcomes["refetched"] += 1
                time.sleep(DELAY)

            if txt is None:
                # Compose from what the row already holds, and mark it.
                txt, htm, _src = compose_news_body(
                    r["title"], r["summary"], r["body_code"],
                    r["document_date"], r["public_url"],
                )
                kind = "composed"
                outcomes["composed"] += 1

            pending.append({"id": r["id"], "t": txt, "h": htm, "k": kind,
                            "d": doc_dt or r["document_date"]})

            if args.apply and len(pending) >= BATCH:
                db.execute(text(
                    "UPDATE economy_items SET body_txt=:t, body_html=:h, "
                    "source_kind=:k, document_date=:d WHERE id=:id"), pending)
                db.commit()
                print(f"[INFO] committed {len(pending)} ({done}/{len(rows)}) {dict(outcomes)}")
                pending = []

        if args.apply and pending:
            db.execute(text(
                "UPDATE economy_items SET body_txt=:t, body_html=:h, "
                "source_kind=:k, document_date=:d WHERE id=:id"), pending)
            db.commit()
            print(f"[INFO] committed final {len(pending)}")

        print(f"[INFO] outcomes: {dict(outcomes)}")
        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        after = _counts(db)
        print(f"[INFO] after : {after}")
        if after["missing"] > before["missing"] - len(rows):
            print(f"[WARN] missing fell from {before['missing']} to {after['missing']}, "
                  f"expected -{len(rows)}; the cron may have inserted rows concurrently. "
                  "Re-run to converge.")
        if after["missing"] == 0:
            print(f"[OK] every news row in economy_items carries body_txt and body_html "
                  f"({after['rows']} rows, {after['composed']} marked source_kind=composed)")
            return 0
        print(f"[INFO] {after['missing']} still missing (re-run, or use --compose-only)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
