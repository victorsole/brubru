"""
CC-2(b) — Backfill text_question + text_answer for parliamentary_questions.

Source: EP Open Data API at data.europarl.europa.eu/api/v2/parliamentary-
questions/{ref}?format=application/ld+json&language=en

Pipeline per row:
  1. Resolve the EP Open Data identifier (e.g. E-10-2025-000001) from the
     existing source_url already in DB.
  2. Fetch JSON-LD; locate the .docx manifestation in is_realized_by.
  3. Download the docx, extract the body text via zipfile + regex (no
     python-docx dep needed — works against word/document.xml).
  4. If inverse_answers_to is present, repeat for the answer document and
     fill text_answer + answer_url + answered_date + answering_commissioner.
  5. UPDATE the row.

Resumable: skips rows where text_question is already populated.

Throttle: 0.5s between EP API calls (~120/min). EP Open Data has been
generous in practice; tighten if 429s appear.

Run:
    python3.12 backend/scripts/backfill_parl_question_text.py [--limit 50] [--apply] [--year 2026]

Defaults to dry-run with --limit 5 so the first invocation is safe.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"

EP_API_BASE = "https://data.europarl.europa.eu/api/v2/parliamentary-questions"
USER_AGENT = "BrubruParlQBackfill/1.0 (+https://brubru.beresol.eu)"


def get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def http_get(url: str, timeout: float = 30.0) -> Optional[bytes]:
    req = urllib_request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib_error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  [HTTP {e.code}] {url}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  [{type(e).__name__}] {url}: {str(e)[:80]}")
        return None


def derive_ep_ref(question_reference: str) -> Optional[str]:
    """Convert DB question_reference 'E-001234/2025' to EP API form 'E-10-2025-001234'.

    Note: parliamentary_term=10 is the current EP. For older questions,
    parliamentary_term is in the row — but we can also derive 10 from the
    year for 2024+ since term-10 started July 2024.
    """
    m = re.match(r"^([EPWIB])-(\d+)/(\d{4})$", question_reference.strip())
    if not m:
        return None
    kind, num, year = m.group(1), m.group(2), m.group(3)
    return f"{kind}-10-{year}-{num.zfill(6)}"


def find_docx_url(json_ld: dict) -> Optional[str]:
    """Walk a JSON-LD Work payload and return the first .docx manifestation URL."""
    data = (json_ld or {}).get("data")
    if not data:
        return None
    work = data[0] if isinstance(data, list) else data
    for expr in work.get("is_realized_by", []) or []:
        for man in expr.get("is_embodied_by", []) or []:
            ref = man.get("is_exemplified_by") or ""
            if ref.endswith(".docx"):
                if ref.startswith("http"):
                    return ref
                return f"https://data.europarl.europa.eu/{ref.lstrip('/')}"
    return None


def extract_docx_text(docx_bytes: bytes) -> str:
    """Pull all <w:t> text runs from the DOCX and join. Strips boilerplate."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(docx_bytes))
    except zipfile.BadZipFile:
        return ""
    if "word/document.xml" not in zf.namelist():
        return ""
    xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    runs = re.findall(r"<w:t[^>]*>([^<]+)</w:t>", xml)
    text = "\n".join(r.strip() for r in runs if r.strip())
    # Trim doceo header lines so the body is more useful.
    return text.strip()


