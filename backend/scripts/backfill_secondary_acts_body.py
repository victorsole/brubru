"""
Backfill secondary_acts.text_body from Cellar PDFs.

The `secondary_acts` table holds 6,722 delegated + implementing acts; only
1 has body text (RegDel ingestion captured metadata only). For each row
that has a CELEX, fetch the Cellar PDF manifestation, extract text via
pypdf, write back. Resumable — skips rows with text_body > 500 chars.

Source: Cellar resource at
  https://publications.europa.eu/resource/celex/{CELEX}
Following the 303-redirect with Accept: application/pdf gets us the PDF.

Throttle: 0.6s between fetches (~100/min). Cellar is generous but we
respect it.

Run:
    python3.12 backend/scripts/backfill_secondary_acts_body.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_secondary_acts_body.py --apply
    python3.12 backend/scripts/backfill_secondary_acts_body.py --apply --limit 200
    python3.12 backend/scripts/backfill_secondary_acts_body.py --apply --act-type delegated
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path
from typing import Optional

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

# Cellar resource URL pattern — content negotiation via Accept header.
# Following redirects yields the PDF binary (or returns 404 if no PDF
# manifestation exists for that CELEX).
CELLAR_PDF_URL = "https://publications.europa.eu/resource/celex/{celex}"

# Throttle: 0.6s between requests = 100 req/min. Cellar tolerates this fine.
THROTTLE_S = 0.6

# Min char length we consider "real body" (matches the API contract default).
MIN_BODY_LEN = 500


def _get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _fetch_pdf_bytes(celex: str) -> Optional[bytes]:
    """Fetch the PDF binary for a CELEX from Cellar. Returns None if missing."""
    import urllib.request
    import urllib.error

    url = CELLAR_PDF_URL.format(celex=celex)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/pdf",
            "Accept-Language": "en",
            "User-Agent": "Brubru/1.0 (+https://brubru.beresol.eu)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ct = r.headers.get("Content-Type", "")
            if "pdf" not in ct.lower():
                return None
            return r.read()
    except urllib.error.HTTPError as e:
        return None
    except Exception:
        return None


def _extract_text(pdf_bytes: bytes) -> Optional[str]:
    """Extract text from PDF bytes via pypdf. Returns None on failure."""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                continue
        text = "\n\n".join(pages).strip()
        return text or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5, help="Default 5 (dry-run safety)")
    ap.add_argument("--act-type", choices=("delegated", "implementing", "all"), default="all")
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    args = ap.parse_args()

    db_url = _get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    where = "celex IS NOT NULL AND (text_body IS NULL OR LENGTH(text_body) < %s)"
    params: list = [MIN_BODY_LEN]
    if args.act_type != "all":
        where += " AND act_type = %s"
        params.append(args.act_type)
    sql = f"""
        SELECT id::text, act_type::text, reference, celex
        FROM secondary_acts
        WHERE {where}
        ORDER BY publication_date DESC NULLS LAST
        LIMIT %s
    """
    params.append(args.limit if args.limit else 100_000)
    cur.execute(sql, params)
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply}, throttle={args.throttle}s)")

    fetched = extracted = persisted = no_pdf = 0
    for i, (row_id, act_type, reference, celex) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        pdf_bytes = _fetch_pdf_bytes(celex)
        if pdf_bytes is None:
            no_pdf += 1
            if i % 50 == 0 or i <= 5:
                print(f"  [{i:4d}/{len(rows)}] {act_type[:4]} {reference:20} celex={celex}: no PDF", flush=True)
            continue
        fetched += 1
        text = _extract_text(pdf_bytes)
        if text is None or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4d}/{len(rows)}] {act_type[:4]} {reference:20} celex={celex}: pdf {len(pdf_bytes):,}b → text={len(text or '')} (skipped, too short)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE secondary_acts SET text_body = %s, last_updated = NOW() WHERE id = %s::uuid",
                    (text[:5_000_000], row_id),  # cap at 5MB just in case
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                print(f"  [{i:4d}] DB error on {reference}: {exc}", flush=True)
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4d}/{len(rows)}] {act_type[:4]} {reference:20} celex={celex}: pdf {len(pdf_bytes):,}b → text={len(text):,} chars{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print("=" * 70)
    print(f"[DONE] candidates={len(rows)}  pdf_fetched={fetched}  text_extracted={extracted}  written={persisted}  no_pdf={no_pdf}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
