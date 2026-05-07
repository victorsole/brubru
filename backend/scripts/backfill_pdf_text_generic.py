"""
Generic PDF-URL → text-body backfill for tables that already have pdf_url
populated but no extracted body. Reuses pypdf for extraction.

Supported tables (each declares its url-column → body-column mapping):
  rsb_opinions        pdf_url       → full_text
  eprs_publications   pdf_url       → full_text
  ep_resolutions      text_url      → summary
  committee_minutes   pdf_url       → full_text   (if any new arrive)

Run:
    python3.12 backend/scripts/backfill_pdf_text_generic.py --table rsb_opinions             # dry-run, 5 rows
    python3.12 backend/scripts/backfill_pdf_text_generic.py --table eprs_publications --apply
    python3.12 backend/scripts/backfill_pdf_text_generic.py --table ep_resolutions --apply --limit 30
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

THROTTLE_S = 0.5
MIN_BODY_LEN = 500

# table → (id_col, url_col, body_col, ts_col)
TABLE_CFG = {
    "rsb_opinions": ("id", "pdf_url", "full_text", "last_updated"),
    "eprs_publications": ("id", "pdf_url", "full_text", "updated_at"),
    "ep_resolutions": ("id", "text_url", "summary", "updated_at"),
    "committee_minutes": ("id", "pdf_url", "full_text", "last_updated"),
}


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_bytes(url: str, timeout: int = 30) -> Tuple[Optional[bytes], Optional[str]]:
    """Fetch URL with browser UA. Returns (bytes, content_type) or (None, err)."""
    if not url:
        return None, "no url"
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "*/*",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "").lower()
            return data, ct
    except urllib_error.HTTPError as e:
        return None, f"HTTP {e.code} {e.reason}"
    except urllib_error.URLError as e:
        return None, f"URL error: {e.reason}"
    except Exception as e:
        return None, f"unexpected: {e}"


def extract_pdf(pdf_bytes: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
        return text or None
    except Exception:
        return None


def extract_html(html_bytes: bytes) -> Optional[str]:
    """Strip HTML to plain text — boilerplate-aware (drop nav/footer/scripts)."""
    try:
        text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None
    # Remove scripts/styles/nav/footer
    text = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ",
                  text, flags=re.DOTALL | re.IGNORECASE)
    # Block-level → newline
    text = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text).strip()
    return text or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, choices=list(TABLE_CFG.keys()))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    args = ap.parse_args()

    id_col, url_col, body_col, ts_col = TABLE_CFG[args.table]

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db)
    cur = conn.cursor()
    sql = f"""
        SELECT {id_col}::text, {url_col}
        FROM {args.table}
        WHERE {url_col} IS NOT NULL
          AND ({body_col} IS NULL OR LENGTH({body_col}) < %s)
        ORDER BY {id_col}
        LIMIT %s
    """
    cur.execute(sql, (MIN_BODY_LEN, args.limit if args.limit else 100_000))
    rows = cur.fetchall()
    print(f"[INFO] {args.table}: {len(rows)} candidate rows (apply={args.apply}, throttle={args.throttle}s)")

    fetched = extracted = persisted = errors = 0
    for i, (rid, url) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        data, ct = fetch_bytes(url)
        if data is None:
            errors += 1
            if i <= 5 or i % 50 == 0:
                print(f"  [{i:4}/{len(rows)}] {rid[:8]}: fetch failed ({ct})", flush=True)
            continue
        fetched += 1
        # Choose extractor by content type
        if "pdf" in (ct or "") or url.lower().endswith(".pdf"):
            text = extract_pdf(data)
        elif "html" in (ct or ""):
            text = extract_html(data)
        else:
            # Try PDF first, fall back to HTML
            text = extract_pdf(data) or extract_html(data)

        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] {rid[:8]}: text {len(text or '')}c (too short)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                upd_sql = (
                    f"UPDATE {args.table} SET {body_col} = %s, {ts_col} = NOW() WHERE {id_col} = %s::uuid"
                    if id_col == "id" else
                    f"UPDATE {args.table} SET {body_col} = %s, {ts_col} = NOW() WHERE {id_col} = %s"
                )
                cur.execute(upd_sql, (text[:5_000_000], rid))
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:4}] DB error {rid}: {exc}", flush=True)
                continue
        if i <= 10 or i % 50 == 0:
            print(f"  [{i:4}/{len(rows)}] {rid[:12]}: pdf {len(data):,}b → text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] {args.table}: candidates={len(rows)}  fetched={fetched}  extracted={extracted}  written={persisted}  errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
