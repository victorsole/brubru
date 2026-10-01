#!/usr/bin/env python3.12
"""Read the missing adoption dates of eu_laws rows from Cellar.

A full walk of /api/v2/legislative/eur-lex/laws over GovClipping's backfill window
(17,947 rows, all 180 pages) found 1,185 serving an empty document_date, a
contracted datapoint. They are real acts -- 651 Regulations, 503 Decisions, 30
Directives -- and every one of them has an adoption date; we simply never stored it.

The date is READ from Cellar, never derived. Cellar is asked for two predicates and
the adoption date is preferred, falling back to publication:

    cdm:work_date_document         the date the act was adopted
    cdm:work_date_creation_legacy  the date it was published in the OJ

A CELEX that Cellar does not answer for is left NULL. An empty cell is honest; a
date inferred from the CELEX year, or from when we happened to import the row, is a
fabrication that would then be served as fact and filtered on.

Batched 80 CELEX per query with a disk cache, so a re-run after an interruption does
not re-ask Cellar for what it already answered.

    python3.12 scripts/backfill_eu_laws_dates.py --rehearse
    python3.12 scripts/backfill_eu_laws_dates.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
_REPO_ROOT = str(BACKEND.parent)
for p in (_REPO_ROOT, str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

BACKUP_DIR = BACKEND.parent / "docs" / "backups"
XSD = "^^<http://www.w3.org/2001/XMLSchema#string>"
BATCH = 80

PICK = text(
    """
    SELECT celex FROM eu_laws
     WHERE date IS NULL AND celex IS NOT NULL AND celex <> ''
     ORDER BY celex
    """
)

SET_DATE = text("UPDATE eu_laws SET date = :d WHERE celex = :celex AND date IS NULL")

COUNT_GAP = text(
    "SELECT count(*) FROM eu_laws WHERE date IS NULL AND celex IS NOT NULL AND celex <> ''"
)


def _query(celexes: list[str]) -> str:
    values = " ".join(f'"{c}"{XSD}' for c in celexes)
    return f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?adopted ?published WHERE {{
  VALUES ?celex {{ {values} }}
  ?work cdm:resource_legal_id_celex ?celex .
  OPTIONAL {{ ?work cdm:work_date_document ?adopted . }}
  OPTIONAL {{ ?work cdm:work_date_creation_legacy ?published . }}
}}
"""


def _val(row: dict, key: str, *, as_date: bool = False):
    """Cellar returns {"value": ...}. Dates are cut to YYYY-MM-DD; identifiers are NOT:
    truncating a CELEX to 10 characters turns 32021R0776R(04) into 32021R0776 and files
    the corrigendum's date under the act it corrects."""
    v = row.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    if not v:
        return None
    return str(v)[:10] if as_date else str(v)


async def resolve(celexes: list[str]) -> dict[str, dict]:
    client = CellarSPARQLClient()
    out: dict[str, dict] = {}
    for i in range(0, len(celexes), BATCH):
        chunk = celexes[i:i + BATCH]
        try:
            rows = await client.select(_query(chunk))
        except Exception as exc:  # recorded, never silently skipped
            print(f"  [ERROR] batch {i // BATCH + 1}: {type(exc).__name__}: {exc}", flush=True)
            continue
        for r in rows:
            celex = _val(r, "celex")
            if celex:
                out[celex] = {"adopted": _val(r, "adopted", as_date=True),
                              "published": _val(r, "published", as_date=True)}
        print(f"  [{min(i + BATCH, len(celexes)):5}/{len(celexes)}] resolved {len(out)}", flush=True)
    return out


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
        celexes = [r.celex for r in conn.execute(PICK)]
        before = conn.execute(COUNT_GAP).scalar_one()
    print(f"[INFO] eu_laws rows with a CELEX and no date: {before}")

    if args.rehearse:
        print(f"[INFO] would ask Cellar for {len(celexes)} CELEX in batches of {BATCH}")
        print(f"[INFO] sample: {celexes[:6]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    cache = BACKUP_DIR / "eu_laws_dates_cache.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    todo = [c for c in celexes if c not in cached]
    if cached:
        print(f"[INFO] {len(cached):,} CELEX already in {cache.name}; asking Cellar for {len(todo):,}")

    found = dict(cached)
    if todo:
        found.update(asyncio.run(resolve(todo)))
        cache.write_text(json.dumps(found, indent=1), encoding="utf-8")

    written = unanswered = 0
    with engine.begin() as conn:
        for celex in celexes:
            rec = found.get(celex) or {}
            d = rec.get("adopted") or rec.get("published")
            if not d:
                unanswered += 1
                continue
            written += conn.execute(SET_DATE, {"d": d, "celex": celex}).rowcount

    with engine.connect() as conn:
        after = conn.execute(COUNT_GAP).scalar_one()

    print(f"\n[INFO] dates written : {written}")
    print(f"[INFO] Cellar had no date for : {unanswered}  (left NULL, never guessed)")
    print(f"[INFO] gap : {before} -> {after}")
    if before - after != written:
        print(f"[ERROR] gap moved by {before - after} but {written} rows were written")
        return 1
    if written == 0 and celexes:
        print("[ERROR] not one date was written; Cellar answered nothing, which is a "
              "failure of the query or the endpoint, not an absence of dates")
        return 1
    print("[OK] every date written was read from Cellar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
