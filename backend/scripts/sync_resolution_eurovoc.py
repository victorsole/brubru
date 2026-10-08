#!/usr/bin/env python3.12
"""Store the EuroVoc descriptors Cellar assigns to each EP resolution.

`ep_resolutions.eurovoc_codes` was empty on all 353 rows (8 Oct 2026): nothing filled
it. The Publications Office indexes every resolution it publishes in the OJ C series
against EuroVoc, and each adopted text now carries its real CELEX (read from Cellar by
backfill_texts_adopted_celex.py), so the classification is read, never inferred.

Same reading and shape as /laws (scripts/sync_eu_law_eurovoc.py, whose functions this
reuses): descriptor URIs from Cellar, labels and domains from eurovoc_concepts.
Three states, kept apart:
  * descriptors found -> eurovoc = [...], eurovoc_codes = ids, eurovoc_domain set
  * on Cellar, none   -> eurovoc = [] (re-asked after 7 days)
  * no CELEX yet      -> not picked; NULL until the text reaches the OJ

eurovoc_fetched_at is bookkeeping: the change-signal trigger ignores it (migration
281), so a re-read that finds the same descriptors does not move updated_at.

    python3.12 scripts/sync_resolution_eurovoc.py            # rehearsal
    python3.12 scripts/sync_resolution_eurovoc.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.sync_eu_law_eurovoc import (  # noqa: E402
    BATCH, RESOLVE, _database_url, build_terms, descriptors_for, primary_domain,
)

PICK = text(
    """
    SELECT r.id, t.celex_number AS celex
      FROM ep_resolutions r
      JOIN texts_adopted t ON t.procedure_ref = r.procedure_ref
                          AND t.ta_reference ~ '^P[0-9]+_TA'
     WHERE t.celex_number IS NOT NULL
       AND (r.eurovoc_fetched_at IS NULL
            OR (r.eurovoc = '[]'::jsonb AND r.eurovoc_fetched_at < now() - interval '7 days'))
     ORDER BY r.eurovoc_fetched_at NULLS FIRST, t.celex_number
    """
)

STORE = text(
    """
    UPDATE ep_resolutions
       SET eurovoc = CAST(:ev AS jsonb), eurovoc_domain = :dom,
           eurovoc_codes = :codes, eurovoc_fetched_at = now()
     WHERE id = :rid
    """
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default rehearsal)")
    args = ap.parse_args()

    engine = create_engine(_database_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        rows = list(conn.execute(PICK))
    print(f"[INFO] resolutions to read: {len(rows)}")

    found = with_terms = empty = absent = 0
    unknown: set[str] = set()
    domains: Counter = Counter()
    params: list[dict] = []
    with httpx.Client() as client:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            got = descriptors_for(client, [r.celex for r in chunk])  # raises on failure
            uris = sorted({u for v in got.values() for u in v})
            with engine.connect() as conn:
                known = {k.concept_uri: (k.label, k.domain)
                         for k in conn.execute(RESOLVE, {"u": uris})} if uris else {}
            unknown |= set(uris) - set(known)
            for r in chunk:
                if r.celex not in got:
                    absent += 1  # not stamped: asked again next run
                    continue
                found += 1
                terms = build_terms(got[r.celex], known)
                dom = primary_domain(terms)
                with_terms += bool(terms)
                empty += not terms
                domains[dom] += 1
                params.append({"rid": r.id, "ev": json.dumps(terms), "dom": dom,
                               "codes": [t["id"] for t in terms]})

    print(f"[INFO] on Cellar: {found}  with descriptors: {with_terms}  none yet: {empty}  "
          f"CELEX not on Cellar: {absent}")
    print(f"[INFO] descriptor URIs not in eurovoc_concepts: {len(unknown)} {sorted(unknown)[:8]}")
    print(f"[INFO] domains: {domains.most_common(12)}")
    if rows and found == 0:
        print("[ERROR] Cellar returned none of the resolutions: a failure of this run, not an absence")
        return 1
    if not args.apply:
        print(f"[REHEARSAL] {len(params)} row(s) would be written")
        return 0
    with engine.begin() as conn:
        for p in params:
            conn.execute(STORE, p)
    print(f"[APPLIED] {len(params)} row(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
