#!/usr/bin/env python3.12
"""Move the CELEX that is already in `reference` into the `celex` column.

A full walk of /api/v2/commission/commission-register-documents (1,424 rows, all 15
pages) found 697 serving an empty public_url and 933 with no body.

The identifier was never missing. Those rows are Official Journal documents whose
`reference` IS a CELEX -- 32026R2160, 31993L0013 -- while the `celex` column is empty.
Both the URL fallback chain and the body lookup key on `celex`, so each found nothing
and the row served neither. All 742 URL-less rows are in that state, and all 742
references match the CELEX form.

Verified at the source before being used: 32026R2160 resolves on EUR-Lex to Council
Implementing Regulation (EU) 2026/2160 of 22 September 2026, 232,715 characters.

Nothing is derived. The value is copied from one column of the same row to another,
only where the reference actually matches a CELEX and only where `celex` is empty, so
a row that already carries a different CELEX is never overwritten.

    python3.12 scripts/backfill_commission_register_celex.py --rehearse
    python3.12 scripts/backfill_commission_register_celex.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

# A CELEX: sector digit, 4-digit year, 1-2 letter document type, then the number,
# optionally a corrigendum suffix like R(01). Anchored at both ends so a reference
# that merely STARTS like a CELEX is not treated as one.
#
# The number is 4 OR 5 digits. Requiring 4 left 39 of the 742 behind -- recent
# decisions are numbered 32026D02811, with five. Checked at the source rather than
# assumed: Cellar answers 200 for 32026D02811 and 404 for an invented 32026D99999,
# so the five-digit form is a real CELEX and not a malformed reference.
CELEX_RE = r'^[1-9][0-9]{4}[A-Z]{1,2}[0-9]{4,5}(R\([0-9]{2}\))?$'

STATE = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(celex, '') = '') AS no_celex,
           count(*) FILTER (WHERE coalesce(portal_url, '') = ''
                              AND coalesce(source_url, '') = ''
                              AND coalesce(pdf_url, '') = ''
                              AND coalesce(celex, '') = '') AS no_url_at_all
      FROM commission_documents
    """
)

CANDIDATES = text(
    f"""
    SELECT count(*) FROM commission_documents
     WHERE coalesce(celex, '') = '' AND reference ~ '{CELEX_RE}'
    """
)

FILL = text(
    f"""
    UPDATE commission_documents
       SET celex = reference, last_updated = now()
     WHERE coalesce(celex, '') = '' AND reference ~ '{CELEX_RE}'
    """
)


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        before = conn.execute(STATE).one()
        candidates = conn.execute(CANDIDATES).scalar_one()

    print(f"[INFO] register documents      : {before.total}")
    print(f"[INFO] with no celex           : {before.no_celex}")
    print(f"[INFO] with no URL of any kind : {before.no_url_at_all}")
    print(f"[INFO] reference IS a CELEX    : {candidates}")
    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0

    with engine.begin() as conn:
        written = conn.execute(FILL).rowcount
    with engine.connect() as conn:
        after = conn.execute(STATE).one()

    print(f"\n[INFO] celex filled    : {written}")
    print(f"[INFO] no celex        : {before.no_celex} -> {after.no_celex}")
    print(f"[INFO] no URL at all   : {before.no_url_at_all} -> {after.no_url_at_all}")
    if written != candidates:
        print(f"[ERROR] {candidates} candidates but {written} written")
        return 1
    print("[OK] every value copied from the row's own reference, none derived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
