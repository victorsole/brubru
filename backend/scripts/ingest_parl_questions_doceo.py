"""
Ingest EP parliamentary questions from doceo (the EP document portal).

NO CURATED SEED. Every row comes from a real
https://www.europarl.europa.eu/doceo/document/E-10-{YYYY}-{NNNNNN}_EN.html
that returns 200 with meta-tag metadata.

Strategy:
  - Probe question numbers across a range (default: most recent 200 of 2026).
  - For each that 200s, parse meta tags: title, author, description, date.
  - UPSERT on question_reference. Failed/404 numbers are skipped silently.

Run: python3.12 backend/scripts/ingest_parl_questions_doceo.py [--year 2026] [--start 1] [--end 200] [--dry-run]
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_env(k):
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


DOCEO_URL = "https://www.europarl.europa.eu/doceo/document/E-{term}-{year}-{num:06d}_EN.html"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruDoceoCrawler/1.0; +https://brubru.beresol.eu)"

# Tag patterns: doceo's question pages all use the same meta structure.
META_PATTERNS = {
    "title": re.compile(r'<meta\s+name="title"\s+content="([^"]+)"', re.IGNORECASE),
    "description": re.compile(r'<meta\s+name="description"\s+content="([^"]+)"', re.IGNORECASE),
    "author": re.compile(r'<meta\s+name="author"\s+content="([^"]+)"', re.IGNORECASE),
    "available": re.compile(r'<meta\s+name="available"\s+content="([^"]+)"', re.IGNORECASE),
}


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def parse_question(html, url, year):
    """Parse the doceo HTML page into a normalised row, or None."""
    if not html:
        return None
    text = html.decode("utf-8", errors="replace")
    out = {}
    for k, pat in META_PATTERNS.items():
        m = pat.search(text)
        if m:
            out[k] = m.group(1).strip()

    title_meta = out.get("title", "")
    description = out.get("description", "")

    # Title format: "Parliamentary question | {SUBJECT} | E-NNNNNN/YYYY | European Parliament"
    parts = [p.strip() for p in title_meta.split("|")]
    subject = parts[1] if len(parts) >= 4 else ""
    ref = next((p for p in parts if re.match(r"^[EOP]-\d{6}/\d{4}$", p)), None)

    if not ref or not subject:
        return None

    # Description format: "Question for written answer {REF} to the {ANSWERING_INSTITUTION} Rule {N} {AUTHOR} ({POLITICAL_GROUP})"
    answering = None
    m_inst = re.search(r"to the\s+([A-Z][a-zA-Z\s]+?)(?:\s+Rule|\s*$)", description)
    if m_inst:
        answering = m_inst.group(1).strip().upper().replace(" ", "_")[:40]

    qtype = "written"
    if ref.startswith("O-"):
        qtype = "oral"
    elif ref.startswith("P-"):
        qtype = "priority"

    submitted = None
    if out.get("available"):
        try:
            submitted = dt.datetime.strptime(out["available"], "%d-%m-%Y").date()
        except Exception:
            try:
                submitted = dt.datetime.strptime(out["available"][:10], "%Y-%m-%d").date()
            except Exception:
                pass

    asking = []
    if out.get("author"):
        asking = [a.strip() for a in re.split(r"[;,]\s*|\s+(?:and|&)\s+", out["author"]) if a.strip()]

    return {
        "question_reference": ref,
        "question_type": qtype,
        "parliamentary_term": 10 if year >= 2024 else 9,
        "subject": subject[:500],
        "submitted_date": submitted,
        "answered_date": None,
        "asking_mep_ids": [],
        "asking_mep_names": asking,
        "answering_institution": answering or "COMMISSION",
        "text_question": None,
        "text_answer": None,
        "answering_commissioner": None,
        "answer_url": None,
        "committees": [],
        "procedure_ref": None,
        "related_celex": [],
        "policy_areas": [],
        "source_url": url,
    }


def upsert_row(cursor, row):
    cursor.execute(
        """
        INSERT INTO parliamentary_questions (
            question_reference, question_type, parliamentary_term, subject,
            submitted_date, answered_date, asking_mep_ids, asking_mep_names,
            answering_institution, text_question, text_answer,
            answering_commissioner, answer_url, committees, procedure_ref,
            related_celex, policy_areas, source_url
        ) VALUES (
            %(question_reference)s, %(question_type)s, %(parliamentary_term)s, %(subject)s,
            %(submitted_date)s, %(answered_date)s, %(asking_mep_ids)s, %(asking_mep_names)s,
            %(answering_institution)s, %(text_question)s, %(text_answer)s,
            %(answering_commissioner)s, %(answer_url)s, %(committees)s, %(procedure_ref)s,
            %(related_celex)s, %(policy_areas)s, %(source_url)s
        )
        ON CONFLICT (question_reference) DO UPDATE SET
            subject = EXCLUDED.subject,
            asking_mep_names = EXCLUDED.asking_mep_names,
            submitted_date = COALESCE(EXCLUDED.submitted_date, parliamentary_questions.submitted_date),
            source_url = EXCLUDED.source_url,
            last_updated = NOW()
        """,
        row,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--term", type=int, default=10)
    ap.add_argument("--start", type=int, default=1, help="First question number to probe")
    ap.add_argument("--end", type=int, default=200, help="Last question number to probe")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)

    print(f"[INFO] Probing E-{args.term}-{args.year}-{args.start:06d} .. {args.end:06d}")
    candidates = []
    n_404 = 0
    for n in range(args.start, args.end + 1):
        url = DOCEO_URL.format(term=args.term, year=args.year, num=n)
        status, body = http_get(url)
        if status != 200:
            n_404 += 1
            time.sleep(0.4)
            continue
        row = parse_question(body, url, args.year)
        if row:
            candidates.append(row)
            if len(candidates) % 10 == 0:
                print(f"  [{len(candidates)}/{n}] {row['question_reference']}: {row['subject'][:50]}")
        time.sleep(0.4)
    print(f"[INFO] Probed {args.end - args.start + 1} numbers: {len(candidates)} parsed, {n_404} non-200.")

    if not candidates:
        print("[WARN] No questions parsed — nothing inserted (honest empty).")
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY-RUN] First 5:")
        for c in candidates[:5]:
            print(f"  {c['question_reference']}  {c['subject'][:60]}  by {','.join(c['asking_mep_names'][:2])}")
        return

    import psycopg2
    conn = psycopg2.connect(db_url)
    inserted = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for row in candidates:
                    upsert_row(cur, row)
                    inserted += 1
        print(f"[OK] UPSERTed {inserted} parliamentary questions.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
