#!/usr/bin/env python3.12
"""Read the CELEX of adopted secondary acts from Cellar, keyed on their C-document number.

After the eu_laws body drain, 1,096 secondary acts still had no body. Almost all of
them have no CELEX at all: the comitology and delegated-acts registers give the
Commission document number (C(2026)1185) and never the OJ number, so the body
fetchers had nothing to ask Cellar for. 664 of them are ADOPTED implementing acts,
which are published in the OJ and do have a CELEX.

Cellar records the C-document number on the act itself, as three typed literals:
resource_legal_internal_number_prefix "C", _year "2026" (xsd:year) and
_sequential_number 1185 (xsd:positiveInteger). Verified on 32026R0441, whose
manuscript reference is C(2026)1185. So the CELEX is READ from the authority, never
derived or matched on a title (a title match hit 5 of 12, two of them ambiguous).

Only an unambiguous answer is stored: exactly one sector-3 CELEX that is not a
corrigendum. Anything else is reported and left NULL. Only empty celex cells are
written.

    python3.12 scripts/backfill_secondary_act_celex_from_cellar.py --rehearse
    python3.12 scripts/backfill_secondary_act_celex_from_cellar.py --apply
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
REF = re.compile(r"^C\((\d{4})\)\s*(\d+)$")
BATCH = 40

PICK = text("""
    SELECT id, reference FROM secondary_acts
     WHERE coalesce(celex, '') = '' AND coalesce(text_body, '') = ''
       AND reference ~ '^C\\([0-9]{4}\\) ?[0-9]+$'
     ORDER BY reference""")
STORE = text("UPDATE secondary_acts SET celex = :c WHERE id = :rid AND coalesce(celex, '') = ''")


def _db_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _ask(pairs: list[tuple[str, str]], ctx) -> dict[tuple[str, str], set[str]]:
    values = " ".join(f'("{y}"^^xsd:year "{n}"^^xsd:positiveInteger)' for y, n in pairs)
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
         "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> "
         f"SELECT ?y ?n ?c WHERE {{ VALUES (?y ?n) {{ {values} }} "
         "?w cdm:resource_legal_internal_number_year ?y ; "
         "cdm:resource_legal_internal_number_sequential_number ?n ; "
         'cdm:resource_legal_internal_number_prefix "C"^^xsd:string ; '
         "cdm:resource_legal_id_celex ?c . }")
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
                data = json.load(r)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for b in data["results"]["bindings"]:
        out[(b["y"]["value"], str(int(b["n"]["value"])))].add(b["c"]["value"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_db_url(), pool_pre_ping=True, pool_recycle=300)
    with engine.connect() as c:
        rows = list(c.execute(PICK))
        # ux_secondary_acts_celex: a CELEX already held by another row means this row
        # is a second record of an act we already have. Never write it twice.
        taken = {r[0]: r[1] for r in c.execute(text(
            "SELECT celex, id FROM secondary_acts WHERE coalesce(celex, '') <> ''"))}
    print(f"[INFO] bodyless acts with a C-number and no CELEX: {len(rows)}")

    keyed = []
    for r in rows:
        m = REF.match(r.reference.strip())
        keyed.append((r.id, r.reference, (m.group(1), str(int(m.group(2))))))

    ctx = ssl.create_default_context(cafile=certifi.where())
    found: dict[tuple[str, str], set[str]] = {}
    pairs = sorted({k for _, _, k in keyed})
    for i in range(0, len(pairs), BATCH):
        found.update(_ask(pairs[i:i + BATCH], ctx))
        time.sleep(0.5)

    verdict: Counter = Counter()
    writes = []
    dupes: list = []
    for rid, ref, k in keyed:
        cands = {c for c in found.get(k, set()) if c.startswith("3") and not c.endswith(")")}
        if not found.get(k):
            verdict["not in Cellar"] += 1
        elif len(cands) != 1:
            verdict[f"ambiguous ({len(cands)})"] += 1
            if len(cands) > 1:
                print(f"   ambiguous {ref}: {sorted(cands)}")
        elif next(iter(cands)) in taken:
            verdict["already held by another row"] += 1
            dupes.append((rid, ref, next(iter(cands)), taken[next(iter(cands))]))
        else:
            writes.append({"rid": rid, "c": next(iter(cands))})
            verdict["resolved"] += 1
    print(f"[INFO] {dict(verdict)}")
    out = BACKEND / "data" / "secondary_act_duplicates.json"
    out.write_text(json.dumps([{"bodyless_id": str(a), "reference": b, "celex": c,
                                "held_by_id": str(d)} for a, b, c, d in dupes], indent=1))
    print(f"[INFO] {len(dupes)} duplicate pairs written to {out.name}")
    for w in writes[:5]:
        print(f"   e.g. {w['c']}")

    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
        return 0
    n = 0
    with engine.begin() as c:
        for w in writes:
            n += c.execute(STORE, w).rowcount
    print(f"[INFO] CELEX stored: {n}")
    if rows and n == 0:
        print("[ERROR] nothing resolved; this run proves nothing")
        return 1
    print("[OK] every stored CELEX was read from Cellar for that C-number")
    return 0


if __name__ == "__main__":
    sys.exit(main())
