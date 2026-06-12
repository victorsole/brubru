#!/usr/bin/env python3.12
"""
Backfill Tenderator translations across the 5 funding sources.

Mirrors backfill_lobby_translations.py (MEUB pattern) — runs LOCALLY against
the prod DB, free CPU M2M100, no HF credits. Detects each item's language
with langdetect; if outside Brubru's 6 (en/es/ca/fr/it/nl), translates
title + description into all 6 up front so any user sees the card in their
UI language. Items already in one of the 6 are left as-is (the read path
falls back to the original).

Resumable: skips rows that already have detected_lang. ON CONFLICT
(item_id, lang) DO UPDATE → idempotent on re-runs.

Usage (from backend/):
    python3.12 scripts/backfill_tenderator_translations.py --table tenders --limit 500
    python3.12 scripts/backfill_tenderator_translations.py --table ft_calls_for_tenders --limit 500
    python3.12 scripts/backfill_tenderator_translations.py --table economy_items --funding-only --limit 200
    python3.12 scripts/backfill_tenderator_translations.py --table ft_calls_for_proposals --limit 200
    python3.12 scripts/backfill_tenderator_translations.py --table ft_funded_projects --limit 200
"""
from __future__ import annotations

import argparse
import sys
import time

import psycopg2
import psycopg2.extras

SIX = ["en", "es", "ca", "fr", "it", "nl"]
SIX_SET = set(SIX)
ENGINE = "m2m100_418M"

# langdetect -> m2m100 (only the divergent ones).
_SRC_MAP = {"zh-cn": "zh", "zh-tw": "zh", "he": "iw"}

# Per-source field map: which columns hold the title + description, the
# FK column on the sidecar, the sidecar table name, and an optional WHERE
# filter on the source rows.
SOURCES = {
    "tenders": {
        "pk": "id",
        "pk_cast": "integer",
        "title": "title",
        "summary": "description",
        "order_by": "publication_date DESC NULLS LAST",
        "where": "title IS NOT NULL AND length(title) >= 12",
        "sidecar": "tenders_translations",
        "sidecar_fk": "tender_id",
    },
    "ft_calls_for_proposals": {
        "pk": "id",
        "pk_cast": "uuid",
        "title": "title",
        "summary": "description",
        "order_by": "deadline DESC NULLS LAST",
        "where": "title IS NOT NULL AND length(title) >= 12 AND is_test IS NOT TRUE",
        "sidecar": "ft_calls_for_proposals_translations",
        "sidecar_fk": "call_id",
    },
    "ft_calls_for_tenders": {
        "pk": "id",
        "pk_cast": "uuid",
        "title": "title",
        "summary": "description",
        "order_by": "deadline DESC NULLS LAST",
        "where": "title IS NOT NULL AND length(title) >= 12 AND is_test IS NOT TRUE",
        "sidecar": "ft_calls_for_tenders_translations",
        "sidecar_fk": "tender_uuid",
    },
    "ft_funded_projects": {
        "pk": "id",
        "pk_cast": "uuid",
        "title": "title",
        "summary": "objective",
        "order_by": "start_date DESC NULLS LAST",
        "where": "title IS NOT NULL AND length(title) >= 12 AND is_test IS NOT TRUE",
        "sidecar": "ft_funded_projects_translations",
        "sidecar_fk": "project_uuid",
    },
    "economy_items": {
        "pk": "id",
        "pk_cast": "integer",
        "title": "title",
        "summary": "summary",
        "order_by": "document_date DESC NULLS LAST",
        # default: ALL economy_items rows; --funding-only narrows below.
        "where": "title IS NOT NULL AND length(title) >= 12",
        "sidecar": "economy_items_translations",
        "sidecar_fk": "item_id",
    },
}


