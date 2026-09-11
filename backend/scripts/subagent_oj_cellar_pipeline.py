#!/usr/bin/env python3.12
"""
Sub-agent Catalan translation harness for the daily-OJ backlog (Cellar-fed).

Sibling of subagent_catalan_pipeline.py, which is Formex-fed off the
LEG_2025-11 dump. The OJ backlog is NOT in that dump (it is 2026 law), so this
variant sources each act from Cellar and parses it with parse_oj_html, then
reuses the identical canonical tail: _do_translate -> generate_html ->
import_to_db. Output HTML is therefore byte-identical in structure to the
Softcatala path; only the translation callable differs.

Built 7 Sep 2026: the local Softcatala model cannot run (the Mac was at 7.07GB
of 8GB swap), so translation moves off-machine to Claude Code sub-agents, which
bill the subscription rather than the unfunded API key.

    dump   --limit N --out DIR    fetch + parse + extract ordered segments
    (sub-agents translate in_*.json -> out_*.json, index-aligned)
    render --jobs DIR             replay, glossary, HTML, DB row (undeployed)

Batches are packed by CHARACTER BUDGET, not a fixed act count: on the 30 Jun
wave a fixed per-agent=6 put several large acts in one job and the agent died
on the output-token ceiling, silently losing all 6.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.catalan_translate import (  # noqa: E402
    fetch_from_cellar, parse_oj_html, _do_translate, generate_html, _apply_glossary,
    _parse_generic_c_html,
)
from scripts.batch_catalan_translate import import_to_db  # noqa: E402
from scripts.subagent_catalan_pipeline import extract_segments  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND_DIR)
TRANSLATIONS_DIR = os.path.join(ROOT, 'data', 'legislacio-ue-catala')
ENGINE = 'haiku-subagent'


# Words that exist in English and NOT in Catalan. Deliberately conservative:
# "no", "a", "or" (gold), "has" (tu has), "son" are real Catalan words and are
# excluded, or the gate would flag correct translations.
_EN_ONLY = re.compile(
    r"\b(the|of|and|shall|which|with|from|this|that|been|have|for|into|"
    r"following|concerning|pursuant|taken|making|available|whereas|thereof|"
    r"therein|such|where|when|their|there|shall|must|been|during|between|"
    r"within|under|upon|these|those|other|than|been|being|about|after|before)\b",
    re.I)


def residue(segments):
    """(flagged_segment_count, total_hits) of untranslated English.

    The segment-count check proves ALIGNMENT, not translation: the first Haiku
    pass returned perfectly aligned output in which 14 of 19 segments were
    half-English ("sobre la prorrogacio of the action taken by..."). Content
    needs its own gate.
    """
    flagged = hits = 0
    for s in segments:
        n = len(_EN_ONLY.findall(s or ""))
        if n:
            flagged += 1
            hits += n
    return flagged, hits


# Case-SENSITIVE (11 Sep 2026): agent placeholders are written in capitals, and
# with re.I the ordinary Catalan word "error" at the start of a sentence ("error
# de classificació d'ingressos: ...") rejected a correct 663-segment resolution.
_PLACEHOLDER = re.compile(r"^\s*[\[<(]?\s*(ERROR|TODO|N/?A|PLACEHOLDER|UNTRANSLATED|FIXME)\b")


def quality_fail(src, tgt):
    """Reason this translation must not ship, or None.

    residue() alone is not enough. An agent that could not translate wrote
    6401 segments of "[ERROR]" and scored a PERFECT 0.000 residue ratio,
    because a placeholder contains no English words. A gate that only looks
    for the failure you already met will keep passing the next one.
    """
    n = len(tgt)
    if not n:
        return 'empty output'

    ph = sum(1 for t in tgt if _PLACEHOLDER.match(t or ''))
    if ph:
        return f'{ph}/{n} placeholder segments'

    # Untranslated copies: identical to source on segments with real prose.
    # Proper names are EXCLUDED: an anti-dumping regulation is largely a list of
    # exporters ("Zhejiang Hengshi Fiberglass Fabrics Co. Ltd"), which must stay
    # identical. Counting those flagged a correct act at 11/41.
    def _is_name(t):
        words = [w for w in (t or '').split() if w[:1].isalpha()]
        if not words:
            return False
        caps = sum(1 for w in words if w[:1].isupper())
        return caps / len(words) >= 0.6 or 'http' in t

    subst = [(a, b) for a, b in zip(src, tgt)
             if len((a or '').split()) > 3 and not _is_name(a)]
    if subst:
        same = sum(1 for a, b in subst if a.strip() == (b or '').strip())
        if same / len(subst) > 0.20:
            return f'{same}/{len(subst)} segments identical to the English source'

    # Length collapse: a translation is never a fraction of the original.
    src_len = sum(len(a or '') for a in src)
    tgt_len = sum(len(b or '') for b in tgt)
    if src_len > 400 and tgt_len < 0.5 * src_len:
        return f'output {tgt_len} chars vs source {src_len} (collapsed)'

    return None


# Orthography that CANNOT occur in Catalan. Portuguese "-ção/-ões/-ão" and
# Castilian "-ción/-idad" are the realistic leaks from a multilingual model.
# "ñ" is deliberately NOT here: it is wrong in Catalan words but legitimate in
# surnames (Muñoz), so it would flag correct pages.
# NOTE: "-idades" is NOT here. Spanish "entidades" ends that way, but so do
# ordinary Catalan participles (validades, convidades, consolidades) — the
# first version of this gate flagged 307 correct pages. Only the Spanish
# SINGULAR "-idad", which no Catalan word ends in, is safe to match.
_FOREIGN = re.compile(r"\w+(ção|ções|ões|ción|ciones)\b|\w+idad\b|\w+ão\b", re.I)


def foreign_leak(segments, sources=None):
    """Catalan text carrying Portuguese/Castilian word forms the SOURCE lacks.

    Found live on 7 Sep 2026: an agent wrote "el registre de população" inside
    an otherwise clean Catalan act, and every existing gate passed it — the
    English-residue check only knows English.

    A form present in the ENGLISH SOURCE is never a leak. Customs and origin
    regulations prescribe wording in several official languages at once, e.g.
    'Cumulation with country(ies) x/y', 'Cumul avec le(s) pays x/y',
    'Acumulación con el(los) país(paeses) x/y' — an exporter must write those
    verbatim, so translating them would be the error.
    """
    hits = []
    for i, s in enumerate(segments):
        src = (sources[i] if sources and i < len(sources) else "") or ""
        for m in _FOREIGN.finditer(s or ""):
            if m.group(0) not in src:
                hits.append((i, m.group(0)))
    return hits


def fetch_act(celex, oj_id=""):
    """Cellar by CELEX, falling back to Cellar by OJ id.

    UN ECE Regulations annexed to EU law 404 on /resource/celex/ but are served
    fine on /resource/oj/{oj_id}. Before this, the only fallback was Playwright
    on EUR-Lex, which returns 202/0 bytes behind the WAF — so 7 acts looked
    permanently unreachable when they were one URL away.
    """
    try:
        return fetch_from_cellar(celex)
    except Exception as first:
        if not oj_id:
            raise
        import httpx
        url = f"https://publications.europa.eu/resource/oj/{oj_id}"
        r = httpx.get(url, headers={
            "User-Agent": "Brubru/1.0 (EU Policy Assistant; +https://brubru.eu)",
            "Accept": "application/xhtml+xml, text/html",
            "Accept-Language": "eng"}, follow_redirects=True, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"celex: {first}; oj id {oj_id}: HTTP {r.status_code}")
        path = f"/tmp/{celex}_ojid.html"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(r.text)
        print(f"  [INFO] {celex} via OJ id {oj_id} ({len(r.text)} bytes)", flush=True)
        return path


def parse_act(html_path, celex):
    """parse_oj_html, falling back to the skeleton-less generic parser.

    UN/ECE Regulations annexed to EU law are valid OJ HTML but have NO articles
    and NO recitals — they are numbered prose plus test-procedure tables — so
    the L-series parser returns 0/0 and the act cannot be translated at all.
    _parse_generic_c_html already solves exactly this for C-series items by
    flattening the body into one pseudo-article; reuse it here rather than
    inventing a second flattener.
    """
    parsed = parse_oj_html(html_path, celex=celex)
    if parsed.get('articles') or parsed.get('recitals'):
        return parsed
    from bs4 import BeautifulSoup
    with open(html_path, encoding='utf-8') as fh:
        soup = BeautifulSoup(fh.read(), 'html.parser')
    print(f'  [INFO] {celex}: no act skeleton, using generic flattener', flush=True)
    return _parse_generic_c_html(soup, html_path, celex)


def _db():
    import psycopg2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _db_url import get_database_url
    return psycopg2.connect(get_database_url(), connect_timeout=20)


def _pending(limit, before_date, only=None):
    """Same predicate as translate_oj_daily_acts._pending, oldest-first.

    Oldest-first is deliberate: the daily job is newest-first and has already
    cleared July onward, so the untouched backlog sits at the far end.
    """
    import psycopg2.extras
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Keyed on COALESCE(celex, oj_id), and EEA Joint Committee decisions are
        # IN (11 Sep 2026). Their exclusion dated from July, when the scraper
        # gave them wrong-sector CELEXes that 404ed; derive_celex now returns
        # None for them, they resolve on Cellar by OJ id, and 98 sat untranslated.
        q = """
            SELECT DISTINCT ON (COALESCE(e.celex, e.oj_id))
                   COALESCE(e.celex, e.oj_id) AS celex, e.oj_id, e.oj_date, e.title
              FROM oj_entries e
             WHERE e.series = 'L' AND COALESCE(e.celex, e.oj_id) IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM catalan_translations ct
                                WHERE ct.celex = COALESCE(e.celex, e.oj_id))
        """
        params = []
        if only:
            q += " AND COALESCE(e.celex, e.oj_id) = ANY(%s)"
            params.append(list(only))
        if before_date:
            q += " AND e.oj_date < %s"
            params.append(before_date)
        q += " ORDER BY COALESCE(e.celex, e.oj_id), e.oj_date DESC"
        cur.execute(q, params)
        rows = sorted(cur.fetchall(), key=lambda r: r['oj_date'])
        return [dict(r) for r in rows][:limit]
    finally:
        conn.close()


def cmd_dump(args):
    os.makedirs(args.out, exist_ok=True)
    rows = _pending(args.limit, args.before,
                    [c.strip() for c in args.only.split(',')] if args.only else None)
    print(f'[INFO] {len(rows)} pending acts to dump')

    acts, failures = [], []
    for i, r in enumerate(rows, 1):
        celex = r['celex']
        try:
            html_path = fetch_act(celex, r.get('oj_id') or '')
            parsed = parse_act(html_path, celex)
            segs = extract_segments(parsed)
            if not segs or (not parsed.get('articles') and not parsed.get('recitals')):
                raise RuntimeError('no articles/recitals parsed')
            acts.append({
                'celex': celex,
                'oj_id': r.get('oj_id') or '',
                'oj_date': str(r['oj_date']),
                'html_path': html_path,
                'chars': sum(len(s) for s in segs),
                'segments': segs,
            })
            print(f'  [{i}/{len(rows)}] {celex}: {len(segs)} segments', flush=True)
        except Exception as e:
            failures.append({'celex': celex, 'error': str(e)[:200]})
            print(f'  [{i}/{len(rows)}] {celex}: FETCH/PARSE FAILED: {str(e)[:110]}', flush=True)

    # Split any act too big for one agent into contiguous segment ranges.
    # A char budget alone is not enough: an act LARGER than the budget still
    # lands in a job by itself and is handed to one agent whole. That is how
    # the 405-segment act came back 343/405 half-English and the 361-segment
    # act came back truncated to 11 segments.
    pieces = []
    for a in acts:
        segs = a['segments']
        start = 0
        while start < len(segs):
            end, chars = start, 0
            while end < len(segs) and (end - start) < args.max_segs and \
                    (chars + len(segs[end]) <= args.max_chars or end == start):
                chars += len(segs[end])
                end += 1
            pieces.append({**a, 'segments': segs[start:end], 'chars': chars,
                           'seg_start': start, 'total_segments': len(segs)})
            start = end

    # Pack pieces by character budget.
    jobs, cur_job, cur_chars = [], [], 0
    for a in sorted(pieces, key=lambda x: -x['chars']):
        if cur_job and (cur_chars + a['chars'] > args.max_chars or len(cur_job) >= args.max_acts):
            jobs.append(cur_job)
            cur_job, cur_chars = [], 0
        cur_job.append(a)
        cur_chars += a['chars']
    if cur_job:
        jobs.append(cur_job)

    for n, job in enumerate(jobs):
        p = os.path.join(args.out, f'in_{n:04d}.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(job, f, ensure_ascii=False, indent=1)
    if failures:
        with open(os.path.join(args.out, 'fetch_failures.json'), 'w') as f:
            json.dump(failures, f, indent=1)
    print(f'[DONE] {len(acts)} acts -> {len(jobs)} jobs in {args.out}; '
          f'{len(failures)} fetch failures; {len(pieces)} pieces '
          f'({sum(1 for p in pieces if p["total_segments"] > len(p["segments"]))} from split acts)')


def cmd_render(args):
    """Reassemble agent output per act, gate it, then render + register.

    Acts may be SPLIT across several job files (large ones are chunked into
    contiguous segment ranges), so this collects every piece first and only
    renders an act whose pieces cover its full segment list exactly once.
    """
    pieces = {}          # celex -> list of piece dicts
    missing = 0
    for inf in sorted(glob.glob(os.path.join(args.jobs, 'in_*.json'))):
        outf = inf.replace('/in_', '/out_')
        if not os.path.exists(outf):
            missing += 1
            continue
        try:
            in_acts = json.load(open(inf, encoding='utf-8'))
            out_acts = json.load(open(outf, encoding='utf-8'))
        except Exception as e:
            print(f'[FAIL] {os.path.basename(outf)}: bad JSON: {e}')
            continue
        # Match on (celex, seg_start) so two pieces of one act never collide.
        out_by = {}
        for a in out_acts:
            out_by.setdefault(a['celex'], []).append(a)
        for ia in in_acts:
            celex = ia['celex']
            start = ia.get('seg_start', 0)
            cands = out_by.get(celex, [])
            oa = None
            for c in cands:
                if c.get('seg_start', start if len(cands) == 1 else None) == start:
                    oa = c
                    break
            if oa is None and len(cands) == 1 and len(in_acts) == len(out_acts):
                oa = cands[0]
            if oa is None:
                print(f'[SKIP] {celex} @{start}: no agent output')
                missing += 1
                continue
            pieces.setdefault(celex, []).append({
                'meta': ia,
                'seg_start': start,
                'src': ia['segments'],
                'tgt': oa.get('segments_ca', []),
            })

    rendered = failed = mismatch = residue_skipped = 0
    for celex, plist in sorted(pieces.items()):
        plist.sort(key=lambda x: x['seg_start'])
        total = plist[0]['meta'].get('total_segments', len(plist[0]['src']))

        # Contiguity: pieces must tile [0, total) exactly.
        src_all, tgt_all, cursor, broken = [], [], 0, False
        for pc in plist:
            if pc['seg_start'] != cursor or len(pc['src']) != len(pc['tgt']):
                broken = True
                break
            src_all += pc['src']
            tgt_all += pc['tgt']
            cursor += len(pc['src'])
        if broken or cursor != total:
            print(f'[SKIP] {celex}: incomplete/misaligned ({cursor}/{total} segments '
                  f'from {len(plist)} piece(s))')
            mismatch += 1
            continue

        leaks = foreign_leak(tgt_all, src_all)
        if leaks:
            print(f'[SKIP] {celex}: non-Catalan word forms {leaks[:4]}')
            residue_skipped += 1
            continue

        why = quality_fail(src_all, tgt_all)
        if why:
            print(f'[SKIP] {celex}: {why}')
            residue_skipped += 1
            continue

        flagged, hits = residue(tgt_all)
        if flagged / max(len(tgt_all), 1) > args.max_residue:
            print(f'[SKIP] {celex}: untranslated English in {flagged}/{len(tgt_all)} '
                  f'segments ({hits} hits) — above --max-residue {args.max_residue}')
            residue_skipped += 1
            continue

        lookup = dict(zip(src_all, tgt_all))

        def translate_text(s, _lk=lookup):
            return s if not s or not s.strip() else _apply_glossary(_lk.get(s, s))

        def translate_batch(texts, label, _lk=lookup):
            return [_apply_glossary(_lk.get(t, t)) if t and t.strip() else t for t in texts]

        meta = plist[0]['meta']
        try:
            html_path = meta['html_path']
            if not os.path.exists(html_path):      # /tmp may have been cleaned
                html_path = fetch_act(celex, meta.get('oj_id') or '')
            parsed = parse_act(html_path, celex)
            translated = _do_translate(parsed, translate_text, translate_batch)
            html = generate_html(translated, celex, meta.get('oj_id', ''))
        except Exception as e:
            print(f'[FAIL] {celex}: render error: {str(e)[:120]}')
            failed += 1
            continue

        out_dir = os.path.join(TRANSLATIONS_DIR, celex)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)

        # Same content gate as the daily driver: never register a page that
        # does not hold the act (11 Sep 2026).
        from pathlib import Path as _P
        from scripts.translate_oj_daily_acts import _page_has_act_text
        good, why = _page_has_act_text(_P(out_dir) / 'index.html')
        if not good:
            print(f'[SKIP] {celex}: content gate: {why}')
            failed += 1
            continue

        import_to_db(
            celex=celex, title_ca=translated.get('title', '') or celex,
            articles=len(parsed.get('articles', [])),
            recitals=len(parsed.get('recitals', [])),
            size=len(html.encode('utf-8')), engine=args.engine,
            file_type='main', oj_ref=meta.get('oj_id', ''), deployed=False,
        )
        rendered += 1

    print(f'[DONE] rendered={rendered} failed={failed} mismatch={mismatch} '
          f'missing_jobs={missing} residue_skipped={residue_skipped}')


def main():
    ap = argparse.ArgumentParser(description='OJ Cellar sub-agent Catalan harness')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('dump')
    d.add_argument('--limit', type=int, default=250)
    d.add_argument('--before', default=None, help='only acts with oj_date < this (YYYY-MM-DD)')
    d.add_argument('--max-chars', type=int, default=12000, help='char budget per agent job')
    d.add_argument('--max-acts', type=int, default=4)
    d.add_argument('--max-segs', type=int, default=60,
                   help='max segments handed to one agent in one piece')
    d.add_argument('--only', help='comma-separated CELEX list to dump (overrides ordering)')
    d.add_argument('--out', default='/tmp/oj_cat_jobs')
    d.set_defaults(func=cmd_dump)
    r = sub.add_parser('render')
    r.add_argument('--jobs', default='/tmp/oj_cat_jobs')
    r.add_argument('--max-residue', type=float, default=0.05,
                   help='max fraction of segments carrying untranslated English')
    r.add_argument('--engine', default=ENGINE,
                   help="engine label stored on the row, e.g. 'sonnet-subagent'")
    r.set_defaults(func=cmd_render)
    a = ap.parse_args()
    return a.func(a)


if __name__ == '__main__':
    sys.exit(main())
