#!/usr/bin/env python3.12
"""Replace deadlines stored as the publication date of agency calls and tenders (20 Oct 2026).

Read on /api/v2/funding the same day: expert lists open until 2029 sorted to the top of
/funding/all as if published in 2029. The listings of EUAA, Eurojust, EUDA, ETF and ERA print
only a deadline and agency_procurement._build stored it as document_date; EEAS tender cards and
HaDEA call and tender cards print their deadline where a news card prints its date. Victor's rule
(ECDC, 30 Sep): document_date is the publication date, else NULL, never the deadline.

The scrapers are fixed; the sync's upsert never nulls a stored date, so the stock is repaired here:
  * each row's own page is read (economy_common.fetch_detail_dated): its publication date replaces
    the stored one, and NULL replaces it when the page names none; a longer page text replaces a
    card-only body;
  * HaDEA calls take the opening date printed on the listing card (unlisted ones are left
    alone); HaDEA tenders take the publication date on their page;
  * a page that cannot be read (EUDA answers this machine 403) is only cleared when its stored date
    is the deadline printed in its own summary; Railway's next sync fills it from the page. An
    EEAS tender is cleared either way: its only date was its card's, which is the deadline.

    python3.12 scripts/repair_procurement_dates.py            # dry run: what would change
    python3.12 scripts/repair_procurement_dates.py --apply
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import re
import sys
import time
from datetime import datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import psycopg2  # noqa: E402

from services.scrapers.economy_common import _parse_ecl_cards, fetch_detail_dated, http_get  # noqa: E402

TARGETS = [("eurojust", "tender"), ("euaa", "eoi_call"), ("euda", "tender"), ("etf", "tender"),
           ("era", "tender"), ("eeas", "tender"), ("hadea", "call"), ("hadea", "tender")]
HADEA_LISTINGS = ["https://hadea.ec.europa.eu/calls-proposals_en", "https://hadea.ec.europa.eu/calls-tenders_en"]


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
        url = m.group(1).strip() if m else ""
    if not url:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return url.replace("postgresql+psycopg2://", "postgresql://")


def _day(d):
    return d.date().isoformat() if d else None


def plan(cur):
    hadea_open = {}
    for listing in HADEA_LISTINGS:
        r = http_get(listing)
        for url, _t, dt, _s in (_parse_ecl_cards(r.text, "https://hadea.ec.europa.eu") if r is not None else []):
            hadea_open[url] = dt
    changes = []
    for body, kind in TARGETS:
        cur.execute("SELECT id, public_url, document_date, coalesce(summary, ''), length(coalesce(body_txt, '')) "
                    "FROM economy_items WHERE body_code = %s AND item_type = %s ORDER BY id", (body, kind))
        for rid, url, stored, summary, body_len in cur.fetchall():
            new_date, new_txt, new_html, why = stored, None, None, ""
            if body == "hadea" and kind == "call":
                # A call card's first date was already its OPENING date (forthcoming calls open
                # in the future). The first run of this script cleared 14 calls no longer
                # listed; they were restored from its backup the same hour. Listed calls take
                # the card's opening date; unlisted ones keep what is stored.
                if url not in hadea_open:
                    continue
                new_date, why = hadea_open[url], "listing opening date"
            elif body == "hadea":
                # A HaDEA tender card prints only the deadline; its page's first <time> is
                # "Publication date" (6 of 6 read on 20 Oct).
                _t, _h, page_kind, dt, carrier = fetch_detail_dated(url)
                if page_kind != "html":
                    continue
                new_date, why = dt, f"page date ({carrier})" if dt else "page names no publication date"
            else:
                txt, html, page_kind, dt, carrier = fetch_detail_dated(url)
                if page_kind in ("unreachable", "moved", "gated"):
                    if body == "eeas":
                        # Every stored EEAS tender date came from its card, and a tender card
                        # prints the deadline: the fixed scraper keeps no card date either.
                        new_date, why = None, f"page {page_kind}; EEAS tender card date is the deadline"
                    elif stored is not None and _day(stored) in summary:
                        new_date, why = None, f"page {page_kind}; stored date is the deadline in the summary"
                    else:
                        why = f"page {page_kind}; left as stored"
                else:
                    new_date, why = dt, (f"page date ({carrier})" if dt else "page names no publication date")
                    if txt and len(txt) > body_len:
                        new_txt, new_html = txt, html
                time.sleep(0.4)
            if _day(new_date) != _day(stored) or new_txt:
                changes.append((rid, body, kind, url, stored, new_date, new_txt, new_html, why))
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = psycopg2.connect(_db_url(), connect_timeout=15)
    cur = conn.cursor()
    changes = plan(cur)
    conn.commit()
    by = {}
    for c in changes:
        k = (c[1], c[2], "date" if _day(c[5]) != _day(c[4]) else "body only")
        by[k] = by.get(k, 0) + 1
    for k, n in sorted(by.items()):
        print(f"   {k[0]}/{k[1]}: {n} {k[2]}")
    for c in changes[:12]:
        print(f"   {c[1]}/{c[2]} {_day(c[4])} -> {_day(c[5])} body+{len(c[6] or '')}  {c[8]}  {c[3][:80]}")
    if not a.apply:
        print(f"[DRY-RUN] {len(changes)} row(s) would change")
        return 0
    out = BACKEND / "data" / "backups" / f"economy_items_procurement_dates_before_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    ids = [c[0] for c in changes]
    cur.execute("SELECT id, body_code, item_type, public_url, document_date, body_txt, body_html FROM economy_items "
                "WHERE id = ANY(%s)", (ids,))
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "body_code", "item_type", "public_url", "document_date", "body_txt", "body_html"])
        w.writerows(cur.fetchall())
    conn.commit()
    print(f"[BACKUP] {out}")
    for rid, *_rest, new_date, new_txt, new_html, _why in changes:
        if new_txt:
            cur.execute("UPDATE economy_items SET document_date = %s, body_txt = %s, body_html = %s WHERE id = %s",
                        (new_date, new_txt, new_html, rid))
        else:
            cur.execute("UPDATE economy_items SET document_date = %s WHERE id = %s", (new_date, rid))
        conn.commit()   # one row per transaction
    print(f"[APPLIED] {len(changes)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
