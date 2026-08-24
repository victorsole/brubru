"""
Backfill CELEX numbers on commission_documents from their reference field.

Reference patterns (from the Commission Register):
  - "COM(2026) 87"        → CELEX 52026PC0087  (proposal — sector 5, year, PC, 4-digit)
  - "SWD(2026) 119"       → CELEX 52026SC0119  (staff working doc)
  - "C(2026) 234"         → CELEX 52026PC0234  (Commission decision/regulation)
  - "JOIN(2026) 12"       → CELEX 52026JC0012
  - "OJ"                  → not derivable (Official Journal items use different pattern)
  - "PV"                  → not derivable

When CELEX is filled, the Cellar resolver `publications.europa.eu/resource/celex/{celex}/PUB_PDF/EN`
returns the actual PDF directly — solves the "no pdf_url" case for partners.
"""

import re
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]


# Reference → CELEX letter mapping (the 6th character of CELEX 5YYYYXNNNN).
# Source: EUR-Lex CELEX format documentation.
DOC_TYPE_TO_CELEX_LETTER = {
    "COM": "PC",   # Commission proposal (PC = Preparatory Communication / proposal)
    "SWD": "SC",   # Staff working document
    "JOIN": "JC",  # Joint communication
    "C":   "PC",   # Commission act (decisions, regulations) — same prefix as COM-style
    "SEC": "SC",   # Secretariat document (older legacy)
}

# Reference shape, e.g.:
#   "COM(2026) 87 final"         → year=2026, num=87
#   "SWD(2026) 119/2"            → year=2026, num=119
#   "JOIN(2026) 12"              → year=2026, num=12
REF_RE = re.compile(r"^\s*(COM|SWD|JOIN|C|SEC)\s*\(\s*(\d{4})\s*\)\s*(\d{1,4})", re.I)


def derive_celex(reference: str, doc_type: str) -> str | None:
    if not reference:
        return None
    m = REF_RE.match(reference)
    if not m:
        return None
    raw_type = (m.group(1) or "").upper()
    year = int(m.group(2))
    num = int(m.group(3))
    letter = DOC_TYPE_TO_CELEX_LETTER.get(raw_type)
    if not letter:
        return None
    return f"5{year}{letter}{num:04d}"


def main():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, reference, doc_type
        FROM commission_documents
        WHERE celex IS NULL OR celex = ''
    """)
    rows = cur.fetchall()
    print(f"Rows without CELEX: {len(rows)}")

    updated = 0
    skipped = 0
    samples = []
    for row_id, reference, doc_type in rows:
        celex = derive_celex(reference, str(doc_type))
        if celex:
            try:
                cur.execute(
                    "UPDATE commission_documents SET celex = %s WHERE id = %s",
                    (celex, row_id),
                )
                updated += 1
                if len(samples) < 5:
                    samples.append((reference, celex))
            except Exception as e:
                print(f"  [ERR] {reference}: {e}")
                conn.rollback()
        else:
            skipped += 1
    conn.commit()

    print(f"Updated: {updated}")
    print(f"Skipped (no derivable CELEX, e.g. OJ/PV): {skipped}")
    print(f"Samples:")
    for r, c in samples:
        print(f"  {r:25s} → {c}")

    cur.execute("SELECT COUNT(*) FROM commission_documents WHERE celex IS NOT NULL AND celex != ''")
    total_with_celex = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM commission_documents")
    total = cur.fetchone()[0]
    print()
    print(f"After backfill: {total_with_celex}/{total} commission_documents have CELEX")


if __name__ == "__main__":
    main()
