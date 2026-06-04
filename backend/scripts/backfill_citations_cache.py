"""
Backfill the citation_verifications cache with body + 5 mandatory datapoints.

Targets primary EU legal acts from eu_laws — Regulations, Directives,
Decisions — and populates the new fields added in migration 066:
  public_url, body_text, body_html, body_fetched_at,
  creation_date (= eu_laws.created_at), document_date (= eu_laws.date),
  + the standard verifier fields (ref, kind, status, resolved_url, http_status,
  verified_at, expires_at).

Cellar XHTML is fetched in EN; bodies above 1.5 MB are kept as body_text only
to bound storage. Async with concurrency=5 to keep Cellar happy.

Run:
    python3.12 backend/scripts/backfill_citations_cache.py            # dry-run, 10 rows
    python3.12 backend/scripts/backfill_citations_cache.py --limit 500 --apply
    python3.12 backend/scripts/backfill_citations_cache.py --since 2022 --apply   # all since 2022
    python3.12 backend/scripts/backfill_citations_cache.py --since 2020 --apply   # broader
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from datetime import datetime, date as _date, timedelta
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

THROTTLE_S = 0.3
CONCURRENCY = 5
BODY_HTML_MAX_BYTES = 1_500_000  # 1.5 MB — bigger HTMLs kept as body_text only
BODY_MIN_LEN = 500
FETCH_TIMEOUT_S = 45
TTL_OK_DAYS = 30


def get_env(k: str) -> str:
    if not ENV.exists():
        return os.environ.get(k, "")
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(k, "")


def _open_db():
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(db, connect_timeout=15)


# ─────────────────────── HTML strip ───────────────────────────────────


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


# ─────────────────────── Cellar fetch (async) ─────────────────────────


async def fetch_cellar_xhtml(session, celex: str) -> Optional[str]:
    """Cellar XHTML manifestation in English. Returns HTML string or None."""
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    try:
        async with session.get(
            url,
            headers={
                "Accept": "application/xhtml+xml",
                "Accept-Language": "en",
                "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
            },
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                return None
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "xhtml" not in ctype and "html" not in ctype:
                return None
            body = await resp.text()
            if len(body) < BODY_MIN_LEN:
                return None
            return body
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


# ─────────────────────── Per-CELEX worker ─────────────────────────────


UPSERT_SQL = """
INSERT INTO citation_verifications (
    ref, kind, status, resolved_url, http_status, latency_ms,
    original_form, verified_at, expires_at,
    public_url, body_text, body_html, body_fetched_at,
    creation_date, document_date
) VALUES (
    %(ref)s, 'celex', 'ok',
    'https://publications.europa.eu/resource/celex/' || %(ref)s,
    200, 0,
    %(ref)s, NOW(), NOW() + INTERVAL '30 days',
    %(public_url)s, %(body_text)s, %(body_html)s,
    CASE WHEN %(body_text)s IS NOT NULL THEN NOW() ELSE NULL END,
    %(creation_date)s, %(document_date)s
)
ON CONFLICT (ref) DO UPDATE SET
    status         = 'ok',
    resolved_url   = COALESCE(citation_verifications.resolved_url, EXCLUDED.resolved_url),
    public_url     = COALESCE(EXCLUDED.public_url, citation_verifications.public_url),
    body_text      = COALESCE(EXCLUDED.body_text, citation_verifications.body_text),
    body_html      = COALESCE(EXCLUDED.body_html, citation_verifications.body_html),
    body_fetched_at = CASE WHEN EXCLUDED.body_text IS NOT NULL THEN NOW()
                          ELSE citation_verifications.body_fetched_at END,
    creation_date  = COALESCE(EXCLUDED.creation_date, citation_verifications.creation_date),
    document_date  = COALESCE(EXCLUDED.document_date, citation_verifications.document_date),
    expires_at     = CASE WHEN EXCLUDED.body_text IS NOT NULL
                          THEN NOW() + INTERVAL '30 days'
                          ELSE citation_verifications.expires_at END;
