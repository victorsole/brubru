#!/usr/bin/env python3.12
"""
Translate the day's Official Journal L-series acts into Catalan (full text).

The My OJ marriage of the two Catalan pipelines: the acquis corpus at
/legislacio-ue-catala/ is frozen at the LEG_2025-11 dump, while the daily OJ is
always ahead of it. This driver keeps the corpus current: for every L-series
``oj_entries`` row whose CELEX has no ``catalan_translations`` record yet, it
runs the existing ``catalan_translate.py --cellar`` path (Cellar XHTML fetch ->
Softcatala -> HTML at data/legislacio-ue-catala/{celex}/), registers the DB row,
and leaves deployment to ``deploy_catalan_backlog.py`` (the same loop that
deploys law batches).

My OJ then links each act card to the full Catalan text (api/oj.py adds
``catalan_url`` when the CELEX is deployed).

Softcatala only — no Anthropic, no paid APIs. Runs locally against prod DB.

Usage (from backend/):
    python3.12 scripts/translate_oj_daily_acts.py --limit 30    # newest first
    python3.12 scripts/translate_oj_daily_acts.py --date 2026-07-22
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parent))

BACKEND = Path(__file__).resolve().parent.parent
OUT_ROOT = BACKEND.parent / "data" / "legislacio-ue-catala"

_TITLE = re.compile(r"<title>(.*?)\s*\|\s*Brubru</title>", re.S)
_COUNTS = re.compile(r"(\d+)\s+articles?,\s+(\d+)\s+recitals?")


def _db():
    url = [l.split("=", 1)[1].strip() for l in open(BACKEND / ".env")
           if l.startswith("DATABASE_URL=")][0]
    return psycopg2.connect(url, connect_timeout=15)


def _pending(limit: int, date: str | None):
    """L-series OJ acts with a CELEX and no catalan_translations row, newest first."""
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        q = """
            SELECT DISTINCT ON (e.celex) e.celex, e.oj_date, e.title
              FROM oj_entries e
             WHERE e.series = 'L' AND e.celex IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM catalan_translations ct
                                WHERE ct.celex = e.celex)
        """
        params: list = []
        if date:
            q += " AND e.oj_date = %s"
            params.append(date)
        q += " ORDER BY e.celex, e.oj_date DESC"
        cur.execute(q, params)
        rows = sorted(cur.fetchall(), key=lambda r: r["oj_date"], reverse=True)
        return rows[:limit]
    finally:
        conn.close()


def _register(celex: str, html_path: Path, articles: int, recitals: int):
    """Create the catalan_translations row (undeployed; the deploy loop ships it)."""
    from batch_catalan_translate import import_to_db
    html = html_path.read_text(encoding="utf-8")
    m = _TITLE.search(html)
    title_ca = (m.group(1).strip() if m else celex)[:2000]
    import_to_db(celex, title_ca, articles, recitals, len(html.encode("utf-8")),
                 "softcatala", file_type="main", deployed=False)


def run(limit: int, date: str | None):
    rows = _pending(limit, date)
    print(f"[INFO] {len(rows)} pending OJ L-series acts", flush=True)
    ok = failed = 0
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        celex = r["celex"]
        print(f"\n[{i}/{len(rows)}] {celex} ({r['oj_date']}) {r['title'][:70]}", flush=True)
        html_path = OUT_ROOT / celex / "index.html"
        articles = recitals = 0
        if not html_path.exists():
            # Cellar fetch + Softcatala translate via the canonical pipeline.
            p = subprocess.run(
                [sys.executable, "scripts/catalan_translate.py", "--cellar", celex],
                cwd=BACKEND, capture_output=True, text=True, timeout=3600)
            out = p.stdout + p.stderr
            if p.returncode != 0 or not html_path.exists():
                reason = [l for l in out.splitlines() if "ERROR" in l or "raise" in l][-1:] or ["?"]
                print(f"  [SKIP] translate failed: {reason[0][:100]}", flush=True)
                failed += 1
                continue
            mc = _COUNTS.search(out)
            if mc:
                articles, recitals = int(mc.group(1)), int(mc.group(2))
        else:
            print("  [INFO] HTML already present, registering only", flush=True)
        try:
            _register(celex, html_path, articles, recitals)
            ok += 1
            print(f"  [OK] registered ({(time.time()-t0)/i:.0f}s/act avg)", flush=True)
        except Exception as e:
            failed += 1
            print(f"  [SKIP] db register failed: {str(e)[:100]}", flush=True)
    print(f"\n[DONE] ok={ok} failed={failed} in {(time.time()-t0)/60:.1f}min "
          f"(deploy via scripts/deploy_catalan_backlog.py)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--date", type=str, default=None, help="only this OJ date (YYYY-MM-DD)")
    args = ap.parse_args()
    os.chdir(BACKEND)
    run(args.limit, args.date)


if __name__ == "__main__":
    sys.exit(main())
