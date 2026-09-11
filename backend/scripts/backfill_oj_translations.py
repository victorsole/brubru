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
import re
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

# Two entries, both derived from this file's own location so the script works
# from any CWD and under `python3.12 -m backend.scripts.<name>`:
#   backend/scripts -> sibling modules below (softcatala_translate_text, ...)
#   backend         -> the "scripts._db_url" package import inside _db()
# Without the second, running it the way oj_catalan_daily.sh does dies with
# ModuleNotFoundError: No module named 'scripts' AFTER the model has loaded,
# so the failure looks like "no entries to translate" rather than a crash.
_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from softcatala_translate_text import ensure_model, load_translator, _tr_span, PROTECT, _POSTFIX
from catalan_translate import _apply_glossary, _sc_protected

LANG = "ca"
ENGINE = "softcatala-eng-cat"

# OJ-title fixes on top of the shared glossary. EU institutional opinions
# (EESC, CoR, ECB, Court of Auditors) are "dictamen" in EU Catalan, not "opinió".
_OJ_POSTFIX = [
    # Merger notices: "Case M.12161" is a case, not a house (80 titles, 11 Sep 2026).
    ("(Casa M.", "(Cas M."),
    ("(Case M.", "(Cas M."),
    # The model writes (PESC) for 138 of 156 CFSP titles and keeps the English
    # acronym on the rest (11 Sep 2026).
    ("(CFSP)", "(PESC)"),
    ("Opinió del Comitè", "Dictamen del Comitè"),
    ("Opinió del Banc Central Europeu", "Dictamen del Banc Central Europeu"),
    ("Opinió del Tribunal de Comptes", "Dictamen del Tribunal de Comptes"),
    ("Opinió del Supervisor Europeu", "Dictamen del Supervisor Europeu"),
]


def _db():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    url = get_database_url()
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
        # Typographic quotes, apostrophes and non-breaking hyphens are normalised
        # inside _sc_protected (11 Sep 2026), shared with the act pages; do not
        # pre-normalise here, or paired quotes lose their Catalan « ».
        parts = PROTECT.split(text)
        # PROTECT guards IDENTIFIERS (CELEX, ECLI, case numbers, brand names). It
        # does nothing about characters, so every foreign letter used to reach the
        # model raw and come back as U+2047. _sc_protected is the CHARACTER guard,
        # measured against the model: it can emit 26 non-ASCII characters and
        # destroys everything else. Both are needed; neither substitutes for the
        # other. Added 9 September 2026.
        rebuilt = [p if (j % 2 == 1) else _sc_protected(p, lambda t: _tr_span(t, tr, sp))
                   for j, p in enumerate(parts)]
        out = _apply_glossary("".join(rebuilt))
        # The U+2047 -> "·" substitution that used to sit here is DELETED, and this
        # comment is here so it does not come back. It did not fix anything: it
        # laundered destroyed text into a character that looks like legitimate
        # Catalan punctuation, so "Höldermann" shipped as "H · ldermann" and
        # "Sociálna poisťovňa" as "Soci · lna pois · ov · a" -- 283 of 2,608 rows,
        # 11% of My OJ -- while a search for the marker returned ZERO and read as
        # a clean bill of health. A visible marker is a bug report; an interpunct
        # is a silent corruption of a party name.
        out = out.replace(' — ', ', ').replace('—', ', ')
        for a, b in _POSTFIX + _OJ_POSTFIX:
            out = out.replace(a, b)
        return out.strip()
    return translate


def _fetch_pending(batch: int):
    """Next chunk: no cached translation, OR a cached row whose explanation is stale.

    The AI plain_explanation is generated AFTER an entry is first synced, so the
    original "no ca row at all" predicate closed the door too early: the title
    backfill cached a row with a NULL explanation, the English explanation
    landed later, and the entry was never revisited. My OJ then showed a Catalan
    title above an English explanation -- 0 of 46 entries had a translated
    explanation across 8-9 Sep 2026. The upsert is ON CONFLICT DO UPDATE, so
    re-selecting an entry is safe and idempotent.
    """
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT e.id, e.title, e.plain_explanation
              FROM oj_entries e
              LEFT JOIN oj_entry_translations t
                     ON t.oj_entry_id = e.id AND t.lang = %s
             WHERE t.id IS NULL
                OR (e.plain_explanation IS NOT NULL AND t.plain_explanation IS NULL)
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


# Debris the pre-normalisation translate() left in stored rows: a restored
# typographic character (the model never emits one itself) or a merger case
# rendered as a house. Re-translating through the CURRENT translate() repairs it.
# ⁇ added the same day: 61 EP adopted-text titles translated on 9 Sep carried
# "P10 ⁇ TA(2026)0089", the underscore destroyed before the character guard.
_DEBRIS_SQL = r"[’‘‑‐⁇]|\((Casa|Case) M\."
_DEBRIS = re.compile(r"[’‘‑‐⁇]|\((?:Casa|Case) M\.")


def repair_typography(limit: int, apply: bool):
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT e.id, e.title, e.plain_explanation,
                   t.title AS ca_title, t.plain_explanation AS ca_expl
              FROM oj_entries e
              JOIN oj_entry_translations t ON t.oj_entry_id = e.id AND t.lang = %s
             WHERE t.title ~ %s OR t.plain_explanation ~ %s
             ORDER BY e.oj_date DESC
             LIMIT %s
        """, (LANG, _DEBRIS_SQL, _DEBRIS_SQL, limit))
        rows = cur.fetchall()
    finally:
        conn.close()
    print(f"[INFO] {len(rows)} row(s) carry typographic debris (apply={apply})", flush=True)
    if not rows:
        return 0
    translate = _translator()
    writes, kept = [], 0
    for r in rows:
        t_title = translate(r["title"])
        t_expl = translate(r["plain_explanation"]) if r["plain_explanation"] else None
        # Never write back something still broken; that only moves the damage.
        if _DEBRIS.search(t_title or "") or _DEBRIS.search(t_expl or ""):
            kept += 1
            print(f"  [KEEP] {r['id']}: still carries debris after re-translation", flush=True)
            continue
        writes.append((r["id"], t_title, t_expl))
        if not apply or len(writes) <= 5:
            # Dry run prints every pair, so the whole repair can be read before it is applied.
            print(f"  [{r['id']}]\n  title before: {r['ca_title']}\n  title after : {t_title}"
                  f"\n  expl  before: {r['ca_expl']}\n  expl  after : {t_expl}", flush=True)
    if apply:
        for i in range(0, len(writes), 25):
            _write_batch(writes[i:i + 25])
    print(f"[DONE] repaired={len(writes) if apply else 0} would_repair={len(writes)} kept={kept}", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--repair-typography", action="store_true",
                    help="Re-translate stored rows carrying ’/‑ debris or 'Casa M.' (dry run without --apply).")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.repair_typography:
        return repair_typography(args.limit, args.apply)
    run(args.limit, args.batch)


if __name__ == "__main__":
    sys.exit(main())
