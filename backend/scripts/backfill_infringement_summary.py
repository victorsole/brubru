"""
Backfill infringement_procedures.summary from the Commission presscorner
PDF API.

URL pattern (verified working):
  https://ec.europa.eu/commission/presscorner/api/files/document/print/en/{INF_REF}/{INF_REF}_EN.pdf

Returns the canonical Commission press-release PDF for the infringement
decision. We extract text via pypdf and write the full body to the
``summary`` column. Resumable.

Run:
    python3.12 backend/scripts/backfill_infringement_summary.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_infringement_summary.py --apply
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

PDF_URL_TPL = "https://ec.europa.eu/commission/presscorner/api/files/document/print/en/{ref}/{ref}_EN.pdf"
THROTTLE_S = 0.6
MIN_BODY_LEN = 200  # press releases are short; lower than the default 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_pdf(inf_ref: str) -> Optional[bytes]:
    url = PDF_URL_TPL.format(ref=inf_ref)
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "application/pdf",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as r:
            ct = r.headers.get("Content-Type", "").lower()
            if "pdf" not in ct:
                return None
            return r.read()
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None
    except Exception:
        return None


def extract_pdf(pdf_bytes: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages).strip() or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    conn = psycopg2.connect(db)
    cur = conn.cursor()
    cur.execute(
        "SELECT id::text, inf_reference FROM infringement_procedures "
        "WHERE inf_reference IS NOT NULL AND (summary IS NULL OR LENGTH(summary) < %s) "
        "ORDER BY decision_date DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = errors = 0
    for i, (rid, ref) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        pdf = fetch_pdf(ref)
        if pdf is None:
            errors += 1
            if i % 50 == 0 or i <= 5:
                print(f"  [{i:4}/{len(rows)}] {ref}: no PDF", flush=True)
            continue
        fetched += 1
        text = extract_pdf(pdf)
        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] {ref}: text too short ({len(text or '')}c)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE infringement_procedures SET summary = %s, last_updated = NOW() WHERE id = %s::uuid",
                    (text[:1_000_000], rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:4}] DB error {ref}: {exc}", flush=True)
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4}/{len(rows)}] {ref}: pdf {len(pdf):,}b → text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
