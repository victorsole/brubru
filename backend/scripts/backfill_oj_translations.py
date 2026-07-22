#!/usr/bin/env python3.12
"""
Backfill My OJ entry translations (EN -> CA) with Softcatala NMT.

Translates ``oj_entries.title`` + ``plain_explanation`` into Catalan and caches
them in ``oj_entry_translations`` (migration 201), one row per (entry, lang) —
the brussels_lobby_news_translations sidecar pattern. Runs LOCALLY against the
prod DB, like the Catalan law pipeline: free, no API calls, no Anthropic.

Engine: Softcatala eng-cat (CTranslate2 + SentencePiece), the same model as
scripts/catalan_translate.py, with the shared protected-token regex (CELEX,
case numbers, URLs survive verbatim) and legal glossary.

Resumable: skips (entry, lang) pairs already cached; newest OJ dates first so
the visible tab fills up immediately. Chunked read -> translate IN MEMORY ->
short write (Supabase's pooler drops long-lived connections during CPU work).

Usage (from backend/):
    python3.12 scripts/backfill_oj_translations.py                 # full backlog
    python3.12 scripts/backfill_oj_translations.py --limit 200
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent))
from softcatala_translate_text import ensure_model, load_translator, _tr_span, PROTECT, _POSTFIX
from catalan_translate import _apply_glossary

LANG = "ca"
ENGINE = "softcatala-eng-cat"

# OJ-title fixes on top of the shared glossary. EU institutional opinions
# (EESC, CoR, ECB, Court of Auditors) are "dictamen" in EU Catalan, not "opinió".
_OJ_POSTFIX = [
    ("Opinió del Comitè", "Dictamen del Comitè"),
    ("Opinió del Banc Central Europeu", "Dictamen del Banc Central Europeu"),
    ("Opinió del Tribunal de Comptes", "Dictamen del Tribunal de Comptes"),
    ("Opinió del Supervisor Europeu", "Dictamen del Supervisor Europeu"),
]


def _db():
    url = [l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("DATABASE_URL=")][0]
    c = psycopg2.connect(url, connect_timeout=15, keepalives=1,
                         keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    c.autocommit = False
    return c


def _translator():
    mdir, pair = ensure_model("en")
    tr, sp = load_translator(mdir, pair)
    print(f"[model] {pair} ready", flush=True)

    def translate(text: str) -> str:
        if not text or not text.strip():
            return text
        parts = PROTECT.split(text)
        rebuilt = [p if (j % 2 == 1) else _tr_span(p, tr, sp) for j, p in enumerate(parts)]
        out = _apply_glossary("".join(rebuilt))
        out = out.replace('⁇', '·').replace(' — ', ', ').replace('—', ', ')
        for a, b in _POSTFIX + _OJ_POSTFIX:
            out = out.replace(a, b)
        return out.strip()
    return translate


def _fetch_pending(batch: int):
    """Short read connection: next chunk of entries with no cached translation."""
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT e.id, e.title, e.plain_explanation
              FROM oj_entries e
             WHERE NOT EXISTS (
                     SELECT 1 FROM oj_entry_translations t
                      WHERE t.oj_entry_id = e.id AND t.lang = %s)
             ORDER BY e.oj_date DESC, e.series, e.oj_number
             LIMIT %s
        """, (LANG, batch))
        return cur.fetchall()
    finally:
        conn.close()


def _write_batch(writes):
    """Short write connection: persist a chunk's translations."""
    conn = _db()
    try:
        cur = conn.cursor()
        for entry_id, t_title, t_expl in writes:
            cur.execute("""
                INSERT INTO oj_entry_translations
                    (oj_entry_id, lang, title, plain_explanation, engine)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (oj_entry_id, lang) DO UPDATE
                    SET title=EXCLUDED.title, plain_explanation=EXCLUDED.plain_explanation,
                        engine=EXCLUDED.engine, translated_at=now()
            """, (str(entry_id), LANG, t_title, t_expl, ENGINE))
        conn.commit()
    finally:
        conn.close()


def run(limit: int, batch: int):
    translate = _translator()
    done = 0
    t0 = time.time()
    while done < limit:
        rows = _fetch_pending(min(batch, limit - done))
        if not rows:
            break
        writes = []
        for r in rows:
            try:
                t_title = translate(r["title"])
                t_expl = translate(r["plain_explanation"]) if r["plain_explanation"] else None
                writes.append((r["id"], t_title, t_expl))
            except Exception as e:
                print(f"  [warn] {r['id']}: {str(e)[:80]}", flush=True)
        # Retry the write once if the pooler dropped us between batches.
        for attempt in (1, 2):
            try:
                _write_batch(writes)
                break
            except psycopg2.OperationalError as e:
                if attempt == 2:
                    raise
                print(f"  [retry] write batch after: {str(e)[:60]}", flush=True)
                time.sleep(3)
        done += len(rows)
        rate = (time.time() - t0) / max(done, 1)
        print(f"  .. {done} translated ({rate:.1f}s/entry)", flush=True)
    print(f"[DONE] {done} entries -> '{LANG}' in {(time.time()-t0)/60:.1f}min", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--batch", type=int, default=25)
    args = ap.parse_args()
    run(args.limit, args.batch)


if __name__ == "__main__":
    sys.exit(main())
