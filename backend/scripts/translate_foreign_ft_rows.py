#!/usr/bin/env python3.12
"""Bulk-translate foreign-language F&T + TED rows via Anthropic Haiku.

User-authorised exception to the no-new-Anthropic rule (15 Jun 2026 chat).
The open-model chain (Cerebras gpt-oss-120b) kept 429-ing on the bulk
workload; Haiku 4.5 is faster, higher-rate-limit, and produces excellent
translations.

Strategy:
  - Each row's detected_lang is already set (we do a langdetect sweep first).
  - Filter to rows whose detected_lang is OUTSIDE Brubru's 6 (en/es/ca/fr/it/nl).
  - Call Anthropic Haiku to translate title + first ~1500 chars of description
    into clean British English.
  - Upsert into the matching sidecar (<table>_translations) for lang='en'.
  - Idempotent on (call_id|tender_uuid|tender_id, lang).
  - Concurrency-capped (default 8) — Haiku tolerates higher fan-out.

Usage:
    python3.12 scripts/translate_foreign_ft_rows.py --table ft_calls_for_proposals --limit 1000
    python3.12 scripts/translate_foreign_ft_rows.py --all --concurrency 8
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from anthropic import AsyncAnthropic  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BRUBRU_LANGS = {"en", "es", "ca", "fr", "it", "nl"}
HAIKU_MODEL = "claude-haiku-4-5-20251001"

SOURCES = {
    "tenders": {
        "pk": "id", "pk_cast": "integer",
        "title_col": "title", "desc_col": "description",
        "sidecar": "tenders_translations", "fk": "tender_id",
    },
    "ft_calls_for_proposals": {
        "pk": "id", "pk_cast": "uuid",
        "title_col": "title", "desc_col": "description",
        "sidecar": "ft_calls_for_proposals_translations", "fk": "call_id",
        "extra_where": "AND is_test IS NOT TRUE",
    },
    "ft_calls_for_tenders": {
        "pk": "id", "pk_cast": "uuid",
        "title_col": "title", "desc_col": "description",
        "sidecar": "ft_calls_for_tenders_translations", "fk": "tender_uuid",
        "extra_where": "AND is_test IS NOT TRUE",
    },
}


def _db():
    url = [l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("DATABASE_URL=")][0]
    return psycopg2.connect(url)


def _fetch_foreign(table: str, limit: int) -> list[dict]:
    spec = SOURCES[table]
    where = (
        f"detected_lang IS NOT NULL "
        f"AND detected_lang NOT IN ('en','es','ca','fr','it','nl','und') "
        f"{spec.get('extra_where','')} "
        f"AND NOT EXISTS ("
        f"  SELECT 1 FROM {spec['sidecar']} s "
        f"  WHERE s.{spec['fk']} = {table}.{spec['pk']} AND s.lang='en'"
        f")"
    )
    sql = (
        f"SELECT {spec['pk']}::text AS id_str, {spec['title_col']} AS title, "
        f"       COALESCE({spec['desc_col']},'') AS description, detected_lang "
        f"FROM {table} WHERE {where} LIMIT %s"
    )
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, (limit,))
        return cur.fetchall()
    finally:
        conn.close()


def _clean(s: str) -> str:
    """Strip AI bleed-text: footer link + stray closing quotes / commentary."""
    s = (s or "").strip().strip('"').strip()
    for sep in ("\n\nRead Brubru", "\n\nWould you like me", "\n\nLet me know"):
        if sep in s:
            s = s.split(sep)[0].strip()
    return s


async def _haiku_translate(client: AsyncAnthropic, prompt: str, max_retries: int = 4) -> str:
    """Single Haiku call with retry on rate-limit / transient errors. Returns
    the translation text only — Haiku is reliably terse and rarely adds
    commentary, so post-stripping is minimal."""
    last_err = None
    for attempt in range(max_retries):
        try:
            r = await client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            # Anthropic returns a list of content blocks; we expect one text block.
            for block in r.content:
                if getattr(block, "type", None) == "text":
                    return block.text
            return ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            retryable = any(x in msg for x in (
                "429", "rate", "overloaded", "timeout", "connection", "reset",
            ))
            if not retryable or attempt == max_retries - 1:
                raise
            wait = min(30, 2 ** (attempt + 1))
            await asyncio.sleep(wait)
    raise last_err if last_err else RuntimeError("Haiku call failed without exception")


async def _translate_pair(client: AsyncAnthropic, lang: str, title: str, desc: str) -> tuple[str, str]:
    """Title + first 1500 chars of description -> English, via Haiku."""
    title_prompt = (
        f"Translate this {lang} EU funding-opportunity title into clear "
        f"British English. ONLY the translation, no commentary, no quotes:\n\n{title}"
    )
    en_title = _clean(await _haiku_translate(client, title_prompt))

    en_desc = ""
    if desc and desc.strip():
        desc_prompt = (
            f"Translate this {lang} EU funding-opportunity description into clear "
            f"British English. Preserve all factual content. ONLY the translation, "
            f"no commentary, no quotes:\n\n{desc[:1500].strip()}"
        )
        en_desc = _clean(await _haiku_translate(client, desc_prompt))
    return en_title, en_desc


async def _process_row(sem, client: AsyncAnthropic, table: str, row: dict, stats: dict):
    spec = SOURCES[table]
    async with sem:
        try:
            en_title, en_desc = await _translate_pair(
                client, row["detected_lang"], row["title"] or "", row["description"] or ""
            )
            if not en_title:
                stats["empty"] += 1
                return
            conn = _db()
            try:
                cur = conn.cursor()
                cur.execute(
                    f"INSERT INTO {spec['sidecar']} ({spec['fk']}, lang, title, summary, engine) "
                    f"VALUES (%s::{spec['pk_cast']}, 'en', %s, %s, %s) "
                    f"ON CONFLICT ({spec['fk']}, lang) DO UPDATE SET "
                    f"  title=EXCLUDED.title, summary=EXCLUDED.summary, "
                    f"  engine=EXCLUDED.engine, translated_at=now()",
                    (row["id_str"], en_title[:500],
                     en_desc[:1800] if en_desc else en_title[:500], HAIKU_MODEL),
                )
                conn.commit()
                stats["ok"] += 1
                if stats["ok"] % 25 == 0:
                    print(f"  ... translated {stats['ok']}/{stats['total']} so far", flush=True)
            finally:
                conn.close()
        except Exception as e:
            stats["err"] += 1
            print(f"  [warn] {row['id_str']} ({row.get('detected_lang')}): {str(e)[:120]}", flush=True)


async def run(table: str, limit: int, concurrency: int):
    if table not in SOURCES:
        raise SystemExit(f"--table must be one of {list(SOURCES.keys())}")
    rows = _fetch_foreign(table, limit)
    if not rows:
        print(f"[{table}] no foreign rows pending translation.")
        return
    print(f"[{table}] {len(rows)} foreign rows to translate via Haiku (concurrency={concurrency})", flush=True)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set in environment.")
    client = AsyncAnthropic()
    sem = asyncio.Semaphore(concurrency)
    stats = {"ok": 0, "err": 0, "empty": 0, "total": len(rows)}
    await asyncio.gather(*[_process_row(sem, client, table, r, stats) for r in rows])
    print(f"[{table}] done. ok={stats['ok']} err={stats['err']} empty={stats['empty']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=list(SOURCES.keys()),
                    help="Source table to bulk-translate")
    ap.add_argument("--all", action="store_true",
                    help="Run on every source table sequentially")
    ap.add_argument("--limit", type=int, default=500,
                    help="Max rows per table (default 500)")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="Concurrent Haiku calls (default 8)")
    args = ap.parse_args()

    async def runner():
        if args.all:
            for t in SOURCES:
                await run(t, args.limit, args.concurrency)
        elif args.table:
            await run(args.table, args.limit, args.concurrency)
        else:
            ap.error("provide --table or --all")

    asyncio.run(runner())


if __name__ == "__main__":
    sys.exit(main())
