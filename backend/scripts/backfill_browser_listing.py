#!/usr/bin/env python3.12
"""
Generic resumable backfill for Playwright-walked EU agency listings (sites behind
a JS / proof-of-work wall, e.g. FRA's Anubis). Upserts each page's items as they
are scraped, so a mid-walk failure loses nothing.

    python3.12 scripts/backfill_browser_listing.py \
        --base https://fra.europa.eu --path /en/case-law-database \
        --body fra --type case_law --link-substr /en/caselaw-reference/ --source fra_caselaw
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._specialised_helpers import get_env  # noqa: E402
from services.scrapers.eu_agency_listing import walk_browser  # noqa: E402

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
  body_html=EXCLUDED.body_html, document_date=EXCLUDED.document_date,
  source_kind=EXCLUDED.source_kind, fetched_at=now();
"""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--type", required=True)
    ap.add_argument("--link-substr", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--max-pages", type=int, default=250)
    args = ap.parse_args()

    dsn = get_env("DATABASE_URL")
    conn = psycopg2.connect(dsn, connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()
    state = {"n": 0, "page": 0}

    def flush(items):
        nonlocal conn, cur
        if not items:
            return
        rows = [(args.body, args.type, it.title, it.summary, it.public_url, it.body_txt,
                 it.body_html, it.document_date, it.creation_date, it.source_kind, it.guid)
                for it in items]
        for attempt in range(4):
            try:
                execute_values(cur, _UPSERT, rows)
                conn.commit()
                state["n"] += len(rows)
                state["page"] += 1
                print(f"  page {state['page']}: +{len(rows)} (total {state['n']})", flush=True)
                return
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                try:
                    cur.close(); conn.close()
                except Exception:
                    pass
                conn = psycopg2.connect(dsn, connect_timeout=15)
                conn.autocommit = False
                cur = conn.cursor()
                if attempt == 3:
                    raise

    await walk_browser(args.base, args.path, args.body, args.type, args.link_substr,
                       args.source, max_pages=args.max_pages, on_page=flush)
    print(f"[DONE] upserted {state['n']} {args.body}/{args.type}", flush=True)
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
