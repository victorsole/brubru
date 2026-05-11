"""
Backfill commission_documents body_html + text_body + publication_date.

For every CELEX-bearing row in commission_documents:
  1. Fetch Cellar XHTML (with 202-retry) → store as body_html
  2. If text_body is missing, derive from body_html (strip tags) OR fall back
     to Cellar PDF → pypdf extract
  3. If publication_date is missing, parse from body_text preamble using the
     "of DD Month YYYY" regex shared with the citations endpoint

For non-CELEX rows (legacy COM/SWD entries with portal_url only), we leave
them alone — no Cellar identifier to fetch by.

Run:
    python3.12 backend/scripts/backfill_commission_documents_body.py          # dry-run, 5 rows
    python3.12 backend/scripts/backfill_commission_documents_body.py --apply  # full
    python3.12 backend/scripts/backfill_commission_documents_body.py --apply --refresh-existing
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import re
import sys
import time
from datetime import datetime, date as _date
from pathlib import Path
from typing import Optional

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

THROTTLE_S = 0.3
CONCURRENCY = 5
BODY_HTML_MAX_BYTES = 1_500_000
BODY_MIN_LEN = 500
FETCH_TIMEOUT_S = 45


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def _open_db():
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(db, connect_timeout=15)


# ─────────────────────── HTML strip + date parser ───────────────────────


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


_DATE_PATTERN = re.compile(
    r"\b(?:REGULATION|DIRECTIVE|DECISION|RECOMMENDATION|COMMUNICATION|RESOLUTION|"
    r"OPINION|REPORT|AGREEMENT|PROTOCOL|REGLAMENTO|DIRECTIVA|DECISIÓN|RÈGLEMENT)"
    r"[^.]{0,400}?\bof\s+(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{4})\b",
    re.IGNORECASE | re.DOTALL,
)
_MONTH_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_document_date(body_text: Optional[str]) -> Optional[_date]:
    if not body_text:
        return None
    head = body_text[:4096]
    m = _DATE_PATTERN.search(head)
    if not m:
        return None
    try:
        day = int(m.group(1))
        month = _MONTH_TO_NUM.get(m.group(2).lower())
        year = int(m.group(3))
        if not month or not (1 <= day <= 31) or not (1950 <= year <= 2099):
            return None
        return _date(year, month, day)
    except (ValueError, TypeError):
        return None


# ─────────────────────── Cellar fetch (async, with 202-retry) ───────────


async def fetch_cellar_xhtml(session, celex: str) -> Optional[str]:
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    backoff = 1.5
    for attempt in range(1, 5):
        try:
            async with session.get(url, headers={
                "Accept": "application/xhtml+xml",
                "Accept-Language": "en",
                "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
            }, allow_redirects=True) as resp:
                if resp.status in (202, 503):
                    if attempt < 4:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    return None
                if resp.status != 200:
                    return None
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "xhtml" not in ctype and "html" not in ctype:
                    return None
                body = await resp.text()
                if len(body) < BODY_MIN_LEN:
                    return None
                return body
        except Exception:
            return None
    return None


async def fetch_cellar_pdf(session, celex: str) -> Optional[bytes]:
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    backoff = 1.5
    for attempt in range(1, 5):
        try:
            async with session.get(url, headers={
                "Accept": "application/pdf",
                "Accept-Language": "en",
                "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
            }, allow_redirects=True) as resp:
                if resp.status in (202, 503):
                    if attempt < 4:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    return None
                if resp.status != 200:
                    return None
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "pdf" in ctype:
                    return await resp.read()
                # Cellar 300-multi-choice — find DOC_1 PDF
                listing = await resp.text()
                m = re.search(r'(https?://publications\.europa\.eu/resource/cellar/[^"\s<>]+DOC_1\.pdf)', listing)
                if not m:
                    return None
                async with session.get(m.group(1), headers={
                    "Accept": "application/pdf",
                    "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)",
                }) as resp2:
                    if "pdf" in (resp2.headers.get("Content-Type") or "").lower():
                        return await resp2.read()
                return None
        except Exception:
            return None
    return None


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip() or None
    except Exception:
        return None


# ─────────────────────── Worker ─────────────────────────────────────────


async def process_row(session, row_id, celex: str, has_body_html: bool,
                      has_text_body: bool, has_pub_date: bool,
                      sem: asyncio.Semaphore, refresh: bool) -> dict:
    body_html = None
    body_text = None
    parsed_date = None

    async with sem:
        if refresh or not has_body_html:
            xhtml = await fetch_cellar_xhtml(session, celex)
            if xhtml:
                if len(xhtml) <= BODY_HTML_MAX_BYTES:
                    body_html = xhtml
                if not has_text_body or refresh:
                    body_text = strip_html_to_text(xhtml)
        if (refresh or not has_text_body) and not body_text:
            pdf = await fetch_cellar_pdf(session, celex)
            if pdf:
                body_text = extract_pdf_text(pdf)
        if (refresh or not has_pub_date) and body_text:
            parsed_date = parse_document_date(body_text)
        await asyncio.sleep(THROTTLE_S)

    return {
        "id": row_id,
        "body_html": body_html,
        "body_text": body_text,
        "parsed_date": parsed_date,
    }


# ─────────────────────── Main ───────────────────────────────────────────


async def main_async(args):
    import aiohttp

    conn = _open_db()
    cur = conn.cursor()

    # Pick universe: CELEX-bearing rows missing any of body_html / text_body / publication_date
    where = "celex IS NOT NULL"
    if not args.refresh_existing:
        where += """ AND (body_html IS NULL OR text_body IS NULL OR publication_date IS NULL)"""
    limit_clause = f"LIMIT {int(args.limit)}" if not args.apply else ""
    cur.execute(f"""
        SELECT id, celex,
               body_html IS NOT NULL AS has_body_html,
               text_body IS NOT NULL AS has_text_body,
               publication_date IS NOT NULL AS has_pub_date
          FROM commission_documents
         WHERE {where}
      ORDER BY first_seen DESC
        {limit_clause}
    """)
    universe = cur.fetchall()

    print(f"[INFO] Backfill universe: {len(universe):,} rows", flush=True)
    if not universe:
        return

    sem = asyncio.Semaphore(CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
    counts = {"upd_html": 0, "upd_text": 0, "upd_date": 0, "errors": 0}
    start = time.time()

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for batch_start in range(0, len(universe), 20):
            batch = universe[batch_start: batch_start + 20]
            tasks = [process_row(session, rid, celex, hh, ht, hp, sem, args.refresh_existing)
                     for rid, celex, hh, ht, hp in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    counts["errors"] += 1
                    continue
                setters = []
                params = {"id": r["id"]}
                if r["body_html"]:
                    setters.append("body_html = %(body_html)s")
                    params["body_html"] = r["body_html"]
                    counts["upd_html"] += 1
                if r["body_text"]:
                    setters.append("text_body = %(body_text)s")
                    params["body_text"] = r["body_text"]
                    counts["upd_text"] += 1
                if r["parsed_date"]:
                    setters.append("publication_date = %(parsed_date)s")
                    params["parsed_date"] = r["parsed_date"]
                    counts["upd_date"] += 1
                if setters:
                    setters.append("last_updated = NOW()")
                    try:
                        cur.execute(
                            f"UPDATE commission_documents SET {', '.join(setters)} WHERE id = %(id)s::uuid",
                            params,
                        )
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        counts["errors"] += 1
                        print(f"  UPDATE error: {e}")

            done = batch_start + len(batch)
            elapsed = time.time() - start
            print(f"  [{done:4}/{len(universe)}] elapsed={elapsed:.0f}s | "
                  f"upd_html={counts['upd_html']} upd_text={counts['upd_text']} "
                  f"upd_date={counts['upd_date']} errors={counts['errors']}", flush=True)

    conn.close()
    print(f"\n[DONE] {counts}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Run full backfill")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--refresh-existing", action="store_true",
                        help="Re-fetch even when row already has body_html/text_body/publication_date")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
