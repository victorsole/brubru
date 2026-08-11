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
import json
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

# Fresh acts 404 on Cellar for a few days after OJ publication; without a
# cooldown they sit at the head of every newest-first run and burn slots.
FAIL_STATE = BACKEND / "logs" / "oj_acts" / "failed_celexes.json"
# Same-day acts have titles but no full-text manifestation yet (Cellar/EUR-Lex
# return 404/202 for a few hours after publication). Retry every ~3h so the
# corpus link appears the moment the Publications Office finishes building it.
FAIL_COOLDOWN_H = 3


def _load_failures() -> dict:
    try:
        return json.loads(FAIL_STATE.read_text())
    except Exception:
        return {}


def _record_failure(celex: str):
    fails = _load_failures()
    fails[celex] = time.time()
    FAIL_STATE.parent.mkdir(parents=True, exist_ok=True)
    FAIL_STATE.write_text(json.dumps(fails))


def _in_cooldown(celex: str, fails: dict) -> bool:
    ts = fails.get(celex)
    return bool(ts) and (time.time() - ts) < FAIL_COOLDOWN_H * 3600

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
               -- EEA Joint Committee decisions carry scraper-derived CELEXes in
               -- the wrong sector (32026R... instead of 22026D...) and 404
               -- everywhere; their cards keep the (working) OJ-id EUR-Lex link.
               AND e.title NOT ILIKE '%%EEA Joint Committee%%'
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
    """Create the catalan_translations row (undeployed; the deploy loop ships it).

    Uses the driver's own psycopg2 connection (connect_timeout + keepalives) —
    batch_catalan_translate.import_to_db goes through SQLAlchemy SessionLocal,
    which hangs indefinitely when the Supabase pooler drops the connection
    during the long CPU translation phase (incident 23 Jul 2026: driver froze
    25 min on a completed act)."""
    from batch_catalan_translate import classify_act, detect_doc_type, detect_subcategory
    html = html_path.read_text(encoding="utf-8")
    m = _TITLE.search(html)
    title_ca = (m.group(1).strip() if m else celex)[:2000]
    cat_ca, cat_en = classify_act(title_ca)
    doc_type = detect_doc_type(title_ca)
    subcategory = detect_subcategory(title_ca)
    size = len(html.encode("utf-8"))
    url = f"https://brubru.beresol.eu/legislacio-ue-catala/{celex}/"
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM catalan_translations WHERE celex = %s", (celex,))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE catalan_translations
                   SET title_ca=%s, articles_count=%s, recitals_count=%s,
                       html_size_bytes=%s, category=%s, category_en=%s,
                       subcategory=COALESCE(%s, subcategory), updated_at=now()
                 WHERE id=%s
            """, (title_ca, articles, recitals, size, cat_ca, cat_en, subcategory, row[0]))
        else:
            cur.execute("""
                INSERT INTO catalan_translations
                    (celex, title_en, title_ca, short_name, doc_type, category,
                     category_en, subcategory, file_type, articles_count,
                     recitals_count, html_size_bytes, engine, source_format,
                     siteground_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'main',%s,%s,%s,'softcatala','formex',%s)
            """, (celex, title_ca, title_ca, celex, doc_type, cat_ca, cat_en,
                  subcategory, articles, recitals, size, url))
        conn.commit()
    finally:
        conn.close()


def _eurlex_fallback(celex: str) -> str | None:
    """Fetch the act's HTML from EUR-Lex (WAF browser bypass) and translate it.
    Returns the translate subprocess output on success, None on failure."""
    try:
        sys.path.insert(0, str(BACKEND))
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}"
        print("  [INFO] Cellar miss; trying EUR-Lex HTML via WAF fetcher", flush=True)
        with WafBrowserFetcher() as f:
            r = f.fetch(url)
        html = (r.html or "")
        if "Article" not in html or len(html) < 5000:
            return None
        tmp = f"/tmp/{celex}_eurlex.html"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(html)
        p = subprocess.run(
            [sys.executable, "scripts/catalan_translate.py", "--html", tmp, "--celex", celex],
            cwd=BACKEND, capture_output=True, text=True, timeout=3600)
        return (p.stdout + p.stderr) if p.returncode == 0 else None
    except Exception as e:
        print(f"  [WARN] EUR-Lex fallback error: {str(e)[:80]}", flush=True)
        return None


def run(limit: int, date: str | None):
    fails = _load_failures()
    rows = _pending(limit + len(fails), date)
    skipped = [r for r in rows if _in_cooldown(r["celex"], fails)]
    rows = [r for r in rows if not _in_cooldown(r["celex"], fails)][:limit]
    if skipped:
        print(f"[INFO] {len(skipped)} in Cellar-404 cooldown, retried after {FAIL_COOLDOWN_H}h", flush=True)
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
                # Fresh acts 404 on Cellar for days; EUR-Lex HTML via the WAF
                # browser fetcher is available from day one.
                out = _eurlex_fallback(celex)
                if out is None or not html_path.exists():
                    reason = [l for l in (out or "").splitlines()
                              if "ERROR" in l or "raise" in l][-1:] or ["Cellar + EUR-Lex both failed"]
                    print(f"  [SKIP] translate failed: {reason[0][:100]}", flush=True)
                    _record_failure(celex)
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
