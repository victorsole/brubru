"""

KNOWN LIMITATION — AWS CloudFront WAF challenge:
  doceo.europarl.europa.eu is fronted by CloudFront with `x-amzn-waf-action:
  challenge`. Anonymous server-side GET returns HTTP 202 with the JS challenge
  page (~2KB) instead of the DOCX. Real browsers / Postman solve the challenge
  silently and get the file; urllib + httpx (even with HTTP/2 + Chrome TLS)
  can't bypass it.
  
  Workaround paths if we need DOCX text:
    1. Playwright/Selenium one-shot backfill (heavy: browser binary in CI).
    2. Pre-warmed session cookies harvested by a periodic headless run.
    3. Mirror via xml-data.europarl.europa.eu when an XML manifestation exists.
  
  For now this script logs every attempt and stamps body_fetched_at so the
  /opinions endpoint composes a metadata-only body from the structured row
  (title + committee + rapporteur + procedure + PE-ref + date + amendments).

backfill_amendment_documents_body — fetch the doceo .docx manifestation for
each amendment_documents row and extract text + a lightly-formatted HTML body.

doceo returns HTTP 202 (Accepted) while the manifestation is being generated;
this script retries with exponential backoff up to 5 attempts.

Run modes:
  python3.12 backend/scripts/backfill_amendment_documents_body.py --limit 5 --dry-run
  python3.12 backend/scripts/backfill_amendment_documents_body.py --limit 50
  python3.12 backend/scripts/backfill_amendment_documents_body.py --document-type AD
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import urllib.request
import urllib.error
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-ad-body")

UA = "Mozilla/5.0 (compatible; Brubru/1.0)"


def fetch_docx(url: str) -> Optional[bytes]:
    """GET with retry-on-202. doceo serves .docx on-demand; first hit is often
    a 202 while the manifestation is rendered server-side."""
    backoff = 1.5
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=45) as r:
                if r.status == 202:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                if r.status != 200:
                    log.warning("[%s] HTTP %s", url, r.status)
                    return None
                data = r.read()
                if not data or data[:2] != b"PK":  # ZIP / DOCX magic
                    if attempt < 5:
                        time.sleep(backoff); backoff *= 2
                        continue
                    log.warning("[%s] not a DOCX (no PK magic)", url)
                    return None
                return data
        except urllib.error.HTTPError as e:
            if e.code == 202 and attempt < 5:
                time.sleep(backoff); backoff *= 2
                continue
            log.warning("[%s] HTTP %s", url, e.code)
            return None
        except Exception as e:
            log.warning("[%s] fetch err: %s", url, e)
            return None
    return None


def docx_to_text_and_html(data: bytes) -> tuple:
    """Extract plain text + minimal HTML from a .docx blob via python-docx."""
    import html as _html
    from docx import Document
    doc = Document(io.BytesIO(data))
    text_lines: list = []
    html_parts: list = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if not t:
            continue
        text_lines.append(t)
        style = (p.style.name if p.style else "") or ""
        if style.startswith("Heading 1"):
            html_parts.append(f"<h1>{_html.escape(t)}</h1>")
        elif style.startswith("Heading 2"):
            html_parts.append(f"<h2>{_html.escape(t)}</h2>")
        elif style.startswith("Heading"):
            html_parts.append(f"<h3>{_html.escape(t)}</h3>")
        else:
            html_parts.append(f"<p>{_html.escape(t)}</p>")
    text_body = "\n\n".join(text_lines) if text_lines else None
    body_html = "<article>" + "".join(html_parts) + "</article>" if html_parts else None
    return text_body, body_html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--document-type", default=None,
                    help="AD | PA | PR | AM | RD — restrict to one type. Default: all that lack body.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    eng = create_engine(os.environ["DATABASE_URL"])
    where = ["doceo_url IS NOT NULL", "(text_body IS NULL OR body_fetched_at IS NULL)"]
    params = {"lim": args.limit}
    if args.document_type:
        where.append("document_type = :dt")
        params["dt"] = args.document_type.upper()
    sql = (f"SELECT id, doceo_url, document_type, procedure_reference FROM amendment_documents "
           f"WHERE {' AND '.join(where)} ORDER BY scraped_at DESC LIMIT :lim")
    with eng.connect() as c:
        rows = c.execute(text(sql), params).fetchall()
    if not rows:
        log.info("Nothing to backfill.")
        return
    log.info("Fetching %d rows", len(rows))
    written = 0
    now = datetime.utcnow()
    for rid, url, dtype, pref in rows:
        data = fetch_docx(url)
        if not data:
            log.warning("  %s %s — no data", dtype, pref)
            if not args.dry_run:
                with eng.begin() as c:
                    c.execute(text("UPDATE amendment_documents SET body_fetched_at=:n WHERE id=:i"),
                              {"n": now, "i": rid})
            continue
        try:
            txt, html = docx_to_text_and_html(data)
        except Exception as e:
            log.warning("  %s %s — parse err: %s", dtype, pref, e)
            continue
        log.info("  %s %s — %d chars text, %d chars html", dtype, pref, len(txt or ""), len(html or ""))
        if args.dry_run:
            continue
        with eng.begin() as c:
            c.execute(text("""
                UPDATE amendment_documents
                SET text_body=:t, body_html=:h, body_fetched_at=:n
                WHERE id=:i
            """), {"t": txt, "h": html, "n": now, "i": rid})
        written += 1
    log.info("[DONE] wrote %d rows.", written)


if __name__ == "__main__":
    main()