def _db():
    url = [l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("DATABASE_URL=")][0]
    c = psycopg2.connect(url, connect_timeout=15, keepalives=1,
                         keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    c.autocommit = False
    return c


def _detector():
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0

    def detect_lang(text: str) -> str:
        try:
            return detect(text)
        except Exception:
            return "und"
    return detect_lang


def _translator():
    """Load m2m100_418M once; return translate(text, src, tgt)."""
    print("[load] facebook/m2m100_418M (first run downloads ~1.9GB) ...", flush=True)
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
    tok = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
    model.eval()
    valid = set(tok.lang_code_to_id.keys())
    print(f"[load] ready ({len(valid)} languages)", flush=True)

    def translate(text: str, src: str, tgt: str) -> str:
        if not text or not text.strip():
            return text
        s = _SRC_MAP.get(src, src)
        if s not in valid:
            s = "en"
        tok.src_lang = s
        enc = tok(text[:1000], return_tensors="pt", truncation=True, max_length=400)
        gen = model.generate(**enc, forced_bos_token_id=tok.get_lang_id(tgt),
                             max_length=400, num_beams=1)
        return tok.batch_decode(gen, skip_special_tokens=True)[0].strip()
    return translate


def _fetch_undetected(table: str, spec: dict, batch: int, funding_only: bool):
    """Short read connection: pull the next chunk of undetected items."""
    where = spec["where"] + " AND detected_lang IS NULL"
    if table == "economy_items" and funding_only:
        where += " AND item_type IN ('tender','grant','eoi_call','startup_funding')"
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = f"""
            SELECT {spec['pk']}::text AS id_str,
                   {spec['title']}    AS title,
                   COALESCE({spec['summary']}, '') AS summary
              FROM {table}
             WHERE {where}
             ORDER BY {spec['order_by']}
             LIMIT %s
        """
        cur.execute(sql, (batch,))
        return cur.fetchall()
    finally:
        conn.close()


def _write_batch(spec: dict, table: str, writes):
    """Short write connection: persist detection + translations for a chunk."""
    conn = _db()
    try:
        cur = conn.cursor()
        for item_id, lang, trans_rows in writes:
            cur.execute(
                f"UPDATE {table} SET detected_lang=%s WHERE {spec['pk']}=%s::{spec['pk_cast']}",
                (lang, item_id),
            )
            for tgt, t_title, t_sum in trans_rows:
                cur.execute(
                    f"""
                    INSERT INTO {spec['sidecar']}
                        ({spec['sidecar_fk']}, lang, title, summary, engine)
                    VALUES (%s::{spec['pk_cast']}, %s, %s, %s, %s)
                    ON CONFLICT ({spec['sidecar_fk']}, lang) DO UPDATE
                        SET title=EXCLUDED.title, summary=EXCLUDED.summary,
                            engine=EXCLUDED.engine, translated_at=now()
                    """,
                    (item_id, tgt, t_title, t_sum, ENGINE),
                )
        conn.commit()
    finally:
        conn.close()


def run(table: str, limit: int, batch: int, funding_only: bool):
    """Read -> translate IN MEMORY (no DB held) -> short write. Robust to
    Supabase closing long-lived connections during slow CPU translation.

    M2M100 (1.9GB) is loaded LAZILY on the first foreign-language row only.
    A cron run that finds zero new foreign rows pays only the langdetect
    cost (negligible) and skips the model load entirely — keeps the
    /sync/daily and /sync/economy budgets cheap on quiet days.
    """
    if table not in SOURCES:
        raise SystemExit(f"--table must be one of {list(SOURCES.keys())}")
    spec = SOURCES[table]
    detect_lang = _detector()

    # Lazy: only load M2M100 when we actually find a foreign row.
    _translate_cache: list = [None]
    def get_translate():
        if _translate_cache[0] is None:
            _translate_cache[0] = _translator()
        return _translate_cache[0]

    done = foreign = 0
    while done < limit:
        rows = _fetch_undetected(table, spec, min(batch, limit - done), funding_only)
        if not rows:
            print(f"[{table}] no more undetected rows.", flush=True)
            break
        writes = []
        for r in rows:
            text = (r["title"] + " " + r["summary"]).strip()
            lang = detect_lang(text)
            trans_rows = []
            if lang not in SIX_SET and lang != "und":
                foreign += 1
                translate = get_translate()
                for tgt in SIX:
                    try:
                        t_title = translate(r["title"], lang, tgt)
                        t_sum = translate(r["summary"], lang, tgt) if r["summary"] else None
                        trans_rows.append((tgt, t_title, t_sum))
                    except Exception as e:
                        print(f"  [warn] {r['id_str']} {lang}->{tgt}: {str(e)[:80]}", flush=True)
            writes.append((r["id_str"], lang, trans_rows))
        # Retry the write once if the pooler dropped us between batches.
        for attempt in (1, 2):
            try:
                _write_batch(spec, table, writes)
                break
            except psycopg2.OperationalError as e:
                if attempt == 2:
                    raise
                print(f"  [retry] write batch after: {str(e)[:60]}", flush=True)
                time.sleep(3)
        done += len(rows)
        print(f"  .. {done} processed ({foreign} foreign → {foreign*6} translation rows so far)",
              flush=True)
    print(f"[{table}] done: {done} processed, {foreign} foreign → {foreign*6} translation rows",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True,
                    choices=list(SOURCES.keys()),
                    help="Source table to backfill")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--funding-only", action="store_true",
                    help="(economy_items only) restrict to funding item_types")
    args = ap.parse_args()
    run(args.table, args.limit, args.batch, args.funding_only)


if __name__ == "__main__":
    sys.exit(main())
