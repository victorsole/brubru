#!/usr/bin/env python3.12
"""Give register documents the text of the act they are, from eu_laws.

/api/v2/commission/commission-register-documents served 933 rows with no body. 841 of
them are Official Journal acts and now carry a CELEX (backfill_commission_register_celex
moved it out of `reference`, where it had been sitting all along), so the text is the
act's own text and eu_laws already fetches it from Cellar.

Re-runnable by design: the eu_laws body drain works through 19,095 acts over hours, so
this copies whatever is available now and is run again as that fills. Only an empty
cell is written, so a later run can never shorten or replace a body already there.

    python3.12 scripts/fill_register_bodies_from_laws.py --rehearse
    python3.12 scripts/fill_register_bodies_from_laws.py --apply
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

FILL = text(
    """
    UPDATE commission_documents d
       SET text_body    = COALESCE(NULLIF(d.text_body, ''), l.body_txt),
           body_html    = COALESCE(NULLIF(d.body_html, ''), l.body_html),
           last_updated = now()
      FROM eu_laws l
     WHERE l.celex = d.celex
       AND coalesce(d.text_body, '') = ''
       AND coalesce(l.body_txt, '') <> ''
    """
)

STATE = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(text_body, '') = '') AS no_body,
           count(*) FILTER (WHERE coalesce(text_body, '') = '' AND EXISTS (
               SELECT 1 FROM eu_laws l
                WHERE l.celex = commission_documents.celex
                  AND coalesce(l.body_txt, '') <> '')) AS fillable
      FROM commission_documents
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
    print(f"[INFO] register documents : {before.total}")
    print(f"[INFO] with no body       : {before.no_body}")
    print(f"[INFO] fillable right now : {before.fillable}  (the rest wait on the eu_laws body drain)")
    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0

    with engine.begin() as conn:
        written = conn.execute(FILL).rowcount
    with engine.connect() as conn:
        after = conn.execute(STATE).one()

    print(f"\n[INFO] bodies copied : {written}")
    print(f"[INFO] no body       : {before.no_body} -> {after.no_body}")
    print(f"[INFO] still fillable: {after.fillable}")
    if written != before.fillable:
        print(f"[ERROR] {before.fillable} were fillable but {written} were written")
        return 1
    print("[OK] every body copied from the act's own eu_laws row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
