#!/usr/bin/env python3.12
"""
Resumable backfill for /api/v2/parliament/supporting-analyses.

Walks the EP Think Tank Policy-Department corpus (contributors=poldep) year by
year (the Think Tank caps each query's displayed results at 500, and every poldep
year is well under that). Plain `requests` works — no browser needed. Upserts
incrementally per year; re-running continues where it stopped.

    python3.12 scripts/backfill_supporting_analyses.py
    python3.12 scripts/backfill_supporting_analyses.py --first-year 2015
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._specialised_helpers import get_env  # noqa: E402
from services.scrapers.ep_supporting_analyses import walk_year, _HEADERS, _FIRST_YEAR  # noqa: E402

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
  body_html=EXCLUDED.body_html, document_date=EXCLUDED.document_date,
  source_kind=EXCLUDED.source_kind, guid=EXCLUDED.guid, fetched_at=now();
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-year", type=int, default=_FIRST_YEAR)
    args = ap.parse_args()

    dsn = get_env("DATABASE_URL")
    conn = psycopg2.connect(dsn, connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()

    def flush(rows):
        nonlocal conn, cur
        for attempt in range(4):
            try:
                execute_values(cur, _UPSERT, rows)
                conn.commit()
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

    s = requests.Session()
    s.headers.update(_HEADERS)
    this_year = datetime.now(timezone.utc).year
    total = 0
    for year in range(this_year, args.first_year - 1, -1):
        rows, refs = [], set()
        for it in walk_year(s, year):
            if it.guid in refs:
                continue
            refs.add(it.guid)
            rows.append(("parliament", "supporting_analysis", it.title, it.summary,
                         it.public_url, it.body_txt, it.body_html, it.document_date,
                         it.creation_date, it.source_kind, it.guid))
        if rows:
            flush(rows)
            total += len(rows)
        print(f"  {year}: {len(rows)} docs (running total {total})", flush=True)
    print(f"[DONE] upserted {total} supporting analyses", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
