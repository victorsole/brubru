"""
Backfill text_answer for parliamentary_questions.

Sister script to backfill_parl_question_text.py — that one fills the
question side; this one fills the answer side. The original script's
fetch_answer_docx_url() is a stub that returns None, so 5,674 rows have
text_question but no text_answer.

EP Open Data path:
  GET /api/v2/parliamentary-questions/{ep_id}?format=application/ld+json
  → data[0].inverse_answers_to[0]
                .is_realized_by[0]
                .is_embodied_by[]
                # find one with format = ".../authority/file-type/DOCX"
                .is_exemplified_by  # relative path, prefix with EP_BASE

Pipeline per row:
  1. Convert question_reference (E-001234/2026) → EP id (E-10-2026-001234)
  2. Fetch JSON-LD; find the answer DOCX manifestation URL
  3. Download docx, extract text via zipfile + regex
  4. UPDATE text_answer + answer_url + answered_date + answering_commissioner

Resumable: skips rows where text_answer is already populated.

Run:
    python3.12 backend/scripts/backfill_parl_question_answers.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_parl_question_answers.py --apply
    python3.12 backend/scripts/backfill_parl_question_answers.py --apply --year 2026
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

EP_BASE = "https://data.europarl.europa.eu"
USER_AGENT = "Brubru/1.0 (+https://brubru.beresol.eu)"
THROTTLE_S = 0.5
MIN_BODY_LEN = 50  # answers can be quite short


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def question_ref_to_ep_id(ref: str) -> Optional[str]:
    """E-001234/2026 → E-10-2026-001234."""
    m = re.match(r"^([A-Z])-(\d{6})/(\d{4})$", ref)
    if not m:
        return None
    qtype, num, year = m.group(1), m.group(2), m.group(3)
    # Map year → parliamentary term (rough heuristic; correct for current term-10).
    term = "10" if int(year) >= 2024 else "9" if int(year) >= 2019 else "8"
    return f"{qtype}-{term}-{year}-{num}"


def fetch_json(url: str, timeout: int = 30) -> Optional[dict]:
    req = urllib_request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/ld+json"})
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            import json
            return json.load(r)
    except urllib_error.HTTPError as e:
        if e.code in (404, 410):
            return None
        return None
    except Exception:
        return None


def find_answer_docx_url(payload: dict) -> Optional[Dict[str, Any]]:
    """Walk the EP JSON-LD response for the answer DOCX manifestation.

    Returns dict with {url, document_date, creator, title} or None.
    """
    if not isinstance(payload, dict):
        return None
    items = payload.get("data") or []
    if not items:
        return None
    item = items[0]
    answers = item.get("inverse_answers_to") or []
    if not answers:
        return None
    answer = answers[0]
    # Walk the manifestation tree
    for expr in answer.get("is_realized_by") or []:
        for manif in expr.get("is_embodied_by") or []:
            fmt = manif.get("format") or ""
            # Prefer DOCX (parses cleanly via zipfile)
            if "DOCX" in fmt or "docx" in (manif.get("media_type") or ""):
                return {
                    "url": EP_BASE + "/" + manif.get("is_exemplified_by", "").lstrip("/"),
                    "document_date": answer.get("document_date"),
                    "creator": answer.get("creator", []),
                    "title": (answer.get("title_dcterms") or {}).get("en") or (answer.get("title", {}).get("en") if isinstance(answer.get("title"), dict) else None),
                }
    # Fall back to PDF if no DOCX
    for expr in answer.get("is_realized_by") or []:
        for manif in expr.get("is_embodied_by") or []:
            fmt = manif.get("format") or ""
            if "PDF" in fmt:
                return {
                    "url": EP_BASE + "/" + manif.get("is_exemplified_by", "").lstrip("/"),
                    "document_date": answer.get("document_date"),
                    "creator": answer.get("creator", []),
                    "title": (answer.get("title_dcterms") or {}).get("en"),
                    "is_pdf": True,
                }
    return None


def extract_docx_text(docx_bytes: bytes) -> Optional[str]:
    """Extract body text from a .docx. zipfile + regex on word/document.xml."""
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            with z.open("word/document.xml") as f:
                xml = f.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    # Strip XML tags, preserving paragraph breaks
    text = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", text)
    # Decode entities
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&apos;", "'").replace("&#39;", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
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
    ap.add_argument("--year", type=int)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = "(text_answer IS NULL OR LENGTH(text_answer) < 50) AND question_reference IS NOT NULL"
    if args.year:
        where += f" AND question_reference LIKE '%/{args.year}'"
    sql = f"""
        SELECT id, question_reference
        FROM parliamentary_questions
        WHERE {where}
        ORDER BY question_reference DESC
    """
    if args.limit:
        sql += f" LIMIT {args.limit}"
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply}, throttle={args.throttle}s)")

    no_payload = no_answer_link = ok = errors = 0
    for i, row in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        qref = row["question_reference"]
        ep_id = question_ref_to_ep_id(qref)
        if not ep_id:
            errors += 1
            continue
        payload = fetch_json(
            f"{EP_BASE}/api/v2/parliamentary-questions/{ep_id}?format=application%2Fld%2Bjson&language=en"
        )
        if not payload:
            no_payload += 1
            if i <= 5 or i % 100 == 0:
                print(f"  [{i:5d}/{len(rows)}] {qref}: no EP payload", flush=True)
            continue
        ans = find_answer_docx_url(payload)
        if not ans:
            no_answer_link += 1
            if i <= 5 or i % 100 == 0:
                print(f"  [{i:5d}/{len(rows)}] {qref}: no answer published yet", flush=True)
            continue
        # Download the answer document
        try:
            req = urllib_request.Request(ans["url"], headers={"User-Agent": USER_AGENT})
            with urllib_request.urlopen(req, timeout=30) as r:
                doc_bytes = r.read()
        except Exception as exc:
            errors += 1
            print(f"  [{i:5d}/{len(rows)}] {qref}: fetch failed: {exc}", flush=True)
            continue
        # Extract text
        if ans.get("is_pdf"):
            text = extract_pdf_text(doc_bytes)
        else:
            text = extract_docx_text(doc_bytes)
        if not text or len(text) < MIN_BODY_LEN:
            errors += 1
            if i <= 5:
                print(f"  [{i:5d}/{len(rows)}] {qref}: extracted text too short ({len(text or '')} chars)", flush=True)
            continue
        # Map answering commissioner from creator (e.g. ['org/EU_COMMISSION'])
        commissioner = None
        creators = ans.get("creator") or []
        if creators:
            c = creators[0] if isinstance(creators, list) else creators
            if "EU_COMMISSION" in str(c):
                commissioner = "European Commission"
            elif "EU_COUNCIL" in str(c):
                commissioner = "Council of the EU"
            elif "ECB" in str(c):
                commissioner = "European Central Bank"
        # Map answered_date
        answered_date = None
        if ans.get("document_date"):
            try:
                from datetime import datetime
                answered_date = datetime.fromisoformat(ans["document_date"]).date()
            except Exception:
                pass

        if args.apply:
            try:
                cur.execute(
                    """
                    UPDATE parliamentary_questions SET
                        text_answer = %s,
                        answer_url = COALESCE(%s, answer_url),
                        answered_date = COALESCE(%s, answered_date),
                        answering_commissioner = COALESCE(%s, answering_commissioner),
                        last_updated = NOW()
                    WHERE id = %s
                    """,
                    (text[:1_000_000], ans["url"], answered_date, commissioner, row["id"]),
                )
                conn.commit()
                ok += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:5d}/{len(rows)}] {qref}: DB error: {exc}", flush=True)
                continue
        else:
            ok += 1

        if i <= 5 or i % 100 == 0:
            print(f"  [{i:5d}/{len(rows)}] {qref}: answer={len(text):,} chars{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print("=" * 70)
    print(f"[DONE] candidates={len(rows)}  filled={ok}  no_payload={no_payload}  no_answer_link={no_answer_link}  errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
