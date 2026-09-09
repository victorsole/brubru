#!/usr/bin/env python3.12
"""Re-translate My OJ entries whose Catalan text carries a laundered interpunct.

Why this exists (9 September 2026). `backfill_oj_translations.py` used to end its
translate() with

    out = out.replace('⁇', '·')

which swapped the Softcatala unknown-character marker for a Catalan interpunct.
That did not repair anything: it made destroyed text look like ordinary Catalan
punctuation. "Holdermann" shipped as "H · ldermann", "Sociálna poisťovňa" as
"Soci · lna pois · ov · a", and a search for the marker returned ZERO,
which read as a clean bill of health. 283 of 2,608 rows -- 11% of My OJ -- were
affected, and the surface is the one the Catalan OJ video showcases.

The laundering is deleted and the character guard is wired in; this script
repairs the rows already stored.

DETECTION. A legitimate Catalan interpunct is ALWAYS between two l's (Brussel·les,
il·lícit). Any other interpunct in this corpus is a destroyed character. That is
the whole test, and it is why a plain "count the interpuncts" check is useless.

    python3.12 scripts/repair_oj_translation_interpuncts.py            # dry run
    python3.12 scripts/repair_oj_translation_interpuncts.py --apply
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import pathlib

_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
sys.path.insert(0, _BACKEND)
sys.path.insert(0, os.path.join(_BACKEND, "scripts"))
os.chdir(_BACKEND)

import psycopg2
import psycopg2.extras

from softcatala_translate_text import ensure_model, load_translator, _tr_span, PROTECT
from catalan_translate import _apply_glossary, _sc_protected

# A destroyed character, as opposed to Brussel·les / il·lícit.
BAD_INTERPUNCT = re.compile(r"(?<![lL])·|·(?![lL])")


def _db_url() -> str:
    from scripts._db_url import get_database_url
    return get_database_url()


def _translator():
    mdir, pair = ensure_model("en")
    tr, sp = load_translator(mdir, pair)

    def translate(text: str) -> str:
        if not text or not text.strip():
            return text
        parts = PROTECT.split(text)
        rebuilt = [p if (j % 2 == 1) else _sc_protected(p, lambda t: _tr_span(t, tr, sp))
                   for j, p in enumerate(parts)]
        return _apply_glossary("".join(rebuilt)).strip()

    return translate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = psycopg2.connect(_db_url(), connect_timeout=15)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.id, t.oj_entry_id, t.title AS ca_title, t.plain_explanation AS ca_expl,
               e.title AS en_title, e.plain_explanation AS en_expl, e.celex
          FROM oj_entry_translations t
          JOIN oj_entries e ON e.id = t.oj_entry_id
         WHERE t.lang = 'ca'
         ORDER BY t.translated_at DESC NULLS LAST
    """)
    rows = [r for r in cur.fetchall()
            if BAD_INTERPUNCT.search(r["ca_title"] or "")
            or BAD_INTERPUNCT.search(r["ca_expl"] or "")]
    if args.limit:
        rows = rows[: args.limit]
    print(f"[INFO] {len(rows)} row(s) carry a destroyed character  (apply={args.apply})")
    if not rows:
        return 0

    translate = _translator()
    repaired = unfixable = 0
    for r in rows:
        new_title = translate(r["en_title"]) if r["en_title"] else r["ca_title"]
        new_expl = translate(r["en_expl"]) if r["en_expl"] else r["ca_expl"]
        # Never write back something still broken -- that would just move the damage.
        if BAD_INTERPUNCT.search(new_title or "") or BAD_INTERPUNCT.search(new_expl or ""):
            print(f"  [KEEP] {r['celex'] or r['oj_entry_id']}: still damaged after re-translation")
            unfixable += 1
            continue
        repaired += 1
        if repaired <= 5 or not args.apply:
            print(f"  [FIX ] {r['celex'] or r['oj_entry_id']}")
            print(f"         before: {(r['ca_title'] or '')[:100]}")
            print(f"         after : {(new_title or '')[:100]}")
        if args.apply:
            cur.execute("""UPDATE oj_entry_translations
                              SET title=%s, plain_explanation=%s, translated_at=now()
                            WHERE id=%s""", (new_title, new_expl, r["id"]))
            if repaired % 25 == 0:
                conn.commit()
    if args.apply:
        conn.commit()

    print(f"\n[DONE] repaired={repaired} left_damaged={unfixable}")

    # Post-run invariant, counted from the database rather than from the loop.
    cur.execute("SELECT title, plain_explanation FROM oj_entry_translations WHERE lang='ca'")
    remaining = sum(1 for r in cur.fetchall()
                    if BAD_INTERPUNCT.search(r["title"] or "")
                    or BAD_INTERPUNCT.search(r["plain_explanation"] or ""))
    print(f"[CHECK] rows still carrying a destroyed character: {remaining}")
    conn.close()
    if args.apply and remaining > unfixable:
        print("[ERROR] more damage remains than the run declared unfixable")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
