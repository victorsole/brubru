#!/usr/bin/env python3.12
"""Backfill the `ep_resolutions` CORPUS from adopted texts Brubru already holds.

Why
---
D3 was recorded as "72 rows, adoption_date NULL on every one". Fixing the dates
answered half of it. The other half is that **72 rows is not the corpus**: the
D2 backfill brought `texts_adopted` to 703 rows, and 157 of those are
resolution-typed texts with no `ep_resolutions` row at all.

Scope, and why it is not all 157
--------------------------------
`ep_resolutions.resolution_type` is an enum of **INL / INI / RSP / OTHER**, and
the 72 existing rows are RSP (43), INI (28), INL (1). That is the table's
subject: own-initiative and topical resolutions.

Of the 157 missing:

    INI  41  |  RSP  31   <- belong here; same taxonomy as every existing row
    COD  33  |  NLE  28  |  CNS 3  |  APP 2  |  BUI 2  |  DEA 1  |  BUD 1
                          <- legislative procedures. The EP's output there is a
                             legislative resolution (its reading position), a
                             different instrument. Typing 66 of them OTHER would
                             double the table while diluting what it means.
    (none) 15             <- no procedure_ref, and that column is NOT NULL and
                             UNIQUE, so they cannot be keyed at all.

So this inserts the 72 that match the table's own taxonomy, and the endpoint's
coverage note states that legislative-procedure texts live in `texts_adopted`
rather than implying they do not exist.

Every field comes from data already held -- adopted text, the OEIL procedure page
parsed in D4, and the roll-call votes. Nothing is fetched.

Usage:
    python3.12 scripts/backfill_ep_resolutions_corpus.py            # dry-run
    python3.12 scripts/backfill_ep_resolutions_corpus.py --apply
"""
import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from services.comparator.cell_extractors import _oeil_url  # noqa: E402

# Only the procedure kinds this table is about. Anything else is deliberately
# left in texts_adopted rather than typed OTHER to inflate the count.
ACCEPTED = {"INI", "RSP", "INL"}
_SUFFIX = re.compile(r"\(([A-Z]+)\)")

_CANDIDATES = """
SELECT t.procedure_ref,
       t.title,
       t.adoption_date::date            AS adoption_date,
       t.source_url                     AS text_url,
       left(t.full_text, 1200)          AS summary,
       t.vote_results,
       COALESCE(c.lead_committee, NULL) AS lead_committee,
       COALESCE(c.rapporteur_name, t.rapporteur_name) AS rapporteur,
       c.policy_areas
FROM texts_adopted t
LEFT JOIN legislative_carriages c ON c.oeil_procedure_ref = t.procedure_ref
WHERE t.text_type::text IN ('resolution', 'legislative_resolution')
  AND t.procedure_ref IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ep_resolutions r WHERE r.procedure_ref = t.procedure_ref)
"""

# ON CONFLICT on the real unique key. A re-run updates rather than duplicating.
_INSERT = """
INSERT INTO ep_resolutions
    (id, procedure_ref, title, resolution_type, adoption_date, vote_date,
     lead_committee, rapporteur, summary, policy_areas,
     vote_for, vote_against, vote_abstention, vote_total,
     oeil_url, text_url, has_commission_followup, created_at, updated_at)
VALUES
    (gen_random_uuid(), :ref, :title, CAST(:rtype AS resolution_type_enum), :adopted, :adopted,
     :lead, :rapporteur, :summary, :policy_areas,
     :vfor, :vagainst, :vabst, :vtotal,
     :oeil, :text_url, false, now(), now())
ON CONFLICT (procedure_ref) DO UPDATE SET
    title          = EXCLUDED.title,
    adoption_date  = COALESCE(ep_resolutions.adoption_date, EXCLUDED.adoption_date),
    summary        = COALESCE(ep_resolutions.summary, EXCLUDED.summary),
    text_url       = COALESCE(ep_resolutions.text_url, EXCLUDED.text_url),
    updated_at     = now()
RETURNING (xmax = 0) AS inserted
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def _votes(vote_results):
    """Pull the tally out of the vote_results json, if it carries one."""
    if not isinstance(vote_results, dict):
        return (None, None, None, None)
    f = vote_results.get("for")
    a = vote_results.get("against")
    b = vote_results.get("abstention")
    total = None
    if all(isinstance(x, int) for x in (f, a, b)):
        total = f + a + b
    return (f, a, b, total)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    args = ap.parse_args()

    with _engine().connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM ep_resolutions")).scalar()
        rows = conn.execute(text(_CANDIDATES)).mappings().all()

        accepted, skipped = [], {}
        for r in rows:
            m = _SUFFIX.search(r["procedure_ref"] or "")
            kind = m.group(1) if m else None
            if kind in ACCEPTED:
                accepted.append((r, kind))
            else:
                skipped[kind or "(none)"] = skipped.get(kind or "(none)", 0) + 1

        print(f"[INFO] ep_resolutions holds {before} row(s)")
        print(f"[INFO] {len(rows)} resolution-typed adopted text(s) have no row here")
        print(f"[INFO] {len(accepted)} match this table's taxonomy "
              f"({'/'.join(sorted(ACCEPTED))}) and will be added")
        # Name what is being left out, with the reason, so the number is readable.
        if skipped:
            print(f"[INFO] {sum(skipped.values())} deliberately NOT added -- legislative "
                  f"procedures, which belong to texts_adopted: {skipped}")

        if not args.apply:
            for r, kind in accepted[:10]:
                print(f"   [{kind}] {r['procedure_ref']:20} {str(r['adoption_date']):11} "
                      f"{str(r['title'])[:48]}")
            print(f"\n[DRY-RUN] {len(accepted)} row(s) would be written.")
            return 0

        ins = upd = 0
        for r, kind in accepted:
            f, a, b, total = _votes(r["vote_results"])
            got = conn.execute(text(_INSERT), {
                "ref": r["procedure_ref"], "title": r["title"], "rtype": kind,
                "adopted": r["adoption_date"], "lead": r["lead_committee"],
                "rapporteur": r["rapporteur"], "summary": r["summary"],
                "policy_areas": r["policy_areas"] or [],
                "vfor": f, "vagainst": a, "vabst": b, "vtotal": total,
                "oeil": _oeil_url(r["procedure_ref"]), "text_url": r["text_url"],
            }).fetchone()
            if got and got.inserted:
                ins += 1
            else:
                upd += 1
        conn.commit()

        after = conn.execute(text("SELECT count(*) FROM ep_resolutions")).scalar()
        print(f"[APPLIED] inserted={ins} updated={upd} | ep_resolutions {before} -> {after}")

        # Verify from the table, per column, testing MEANING not non-NULL.
        for col, cond in (("adoption_date", "adoption_date IS NOT NULL"),
                          ("summary", "btrim(summary) <> ''"),
                          ("text_url", "btrim(text_url) <> ''"),
                          ("lead_committee", "btrim(lead_committee) <> ''"),
                          ("policy_areas", "array_length(policy_areas,1) > 0"),
                          ("vote_for", "vote_for IS NOT NULL")):
            k = conn.execute(text(f"SELECT count(*) FROM ep_resolutions WHERE {cond}")).scalar()
            print(f"[VERIFY] {col:16} {k:>4}/{after} ({k*100//after if after else 0:>3}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
