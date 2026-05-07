"""
Backfill commission_documents.text_body for rows where ``celex`` is null
but ``reference`` looks like a CELEX (sector 5 PC/SC/JC patterns or
sector 3 acts).

Sample stored references: 32017R1129, 52026PC0066, 52026PC0069. These
are valid CELEX numbers. Try fetching Cellar PDF; if it returns one, use
the reference value as the canonical celex and write both ``celex`` and
``text_body``.

Run:
    python3.12 backend/scripts/backfill_commission_docs_via_reference.py
    python3.12 backend/scripts/backfill_commission_docs_via_reference.py --apply
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

CELLAR_URL = "https://publications.europa.eu/resource/celex/{celex}"
THROTTLE_S = 0.6
MIN_BODY_LEN = 500
# CELEX patterns we accept as drop-in: sectors 3 (binding) and 5 (proposals/SWD).
CELEX_RE = re.compile(r"^[35]\d{4}[A-Z]{1,2}\d{4}$")


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_pdf(celex: str) -> Optional[bytes]:
    req = urllib_request.Request(
        CELLAR_URL.format(celex=celex),
        headers={
            "Accept": "application/pdf",
            "Accept-Language": "en",
            "User-Agent": "Brubru/1.0",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as r:
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
    # Look at rows where celex is null but reference matches a CELEX pattern.
    cur.execute(
        "SELECT id::text, reference FROM commission_documents "
        "WHERE celex IS NULL AND reference ~ '^[35][0-9]{4}[A-Z]{1,2}[0-9]{4}$' "
        "AND (text_body IS NULL OR LENGTH(text_body) < %s) "
        "ORDER BY publication_date DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = no_pdf = 0
    for i, (rid, ref) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        if not CELEX_RE.match(ref):
            continue
        pdf = fetch_pdf(ref)
        if pdf is None:
            no_pdf += 1
            if i % 50 == 0 or i <= 5:
                print(f"  [{i:4}/{len(rows)}] {ref}: no PDF", flush=True)
            continue
        fetched += 1
        text = extract_pdf(pdf)
        if not text or len(text) < MIN_BODY_LEN:
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE commission_documents SET text_body = %s, celex = COALESCE(celex, %s), last_updated = NOW() WHERE id = %s::uuid",
                    (text[:5_000_000], ref, rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                print(f"  [{i:4}] DB error {ref}: {exc}", flush=True)
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4}/{len(rows)}] {ref}: pdf {len(pdf):,}b → text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} no_pdf={no_pdf}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
