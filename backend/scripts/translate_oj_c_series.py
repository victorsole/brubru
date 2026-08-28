#!/usr/bin/env python3.12
"""
Translate the day's Official Journal C-series items into Catalan (full text).

The L-series sibling of this driver (translate_oj_daily_acts.py) is keyed on
CELEX. C-series cannot be: oj_scraper.derive_celex() returns None for anything
that is not L by design, so all C rows have celex IS NULL and could never gain
a Catalan link -- even though C is the BULK of daily OJ volume (26 of 27 entries
on 26 Aug 2026). Since C is most of what a reader sees, "the whole OJ in
Catalan" is unreachable without it.

Every C entry does carry a stable oj_id ('C_202604005'), and EUR-Lex serves the
full text straight from it (OJ:C_202604005) with no CELEX needed. So this driver
keys on oj_id end to end: fetch -> Softcatala -> HTML at
data/legislacio-ue-catala/{oj_id}/ -> a catalan_translations row whose oj_id is
set and whose celex stays NULL (migration 223). api/oj.py then matches either
key and emits catalan_url, so a C card stops falling back to English EUR-Lex.

Cellar is not used: C items are not CELEX-addressable there. EUR-Lex sits behind
a WAF, so the fetch goes through WafBrowserFetcher (Playwright), which is the
same fallback the L driver already relies on.

Softcatala only -- no Anthropic, no paid APIs. Runs locally against prod DB.

Usage (from backend/):
    python3.12 scripts/translate_oj_c_series.py --limit 40      # newest first
    python3.12 scripts/translate_oj_c_series.py --date 2026-08-26
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

# Same-day C items can lag EUR-Lex's HTML build by a few hours; without a
# cooldown they sit at the head of every newest-first run and burn slots.
# One file per shard: parallel workers each rewrite this whole JSON, so a
# shared path would have them clobbering each other's cooldown records.
SHARD = int(os.environ.get("OJ_C_SHARD", "0"))
SHARDS = int(os.environ.get("OJ_C_SHARDS", "1"))
FAIL_STATE = (BACKEND / "logs" / "oj_c_series" /
              (f"failed_oj_ids_{SHARD}of{SHARDS}.json" if SHARDS > 1
               else "failed_oj_ids.json"))
FAIL_COOLDOWN_H = 3

# A C item whose rendered text is shorter than this is a stub (WAF interstitial,
# "not yet available" placeholder, or a pure PDF pointer). Translating it would
# publish an empty Catalan page, which is worse than falling back to EUR-Lex.
MIN_TEXT_CHARS = 1200

# Same patterns as translate_oj_daily_acts.py: both drivers read the identical
# page template and the identical "N articles, M recitals" summary line.
_TITLE = re.compile(r"<title>(.*?)\s*\|\s*Brubru</title>", re.S)
_COUNTS = re.compile(r"(\d+)\s+articles?,\s+(\d+)\s+recitals?")


def _db():
    # Read .env directly (as translate_oj_daily_acts.py does): these drivers run
    # as plain scripts, so os.environ has no DATABASE_URL unless dotenv is loaded.
    url = [l.split("=", 1)[1].strip() for l in open(BACKEND / ".env")
           if l.startswith("DATABASE_URL=")][0]
    return psycopg2.connect(
        url, connect_timeout=15,
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)


def _load_failures() -> dict:
    try:
        return json.loads(FAIL_STATE.read_text())
    except Exception:
        return {}


def _record_failure(oj_id: str):
    fails = _load_failures()
    fails[oj_id] = time.time()
    FAIL_STATE.parent.mkdir(parents=True, exist_ok=True)
    FAIL_STATE.write_text(json.dumps(fails))


def _in_cooldown(oj_id: str, fails: dict) -> bool:
    ts = fails.get(oj_id)
    return bool(ts and (time.time() - ts) < FAIL_COOLDOWN_H * 3600)


def _pending(limit: int, date: str | None):
    conn = _db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        q = """
            SELECT DISTINCT ON (e.oj_id) e.oj_id, e.oj_date, e.title
              FROM oj_entries e
             WHERE e.series = 'C' AND e.oj_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM catalan_translations ct
                                WHERE ct.oj_id = e.oj_id)
        """
        # Disjoint slices so N workers never collide on the same item. hashtext
        # is deterministic per oj_id, so a worker always owns the same subset
        # even across restarts -- no coordination or work queue needed.
        if SHARDS > 1:
            q += f" AND abs(hashtext(e.oj_id)) %% {SHARDS} = {SHARD}"
        params: list = []
        if date:
            q += " AND e.oj_date = %s"
            params.append(date)
        q += " ORDER BY e.oj_id, e.oj_date DESC"
        cur.execute(q, params)
        rows = sorted(cur.fetchall(), key=lambda r: r["oj_date"], reverse=True)
        return rows[:limit]
    finally:
        conn.close()


def _fetch_html(oj_id: str) -> str | None:
    """EUR-Lex full text for an OJ C id, through the WAF browser fetcher."""
    sys.path.insert(0, str(BACKEND))
    from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
    url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:{oj_id}"
    # Two attempts, as in translate_oj_daily_acts._eurlex_fallback: under CPU
    # contention the WAF returns a short challenge page rather than the item,
    # which is transient. Retrying cost nothing and lifted the L-series success
    # rate from 67% to 87% on 26 Aug, so do not fetch only once here either.
    text = ""
    for attempt in (1, 2):
        with WafBrowserFetcher() as f:
            r = f.fetch(url)
        html = r.html or ""
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        if len(text) >= MIN_TEXT_CHARS:
            return html
        print(f"  [WARN] fetch attempt {attempt}: {len(text)} chars "
              f"(WAF challenge, stub or PDF-only item)", flush=True)
        if attempt == 1:
            time.sleep(20)
    print(f"  [SKIP] stub/placeholder ({len(text)} chars of text)", flush=True)
    return None


def _register(oj_id: str, html_path: Path, articles: int, recitals: int):
    """Create the catalan_translations row keyed on oj_id (celex stays NULL).

    Mirrors translate_oj_daily_acts._register, including its psycopg2-not-ORM
    choice: SQLAlchemy SessionLocal hangs when the Supabase pooler drops the
    connection during the long CPU translation phase."""
    from batch_catalan_translate import classify_act, detect_doc_type, detect_subcategory
    html = html_path.read_text(encoding="utf-8")
    m = _TITLE.search(html)
    title_ca = (m.group(1).strip() if m else oj_id)[:2000]
    cat_ca, cat_en = classify_act(title_ca)
    doc_type = detect_doc_type(title_ca)
    subcategory = detect_subcategory(title_ca)
    size = len(html.encode("utf-8"))
    url = f"https://brubru.beresol.eu/legislacio-ue-catala/{oj_id}/"
    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM catalan_translations WHERE oj_id = %s", (oj_id,))
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
                    (oj_id, title_en, title_ca, short_name, doc_type, category,
                     category_en, subcategory, file_type, articles_count,
                     recitals_count, html_size_bytes, engine, source_format,
                     siteground_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'main',%s,%s,%s,'softcatala','eurlex_html',%s)
            """, (oj_id, title_ca, title_ca, oj_id, doc_type, cat_ca, cat_en,
                  subcategory, articles, recitals, size, url))
        conn.commit()
    finally:
        conn.close()