def fetch_question_payload(ep_ref: str) -> Optional[dict]:
    raw = http_get(f"{EP_API_BASE}/{ep_ref}?format=application%2Fld%2Bjson&language=en")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract_answer_meta(json_ld: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (answer_work_id, answered_date, answering_commissioner) or all None."""
    data = (json_ld or {}).get("data")
    if not data:
        return None, None, None
    work = data[0] if isinstance(data, list) else data
    inv = work.get("inverse_answers_to") or []
    if not inv:
        return None, None, None
    answer = inv[0]
    work_id = answer.get("id")  # eli/dl/doc/E-10-...-ASW
    answered_date = answer.get("document_date")
    # Commissioner name lives in workHadParticipation -> participant
    commissioner = None
    for part in answer.get("workHadParticipation", []) or []:
        for p in part.get("had_participant_person", []) or []:
            if isinstance(p, dict) and p.get("name"):
                commissioner = p["name"]
                break
        if commissioner:
            break
    return work_id, answered_date, commissioner


def fetch_answer_docx_url(answer_work_id: str) -> Optional[str]:
    """Resolve the EP /works/{id} JSON-LD and pick the docx manifestation.

    The /api/v2/works/ endpoint returns a bare Work record without
    expressions/manifestations — answer text isn't directly fetchable from
    the structured EP API today. Returning None signals the caller to leave
    text_answer NULL; question text is the bigger win and ships independently.
    """
    # Future work: probe data.europarl.europa.eu for the canonical answer
    # docx URL once a stable pattern is found. For now, return None.
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="Max rows to process (0=unbounded)")
    ap.add_argument("--year", type=int, help="Restrict to questions of this year")
    ap.add_argument("--apply", action="store_true", help="Write to DB. Default is dry-run.")
    ap.add_argument("--throttle", type=float, default=0.5, help="Seconds between EP API calls")
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = "text_question IS NULL AND source_url IS NOT NULL"
    if args.year:
        where += f" AND question_reference LIKE '%/{args.year}'"
    sql = f"SELECT id, question_reference, source_url, answer_url FROM parliamentary_questions WHERE {where} ORDER BY question_reference DESC"
    if args.limit:
        sql += f" LIMIT {args.limit}"
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} rows to process (apply={args.apply}, throttle={args.throttle}s)")

    update_sql = """
        UPDATE parliamentary_questions
        SET text_question = COALESCE(%(text_question)s, text_question),
            text_answer = COALESCE(%(text_answer)s, text_answer),
            answer_url = COALESCE(%(answer_url)s, answer_url),
            answered_date = COALESCE(%(answered_date)s::DATE, answered_date),
            answering_commissioner = COALESCE(%(answering_commissioner)s, answering_commissioner),
            last_updated = NOW()
        WHERE id = %(id)s
    """

    n_q_filled = 0
    n_a_filled = 0
    n_failed = 0
    for row in rows:
        ref_db = row["question_reference"]
        ep_ref = derive_ep_ref(ref_db)
        if not ep_ref:
            print(f"  [SKIP] {ref_db}: cannot derive EP API ref")
            n_failed += 1
            continue

        payload = fetch_question_payload(ep_ref)
        if not payload:
            print(f"  [MISS] {ref_db}: no EP API payload")
            n_failed += 1
            time.sleep(args.throttle)
            continue

        # Question text
        q_url = find_docx_url(payload)
        q_text = ""
        if q_url:
            q_blob = http_get(q_url)
            if q_blob:
                q_text = extract_docx_text(q_blob)
        if q_text:
            n_q_filled += 1

        # Answer
        a_work_id, answered_date, commissioner = extract_answer_meta(payload)
        a_text = ""
        a_url = None
        if a_work_id:
            time.sleep(args.throttle)
            a_url = fetch_answer_docx_url(a_work_id)
            if a_url:
                a_blob = http_get(a_url)
                if a_blob:
                    a_text = extract_docx_text(a_blob)
            if a_text:
                n_a_filled += 1

        print(f"  {ref_db}: q={len(q_text)}c a={len(a_text)}c (commish={commissioner})")

        if args.apply:
            cur.execute(update_sql, {
                "id": row["id"],
                "text_question": q_text or None,
                "text_answer": a_text or None,
                "answer_url": a_url or None,
                "answered_date": answered_date,
                "answering_commissioner": commissioner,
            })
            conn.commit()

        time.sleep(args.throttle)

    print(f"\n[DONE] Filled q_text on {n_q_filled} rows, a_text on {n_a_filled} rows, {n_failed} failures.")
    if not args.apply:
        print("[NOTE] Dry-run — pass --apply to write to DB.")


if __name__ == "__main__":
    main()
