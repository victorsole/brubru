#!/usr/bin/env python3.12
"""Give adopted-act carriages the text and date of the act they point at.

A full walk of /api/v2/legislative/oeil/procedures (3,382 rows, all 34 pages) found
body_txt and body_html empty on 1,534 and document_date empty on 1,545.

The cause is that legislative_carriages holds three populations and only one is an
OEIL procedure file. The 1,090 EURLEX rows are adopted acts: they have no OEIL body
and no OEIL key events, so both datapoints came back empty. Their `description` is
about 206 characters -- a summary. A title plus a summary is not a body.

Each of those rows carries its CELEX, so the act's own text and date are read from
eu_laws, which holds them from Cellar. Nothing is derived: a CELEX eu_laws does not
have yet is left alone for a later run rather than filled from the CELEX year or the
import timestamp.

    python3.12 scripts/fill_carriage_bodies_from_acts.py --rehearse
    python3.12 scripts/fill_carriage_bodies_from_acts.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
_REPO_ROOT = str(BACKEND.parent)
for p in (_REPO_ROOT, str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

# COALESCE on every target so this can never shorten or blank a value another writer
# already put there; it only turns an empty cell into the act's own content.
FILL = text(
    """
    UPDATE legislative_carriages c
       SET oeil_text_body = COALESCE(NULLIF(c.oeil_text_body, ''), l.body_txt),
           oeil_html_body = COALESCE(NULLIF(c.oeil_html_body, ''), l.body_html),
           act_date       = COALESCE(c.act_date, l.date),
           last_updated   = now()
      FROM eu_laws l
     WHERE l.celex = ANY(c.celex_numbers)
       AND (
             (coalesce(c.oeil_text_body, '') = '' AND coalesce(l.body_txt, '') <> '')
          OR (c.act_date IS NULL AND l.date IS NOT NULL)
           )
    """
)

STATE = text(
    """
    SELECT count(*) AS total,
           count(*) FILTER (WHERE coalesce(oeil_text_body, '') = '') AS no_body,
           count(*) FILTER (WHERE act_date IS NULL) AS no_act_date
      FROM legislative_carriages
    """
)

AVAILABLE = text(
    """
    SELECT count(*) FROM legislative_carriages c
     WHERE EXISTS (SELECT 1 FROM eu_laws l
                    WHERE l.celex = ANY(c.celex_numbers)
                      AND (coalesce(l.body_txt, '') <> '' OR l.date IS NOT NULL))
       AND (coalesce(c.oeil_text_body, '') = '' OR c.act_date IS NULL)
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
        avail = conn.execute(AVAILABLE).scalar_one()

    print(f"[INFO] carriages              : {before.total}")
    print(f"[INFO] with no body           : {before.no_body}")
    print(f"[INFO] with no act_date       : {before.no_act_date}")
    print(f"[INFO] fillable from eu_laws  : {avail}")
    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0

    with engine.begin() as conn:
        written = conn.execute(FILL).rowcount
    with engine.connect() as conn:
        after = conn.execute(STATE).one()

    print(f"\n[INFO] rows written  : {written}")
    print(f"[INFO] no body       : {before.no_body} -> {after.no_body}")
    print(f"[INFO] no act_date   : {before.no_act_date} -> {after.no_act_date}")
    if written == 0 and avail:
        print(f"[ERROR] {avail} rows were fillable but none was written")
        return 1
    print("[OK] every value written was read from the act's own eu_laws row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
