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

import os  # noqa: E402

from psycopg2.extras import execute_values  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


def _make_engine():
    """A DEDICATED engine for the seed — fresh, unpooled, no echo. Avoids the
    app's shared SessionLocal (echo=True + pooled), whose pooled connections
    can wedge during a long bulk load. Standalone engines proved reliable."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        from pathlib import Path as _P
        for line in (_P(__file__).resolve().parents[2] / ".env").read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
                break
    for a in ("postgres://", "postgresql://"):
        if url.startswith(a):
            url = "postgresql+psycopg2://" + url[len(a):]
            break
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    return create_engine(url, echo=False, poolclass=NullPool)


_ENGINE = _make_engine()

# Single round-trip per batch via execute_values. psycopg2 executemany sends one
# statement PER ROW (200 network round-trips/batch) which stalls on large bodies.
_UPSERT_SQL = """
    INSERT INTO public.proprietary_report_bodies (source, ref, lang, body_html, body_txt, char_count, fetched_at)
    VALUES %s
    ON CONFLICT (source, ref, lang) DO UPDATE
       SET body_html = EXCLUDED.body_html,
           body_txt = EXCLUDED.body_txt,
           char_count = EXCLUDED.char_count,
           fetched_at = NOW()
"""


def _flush(raw, pending: list[dict]) -> None:
    """Bulk-upsert a batch in ONE round-trip via psycopg2 execute_values."""
    with raw.cursor() as cur:
        execute_values(
            cur,
            _UPSERT_SQL,
            [(p["source"], p["ref"], p["lang"], p["body_html"], p["body_txt"], p["char_count"]) for p in pending],
            template="(%s, %s, %s, %s, %s, %s, NOW())",
            page_size=len(pending),
        )
    raw.commit()


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


SITE_CATALAN = "https://brubru.beresol.eu/legislacio-ue-catala/{celex}/index.html"


def _binding_celexes() -> list[str]:
    with _ENGINE.connect() as c:
        return [
            row[0] for row in c.execute(text(
                "SELECT celex FROM public.catalan_translations WHERE file_type='main' ORDER BY celex"
            )).fetchall()
            if BINDING_CELEX_RE.match(row[0] or "")
        ]


def _fetch_one_catalan(celex: str):
    """Fetch one Catalan body from SiteGround. Runs on the dev machine (whose
    residential IP is NOT blocked, unlike Railway), so it sidesteps both the
    datacenter block and the iCloud-evicted local files."""
    import urllib.error
    import urllib.request
    url = SITE_CATALAN.format(celex=celex)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BrubruSeed/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                content = resp.read()
                if len(content) > 300:
                    return celex, content.decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        pass
    return celex, None


def _rows_catalan():
    """Yield Catalan bodies fetched concurrently from SiteGround."""
    from concurrent.futures import ThreadPoolExecutor

    celexes = _binding_celexes()
    print(f"  [catalan] fetching {len(celexes)} bodies from SiteGround...", flush=True)
    done = failed = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for celex, html in ex.map(_fetch_one_catalan, celexes):
            done += 1
            if done % 1000 == 0:
                print(f"  [catalan] fetched {done}/{len(celexes)} ({failed} failed)...", flush=True)
            if html is None:
                failed += 1
                continue
            yield {"source": "catalan", "ref": celex, "lang": "ca", "html": html}
    if failed:
        print(f"  [catalan] WARNING: {failed} bodies failed to fetch", flush=True)


def _seed_via_copy(gen, label: str) -> None:
    """Bulk-load a source via COPY FROM STDIN — one streaming op, no per-row
    round-trips and no giant parameterized statements (the Supabase pooler
    stalls on those for the 236 MB Catalan corpus). The table is a cache we own,
    so we DELETE this source's rows and COPY a fresh set in one transaction.
    """
    import csv
    import tempfile

    n = skipped = 0
    with tempfile.TemporaryFile("w+", newline="", encoding="utf-8") as tf:
        # Phase 1: drain the generator into a CSV. The gen opens (and closes) its
        # OWN DB connection for the celex SELECT — so we do NOT hold a second
        # connection open here (the session pooler blocks if we do).
        w = csv.writer(tf)
        for row in gen:
            html = row.pop("html")
            txt = strip_html(html)
            if not txt:
                skipped += 1
                continue
            html = html.replace("\x00", "")  # Postgres TEXT can't hold NUL
            txt = txt.replace("\x00", "")
            w.writerow([row["source"], row["ref"], row["lang"], html, txt, len(txt)])
            n += 1
            if n % 1000 == 0:
                print(f"  [{label}] staged {n}...", flush=True)
        tf.flush()
        tf.seek(0)
        print(f"  [{label}] staged {n} rows; COPYing...", flush=True)

        # Phase 2: one fresh raw connection for DELETE + COPY.
        raw = _ENGINE.raw_connection()
        try:
            with raw.cursor() as cur:
                cur.execute("SET statement_timeout = 0")  # 236 MB COPY exceeds the default
                cur.execute("DELETE FROM public.proprietary_report_bodies WHERE source = %s", (label,))
                cur.copy_expert(
                    "COPY public.proprietary_report_bodies "
                    "(source, ref, lang, body_html, body_txt, char_count) "
                    "FROM STDIN WITH (FORMAT csv)",
                    tf,
                )
            raw.commit()
            print(f"[OK] {label}: {n} bodies COPYed ({skipped} skipped: no file/empty)")
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()


def _seed_via_values(gen, label: str, batch: int) -> None:
    """Batched execute_values upsert — fine for the small canon set."""
    raw = _ENGINE.raw_connection()
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
                _flush(raw, pending)
                n += len(pending)
                pending = []
        if pending:
            _flush(raw, pending)
            n += len(pending)
        print(f"[OK] {label}: {n} bodies upserted ({skipped} skipped: no file/empty)")
    finally:
        raw.close()


def seed(source: str, batch: int = 100) -> None:
    logging.disable(logging.INFO)
    if source in ("canon", "all"):
        _seed_via_values(_rows_canon(), "canon", batch)
    if source in ("catalan", "all"):
        _seed_via_copy(_rows_catalan(), "catalan")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["canon", "catalan", "all"], default="all")
    ap.add_argument("--batch", type=int, default=100)
    args = ap.parse_args()
    seed(args.source, batch=args.batch)
