"""
Backfill commission_documents.text_body from Cellar PDFs.

Companion to backfill_secondary_acts_body.py — same Cellar resource URL
pattern, same pypdf extraction. 433 rows currently missing body text.

Run:
    python3.12 backend/scripts/backfill_commission_docs_body.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_commission_docs_body.py --apply
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

CELLAR_PDF_URL = "https://publications.europa.eu/resource/celex/{celex}"
THROTTLE_S = 0.6
MIN_BODY_LEN = 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_pdf(celex: str) -> Optional[bytes]:
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        CELLAR_PDF_URL.format(celex=celex),
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
        "SELECT id::text, reference, celex FROM commission_documents "
        "WHERE celex IS NOT NULL AND (text_body IS NULL OR LENGTH(text_body) < %s) "
        "ORDER BY publication_date DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = no_pdf = 0
    for i, (rid, reference, celex) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        pdf = fetch_pdf(celex)
        if pdf is None:
            no_pdf += 1
            if i % 50 == 0 or i <= 5:
                print(f"  [{i:4}/{len(rows)}] {reference} celex={celex}: no PDF", flush=True)
            continue
        fetched += 1
        text = extract_pdf(pdf)
        if not text or len(text) < MIN_BODY_LEN:
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE commission_documents SET text_body = %s, last_updated = NOW() WHERE id = %s::uuid",
                    (text[:5_000_000], rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                print(f"  [{i:4}] DB error {reference}: {exc}", flush=True)
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4}/{len(rows)}] {reference} celex={celex}: pdf {len(pdf):,}b → text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} no_pdf={no_pdf}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
