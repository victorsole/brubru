#!/usr/bin/env python3.12
"""Each Commission document's interinstitutional procedure, from Cellar (15 Oct 2026).

Why: /api/v2/commission/commission-register-documents served procedure_ref empty on
1,623 of 1,627 documents. The register sync takes it only from a title that happens to
quote one. Cellar files every proposal, and the staff working documents and other acts
of the same file, in a dossier that carries the procedure:

    52025PC0100 -> work_part_of_dossier -> procedure_code_interinstitutional_reference_procedure
                   "2025/0052/COD"  (OEIL writes it 2025/0052(COD))

Only an empty procedure_ref is written; the register sync never updates the column after
insert, so nothing undoes it. A document Cellar files in no dossier keeps it empty.

    python3.12 scripts/backfill_commission_procedure_refs.py            # dry run
    python3.12 scripts/backfill_commission_procedure_refs.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
_CELEX = re.compile(r"^5\d{4}(?:PC|DC|JC|SC)\d{4}$")
_CELLAR_PROC = re.compile(r"^(\d{4})/(\d{4})/([A-Z]{3})$")

TODO = text("""SELECT id, coalesce(celex, reference) AS celex FROM commission_documents
                WHERE procedure_ref IS NULL
                  AND coalesce(celex, reference) ~ '^5[0-9]{4}(PC|DC|JC|SC)[0-9]{4}$'""")
STORE = text("""UPDATE commission_documents SET procedure_ref = :proc, last_updated = now()
                 WHERE id = :id AND procedure_ref IS NULL""")


def oeil_form(cellar_ref: str) -> str | None:
    """'2025/0052/COD' -> '2025/0052(COD)'; None for anything else."""
    m = _CELLAR_PROC.match((cellar_ref or "").strip())
    return f"{m.group(1)}/{m.group(2)}({m.group(3)})" if m else None


def query(celexes: list[str]) -> dict[str, str]:
    values = " ".join(f'"{c}"^^xsd:string' for c in celexes if _CELEX.match(c))
    q = f"""PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?celex ?proc WHERE {{
  VALUES ?celex {{ {values} }}
  ?w cdm:resource_legal_id_celex ?celex ; cdm:work_part_of_dossier ?d .
  ?d cdm:procedure_code_interinstitutional_reference_procedure ?proc .
}}"""
    data = urllib.parse.urlencode({"query": q}).encode()
    for n in range(3):
        try:
            req = urllib.request.Request(SPARQL, data=data,
                                         headers={"Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                rows = json.load(r)["results"]["bindings"]
            found: dict[str, set[str]] = {}
            for b in rows:
                proc = oeil_form(b["proc"]["value"])
                if proc:
                    found.setdefault(b["celex"]["value"], set()).add(proc)
            # A document filed in two procedures names neither: never guess between them.
            return {c: next(iter(p)) for c, p in found.items() if len(p) == 1}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            if n == 2:
                raise
            time.sleep(10 * (n + 1))
    return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--batch", type=int, default=60)
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1),
                           pool_pre_ping=True)
    with engine.connect() as c:
        rows = c.execute(TODO).fetchall()
    print(f"[INFO] {len(rows)} Commission document(s) without a procedure")
    if not rows:
        return 0
    found = written = 0
    failed_batches = 0
    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        try:
            procs = query([r.celex for r in chunk])
        except Exception as exc:  # noqa: BLE001
            failed_batches += 1
            print(f"[WARN] Cellar did not answer a batch: {type(exc).__name__}")
            continue
        found += len(procs)
        for r in chunk:
            proc = procs.get(r.celex)
            if not proc:
                continue
            if not args.apply:
                if found <= 5:
                    print(f"  {r.celex} -> {proc}")
                continue
            with engine.begin() as c:
                written += c.execute(STORE, {"id": r.id, "proc": proc}).rowcount
        time.sleep(1)
    print(f"[DONE] Cellar names a procedure for {found}; written {written}"
          + ("" if args.apply else " (DRY RUN)"))
    if failed_batches and failed_batches * args.batch >= len(rows):
        print("[ERROR] Cellar answered no batch")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
