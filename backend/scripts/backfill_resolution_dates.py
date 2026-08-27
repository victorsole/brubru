#!/usr/bin/env python3.12
"""D3: give `ep_resolutions` its adoption dates, from data Brubru already holds.

The defect (measured 27 Aug 2026): `/api/v2/parliament/resolutions` served **72
rows with `adoption_date` NULL on every single one**, so date filtering could not
work at all and `?q=social media` / `?q=minors online` both returned nothing.

Nothing needs re-fetching. Of the 72 rows:

    71 match a legislative_carriage that has a STORED OEIL page
    24 match a texts_adopted row that already carries an adoption date

Two sources, deliberately ranked:

  1. `texts_adopted.adoption_date` -- the Parliament's own record of the sitting
     at which the text was adopted. Preferred.
  2. the "Decision by Parliament" event on the procedure's OEIL page.

Where BOTH exist they are compared, and any disagreement is reported rather than
silently resolved. The handover asked for exactly that: the two EP surfaces must
not quietly contradict each other, and a backfill that picks a winner without
saying so is how they start to.

Usage:
    python3.12 scripts/backfill_resolution_dates.py            # dry-run
    python3.12 scripts/backfill_resolution_dates.py --apply
"""
import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

# One row per resolution, with both candidate dates side by side so they can be
# compared rather than coalesced blindly.
_CANDIDATES = """
SELECT r.id,
       r.procedure_ref,
       r.adoption_date                       AS current_date_,
       r.lead_committee                      AS current_lead,
       r.rapporteur                          AS current_rapporteur,
       t.adoption_date::date                 AS ta_date,
       c.lead_committee                      AS carriage_lead,
       c.rapporteur_name                     AS carriage_rapporteur,
       c.oeil_roles_parsed_at                AS roles_parsed,
       (SELECT max((e->>'date')::date)
          FROM json_array_elements(COALESCE(c.oeil_key_events, '[]'::json)) e
         WHERE e->>'event_type' ILIKE '%Decision by Parliament%'
           AND (e->>'date') ~ '^\\d{4}-\\d{2}-\\d{2}$')  AS oeil_date
FROM ep_resolutions r
LEFT JOIN texts_adopted t          ON t.procedure_ref      = r.procedure_ref
LEFT JOIN legislative_carriages c  ON c.oeil_procedure_ref = r.procedure_ref
ORDER BY r.procedure_ref
"""

_UPDATE = """
UPDATE ep_resolutions SET
    adoption_date  = COALESCE(CAST(:adoption AS date), adoption_date),
    lead_committee = COALESCE(:lead, lead_committee),
    rapporteur     = COALESCE(:rapporteur, rapporteur),
    updated_at     = now()
WHERE id = :id
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    args = ap.parse_args()

    with _engine().connect() as conn:
        rows = conn.execute(text(_CANDIDATES)).fetchall()
        total = len(rows)

        dated = disagreed = still_null = 0
        lead_filled = rapp_filled = 0
        conflicts, unresolvable = [], []

        for r in rows:
            chosen = r.ta_date or r.oeil_date

            if r.ta_date and r.oeil_date and r.ta_date != r.oeil_date:
                # Do not hide it. Two EP surfaces disagreeing about when the
                # Parliament adopted a text is a finding, not a tie to break.
                disagreed += 1
                if len(conflicts) < 10:
                    conflicts.append(
                        f"{r.procedure_ref:20} texts_adopted={r.ta_date} "
                        f"oeil={r.oeil_date}  (using texts_adopted)")

            if chosen is None and r.current_date_ is None:
                still_null += 1
                if len(unresolvable) < 10:
                    unresolvable.append(r.procedure_ref)
            elif chosen is not None and r.current_date_ is None:
                dated += 1

            # Reuse the committee roles recovered in D4 rather than leaving these
            # columns half-empty on a second EP surface.
            lead = r.carriage_lead if (r.roles_parsed and not r.current_lead) else None
            rapporteur = (r.carriage_rapporteur
                          if (r.roles_parsed and not r.current_rapporteur) else None)
            if lead:
                lead_filled += 1
            if rapporteur:
                rapp_filled += 1

            if args.apply:
                conn.execute(text(_UPDATE), {
                    "id": r.id,
                    "adoption": chosen,
                    "lead": lead,
                    "rapporteur": rapporteur,
                })

        if args.apply:
            conn.commit()

        print(f"[{'APPLIED' if args.apply else 'DRY-RUN'}] {total} resolution(s): "
              f"dated={dated} lead_committee_filled={lead_filled} "
              f"rapporteur_filled={rapp_filled} still_undated={still_null}")
        if conflicts:
            print(f"[WARN] {disagreed} resolution(s) where the two EP surfaces "
                  f"give DIFFERENT adoption dates:")
            for c in conflicts:
                print("   " + c)
        if unresolvable:
            # Named, so "we could not date these" never reads as "these have no date".
            print(f"[INFO] {still_null} could not be dated from anything we hold: "
                  + ", ".join(unresolvable))

        if args.apply:
            got = conn.execute(text(
                "SELECT count(*) n, count(adoption_date) d, min(adoption_date) lo, "
                "max(adoption_date) hi FROM ep_resolutions")).fetchone()
            print(f"[VERIFY] rows={got.n} dated={got.d} range={got.lo}..{got.hi}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
