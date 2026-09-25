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
sys.path.insert(0, str(ROOT / "backend"))
ENV = ROOT / ".env"


def get_env(k: str) -> str:
    """The real environment first, then a local .env (25 Sep 2026).

    This used to read the repo-root .env and nothing else. Railway has no .env
    file, so under the cron this returned "" for DATABASE_URL and the job exited
    "[FATAL] DATABASE_URL missing" every run, unrecorded. Same fix as
    scripts/_db_url.py and ingest_funding_sedia.get_env.
    """
    import os
    value = os.environ.get(k, "").strip()
    if value:
        return value
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def _legacy_description(xml: str) -> Optional[str]:
    """Pre-eForms TED (R2.0.9): SHORT_DESCR / OBJECT_DESCR."""
    parts = []
    for tag in ("SHORT_DESCR", "OBJECT_DESCR"):
        for m in re.finditer(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL):
            inner = m.group(1)
            # Strip nested tags + collapse whitespace
            text = re.sub(r"<[^>]+>", " ", inner)
            text = re.sub(r"\s+", " ", text).strip()
            if text and text not in parts:
                parts.append(text)
    return "\n\n".join(parts) if parts else None


def extract_description(xml: str) -> Optional[str]:
    """The tender's description, from either TED format.

    Until 25 Sep 2026 this read only the legacy tags, which 10 of the 31,985
    rows without a description carry; the other 31,975 are eForms. It now asks
    the ingest's own parser, so the backfill and the ingest cannot disagree.
    """
    if not xml:
        return None
    legacy = _legacy_description(xml)
    if legacy:
        return legacy
    from services.tenders.eforms_parser import EFormsParser
    return EFormsParser().parse(xml).get("description")


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
    # Ids first, XML in chunks: the backlog is ~56 KB of XML a row (1.6 GB for
    # 30k rows), which a single fetchall would hold in memory at once.
    cur.execute(
        "SELECT id FROM tenders "
        "WHERE xml_content IS NOT NULL AND description IS NULL "
        "ORDER BY publication_date DESC NULLS LAST, id DESC LIMIT %s",
        (args.limit if args.limit else 100_000,),
    )
    ids = [r[0] for r in cur.fetchall()]
    print(f"[INFO] {len(ids)} candidate rows (apply={args.apply})")

    def _chunks():
        for k in range(0, len(ids), 200):
            cur.execute("SELECT id, title, xml_content FROM tenders WHERE id = ANY(%s) "
                        "ORDER BY publication_date DESC NULLS LAST, id DESC", (ids[k:k + 200],))
            yield from cur.fetchall()

    rows = ids  # for the progress counters below
    extracted = persisted = skipped = 0
    for i, (tid, title, xml) in enumerate(_chunks(), 1):
        desc = extract_description(xml)
        if not desc or len(desc) < 50:
            # Stored as '' ("read, nothing to take"), never left NULL: a NULL row
            # is selected again on the next run, so a few hundred notices with no
            # usable text would crowd the backlog out of every batch for ever.
            # The same went for "< 500 chars", which re-selected every tender
            # whose real description is simply short (25 Sep 2026).
            skipped += 1
            if args.apply:
                cur.execute("UPDATE tenders SET description = '' WHERE id = %s AND description IS NULL", (tid,))
                conn.commit()
            if skipped <= 5:
                print(f"  [{i:4}/{len(rows)}] tender {tid}: nothing to extract", flush=True)
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
    print(f"[DONE] candidates={len(rows)}  extracted={extracted}  written={persisted}  nothing_to_extract={skipped}{' (DRY)' if not args.apply else ''}")
    if args.apply:
        cur.execute("SELECT count(*) FROM tenders WHERE xml_content IS NOT NULL AND description IS NULL")
        left = cur.fetchone()[0]
        print(f"[INFO] backlog left: {left}")
        if left:
            # Read by api/cron.py::_run_script: still owed, so not a success.
            print(f"[SYNC_STATUS] degraded: {left} tender(s) still without a description")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
