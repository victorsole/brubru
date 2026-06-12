#!/usr/bin/env python3.12
"""
Resumable backfill for /api/v2/euda/publications.

The complete set of EUDA publication URLs comes from the site's XML sitemap
(~1,238, served cleanly to crawlers); the title of each is read from its page's
og:title. URLs already in the DB are skipped, so a stall loses nothing — re-run
to continue. Plain requests, no browser.

    python3.12 scripts/backfill_euda_publications.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._specialised_helpers import get_env  # noqa: E402
from services.scrapers.euda_publications import (  # noqa: E402
    sitemap_publication_urls, fetch_title, _item, _HEADERS)

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
  body_html=EXCLUDED.body_html, source_kind=EXCLUDED.source_kind, fetched_at=now();
"""


def main() -> None:
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

    cur.execute("SELECT public_url FROM economy_items "
                "WHERE body_code='euda' AND item_type='publication'")
    done = {r[0] for r in cur.fetchall()}

    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    urls = sitemap_publication_urls(s)
    todo = [u for u in urls if u not in done]
    print(f"[INFO] {len(urls)} publication URLs, {len(done)} done, {len(todo)} to fetch",
          flush=True)

    batch, n = [], 0
    for url in todo:
        it = _item(url, fetch_title(s, url), now)
        batch.append(("euda", "publication", it.title, it.summary, it.public_url,
                      it.body_txt, it.body_html, it.document_date, it.creation_date,
                      it.source_kind, it.guid))
        n += 1
        if len(batch) >= 25:
            flush(batch)
            print(f"  upserted {n}/{len(todo)} (last: {it.title[:50]})", flush=True)
            batch = []
        time.sleep(0.15)
    if batch:
        flush(batch)
    print(f"[DONE] upserted {n} EUDA publications this run", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