def run(limit: int, date: str | None):
    fails = _load_failures()
    rows = _pending(limit + len(fails), date)
    skipped = [r for r in rows if _in_cooldown(r["oj_id"], fails)]
    rows = [r for r in rows if not _in_cooldown(r["oj_id"], fails)][:limit]
    if skipped:
        print(f"[INFO] {len(skipped)} in fetch-fail cooldown, retried after {FAIL_COOLDOWN_H}h", flush=True)
    print(f"[INFO] {len(rows)} pending OJ C-series items", flush=True)
    ok = failed = 0
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        oj_id = r["oj_id"]
        print(f"\n[{i}/{len(rows)}] {oj_id} ({r['oj_date']}) {r['title'][:70]}", flush=True)
        html_path = OUT_ROOT / oj_id / "index.html"
        articles = recitals = 0
        if not html_path.exists():
            try:
                html = _fetch_html(oj_id)
            except Exception as e:
                print(f"  [SKIP] fetch failed: {type(e).__name__}: {str(e)[:80]}", flush=True)
                _record_failure(oj_id); failed += 1; continue
            if html is None:
                _record_failure(oj_id); failed += 1; continue
            tmp = f"/tmp/{oj_id}_eurlex.html"
            Path(tmp).write_text(html, encoding="utf-8")
            p = subprocess.run(
                [sys.executable, "scripts/catalan_translate.py", "--html", tmp, "--celex", oj_id],
                cwd=BACKEND, capture_output=True, text=True, timeout=3600)
            out = p.stdout + p.stderr
            if p.returncode != 0 or not html_path.exists():
                reason = [l for l in out.splitlines() if "ERROR" in l or "raise" in l][-1:] \
                         or ["translate produced no page"]
                print(f"  [SKIP] translate failed: {reason[0][:100]}", flush=True)
                _record_failure(oj_id); failed += 1; continue
            mc = _COUNTS.search(out)
            if mc:
                articles, recitals = int(mc.group(1)), int(mc.group(2))
        else:
            print("  [INFO] HTML already present, registering only", flush=True)
        try:
            _register(oj_id, html_path, articles, recitals)
            ok += 1
            print(f"  [OK] registered ({(time.time()-t0)/i:.0f}s/item avg)", flush=True)
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
