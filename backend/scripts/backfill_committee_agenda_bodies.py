#!/usr/bin/env python3.12
"""Fill the cached body of EP committee draft agendas.

The defect
----------
`/api/v1|v2/.../committee-agendas` promises `body_txt` + `body_html` on every
row ("Null only when the document could not be fetched"). Measured on
28 August 2026:

    agenda events ...................... 226
    with an agenda_url ................. 186
    with a cached body ..................  0

Zero. Not in production either. The request path calls `ensure_agenda_body`,
which fetches the doceo PDF over urllib; doceo answers a JS WAF challenge with
**HTTP 202 and an empty body**, and an empty fetch is returned as `(None, None)`
without raising. So the endpoint has served `body_txt: null` for every agenda
since it shipped, and nothing anywhere said so -- the row still had a title, a
date and a URL, so it looked fine.

The fix is the house rule for a WAF: use a real browser, never tune headers.
Chromium clears the challenge once and every PDF then comes through the same
context. The same URL that gives urllib 0 bytes gives the browser 186KB.

Why a script and not the request path
-------------------------------------
The list endpoint fetches a body PER ROW, so putting Chromium there would launch
a browser per item. This fills the cache out of band; the request path keeps its
cheap urllib attempt and reads the cache.

What changed from the previous version of this script
----------------------------------------------------
It already existed and had never worked: it called `extract_agenda_body`, i.e.
the same urllib path the request handler uses, so every run reported
`fetched=0 empty=226` and looked like an empty upstream rather than a wall. The
flags are kept (`--committee`, `--recompute`, `--limit 0` = no cap) with one
deliberate change: writing now needs `--apply`, so a bare run is a dry-run, as
in every other backfill here.

Usage:
    python3.12 scripts/backfill_committee_agenda_bodies.py             # dry-run
    python3.12 scripts/backfill_committee_agenda_bodies.py --apply
    python3.12 scripts/backfill_committee_agenda_bodies.py --apply --committee LIBE
    python3.12 scripts/backfill_committee_agenda_bodies.py --apply --limit 0 --recompute
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from services.scrapers.committee_agenda_body_extractor import (  # noqa: E402
    CACHE_AT, CACHE_HTML, CACHE_TXT, AgendaPdfBrowser, pdf_bytes_to_body,
)

_SOURCE = "ep_committee_agenda"


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    ap.add_argument("--limit", type=int, default=40,
                    help="Cap agendas per run (default 40) so one run fits the cron window; 0 = no cap")
    ap.add_argument("--committee", help="Restrict to one committee code (e.g. LIBE)")
    ap.add_argument("--recompute", action="store_true",
                    help="Re-fetch even where a body is already cached")
    args = ap.parse_args()

    eng = _engine()
    with eng.connect() as conn:
        total, with_url, cached = conn.execute(text(
            "SELECT count(*), count(agenda_url), "
            "       count(*) FILTER (WHERE related_documents ? :k) "
            "FROM eu_calendar_events WHERE source = :s"),
            {"k": CACHE_TXT, "s": _SOURCE}).fetchone()
        print(f"[INFO] {total} agenda(s); {with_url} have a document URL; "
              f"{cached} already hold their text")
        if total > with_url:
            print(f"[INFO] {total - with_url} agenda(s) have no agenda document yet "
                  f"(their only link is a committee homepage) -- not a gap, and not "
                  f"retried")

        # agenda_url, NOT coalesce(agenda_url, source_url): 40 of the 226 events
        # carry only a committee HOMEPAGE as source_url, and a homepage is not a
        # draft agenda. Falling back to it meant fetching 40 HTML pages every run
        # for the %PDF guard to reject each time -- work that can never succeed,
        # reported as 40 failures. They are a distinct state (no agenda document
        # published yet), counted below and left alone.
        where = ["source = :s", "agenda_url IS NOT NULL"]
        params = {"s": _SOURCE, "k": CACHE_TXT}
        if not args.recompute:
            where.append("NOT (related_documents ? :k)")
        if args.committee:
            where.append("upper(ep_committee_code) = :cm")
            params["cm"] = args.committee.upper()
        # Newest first: an upcoming meeting is the one anyone is asking about,
        # so a capped run still covers what matters and the tail catches up.
        sql = ("SELECT id, agenda_url, source_url, start_date, ep_committee_code "
               "FROM eu_calendar_events WHERE " + " AND ".join(where) +
               " ORDER BY start_date DESC")
        if args.limit:
            sql += " LIMIT :lim"
            params["lim"] = args.limit
        rows = conn.execute(text(sql), params).fetchall()

    print(f"[INFO] {len(rows)} agenda(s) to fetch this run")
    if not rows:
        print("[OK] nothing to do")
        return 0
    if not args.apply:
        for r in rows[:10]:
            print(f"   would fetch {r.start_date} {r.ep_committee_code or '-':6} "
                  f"{(r.agenda_url or r.source_url)[:88]}")
        print(f"[DRY-RUN] {len(rows)} agenda(s) would be fetched -- pass --apply")
        return 0

    got = empty = failed = 0
    with AgendaPdfBrowser() as browser, eng.connect() as conn:
        for r in rows:
            url = r.agenda_url
            try:
                data = browser.get(url)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"[ERROR] {r.ep_committee_code} {r.start_date}: "
                      f"{type(exc).__name__}: {exc}")
                continue
            if not data:
                failed += 1
                continue
            txt, html = pdf_bytes_to_body(data)
            if not txt:
                # A real PDF that carries no extractable text (scanned image).
                # Distinct from a failed fetch, and counted apart so a scraper
                # regression cannot hide inside an expected number.
                empty += 1
                continue
            conn.execute(text(
                "UPDATE eu_calendar_events SET related_documents = "
                "  coalesce(related_documents, '{}'::jsonb) || CAST(:patch AS jsonb) "
                "WHERE id = :id"),
                {"id": r.id, "patch": json.dumps({
                    CACHE_TXT: txt, CACHE_HTML: html,
                    CACHE_AT: datetime.utcnow().isoformat()})})
            got += 1
        conn.commit()

    print(f"[APPLIED] cached={got} no_text_in_pdf={empty} fetch_failed={failed}")

    # Verify from the table, never from the loop counter.
    with eng.connect() as conn:
        now_cached, tot = conn.execute(text(
            "SELECT count(*) FILTER (WHERE related_documents ? :k), count(*) "
            "FROM eu_calendar_events WHERE source = :s"),
            {"k": CACHE_TXT, "s": _SOURCE}).fetchone()
        print(f"[VERIFY] {now_cached}/{tot} agendas now hold their text")
    # A run in which every single fetch failed is a broken instrument, not a
    # quiet success -- say so through the exit code.
    return 1 if (got == 0 and failed > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
