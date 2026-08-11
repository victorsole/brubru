#!/usr/bin/env python3.12
"""
Descriptor pipeline for the Catalan EuroVoc: dump ES labels -> (Sonnet sub-agents ES->CA)
-> write ca back to eurovoc_concepts.

dump:   python3.12 scripts/eurovoc_descriptor_pipeline.py dump --per-agent 200 --out /tmp/eurovoc_jobs
render: python3.12 scripts/eurovoc_descriptor_pipeline.py render --jobs /tmp/eurovoc_jobs
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from sqlalchemy import create_engine, text


def engine():
    return create_engine(os.environ['DATABASE_URL'])


def cmd_dump(args):
    with engine().connect() as conn:
        rows = list(conn.execute(text(
            "SELECT concept_uri, labels->>'es' AS es, labels->>'en' AS en "
            "FROM eurovoc_concepts WHERE concept_type='descriptor' "
            "AND NOT (labels ? 'ca') ORDER BY notation")))
    os.makedirs(args.out, exist_ok=True)
    items = [{'uri': r[0], 'es': r[1] or r[2], 'en': r[2]} for r in rows if (r[1] or r[2])]
    n = 0
    for i in range(0, len(items), args.per_agent):
        batch = items[i:i+args.per_agent]
        json.dump(batch, open(os.path.join(args.out, f'in_{n:03d}.json'), 'w'), ensure_ascii=False)
        n += 1
    json.dump({'agents': n, 'items': len(items), 'per_agent': args.per_agent},
              open(os.path.join(args.out, 'manifest.json'), 'w'))
    print(f'[DONE] dumped {len(items)} descriptors into {n} agent files -> {args.out}')


def cmd_render(args):
    ups = []
    missing = 0
    for inf in sorted(glob.glob(os.path.join(args.jobs, 'in_*.json'))):
        outf = inf.replace('/in_', '/out_')
        if not os.path.exists(outf):
            missing += 1
            continue
        try:
            out = json.load(open(outf, encoding='utf-8'))
        except Exception as e:
            print(f'[FAIL] {os.path.basename(outf)}: {e}')
            continue
        for o in out:
            if o.get('uri') and o.get('ca') and o['ca'].strip():
                ups.append({'uri': o['uri'], 'ca': o['ca'].strip()})
    if ups:
        with engine().begin() as conn:
            conn.execute(text(
                "UPDATE eurovoc_concepts SET labels = labels || jsonb_build_object('ca', :ca) "
                "WHERE concept_uri = :uri"), ups)
    print(f'[DONE] wrote ca for {len(ups)} descriptors (missing agent outputs: {missing})')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('dump'); d.add_argument('--per-agent', type=int, default=200)
    d.add_argument('--out', default='/tmp/eurovoc_jobs'); d.set_defaults(func=cmd_dump)
    r = sub.add_parser('render'); r.add_argument('--jobs', default='/tmp/eurovoc_jobs')
    r.set_defaults(func=cmd_render)
    args = ap.parse_args(); args.func(args)


if __name__ == '__main__':
    main()
