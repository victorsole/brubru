#!/usr/bin/env python3.12
"""
Fill the empty `ca` labels on eurovoc_concepts -> the first Catalan EuroVoc.

Engine: Softcatala eng-cat NMT (CTranslate2, local, €0) + Brubru Catalan glossary.
(The memory prefers an ES pivot, but only the eng-cat model is available offline; EN->CA
is accurate for short controlled-vocabulary terms. Re-runnable: overwrites ca only.)

- Domains + microthesauri labels are "NOTATION text" -> translate text, keep NOTATION,
  UPPERCASE domains to match the "04 VIDA POLITICA" house style.
- Descriptors are plain terms.
- Writes: UPDATE eurovoc_concepts SET labels = labels || jsonb_build_object('ca', :ca).

Usage: python3.12 scripts/eurovoc_translate_ca.py [--limit N] [--type domain|microthesaurus|descriptor]
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.catalan_translate import _ensure_softcatala_model, _apply_glossary  # noqa: E402


def load_model():
    import ctranslate2
    import sentencepiece as spm
    md = _ensure_softcatala_model()
    ct2 = os.path.join(md, "ctranslate2")
    sp = os.path.join(md, "tokenizer", "sp_m.model")
    if not os.path.exists(sp):
        sp = os.path.join(md, "eng-cat", "tokenizer", "sp_m.model")
        ct2 = os.path.join(md, "eng-cat", "ctranslate2")
    return spm.SentencePieceProcessor(model_file=sp), ctranslate2.Translator(ct2)


NOTATION_RE = re.compile(r'^(\d[\w.]*)\s+(.*)$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--type', default='all')
    ap.add_argument('--batch', type=int, default=128)
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ['DATABASE_URL'])

    where = "WHERE (labels->>'en') IS NOT NULL"
    if args.type != 'all':
        where += f" AND concept_type = '{args.type}'"
    q = f"SELECT concept_uri, concept_type, labels->>'en' AS en FROM eurovoc_concepts {where} ORDER BY concept_type, notation"
    with engine.connect() as conn:
        rows = list(conn.execute(text(q)))
    if args.limit:
        rows = rows[:args.limit]
    print(f'[INFO] {len(rows)} concepts to translate')

    sp, tr = load_model()

    def translate_texts(texts):
        toks = [sp.encode(t, out_type=str) for t in texts]
        res = tr.translate_batch(toks, beam_size=5, max_decoding_length=256)
        return [_apply_glossary(sp.decode(r.hypotheses[0])) for r in res]

    # Prepare (uri, en_text_to_translate, prefix, is_domain)
    jobs = []
    for uri, ctype, en in rows:
        prefix = ''
        txt = en
        m = NOTATION_RE.match(en)
        if m and ctype in ('domain', 'microthesaurus'):
            prefix, txt = m.group(1), m.group(2)
        jobs.append((uri, txt, prefix, ctype == 'domain'))

    updates = []
    B = args.batch
    for i in range(0, len(jobs), B):
        chunk = jobs[i:i+B]
        cats = translate_texts([j[1] for j in chunk])
        for (uri, _txt, prefix, is_dom), ca in zip(chunk, cats):
            ca = ca.strip()
            if is_dom:
                ca = ca.upper()
            label_ca = f'{prefix} {ca}'.strip() if prefix else ca
            updates.append({'uri': uri, 'ca': label_ca})
        print(f'  [{min(i+B, len(jobs))}/{len(jobs)}] translated')

    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE eurovoc_concepts SET labels = labels || jsonb_build_object('ca', :ca) "
            "WHERE concept_uri = :uri"), updates)
    print(f'[DONE] wrote ca for {len(updates)} concepts')


if __name__ == '__main__':
    main()
