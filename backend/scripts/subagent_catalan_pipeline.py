#!/usr/bin/env python3.12
"""
Sub-agent Catalan translation harness.

Bulk-translates EU acts to Catalan using Claude Code sub-agents (Sonnet) running on
Victor's Claude Code subscription -- NOT the unfunded Anthropic API (see
memory/feedback_bulk_translation_via_subagents.md). The slow Softcatala NMT loop is the
default €0 path; this harness is the on-demand "spend my usage to go fast" path.

Architecture (reuses catalan_translate.py end to end):
  parse_formex(xml) -> parsed dict
  _do_translate(parsed, translate_text, translate_batch) -> translated dict
  generate_html(translated, celex) -> HTML

  DUMP  : parse each act, extract the exact ordered set of source segments
          _do_translate would request, group N acts per agent file.
  (agents translate segments -> Catalan, written back as parallel arrays)
  RENDER: rebuild a {source_text: catalan_text} lookup per act, replay
          _do_translate with lookup callables, generate_html, write index.html,
          import_to_db(engine='sonnet-subagent', deployed=False).

Deploy is handled by the existing deploy_catalan_backlog.py (deployed_at IS NULL sweep).

Usage:
  # 1. Build agent input files for the next 3900 pending admin acts:
  python3.12 scripts/subagent_catalan_pipeline.py dump \
      --count 3900 --max-size 50 --per-agent 6 --out /tmp/cat_jobs

  # 2. (Claude orchestrates: one Sonnet sub-agent per /tmp/cat_jobs/in_*.json
  #     -> writes /tmp/cat_jobs/out_*.json)

  # 3. Render + DB-insert every translated act:
  python3.12 scripts/subagent_catalan_pipeline.py render --jobs /tmp/cat_jobs
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the canonical pipeline.
from scripts.catalan_translate import (  # noqa: E402
    parse_formex, _do_translate, generate_html, _apply_glossary,
)
from scripts.batch_catalan_translate import import_to_db  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND_DIR)
TRANSLATIONS_DIR = os.path.join(ROOT, 'data', 'legislacio-ue-catala')
FULL_QUEUE = os.path.join(TRANSLATIONS_DIR, 'translation_queue_full.txt')
OLD_QUEUE = os.path.join(TRANSLATIONS_DIR, 'translation_queue.txt')


def resolve_xml(path: str) -> str:
    """Queue paths may be absolute, repo-root-relative, or backend-relative (../docs/...)."""
    cands = [path,
             os.path.normpath(os.path.join(BACKEND_DIR, path)),
             os.path.normpath(os.path.join(ROOT, path))]
    for c in cands:
        if os.path.exists(c):
            return c
    return path


def extract_segments(parsed: dict) -> list:
    """The exact set of source strings _do_translate would translate, first-seen order, deduped."""
    seen = set()
    out = []

    def add(s):
        if s and s.strip() and s not in seen:
            seen.add(s)
            out.append(s)

    add(parsed.get('title', ''))
    add(parsed.get('preamble_init', ''))
    add(parsed.get('preamble_final', ''))
    add(parsed.get('recitals_init', ''))
    for v in parsed.get('visas', []):
        add(v)
    for r in parsed.get('recitals', []):
        add(r)
    for art in parsed.get('articles', []):
        add(art.get('title', ''))
        for p in art.get('paragraphs', []):
            add(p)
    add(parsed.get('final', ''))
    return out


def load_queue():
    qf = FULL_QUEUE if os.path.exists(FULL_QUEUE) else OLD_QUEUE
    lines = [l.strip() for l in open(qf) if l.strip() and not l.startswith('#')]
    rows = []
    for l in lines:
        p = l.split('|')
        if len(p) < 3:
            continue
        rows.append({
            'xml_path': p[0], 'celex': p[1], 'size_kb': int(p[2]),
            'file_type': p[3] if len(p) > 3 else 'main',
            'oj_ref': p[4] if len(p) > 4 else '',
            'parent_celex': p[5] if len(p) > 5 else '',
        })
    return rows


def already_done():
    if not os.path.isdir(TRANSLATIONS_DIR):
        return set()
    return {d for d in os.listdir(TRANSLATIONS_DIR)
            if os.path.isdir(os.path.join(TRANSLATIONS_DIR, d)) and not d.endswith('-softcatala')}


def cmd_dump(args):
    rows = load_queue()
    done = already_done()
    exclude = set()
    if args.exclude:
        exclude = {l.strip() for l in open(args.exclude) if l.strip()}

    pending = []
    for r in rows:
        if r['celex'] in done or r['celex'] in exclude:
            continue
        if r['size_kb'] > args.max_size or r['size_kb'] < args.min_size:
            continue
        if args.file_type != 'all' and r['file_type'] != args.file_type:
            continue
        pending.append(r)
        if len(pending) >= args.count:
            break

    os.makedirs(args.out, exist_ok=True)
    # Resolve xml paths relative to repo root if not absolute.
    n_agents = 0
    n_acts = 0
    n_skipped = 0
    batch = []

    def flush(idx, batch):
        path = os.path.join(args.out, f'in_{idx:04d}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False)

    for r in pending:
        xml_path = resolve_xml(r['xml_path'])
        try:
            parsed = parse_formex(xml_path)
            segs = extract_segments(parsed)
        except Exception as e:
            print(f'[SKIP] {r["celex"]}: parse failed: {e}')
            n_skipped += 1
            continue
        if not segs:
            print(f'[SKIP] {r["celex"]}: no segments')
            n_skipped += 1
            continue
        batch.append({
            'celex': r['celex'], 'xml_path': xml_path,
            'file_type': r['file_type'], 'oj_ref': r['oj_ref'],
            'parent_celex': r['parent_celex'], 'size_kb': r['size_kb'],
            'segments': segs,
        })
        n_acts += 1
        if len(batch) >= args.per_agent:
            flush(n_agents, batch)
            n_agents += 1
            batch = []
    if batch:
        flush(n_agents, batch)
        n_agents += 1

    manifest = {'agents': n_agents, 'acts': n_acts, 'skipped': n_skipped,
                'per_agent': args.per_agent, 'out': args.out}
    with open(os.path.join(args.out, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f'[DONE] dumped {n_acts} acts into {n_agents} agent files '
          f'(per_agent={args.per_agent}, skipped={n_skipped}) -> {args.out}')


def cmd_render(args):
    in_files = sorted(glob.glob(os.path.join(args.jobs, 'in_*.json')))
    rendered = 0
    failed = 0
    missing_out = 0
    mismatch = 0
    for inf in in_files:
        outf = inf.replace('/in_', '/out_')
        if not os.path.exists(outf):
            missing_out += 1
            continue
        try:
            in_acts = json.load(open(inf, encoding='utf-8'))
            out_acts = json.load(open(outf, encoding='utf-8'))
        except Exception as e:
            print(f'[FAIL] {os.path.basename(outf)}: bad JSON: {e}')
            failed += 1
            continue
        out_by_celex = {a['celex']: a for a in out_acts}
        for ia in in_acts:
            celex = ia['celex']
            oa = out_by_celex.get(celex)
            if not oa:
                print(f'[SKIP] {celex}: no agent output')
                missing_out += 1
                continue
            src = ia['segments']
            tgt = oa.get('segments_ca', [])
            if len(src) != len(tgt):
                print(f'[SKIP] {celex}: segment count mismatch ({len(src)} vs {len(tgt)})')
                mismatch += 1
                continue
            lookup = {s: t for s, t in zip(src, tgt)}

            def translate_text(s, _lk=lookup):
                if not s or not s.strip():
                    return s
                return _apply_glossary(_lk.get(s, s))

            def translate_batch(texts, label, _lk=lookup):
                return [_apply_glossary(_lk.get(t, t)) if t and t.strip() else t for t in texts]

            xml_path = resolve_xml(ia['xml_path'])
            try:
                parsed = parse_formex(xml_path)
                translated = _do_translate(parsed, translate_text, translate_batch)
                html = generate_html(translated, celex)
            except Exception as e:
                print(f'[FAIL] {celex}: render error: {e}')
                failed += 1
                continue

            out_dir = os.path.join(TRANSLATIONS_DIR, celex)
            os.makedirs(out_dir, exist_ok=True)
            html_path = os.path.join(out_dir, 'index.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            import_to_db(
                celex=celex,
                title_ca=translated.get('title', '') or celex,
                articles=len(parsed.get('articles', [])),
                recitals=len(parsed.get('recitals', [])),
                size=len(html.encode('utf-8')),
                engine='sonnet-subagent',
                file_type=ia.get('file_type', 'main'),
                oj_ref=ia.get('oj_ref', ''),
                parent_celex=ia.get('parent_celex', ''),
                deployed=False,
            )
            rendered += 1
            if rendered % 25 == 0:
                print(f'  [{rendered}] rendered...')

    print(f'[DONE] rendered={rendered} failed={failed} mismatch={mismatch} '
          f'missing_out={missing_out}')


def main():
    ap = argparse.ArgumentParser(description='Sub-agent Catalan translation harness')
    sub = ap.add_subparsers(dest='cmd', required=True)

    d = sub.add_parser('dump', help='Extract source segments into per-agent input files')
    d.add_argument('--count', type=int, default=3900)
    d.add_argument('--per-agent', type=int, default=6)
    d.add_argument('--max-size', type=int, default=50)
    d.add_argument('--min-size', type=int, default=0)
    d.add_argument('--file-type', default='all', choices=['all', 'main', 'annex'])
    d.add_argument('--exclude', help='File of CELEX to exclude (e.g. in-flight Softcatala batch)')
    d.add_argument('--out', default='/tmp/cat_jobs')
    d.set_defaults(func=cmd_dump)

    r = sub.add_parser('render', help='Render translated agent output to HTML + DB')
    r.add_argument('--jobs', default='/tmp/cat_jobs')
    r.set_defaults(func=cmd_render)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
