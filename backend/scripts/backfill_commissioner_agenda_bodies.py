"""
Backfill body_text + body_html for the 242 rows in commission_calendar_urls.

Each row has a detail_url pointing to commission.europa.eu/.../<event-slug>.
We fetch each page, lightly clean the HTML, and strip to text. Throttled at
0.5s/request with concurrency=5.

Run:
    python3.12 backend/scripts/backfill_commissioner_agenda_bodies.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_commissioner_agenda_bodies.py --apply    # all
    python3.12 backend/scripts/backfill_commissioner_agenda_bodies.py --apply --refresh
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Optional

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

CONCURRENCY = 5
THROTTLE_S = 0.3
TIMEOUT_S = 30
MIN_BODY_LEN = 200


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def _open_db():
    return psycopg2.connect(get_env("DATABASE_URL"), connect_timeout=15)


def strip_html_to_text(html: str) -> str:
    t = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>",
               " ", html, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'"))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]*\n+", "\n\n", t)
    return t.strip()


def extract_main_content(html: str) -> str:
    """Pull the article body from a commission.europa.eu detail page.
    Falls back to whole-page strip if no specific container found."""
    # Try to isolate the main article first — they use ecl-paragraph + main classes
    m = re.search(r'<main[^>]*>(.*?)</main>', html, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    # Fall back to article tag
    m = re.search(r'<article[^>]*>(.*?)</article>', html, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    return html


async def fetch_detail_page(session, url: str) -> Optional[str]:
    try:
        async with session.get(
            url,
            headers={
                "Accept": "text/html",
                "Accept-Language": "en",
                "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
            },
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                return None
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in ctype:
                return None
            body = await resp.text()
            if len(body) < MIN_BODY_LEN:
                return None
            return body
    except Exception:
        return None


async def process_row(session, row, sem: asyncio.Semaphore) -> dict:
    async with sem:
        html = await fetch_detail_page(session, row["detail_url"])
        await asyncio.sleep(THROTTLE_S)
    if not html:
        return {"id": row["id"], "body_text": None, "body_html": None}
    main = extract_main_content(html)
    text = strip_html_to_text(main)
    if len(text) < MIN_BODY_LEN:
        return {"id": row["id"], "body_text": None, "body_html": None}
    return {"id": row["id"], "body_text": text, "body_html": main}


async def main_async(args):
    import aiohttp

    conn = _open_db()
    cur = conn.cursor()

    where = "detail_url IS NOT NULL"
    if not args.refresh:
        where += " AND body_text IS NULL"
    limit_clause = f"LIMIT {args.limit}" if not args.apply else ""
    cur.execute(f"""
        SELECT id, detail_url FROM commission_calendar_urls
        WHERE {where}
        ORDER BY event_date DESC NULLS LAST
        {limit_clause}
    """)
    rows = [{"id": r[0], "detail_url": r[1]} for r in cur.fetchall()]
    print(f"[INFO] Universe: {len(rows):,} rows to fetch", flush=True)
    if not rows:
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_S)
    counts = {"updated": 0, "no_body": 0, "errors": 0}
    start = time.time()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for batch_start in range(0, len(rows), 20):
            batch = rows[batch_start: batch_start + 20]
            tasks = [process_row(session, r, sem) for r in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    counts["errors"] += 1
                    continue
                if r["body_text"]:
                    try:
                        cur.execute(
                            """UPDATE commission_calendar_urls
                                  SET body_text = %(body_text)s,
                                      body_html = %(body_html)s,
                                      body_fetched_at = NOW()
                                WHERE id = %(id)s::uuid""",
                            r,
                        )
                        conn.commit()
                        counts["updated"] += 1
                    except Exception as e:
                        conn.rollback()
                        counts["errors"] += 1
                        print(f"  UPDATE error: {e}")
                else:
                    counts["no_body"] += 1

            done = batch_start + len(batch)
            elapsed = time.time() - start
            print(f"  [{done:4}/{len(rows)}] elapsed={elapsed:.0f}s | "
                  f"updated={counts['updated']} no_body={counts['no_body']} errors={counts['errors']}",
                  flush=True)

    conn.close()
    print(f"\n[DONE] {counts}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
