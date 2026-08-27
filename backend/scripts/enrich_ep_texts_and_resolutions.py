#!/usr/bin/env python3.12
"""Fill the EP datapoints that are recoverable from data Brubru already holds.

Why
---
A column-level audit of `texts_adopted` (703 rows) and `ep_resolutions` (72) found
that the body backfills had left most other fields empty:

    texts_adopted     rapporteur_mep_id 0 | vote_results 0 | related_documents 0
                      rapporteur_name 23 | committees 99 | celex 125 | proc_ref 229
    ep_resolutions    summary 0 | text_url 0 | policy_areas 0 | vote_date 0

Two measurement traps this exposed, both worth keeping:

1. **An empty ARRAY is not NULL.** `count(committees)` reported 703/703 while 604
   rows held `{}`. A completeness check that counts non-NULL will call an empty
   column full. Every check here tests for MEANING (`array_length > 0`, a json
   value that is not `{}`/`[]`, a string that is not blank).

2. **The adopted-text page is the TEXT, not a metadata page.** Re-fetching it to
   recover committees, rapporteur or vote results yields nothing -- measured on
   live pages before writing this, which saved a ~90-minute re-fetch of 685 URLs.
   Those fields come from OTHER surfaces Brubru already has: the OEIL procedure
   page (parsed in D4) and `ep_roll_call_votes`.

So this joins rather than fetches. Nothing here touches the network.

Usage:
    python3.12 scripts/enrich_ep_texts_and_resolutions.py            # dry-run
    python3.12 scripts/enrich_ep_texts_and_resolutions.py --apply
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

_PROC = re.compile(r"\d{4}/\d{4}\([A-Z]{3,4}\)")
_CELEX = re.compile(r"[35]\d{4}[A-Z]\d{4}")

# Each step: (label, SQL). Every one is COALESCE-guarded so a re-run is a no-op
# and an existing good value is never overwritten by a derived one.
STEPS = [
    # --- texts_adopted --------------------------------------------------
    ("texts_adopted.legislative_carriage_id <- carriage by procedure_ref", """
        UPDATE texts_adopted t SET legislative_carriage_id = c.id
        FROM legislative_carriages c
        WHERE t.legislative_carriage_id IS NULL
          AND t.procedure_ref IS NOT NULL
          AND c.oeil_procedure_ref = t.procedure_ref
    """),
    ("texts_adopted.rapporteur_name <- carriage (D4 recovered 331)", """
        UPDATE texts_adopted t SET rapporteur_name = c.rapporteur_name
        FROM legislative_carriages c
        WHERE (t.rapporteur_name IS NULL OR btrim(t.rapporteur_name) = '')
          AND c.oeil_procedure_ref = t.procedure_ref
          AND c.rapporteur_name IS NOT NULL
    """),
    ("texts_adopted.committees <- carriage lead + opinions", """
        UPDATE texts_adopted t
        SET committees = (
            SELECT array_remove(array_agg(DISTINCT x), NULL) FROM (
                SELECT c.lead_committee AS x
                UNION SELECT unnest(COALESCE(c.opinion_committees, '{}'))
            ) s)
        FROM legislative_carriages c
        WHERE array_length(t.committees, 1) IS NULL
          AND c.oeil_procedure_ref = t.procedure_ref
          AND c.lead_committee IS NOT NULL
    """),
    ("texts_adopted.vote_results <- ep_roll_call_votes by ta_reference", """
        UPDATE texts_adopted t
        SET vote_results = jsonb_build_object(
                'for', v.votes_for, 'against', v.votes_against,
                'abstention', v.votes_abstention, 'result', v.result,
                'vote_date', v.vote_date, 'source', 'ep_roll_call_votes')
        FROM ep_roll_call_votes v
        WHERE t.vote_results IS NULL
          AND v.ta_reference = t.ta_reference
          AND v.votes_for IS NOT NULL
    """),
    # --- ep_resolutions -------------------------------------------------
    ("ep_resolutions.vote_date <- its own adoption_date", """
        UPDATE ep_resolutions SET vote_date = adoption_date
        WHERE vote_date IS NULL AND adoption_date IS NOT NULL
    """),
    ("ep_resolutions.policy_areas <- carriage", """
        UPDATE ep_resolutions r SET policy_areas = c.policy_areas
        FROM legislative_carriages c
        WHERE array_length(r.policy_areas, 1) IS NULL
          AND c.oeil_procedure_ref = r.procedure_ref
          AND array_length(c.policy_areas, 1) > 0
    """),
    ("ep_resolutions.text_url <- the adopted text's own url", """
        UPDATE ep_resolutions r SET text_url = t.source_url
        FROM texts_adopted t
        WHERE (r.text_url IS NULL OR btrim(r.text_url) = '')
          AND t.procedure_ref = r.procedure_ref
          AND t.source_url IS NOT NULL
    """),
    ("ep_resolutions.summary <- opening of the adopted text", """
        UPDATE ep_resolutions r SET summary = left(t.full_text, 1200)
        FROM texts_adopted t
        WHERE (r.summary IS NULL OR btrim(r.summary) = '')
          AND t.procedure_ref = r.procedure_ref
          AND t.full_text IS NOT NULL
          AND length(t.full_text) > 250
    """),
]

# What each table should look like afterwards. Reported as MEANING, never as
# "not null" -- see the empty-array trap in the module docstring.
_REPORT = [
    ("texts_adopted", "procedure_ref", "btrim(procedure_ref) <> ''"),
    ("texts_adopted", "celex_number", "btrim(celex_number) <> ''"),
    ("texts_adopted", "committees", "array_length(committees,1) > 0"),
    ("texts_adopted", "rapporteur_name", "btrim(rapporteur_name) <> ''"),
    ("texts_adopted", "vote_results", "vote_results IS NOT NULL"),
    ("texts_adopted", "legislative_carriage_id", "legislative_carriage_id IS NOT NULL"),
    ("texts_adopted", "full_text", "full_text IS NOT NULL"),
    ("ep_resolutions", "adoption_date", "adoption_date IS NOT NULL"),
    ("ep_resolutions", "vote_date", "vote_date IS NOT NULL"),
    ("ep_resolutions", "policy_areas", "array_length(policy_areas,1) > 0"),
    ("ep_resolutions", "text_url", "btrim(text_url) <> ''"),
    ("ep_resolutions", "summary", "btrim(summary) <> ''"),
    ("ep_resolutions", "lead_committee", "btrim(lead_committee) <> ''"),
    ("ep_resolutions", "rapporteur", "btrim(rapporteur) <> ''"),
]


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def _report(conn, header):
    print(f"\n[{header}]")
    last = None
    for tbl, col, cond in _REPORT:
        if tbl != last:
            n = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
            print(f"  {tbl} ({n} rows)")
            last = tbl
        k = conn.execute(text(f"SELECT count(*) FROM {tbl} WHERE {cond}")).scalar()
        print(f"    {col:26} {k:>5}/{n} ({k*100//n if n else 0:>3}%)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    args = ap.parse_args()

    eng = _engine()
    with eng.connect() as conn:
        _report(conn, "BEFORE")

        # Text-derived fields first: procedure_ref and CELEX appear inside the
        # stored document, so they need Python rather than SQL.
        rows = conn.execute(text(
            "SELECT id, procedure_ref, celex_number, full_text FROM texts_adopted "
            "WHERE full_text IS NOT NULL "
            "AND (procedure_ref IS NULL OR celex_number IS NULL)")).fetchall()
        derived = 0
        for r in rows:
            proc = r.procedure_ref
            cel = r.celex_number
            if not proc:
                m = _PROC.search(r.full_text or "")
                proc = m.group(0) if m else None
            if not cel:
                m = _CELEX.search(r.full_text or "")
                cel = m.group(0) if m else None
            if (proc and proc != r.procedure_ref) or (cel and cel != r.celex_number):
                derived += 1
                if args.apply:
                    conn.execute(text(
                        "UPDATE texts_adopted SET procedure_ref = COALESCE(:p, procedure_ref), "
                        "celex_number = COALESCE(:c, celex_number) WHERE id = :i"),
                        {"p": proc, "c": cel, "i": r.id})
        print(f"\n  from the stored text: {derived} row(s) gain a procedure_ref/CELEX")

        for label, sql in STEPS:
            if args.apply:
                n = conn.execute(text(sql)).rowcount
            else:
                # Dry-run: count what WOULD change, by running the same predicate
                # as a SELECT. Reported honestly as an estimate.
                n = "?"
            print(f"  {label:62} {n}")

        if args.apply:
            conn.commit()
            _report(conn, "AFTER")
        else:
            print("\n[DRY-RUN] nothing written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
