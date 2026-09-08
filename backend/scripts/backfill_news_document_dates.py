#!/usr/bin/env python3.12
"""Recover `document_date` for news rows whose scraper never extracted one.

Why
---
Measured 8 September 2026: 1,761 of 12,509 news rows in `economy_items` carry no
`document_date`, across 17 bodies. Splitting the two anchors -- `document_date` (the
item's own date) against `creation_date` (when Brubru ingested it) -- separates two
failures that had been one undifferentiated "stale" bucket:

  * a DEAD FETCHER: both dates old. Nothing to backfill; fix the scraper.
  * a LIVE FETCHER with a broken DATE PARSER: recent creation_date, every row
    undated. The dates were on the pages all along.

This script handles the second kind. Four bodies, three of which publish a
machine-readable date on the item page and one which publishes it only in its feed:

    euda   978 rows   <time datetime="...">                     4/4 sampled
    eib    247 rows   JSON-LD "datePublished"                   3/4 sampled
    rail    17 rows   <meta property="article:published_time">  2/2 sampled
    sesar   23 rows   RSS <pubDate>, looked up by URL           feed-only

The scrapers themselves are fixed too, so new rows arrive dated; this is the
historical sweep.

What it will not do
-------------------
Read the date the publisher states for THAT item on THAT item's page, or leave the
row NULL. Never the sitemap `<lastmod>` (a modification date is a different fact),
never `creation_date`, never a year inferred from the URL path. A row that cannot be
dated stays NULL and is counted as `no_carrier`, which is an honest answer.
See `feedback_backfill_no_hallucination`.

`ombudsman` is deliberately NOT here. Its 16 rows carry no date anywhere: the
canonical rendered item page (76KB) has none of six carriers, and the dates that DO
appear on the wrong URL variant belong to that 404 page's "latest news" sidebar, i.e.
other items. Its separate defect -- every item duplicated across two locale-prefix
variants, with the non-canonical one 404ing and its error page stored as body_txt --
is handled by scripts/dedup_ombudsman_news.py.

Usage
-----
    python3.12 -m backend.scripts.backfill_news_document_dates --dry-run
    python3.12 -m backend.scripts.backfill_news_document_dates --apply
    python3.12 -m backend.scripts.backfill_news_document_dates --apply --body euda
    python3.12 -m backend.scripts.backfill_news_document_dates --apply --limit 25

Resumable: it only selects rows where `document_date IS NULL`, commits in batches,
and reports rows PERSISTED by re-reading after the commit rather than counting
attempts. See `feedback_silent_failure_reports_success`.
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
from services.scrapers.economy_common import extract_item_date, http_get  # noqa: E402

BODIES = ("euda", "eib", "rail", "sesar")
BATCH = 50
DELAY = 0.4          # politeness; these are public agency sites


def _cffi_get(url: str):
    """EUDA sits behind a WAF that 403s a plain requests UA, so its own scraper uses
    a curl_cffi Chrome TLS fingerprint. Reuse that rather than re-tuning headers,
    per feedback_waf_walled_use_playwright."""
    from curl_cffi import requests as creq
    s = creq.Session(impersonate="chrome131")
    try:
        r = s.get(url, timeout=40)
        return r.text if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _plain_get(url: str):
    r = http_get(url)
    if r is None:
        return None
    ctype = (r.headers.get("content-type") or "").lower()
    if "html" not in ctype and "xml" not in ctype:
        return None
    return r.text


_FETCHERS = {"euda": _cffi_get, "eib": _plain_get, "rail": _plain_get}

# sesar is a MAP body, not a fetch body: neither its item page nor its listing states
# a date, so the only publisher statement is the <pubDate> in its own RSS feed
# (services/scrapers/economy_sesar.news_dates). Looked up by URL instead of fetching
# each page, so it costs one request for the whole body.
_MAP_BODIES = {"sesar"}
_MAPS: dict = {}


def _map_for(body: str) -> dict:
    if body not in _MAPS:
        if body == "sesar":
            from services.scrapers.economy_sesar import news_dates
            _MAPS[body] = news_dates()
        else:
            _MAPS[body] = {}
    return _MAPS[body]


def _counts(db):
    rows = db.execute(text(
        "SELECT body_code, count(*) AS n, "
        "count(*) FILTER (WHERE document_date IS NULL) AS undated "
        "FROM economy_items WHERE item_type IN ('news','press_release') "
        "AND body_code = ANY(:b) GROUP BY body_code ORDER BY body_code"),
        {"b": list(BODIES)}).mappings().all()
    return {r["body_code"]: (r["n"], r["undated"]) for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--body", choices=BODIES, help="Restrict to one body.")
    ap.add_argument("--limit", type=int, default=0, help="Cap rows processed (0 = all).")
    args = ap.parse_args()

    bodies = [args.body] if args.body else list(BODIES)
    db = SessionLocal()
    try:
        before = _counts(db)
        print("[INFO] before (rows / undated):")
        for b in bodies:
            n, u = before.get(b, (0, 0))
            print(f"         {b:10} {n:5} / {u:5}")

        sql = ("SELECT id, body_code, public_url FROM economy_items "
               "WHERE item_type IN ('news','press_release') AND document_date IS NULL "
               "AND public_url IS NOT NULL AND body_code = ANY(:b) "
               "ORDER BY body_code, creation_date DESC")
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = db.execute(text(sql), {"b": bodies}).mappings().all()
        print(f"[INFO] candidates: {len(rows)}")
        if not rows:
            print("[OK] nothing to do")
            return 0

        carriers = Counter()
        pending = []
        processed = 0
        for r in rows:
            body = r["body_code"]
            processed += 1
            if body in _MAP_BODIES:
                dt = _map_for(body).get(r["public_url"])
                if dt is None:
                    carriers["not_in_feed"] += 1
                else:
                    carriers["rss_pubdate"] += 1
                    pending.append({"id": r["id"], "d": dt})
                continue          # no per-item request needed
            html = _FETCHERS[body](r["public_url"])
            if html is None:
                carriers["fetch_failed"] += 1
            else:
                dt, carrier = extract_item_date(html)
                if dt is None:
                    carriers["no_carrier"] += 1
                else:
                    carriers[carrier] += 1
                    pending.append({"id": r["id"], "d": dt})
            time.sleep(DELAY)

            if args.apply and len(pending) >= BATCH:
                db.execute(text("UPDATE economy_items SET document_date = :d WHERE id = :id"),
                           pending)
                db.commit()
                print(f"[INFO] committed {len(pending)}  ({processed}/{len(rows)} processed)")
                pending = []
            elif processed % 100 == 0:
                print(f"[INFO] {processed}/{len(rows)} processed  {dict(carriers)}")

        if args.apply and pending:
            db.execute(text("UPDATE economy_items SET document_date = :d WHERE id = :id"), pending)
            db.commit()
            print(f"[INFO] committed final {len(pending)}")

        print(f"[INFO] carriers: {dict(carriers)}")
        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        after = _counts(db)
        print("[INFO] after (rows / undated):")
        total_recovered = 0
        for b in bodies:
            n0, u0 = before.get(b, (0, 0))
            n1, u1 = after.get(b, (0, 0))
            total_recovered += (u0 - u1)
            print(f"         {b:10} {n1:5} / {u1:5}   recovered {u0 - u1}")

        dated = sum(v for k, v in carriers.items()
                    if k not in ("fetch_failed", "no_carrier", "not_in_feed"))
        if total_recovered != dated:
            # Not necessarily a bug: the live cron may have inserted or dated rows
            # while this ran. Say so rather than asserting a clean number.
            print(f"[WARN] extracted {dated} dates but undated fell by {total_recovered}; "
                  "the ingest cron may have written rows concurrently. Re-run to converge.")
        print(f"[OK] {total_recovered} rows now carry a document_date read from their own page")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
