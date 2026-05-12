"""
backfill_secondary_acts_html — populate secondary_acts.{body_html, text_body}
from EUR-Lex Cellar XHTML manifestations for adopted delegated/implementing
acts that have a CELEX.

Sibling of the legacy backfill_secondary_acts_body.py (which fetches PDFs).
This one prefers XHTML so we get both an HTML body AND a clean text rendering
in a single fetch.

For records with no CELEX (drafts not yet adopted), nothing is fetched —
they keep null body. The /api/v1/delegated-acts route emits the regdel
record URL as public_url in that case (filled in by backfill_regdel_ids.py).

Run modes:
  python3.12 backend/scripts/backfill_secondary_acts_html.py --limit 10 --dry-run
  python3.12 backend/scripts/backfill_secondary_acts_html.py --limit 200
  python3.12 backend/scripts/backfill_secondary_acts_html.py --refresh-older-than 90
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-secondary-acts-html")

CELLAR_TEMPLATE = "https://publications.europa.eu/resource/celex/{celex}"
TIMEOUT_S = 45
MIN_LEN = 500


def _strip_html_to_text(html: str) -> str:
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


async def _fetch_one(celex: str, session: aiohttp.ClientSession) -> Optional[str]:
    url = CELLAR_TEMPLATE.format(celex=celex)
    backoff = 1.5
    for attempt in range(1, 5):
        try:
            async with session.get(
                url,
                headers={"Accept": "application/xhtml+xml",
                         "Accept-Language": "en",
                         "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)"},
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_S),
            ) as r:
                if r.status in (202, 503):
                    if attempt < 4:
                        await asyncio.sleep(backoff); backoff *= 2
                        continue
                    log.warning("[%s] gave up after retries (last status %s)", celex, r.status)
                    return None
                if r.status != 200:
                    log.warning("[%s] cellar returned %s", celex, r.status)
                    return None
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "xhtml" not in ctype and "html" not in ctype:
                    log.warning("[%s] wrong content-type %r", celex, ctype)
                    return None
                body = await r.text()
                if len(body) < MIN_LEN:
                    log.warning("[%s] body too small (%d bytes)", celex, len(body))
                    return None
                return body
        except Exception as exc:
            log.warning("[%s] fetch error: %s", celex, exc)
            return None
    return None


async def _run(engine, rows: list, dry_run: bool, concurrency: int):
    sem = asyncio.Semaphore(concurrency)
    results: dict = {}
    async with aiohttp.ClientSession() as session:
        async def _go(rid, celex):
            async with sem:
                results[rid] = (celex, await _fetch_one(celex, session))
        await asyncio.gather(*[_go(rid, celex) for rid, celex in rows])
    ok = sum(1 for v in results.values() if v[1])
    log.info("Fetched %d / %d successfully", ok, len(results))
    if dry_run:
        shown = 0
        for rid, (celex, body) in results.items():
            if not body:
                continue
            log.info("  %s → %d bytes, text preview: %r",
                     celex, len(body), _strip_html_to_text(body)[:120])
            shown += 1
            if shown >= 3:
                break
        return
    now = datetime.utcnow()
    with engine.begin() as c:
        for rid, (celex, html) in results.items():
            if not html:
                c.execute(text("UPDATE secondary_acts SET body_fetched_at = :now WHERE id = :id"),
                          {"now": now, "id": rid})
                continue
            txt = _strip_html_to_text(html)
            c.execute(text("""
                UPDATE secondary_acts
                SET body_html       = :h,
                    text_body       = COALESCE(NULLIF(:t,''), text_body),
                    body_fetched_at = :now
                WHERE id = :id
            """), {"h": html, "t": txt, "now": now, "id": rid})
    log.info("Wrote %d rows.", ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--refresh-older-than", type=int, default=None,
                    help="Also refresh rows whose body was fetched > N days ago.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--act-type", default="delegated",
                    choices=["delegated", "implementing"],
                    help="delegated (default) | implementing")
    args = ap.parse_args()

    eng = create_engine(os.environ["DATABASE_URL"])
    where = ["celex IS NOT NULL AND celex <> ''", "act_type = :act_type"]
    params = {"act_type": args.act_type, "lim": args.limit}
    if args.refresh_older_than is None:
        where.append("(body_html IS NULL OR body_fetched_at IS NULL)")
    else:
        cutoff = datetime.utcnow() - timedelta(days=args.refresh_older_than)
        where.append(f"(body_html IS NULL OR body_fetched_at IS NULL OR body_fetched_at < '{cutoff.isoformat()}')")
    sql = (f"SELECT id, celex FROM secondary_acts WHERE {' AND '.join(where)} "
           f"ORDER BY first_seen DESC LIMIT :lim")
    with eng.connect() as c:
        rows = [(r[0], r[1]) for r in c.execute(text(sql), params).fetchall()]
    if not rows:
        log.info("Nothing to fetch.")
        return
    log.info("Fetching %d %s acts with concurrency=%d", len(rows), args.act_type, args.concurrency)
    asyncio.run(_run(eng, rows, dry_run=args.dry_run, concurrency=args.concurrency))


if __name__ == "__main__":
    main()
