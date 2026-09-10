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
from services.scrapers.economy_common import (  # noqa: E402
    extract_item_date, extract_dateline_or_url_date, http_get, sole_text_date,
)

# Bodies with a KNOWN bespoke path (a WAF-aware fetcher, an RSS map, or stored PDF
# text). Everything else falls through to the generic path below, which is the point:
# on 9 Sep 2026 four bodies -- eige 31, euiss 10, aviation 9, europol 4 -- were sitting
# on 54 undated rows whose pages already carried a <time datetime> or a JSON-LD
# datePublished. extract_item_date found every one of them on the first try. Nothing
# needed writing; their scrapers simply never called it. Hardcoding a fifth, sixth and
# seventh body here would have hidden the next four the same way.
BODIES = ("euda", "eib", "rail", "sesar", "f4e")
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


# WAF / rate-limit statuses. A 403 is a wall, a 429 is us going too fast, and a
# 503 is either. None of the three means "this page has no date".
_WALL_STATUSES = {403, 406, 429, 503}


def _plain_get(url: str):
    r = http_get(url)
    if r is None:
        return None
    ctype = (r.headers.get("content-type") or "").lower()
    if "html" not in ctype and "xml" not in ctype:
        return None
    return r.text


def _escalating_get(url: str):
    """Plain GET, then a real TLS fingerprint, then a real browser.

    Added 10 September 2026 after the first eu_news_items sweep reported
    `fetch_failed` on 360 of 589 rows and the number was taken at face value for
    about a minute. Sampling the failures showed THREE different things wearing
    one label:

      * HTTP 200 with a full page (EIT, EEAS, CNECT) -- the page was fine and the
        sweep had simply outrun the host. That is the rate limiter being measured,
        not the site (feedback_paced_regression_measures_the_model).
      * HTTP 403 (EUIPO, ECHA) -- a WAF. Use a browser, never tune headers
        (feedback_waf_walled_use_playwright).
      * HTTP 429 (EEAS) -- explicitly us, going too fast.

    So a wall or an empty 200 escalates instead of being recorded as an absent
    date. An empty result is not absence; it is usually the instrument
    (feedback_empty_result_is_a_broken_instrument).
    """
    r = http_get(url)
    walled = r is None or getattr(r, "status_code", 0) in _WALL_STATUSES
    if not walled:
        ctype = (r.headers.get("content-type") or "").lower()
        if ("html" in ctype or "xml" in ctype) and len(r.text) > 2000:
            return r.text
        walled = True          # a 200 with nothing parseable is also a wall
    try:
        html = _cffi_get(url)
        if html and len(html) > 2000:
            return html
    except Exception:  # noqa: BLE001
        pass
    try:
        return _browser_get(url)
    except Exception:  # noqa: BLE001
        return None


def _browser_get(url: str):
    """Playwright. chips-ju renders its item pages client-side (NewsDetails?id=<guid>)
    and satcen serves a 1.7KB stub to a plain GET, so both came back `fetch_failed`
    on every attempt -- 18 rows. At a WAF or a JS app, use the browser rather than
    tuning headers (feedback_waf_walled_use_playwright)."""
    import importlib.util
    import pathlib as _pl
    global _BROWSER
    if _BROWSER is None:
        f = _pl.Path(__file__).resolve().parents[1] / "services/scrapers/waf_browser_fetcher.py"
        spec = importlib.util.spec_from_file_location("waf_browser_fetcher", f)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["waf_browser_fetcher"] = mod
        spec.loader.exec_module(mod)
        _BROWSER = mod
    try:
        return (_BROWSER.fetch_one(url).html or "") or None
    except Exception:
        return None


_BROWSER = None

_FETCHERS = {"euda": _cffi_get, "eib": _plain_get, "rail": _plain_get,
             "chips": _browser_get, "satcen": _browser_get}

# Bodies whose item pages expose NO date carrier at all, where the only remaining
# evidence is the page holding exactly one date. Opt-in per body on purpose: see
# sole_text_date's docstring for why this must never apply corpus-wide.
_SOLE_DATE_BODIES = {"chips", "satcen"}

# sesar is a MAP body, not a fetch body: neither its item page nor its listing states
# a date, so the only publisher statement is the <pubDate> in its own RSS feed
# (services/scrapers/economy_sesar.news_dates). Looked up by URL instead of fetching
# each page, so it costs one request for the whole body.
_MAP_BODIES = {"sesar"}
_MAPS: dict = {}

