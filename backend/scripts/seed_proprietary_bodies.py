#!/usr/bin/env python3.12
"""
Seed proprietary_report_bodies (migration 087) from LOCAL rendered HTML.

The Railway backend cannot fetch brubru.beresol.eu (datacenter IP blocked) and
frontend/public is not in its build context, so the canon/deep-dive + Catalan
bodies are cached in the DB and served from there. This script runs LOCALLY
(where the HTML files exist) and writes to whatever DATABASE_URL points at
(prod Supabase). Re-runnable (upsert).

    python3.12 -m scripts.seed_proprietary_bodies --source canon
    python3.12 -m scripts.seed_proprietary_bodies --source catalan
    python3.12 -m scripts.seed_proprietary_bodies --source all

Sources:
- canon   : frontend/public/eucanon/<slug>/ + deep-dive dirs, per the manifest
            knowledge_base/canon_reports.json (all published languages).
- catalan : data/legislacio-ue-catala/<celex>/index.html for every binding-law
            CELEX in catalan_translations (lang='ca').
"""

from __future__ import annotations

import argparse
import html as _html
import json
import logging
import re
import sys
from pathlib import Path

# Silence SQLAlchemy's statement echo — it would dump every multi-KB body.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

ROOT = _BACKEND.parent
PUBLIC = ROOT / "frontend" / "public"
MANIFEST = _BACKEND / "knowledge_base" / "canon_reports.json"
CATALAN_DIR = ROOT / "data" / "legislacio-ue-catala"
LANG_FILES = {"en": "index.html", "es": "es.html", "ca": "ca.html", "fr": "fr.html", "it": "it.html", "nl": "nl.html"}
BINDING_CELEX_RE = re.compile(r"^3[0-9]{4}[RLD][0-9]{4}$")

from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

_UPSERT = text("""
    INSERT INTO public.proprietary_report_bodies (source, ref, lang, body_html, body_txt, char_count, fetched_at)
    VALUES (:source, :ref, :lang, :body_html, :body_txt, :char_count, NOW())
    ON CONFLICT (source, ref, lang) DO UPDATE
       SET body_html = EXCLUDED.body_html,
           body_txt = EXCLUDED.body_txt,
           char_count = EXCLUDED.char_count,
           fetched_at = NOW()
""")


def strip_html(html: str) -> str:
    text_ = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text_ = re.sub(r"<[^>]+>", " ", text_)
    text_ = _html.unescape(text_)  # &aacute; / &middot; / &nbsp; -> á / · / space
    text_ = re.sub(r"\s+", " ", text_)
    return text_.strip()


def _rows_canon():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for r in payload.get("reports", []):
        slug = r["slug"]
        base = PUBLIC / ("eucanon" if r["report_type"] == "canon" else "") / slug
        for lang in r.get("languages", []):
            f = base / LANG_FILES[lang]
            if not f.is_file():
                continue
            html = f.read_text(encoding="utf-8", errors="replace")
            yield {"source": "canon", "ref": slug, "lang": lang, "html": html}


def _rows_catalan():
    db = SessionLocal()
    try:
        celexes = [
            row[0] for row in db.execute(text(
                "SELECT celex FROM public.catalan_translations WHERE file_type='main' ORDER BY celex"
            )).fetchall()
            if BINDING_CELEX_RE.match(row[0] or "")
        ]
    finally:
        db.close()
    for celex in celexes:
        f = CATALAN_DIR / celex / "index.html"
        if not f.is_file():
            continue
        html = f.read_text(encoding="utf-8", errors="replace")
        yield {"source": "catalan", "ref": celex, "lang": "ca", "html": html}


def seed(source: str, batch: int = 100) -> None:
    # core.database creates the engine with echo=True, which logs the FULL SQL
    # + params on every statement — for a 200-row executemany of ~28 KB bodies
    # that's megabytes of log per batch and effectively stalls the run. Disable
    # INFO globally (blunt but correct for a one-shot CLI seed).
    logging.disable(logging.INFO)
    gens = []
    if source in ("canon", "all"):
        gens.append(("canon", _rows_canon()))
    if source in ("catalan", "all"):
        gens.append(("catalan", _rows_catalan()))

    for label, gen in gens:
        db = SessionLocal()
        n = skipped = 0
        pending = []
        try:
            for row in gen:
                html = row.pop("html")
                txt = strip_html(html)
                if not txt:
                    skipped += 1
                    continue
                pending.append({**row, "body_html": html, "body_txt": txt, "char_count": len(txt)})
                if len(pending) >= batch:
                    db.execute(_UPSERT, pending)
                    db.commit()
                    n += len(pending)
                    pending = []
                    print(f"  [{label}] {n} rows...", flush=True)
            if pending:
                db.execute(_UPSERT, pending)
                db.commit()
                n += len(pending)
            print(f"[OK] {label}: {n} bodies upserted ({skipped} skipped: no file/empty)")
        finally:
            db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["canon", "catalan", "all"], default="all")
    ap.add_argument("--batch", type=int, default=100)
    args = ap.parse_args()
    seed(args.source, batch=args.batch)