"""


async def process_celex(session, celex: str, doc_date, created_at,
                        sem: asyncio.Semaphore) -> dict:
    """Fetch body + return upsert params. Throttled by semaphore."""
    public_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    body_text = None
    body_html = None
    async with sem:
        xhtml = await fetch_cellar_xhtml(session, celex)
        if xhtml:
            body_text = strip_html_to_text(xhtml)
            if len(xhtml) <= BODY_HTML_MAX_BYTES:
                body_html = xhtml
            # else: keep body_text only to bound storage
        await asyncio.sleep(THROTTLE_S)
    return {
        "ref": celex,
        "public_url": public_url,
        "body_text": body_text if body_text and len(body_text) >= BODY_MIN_LEN else None,
        "body_html": body_html,
        "creation_date": created_at,
        "document_date": doc_date,
    }


# ─────────────────────── Main ─────────────────────────────────────────


def pick_universe(conn, since_year: int, limit: Optional[int],
                  refresh_existing: bool) -> list[tuple[str, _date, datetime]]:
    """Return (celex, document_date, created_at) tuples to backfill."""
    cur = conn.cursor()
    skip_clause = "" if refresh_existing else """
        AND NOT EXISTS (
            SELECT 1 FROM citation_verifications cv
            WHERE cv.ref = l.celex AND cv.body_text IS NOT NULL
        )
    """
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    cur.execute(f"""
        SELECT DISTINCT ON (l.celex) l.celex, l.date, l.created_at
          FROM eu_laws l
         WHERE l.celex IS NOT NULL
           AND l.date IS NOT NULL
           AND l.celex LIKE '3%'  -- adopted instruments only (sector 3)
           AND SUBSTRING(l.celex FROM 6 FOR 1) IN ('R','L','D','H')  -- regulation/directive/decision/recommendation
           AND EXTRACT(YEAR FROM l.date) >= {int(since_year)}
           {skip_clause}
         ORDER BY l.celex, l.date DESC
        {limit_clause}
    """)
    return cur.fetchall()


async def main_async(args):
    import aiohttp

    conn = _open_db()
    universe = pick_universe(conn, args.since, args.limit if not args.apply else None,
                             args.refresh_existing)
    if not args.apply:
        universe = universe[: args.limit]

    print(f"[INFO] Universe: {len(universe):,} CELEX to backfill (since {args.since}, "
          f"skip_existing={not args.refresh_existing})", flush=True)

    if not universe:
        print("[DONE] nothing to do", flush=True)
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)

    counts = {"upserted": 0, "with_body": 0, "no_body": 0, "html_capped": 0, "errors": 0}
    start = time.time()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for batch_start in range(0, len(universe), 20):
            batch = universe[batch_start: batch_start + 20]
            tasks = [process_celex(session, celex, doc_date, created_at, sem)
                     for celex, doc_date, created_at in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    counts["errors"] += 1
                    continue
                try:
                    cur = conn.cursor()
                    cur.execute(UPSERT_SQL, r)
                    conn.commit()
                    counts["upserted"] += 1
                    if r["body_text"]:
                        counts["with_body"] += 1
                        if not r["body_html"]:
                            counts["html_capped"] += 1
                    else:
                        counts["no_body"] += 1
                except Exception as e:
                    conn.rollback()
                    counts["errors"] += 1
                    print(f"  UPSERT error for {r['ref']}: {e}", flush=True)

            elapsed = time.time() - start
            done = batch_start + len(batch)
            rate = done / max(elapsed, 0.001)
            eta = (len(universe) - done) / max(rate, 0.001)
            print(f"  [{done:5}/{len(universe)}] elapsed={elapsed:.0f}s "
                  f"rate={rate:.1f}/s eta={eta:.0f}s | "
                  f"upserted={counts['upserted']} body={counts['with_body']} "
                  f"capped={counts['html_capped']} no_body={counts['no_body']} errors={counts['errors']}",
                  flush=True)

    conn.close()
    print("\n[DONE]", counts, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Run full backfill")
    parser.add_argument("--limit", type=int, default=10, help="Dry-run row cap (default: 10)")
    parser.add_argument("--since", type=int, default=2022, help="Minimum document year (default: 2022)")
    parser.add_argument("--refresh-existing", action="store_true",
                        help="Re-fetch body even if cache row already has body_text")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