# f4e is a STORED body: a third class again. Its releases are PDFs, its listing
# markup carries no date at all (no <time>, link text is often just "EN"), and the
# PDF text is ALREADY in body_txt -- so the date comes from the row itself and the
# backfill needs no network. The publisher's own dateline wins; the filename is the
# fallback, and where they disagree the dateline is kept, because five releases
# carry `140620101200` (14 June 2010, a file migration) while the documents say
# 2006, 2007 and 2008.
_STORED_BODIES = {"f4e"}


def _map_for(body: str) -> dict:
    if body not in _MAPS:
        if body == "sesar":
            from services.scrapers.economy_sesar import news_dates
            _MAPS[body] = news_dates()
        else:
            _MAPS[body] = {}
    return _MAPS[body]



# --------------------------------------------------------------------------
# Two news stores, one recovery path (10 September 2026).
#
# `economy_items` is the economy/agency half; `eu_news_items` is the
# institutional half. On 10 September the institutional half held 475 rows
# across 16 source keys with NO date at all -- EIT, COR, ESMA, EUROJUST,
# EU-OSHA, EUIPO, OMBUDSMAN, ACER, EUAA, ECDC, CEPOL, ENISA, CPVO, ECHA, CDT
# and DG REFORM -- and every one of them read as "publisher_quiet" in
# /api/v2/news/latest, which is the wrong verdict for a row nobody dated.
#
# The extraction, the guards and the honesty rules are identical; only the
# column names differ. So the profile is data and the logic is not duplicated.
# Writing a second script would have meant a second place for the
# no-hallucination rules to drift out of.
_TABLES = {
    "economy_items": dict(
        table="economy_items", pk="id", date_col="document_date",
        url_col="public_url", body_col="body_code", text_col="body_txt",
        order_col="creation_date",
        where_extra="item_type IN ('news','press_release')",
    ),
    "eu_news_items": dict(
        table="eu_news_items", pk="id", date_col="news_date",
        url_col="source_url", body_col="source_key", text_col="body_txt",
        order_col="fetched_at",
        where_extra="TRUE",
    ),
}

