#!/usr/bin/env python3.12
"""Give every adopted text its CELEX number, read from Cellar.

Why
---
`texts_adopted.celex_number` held identifiers that do not exist (8 Oct 2026):
97 rows `5YYYYATNNNN`, a type Cellar never issued (6 of 6 sampled: HTTP 404),
written by a writer gone since April. A second writer, still live, filled an empty
value with the first CELEX-shaped string in the adopted text, which is an act the
text CITES (single-letter types such as R or L), never the text's own number.

Cellar links the two itself: the work for an EP adopted text carries
`cdm:work_id_document "immc:P10_TA(2026)0086"` next to its real
`cdm:resource_legal_id_celex "52026IP0086"`. This job reads that link and nothing
else. A text that Cellar does not hold yet (it reaches the Official Journal C
series months after the vote) gets NULL, which reads as "not published in the OJ
yet", never as a guessed number.

Owner of `texts_adopted.celex_number`. Scheduled in the warm tier, so a text gains
its CELEX on the run after Cellar publishes it.

Safety: a failed Cellar batch aborts the run with exit 1 BEFORE anything is
written. An outage must never read as "Cellar holds none" and clear good values.

Usage:
    python3.12 scripts/backfill_texts_adopted_celex.py            # dry-run
    python3.12 scripts/backfill_texts_adopted_celex.py --apply
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

BATCH = 100

_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?id ?celex WHERE {{
  VALUES ?id {{ {values} }}
  ?w cdm:work_id_document ?id .
  ?w cdm:resource_legal_id_celex ?celex .
}}"""

# Only the row's value moves; the touch trigger stamps last_updated when it changes.
_UPDATE = """
UPDATE texts_adopted SET celex_number = :celex
WHERE id = :id AND celex_number IS DISTINCT FROM :celex
"""


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


async def _cellar_celex(refs: list[str]) -> dict[str, set[str]]:
    """ta_reference -> the CELEX numbers Cellar links to it. Raises on any failure."""
    found: dict[str, set[str]] = {}
    async with CellarSPARQLClient(enable_cache=False) as client:
        for i in range(0, len(refs), BATCH):
            chunk = refs[i:i + BATCH]
            values = " ".join(f'"immc:{r}"^^xsd:string' for r in chunk)
            rows = await client.select(_QUERY.format(values=values))
            if rows is None:
                raise RuntimeError(f"Cellar returned nothing usable for batch {i // BATCH + 1}")
            for row in rows:
                ref = (row.get("id") or "").removeprefix("immc:")
                if ref and row.get("celex"):
                    found.setdefault(ref, set()).add(row["celex"])
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="Persist (default dry-run)")
    args = ap.parse_args()

    eng = _engine()
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, ta_reference, celex_number, ta_reference ~ '^P[0-9]+_TA' AS adopted "
            "FROM texts_adopted ORDER BY ta_reference")).fetchall()
    # Committee REPORTS (A10/...) share the table but are not published in the OJ,
    # so they have no CELEX of their own: A10/2026/0100 carried 32004L0037, a
    # directive it cites. They are set to NULL and never looked up.
    adopted = [r for r in rows if r.adopted]
    print(f"[INFO] {len(adopted)} adopted text(s) to look up on Cellar "
          f"({len(rows) - len(adopted)} report row(s) carry no CELEX of their own)")

    try:
        found = asyncio.run(_cellar_celex([r.ta_reference for r in adopted]))
    except Exception as exc:  # noqa: BLE001 -- any failure aborts before a write
        print(f"[ERROR] Cellar lookup failed, nothing written: {type(exc).__name__}: {exc}")
        return 1

    plan, ambiguous = [], []
    kept = set_new = corrected = cleared = still_none = 0
    for r in rows:
        celexes = found.get(r.ta_reference, set()) if r.adopted else set()
        # A corrigendum is its own work; the text's number is the one without "R(..)".
        base = {c for c in celexes if "R(" not in c}
        if len(base) > 1:
            ambiguous.append((r.ta_reference, sorted(base)))
            continue  # never guess between two
        new = next(iter(base), None)
        if new == r.celex_number:
            kept += new is not None
            still_none += new is None
            continue
        if new and r.celex_number is None:
            set_new += 1
        elif new:
            corrected += 1
        else:
            cleared += 1
        plan.append((r.id, r.ta_reference, r.celex_number, new))

    print(f"[INFO] Cellar holds a CELEX for {sum(1 for r in adopted if found.get(r.ta_reference))} "
          f"of {len(adopted)}; the rest are not in the Official Journal yet")
    print(f"[INFO] unchanged={kept} set={set_new} corrected={corrected} "
          f"cleared={cleared} still_unpublished={still_none} ambiguous={len(ambiguous)}")
    for a in ambiguous[:10]:
        print(f"   [AMBIGUOUS] {a[0]}: {a[1]}")
    for _, ref, old, new in plan[:12]:
        print(f"   {ref:20} {str(old):14} -> {new}")

    if not args.apply:
        print(f"\n[DRY-RUN] {len(plan)} row(s) would change.")
        return 0

    written = 0
    with eng.begin() as conn:
        for row_id, _, _, new in plan:
            written += conn.execute(text(_UPDATE), {"id": row_id, "celex": new}).rowcount
    print(f"[APPLIED] {written} row(s) written")
    if written != len(plan):
        print(f"[ERROR] planned {len(plan)} but wrote {written}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
