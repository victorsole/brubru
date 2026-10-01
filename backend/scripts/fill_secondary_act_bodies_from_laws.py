#!/usr/bin/env python3.12
"""Give delegated and implementing acts the text of the act, from eu_laws.

/api/v2/legislative/delegated-acts served 470 of 2,156 rows with no body, and
/implementing-acts 2,917 of 6,284. Where a body is present it averages 48,536
characters, so this is not a formatting question: a fifth of the delegated acts and
nearly half the implementing acts carried nothing at all.

338 of the 470 carry a CELEX, which makes the act's text the act's own text, and
eu_laws fetches exactly that from Cellar. This copies it across.

Re-runnable by design: the eu_laws body drain works through 19,095 acts over hours, so
this takes whatever is available now and is run again as that fills. Only an empty
cell is written, so a later run can never shorten or replace a body already there, and
the acts with no CELEX are left alone rather than filled from something that is not
their text.

    python3.12 scripts/fill_secondary_act_bodies_from_laws.py --rehearse
    python3.12 scripts/fill_secondary_act_bodies_from_laws.py --apply
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
    UPDATE secondary_acts s
       SET text_body       = COALESCE(NULLIF(s.text_body, ''), l.body_txt),
           body_html       = COALESCE(NULLIF(s.body_html, ''), l.body_html),
           body_fetched_at = COALESCE(s.body_fetched_at, now()),
           last_updated    = now()
      FROM eu_laws l
     WHERE l.celex = s.celex
       AND coalesce(s.celex, '') <> ''
       AND coalesce(s.text_body, '') = ''
       AND coalesce(l.body_txt, '') <> ''
    """
)

STATE = text(
    """
    SELECT act_type,
           count(*) AS total,
           count(*) FILTER (WHERE coalesce(text_body, '') = '') AS no_body,
           count(*) FILTER (WHERE coalesce(text_body, '') = '' AND EXISTS (
               SELECT 1 FROM eu_laws l
                WHERE l.celex = secondary_acts.celex
                  AND coalesce(l.body_txt, '') <> '')) AS fillable
      FROM secondary_acts
     GROUP BY act_type
     ORDER BY act_type
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
        before = list(conn.execute(STATE))
    for r in before:
        print(f"[INFO] {r.act_type:<13} rows={r.total:<6} no_body={r.no_body:<6} fillable now={r.fillable}")
    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0

    expected = sum(r.fillable for r in before)
    with engine.begin() as conn:
        written = conn.execute(FILL).rowcount
    with engine.connect() as conn:
        after = list(conn.execute(STATE))

    print(f"\n[INFO] bodies copied : {written}")
    for b, a in zip(before, after):
        print(f"[INFO] {b.act_type:<13} no_body {b.no_body} -> {a.no_body}")
    if written != expected:
        print(f"[ERROR] {expected} were fillable but {written} were written")
        return 1
    print("[OK] every body copied from the act's own eu_laws row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