def _counts(db, bodies=None, prof=None):
    """Row / undated counts for the bodies THIS RUN is touching.

    Took `BODIES` before, which silently reported `eige 0 / 0` the moment --body
    accepted a code outside that tuple: the before/after report showed a zero for a
    body holding 31 undated rows. A counter that cannot see what the run is changing
    is worse than no counter (feedback_verify_the_instrument_before_the_reading).
    """
    p = prof or _TABLES["economy_items"]
    rows = db.execute(text(
        f"SELECT {p['body_col']} AS body, count(*) AS n, "
        f"count(*) FILTER (WHERE {p['date_col']} IS NULL) AS undated "
        f"FROM {p['table']} WHERE {p['where_extra']} "
        f"AND {p['body_col']} = ANY(:b) GROUP BY 1 ORDER BY 1"),
        {"b": list(bodies or BODIES)}).mappings().all()
    return {r["body"]: (r["n"], r["undated"]) for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--body", help="Restrict to one body_code. Any body works, not "
                                   "only the ones with a bespoke fetcher.")
    ap.add_argument("--all-undated", action="store_true",
                    help="Every body with at least one undated news row.")
    ap.add_argument("--limit", type=int, default=0, help="Cap rows processed (0 = all).")
    ap.add_argument("--pace", type=float, default=None,
                    help="Seconds between requests. Raise it for hosts that 429; "
                         "an unpaced sweep measures the rate limiter, not the site.")
    ap.add_argument("--table", choices=sorted(_TABLES), default="economy_items",
                    help="Which news store to repair. eu_news_items is the "
                         "institutional half (see _TABLES).")
    args = ap.parse_args()
    prof = _TABLES[args.table]
    global DELAY
    if args.pace is not None:
        DELAY = args.pace

    db_probe = SessionLocal()
    try:
        if args.body:
            bodies = [args.body]
        elif args.all_undated:
            bodies = [r[0] for r in db_probe.execute(text(
                f"SELECT {prof['body_col']} FROM {prof['table']} "
                f"WHERE {prof['where_extra']} AND {prof['date_col']} IS NULL "
                f"AND {prof['url_col']} IS NOT NULL "
                f"GROUP BY 1 ORDER BY count(*) DESC")).all()]
        else:
            bodies = list(BODIES)
    finally:
        db_probe.close()
    print(f"[INFO] bodies: {bodies}")
    db = SessionLocal()
    try:
        before = _counts(db, bodies, prof)
        print("[INFO] before (rows / undated):")
        for b in bodies:
            n, u = before.get(b, (0, 0))
            print(f"         {b:10} {n:5} / {u:5}")

        sql = (f"SELECT {prof['pk']} AS id, {prof['body_col']} AS body_code, "
               f"{prof['url_col']} AS public_url, {prof['text_col']} AS body_txt "
               f"FROM {prof['table']} WHERE {prof['where_extra']} "
               f"AND {prof['date_col']} IS NULL AND {prof['url_col']} IS NOT NULL "
               f"AND {prof['body_col']} = ANY(:b) "
               f"ORDER BY {prof['body_col']}, {prof['order_col']} DESC NULLS LAST")
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
            if body in _STORED_BODIES:
                dt, prov = extract_dateline_or_url_date(r["body_txt"] or "",
                                                        r["public_url"] or "")
                carriers[prov] += 1
                if dt is not None:
                    pending.append({"id": r["id"], "d": dt})
                continue          # no request at all: the text is already stored
            if body in _MAP_BODIES:
                dt = _map_for(body).get(r["public_url"])
                if dt is not None:
                    carriers["rss_pubdate"] += 1
                    pending.append({"id": r["id"], "d": dt})
                    continue      # free: no per-item request needed
                # A MISS is not an answer. sesar's RSS window holds 6 entries, so all
                # 18 undated rows had scrolled off it and were being counted
                # `not_in_feed` and abandoned -- the map treated as the only source
                # rather than the cheap shortcut it is. Fall through to the page,
                # which is where the date actually lives
                # (<div class="published-date">).
                carriers["not_in_feed_fell_through"] += 1
            # Generic path for any body with no bespoke fetcher: a plain GET and
            # extract_item_date, which reads <time datetime>, article:published_time
            # and JSON-LD datePublished. Most agency pages carry one of the three.
            html = _FETCHERS.get(body, _escalating_get)(r["public_url"])
            if html is None:
                carriers["fetch_failed"] += 1
            else:
                dt, carrier = extract_item_date(html)
                if dt is None and body in _SOLE_DATE_BODIES:
                    dt, carrier = sole_text_date(html)
                if dt is None:
                    carriers["no_carrier"] += 1
                else:
                    carriers[carrier] += 1
                    pending.append({"id": r["id"], "d": dt})
            time.sleep(DELAY)

            if args.apply and len(pending) >= BATCH:
                db.execute(text(f"UPDATE {prof['table']} SET {prof['date_col']} = :d "
                                f"WHERE {prof['pk']} = :id"), pending)
                db.commit()
                print(f"[INFO] committed {len(pending)}  ({processed}/{len(rows)} processed)")
                pending = []
            elif processed % 100 == 0:
                print(f"[INFO] {processed}/{len(rows)} processed  {dict(carriers)}")

        if args.apply and pending:
            db.execute(text(f"UPDATE {prof['table']} SET {prof['date_col']} = :d "
                            f"WHERE {prof['pk']} = :id"), pending)
            db.commit()
            print(f"[INFO] committed final {len(pending)}")

        print(f"[INFO] carriers: {dict(carriers)}")
        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        after = _counts(db, bodies, prof)
        print("[INFO] after (rows / undated):")
        total_recovered = 0
        for b in bodies:
            n0, u0 = before.get(b, (0, 0))
            n1, u1 = after.get(b, (0, 0))
            total_recovered += (u0 - u1)
            print(f"         {b:10} {n1:5} / {u1:5}   recovered {u0 - u1}")

        dated = sum(v for k, v in carriers.items()
                    # Keys that are NOT a recovered date. `not_in_feed_fell_through`
                    # is the important one: it is incremented for the same row that
                    # a carrier key then counts, so leaving it in double-counted
                    # every map-body row -- 36 "dates" for 18 rows -- and tripped
                    # the concurrency warning below on a run that was perfectly
                    # clean. A tally that counts one row twice is not a tally.
                    if k not in ("fetch_failed", "no_carrier", "not_in_feed",
                                 "not_in_feed_fell_through", "none"))
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
