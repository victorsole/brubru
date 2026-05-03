"""
Body-fallback for commission_documents whose Cellar metadata didn't expose
a title. Extracts the real title from the document's text_body using the
canonical Commission header structure:

  EN EN EUROPEAN COMMISSION Brussels, DD.MM.YYYY <REF> COMMISSION <DOCTYPE>
  <REAL TITLE — possibly multi-line>
  <Table of contents | 1. INTRODUCTION | 1 Table of contents>

Run:
    python3.12 backend/scripts/backfill_commission_titles_from_body.py            # dry-run
    python3.12 backend/scripts/backfill_commission_titles_from_body.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# Marker for end of header / start of body proper.
_TOC_MARKERS = (
    r"\bTable of [Cc]ontents\b",
    r"\bTABLE OF CONTENTS\b",
    r"\b1\.\s+(?:INTRODUCTION|Introduction|Introduzione)\b",
    r"\b1\s+(?:Introduction|INTRODUCTION)\b",
)
_TOC_RE = re.compile("|".join(_TOC_MARKERS))

# Header openers — split to find the position right after the doctype line.
_HEADER_OPENERS = (
    r"COMMISSION STAFF WORKING DOCUMENT(?: IMPACT ASSESSMENT(?: REPORT)?)?",
    r"COMMUNICATION FROM THE COMMISSION",
    r"COMMUNICATION TO THE COMMISSION",
    r"REPORT FROM THE COMMISSION",
    r"WHITE PAPER",
    r"GREEN PAPER",
    r"PROPOSAL FOR A REGULATION",
    r"PROPOSAL FOR A DIRECTIVE",
    r"PROPOSAL FOR A DECISION",
)
_HEADER_RE = re.compile("|".join(f"({h})" for h in _HEADER_OPENERS))


def extract_title_from_body(body: str) -> str | None:
    if not body:
        return None
    head = body[:5000]

    # Find the doctype opener line position
    m = _HEADER_RE.search(head)
    if not m:
        return None
    after_header = head[m.end():]

    # Cut at the next TOC/section marker
    cut = _TOC_RE.search(after_header)
    candidate = after_header[: cut.start()] if cut else after_header

    # Clean: collapse whitespace, strip trailing curly-brace footers
    candidate = re.sub(r"\s+", " ", candidate).strip()
    # Drop trailing accompanying-document refs like "{COM(2026) 173 final}"
    candidate = re.sub(r"\{[^{}]*\}", "", candidate).strip()
    # Cap length
    candidate = candidate.strip(" ,.-")
    candidate = candidate[:500].strip()

    # Reject if too short or still looks like header noise
    if len(candidate) < 25:
        return None
    if candidate.lower().startswith(("annex", "table of", "page ")):
        return None
    return candidate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        r"""
        SELECT id::text, celex, title, text_body
          FROM commission_documents
         WHERE title ~ '^(SWD|COM|JOIN|C)\s+document\s+\d'
           AND text_body IS NOT NULL
           AND length(text_body) > 500
         ORDER BY publication_date DESC NULLS LAST
         LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} placeholder rows queued (apply={args.apply})")

    updated = skipped = 0
    for row_id, celex, title, body in rows:
        new_title = extract_title_from_body(body)
        if not new_title:
            skipped += 1
            print(f"  [SKIP] {celex}: no clean title found")
            continue
        print(f"  [OK] {celex}: {new_title[:80]}...")
        if args.apply:
            cur2 = conn.cursor()
            cur2.execute(
                "UPDATE commission_documents SET title = %s, last_updated = NOW() WHERE id = %s",
                (new_title, row_id),
            )
            conn.commit()
            cur2.close()
        updated += 1

    conn.close()
    print(f"[DONE] updated={updated} skipped={skipped}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
