"""
Extract tender description from existing xml_content (TED eForms / R2.0.9).

The `tenders` table has 100 rows with xml_content populated but only 52
have description > 500 chars. Pure compute — no network calls — extract
from the SHORT_DESCR / OBJECT_DESCR tags in the existing XML.

Run:
    python3.12 backend/scripts/backfill_tenders_description.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_tenders_description.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

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


def extract_description(xml: str) -> Optional[str]:
    """Pull all SHORT_DESCR + OBJECT_DESCR text content; strip inner tags."""
    if not xml:
        return None
    parts = []
    for tag in ("SHORT_DESCR", "OBJECT_DESCR"):
        for m in re.finditer(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL):
            inner = m.group(1)
            # Strip nested tags + collapse whitespace
            text = re.sub(r"<[^>]+>", " ", inner)
            text = re.sub(r"\s+", " ", text).strip()
            if text and text not in parts:
                parts.append(text)
    if not parts:
        return None
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, xml_content FROM tenders "
        "WHERE xml_content IS NOT NULL AND (description IS NULL OR LENGTH(description) < 500) "
        "ORDER BY id LIMIT %s",
        (args.limit if args.limit else 100_000,),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    extracted = persisted = 0
    for i, (tid, title, xml) in enumerate(rows, 1):
        desc = extract_description(xml)
        if not desc or len(desc) < 50:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] tender {tid}: skipped (too short)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE tenders SET description = %s, updated_at = NOW() WHERE id = %s",
                    (desc[:1_000_000], tid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                print(f"  [{i:4}] DB error tender {tid}: {exc}", flush=True)
        if i <= 10 or i % 50 == 0:
            print(f"  [{i:4}/{len(rows)}] tender {tid} {(title or '')[:35]:35} → {len(desc):,} chars{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)}  extracted={extracted}  written={persisted}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
