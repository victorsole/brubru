#!/usr/bin/env python3.12
"""
Resumable backfill for EUDA news / events (sitemap + og:title, skip already-done).

    python3.12 scripts/backfill_euda_content.py --kind news
    python3.12 scripts/backfill_euda_content.py --kind events
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts._specialised_helpers import get_env  # noqa: E402
from services.scrapers.euda_publications import sitemap_urls, fetch_title, _HEADERS  # noqa: E402
from services.scrapers.euda_content import _item  # noqa: E402

_UPSERT = """
INSERT INTO economy_items
  (body_code, item_type, title, summary, public_url, body_txt, body_html,
   document_date, creation_date, source_kind, guid)
VALUES %s
ON CONFLICT (body_code, item_type, public_url) DO UPDATE SET
  title=EXCLUDED.title, summary=EXCLUDED.summary, body_txt=EXCLUDED.body_txt,
  body_html=EXCLUDED.body_html, source_kind=EXCLUDED.source_kind, fetched_at=now();
"""
_KINDS = {"news": ("/news/", "news"), "events": ("/events/", "event")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=list(_KINDS), required=True)
    args = ap.parse_args()
    substr, item_type = _KINDS[args.kind]

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
                "WHERE body_code='euda' AND item_type=%s", (item_type,))
    done = {r[0] for r in cur.fetchall()}

    s = requests.Session()
    s.headers.update(_HEADERS)
    now = datetime.now(timezone.utc)
    urls = sitemap_urls(s, substr)
    todo = [u for u in urls if u not in done]
    print(f"[INFO] {len(urls)} {args.kind} URLs, {len(done)} done, {len(todo)} to fetch", flush=True)

    batch, n = [], 0
    for url in todo:
        it = _item(url, fetch_title(s, url), item_type, now)
        batch.append(("euda", item_type, it.title, it.summary, it.public_url, it.body_txt,
                      it.body_html, it.document_date, it.creation_date, it.source_kind, it.guid))
        n += 1
        if len(batch) >= 25:
            flush(batch)
            print(f"  upserted {n}/{len(todo)} (last: {it.title[:45]})", flush=True)
            batch = []
        time.sleep(0.15)
    if batch:
        flush(batch)
    print(f"[DONE] upserted {n} EUDA {args.kind} this run", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
