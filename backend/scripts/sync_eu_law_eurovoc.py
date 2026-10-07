#!/usr/bin/env python3.12
"""Store the EuroVoc descriptors Cellar assigns to each law (eu_laws.eurovoc).

/laws served policy_area from Brubru's classifier, which guesses: the decision electing
the European Ombudsman read "Energy". The Publications Office indexes every act against
EuroVoc, the EU's own thesaurus, so the classification is read, never inferred.

Per law: the descriptor URIs from Cellar SPARQL (cdm:work_is_about_concept_eurovoc),
resolved to an English label and a EuroVoc domain through eurovoc_concepts (migration
199). eurovoc_domain is the domain most descriptors belong to (ties: lowest notation;
72 GEOGRAPHY only when it is the sole domain).

Three outcomes, kept apart:
  * descriptors found  -> eurovoc = [...], eurovoc_domain set
  * act found, none    -> eurovoc = [] (indexing lags weeks for new acts; re-asked
                          after 7 days while the act is under two years old)
  * act not on Cellar  -> eurovoc NULL, counted and reported, never invented

    python3.12 scripts/sync_eu_law_eurovoc.py --limit 300 --rehearse
    python3.12 scripts/sync_eu_law_eurovoc.py --limit 20000 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from collections import Counter

import httpx
from sqlalchemy import create_engine, text

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
BATCH = 150

PICK = text(
    """
    SELECT id, celex FROM eu_laws
     WHERE celex IS NOT NULL AND celex <> ''
       AND (eurovoc_fetched_at IS NULL
            OR (eurovoc = '[]'::jsonb AND eurovoc_fetched_at < now() - interval '7 days'
                AND coalesce(date, created_at::date) > current_date - 730))
     ORDER BY eurovoc_fetched_at NULLS FIRST, celex
     LIMIT :lim
    """
)

RESOLVE = text(
    """
    SELECT d.concept_uri, d.labels->>'en' AS label, dm.labels->>'en' AS domain
      FROM eurovoc_concepts d
      LEFT JOIN eurovoc_concepts dm ON dm.concept_uri = d.domain_uri
     WHERE d.concept_uri = ANY(:u)
    """
)

STORE = text(
    """
    UPDATE eu_laws
       SET eurovoc = CAST(:ev AS jsonb), eurovoc_domain = :dom, eurovoc_fetched_at = now()
     WHERE id = :rid
    """
)


def _database_url() -> str:
    # The cron runs this inside the Railway container, which has the variable and no .env.
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found")
    return m.group(1).strip()


def _literal(celex: str) -> str:
    return '"' + celex.replace("\\", "\\\\").replace('"', '\\"') + '"^^<http://www.w3.org/2001/XMLSchema#string>'


def descriptors_for(client: httpx.Client, celexes: list[str]) -> dict[str, list[str]]:
    """{celex: [descriptor uri, ...]} for every CELEX Cellar knows; absent = not on Cellar."""
    q = (
        "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
        "SELECT ?c ?ev WHERE { VALUES ?c { " + " ".join(_literal(c) for c in celexes) + " }\n"
        "  ?w cdm:resource_legal_id_celex ?c .\n"
        "  OPTIONAL { ?w cdm:work_is_about_concept_eurovoc ?ev } }"
    )
    for attempt in range(4):
        try:
            r = client.post(SPARQL, data={"query": q},
                            headers={"Accept": "application/sparql-results+json"}, timeout=90)
            r.raise_for_status()
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    out: dict[str, list[str]] = {}
    for b in r.json()["results"]["bindings"]:
        uris = out.setdefault(b["c"]["value"], [])
        ev = b.get("ev", {}).get("value")
        if ev and ev not in uris:
            uris.append(ev)
    return out


GEOGRAPHY = "72 GEOGRAPHY"


def primary_domain(terms: list[dict]) -> str | None:
    """The domain most descriptors belong to; ties go to the lowest notation ("04 POLITICS").

    Geography counts only when it is the act's only domain: it says where, not what, and
    three country names outvoted "accession to the European Union" on 1989 protocols."""
    counts = Counter(t["domain"] for t in terms if t.get("domain"))
    if len(counts) > 1:
        counts.pop(GEOGRAPHY, None)
    if not counts:
        return None
    top = max(counts.values())
    return sorted(d for d, n in counts.items() if n == top)[0]


def build_terms(uris: list[str], known: dict[str, tuple[str, str | None]]) -> list[dict]:
    terms = []
    for u in uris:
        if u not in known:
            continue  # not a descriptor in the thesaurus table: reported, never labelled by guess
        label, domain = known[u]
        terms.append({"id": u.rsplit("/", 1)[-1], "uri": u, "label": label, "domain": domain})
    return sorted(terms, key=lambda t: (t["domain"] or "", t["label"] or ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=300)
    args = ap.parse_args()

    engine = create_engine(_database_url(), pool_pre_ping=True, pool_recycle=300,
                           connect_args={"keepalives": 1, "keepalives_idle": 20, "connect_timeout": 20})
    with engine.connect() as conn:
        rows = list(conn.execute(PICK, {"lim": args.limit}))
    print(f"[INFO] laws to read: {len(rows)}")

    found = with_terms = empty = absent = 0
    unknown_uris: set[str] = set()
    domains: Counter = Counter()
    with httpx.Client() as client:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            got = descriptors_for(client, [r.celex for r in chunk])
            all_uris = sorted({u for v in got.values() for u in v})
            with engine.connect() as conn:
                known = {r.concept_uri: (r.label, r.domain)
                         for r in conn.execute(RESOLVE, {"u": all_uris})} if all_uris else {}
            unknown_uris |= set(all_uris) - set(known)
            params = []
            for r in chunk:
                if r.celex not in got:
                    absent += 1
                    params.append({"rid": r.id, "ev": None, "dom": None})
                    continue
                found += 1
                terms = build_terms(got[r.celex], known)
                dom = primary_domain(terms)
                with_terms += bool(terms)
                empty += not terms
                domains[dom] += 1
                params.append({"rid": r.id, "ev": json.dumps(terms), "dom": dom})
            if args.apply and params:
                for attempt in range(5):
                    try:
                        with engine.begin() as conn:
                            conn.execute(STORE, params)
                        break
                    except Exception:
                        engine.dispose()
                        time.sleep(2 * (attempt + 1))
                else:
                    raise RuntimeError("database unreachable after retries")
            if (i // BATCH) % 10 == 9:
                print(f"   ...{i + len(chunk)}/{len(rows)}", flush=True)

    print(f"[INFO] on Cellar: {found}  with descriptors: {with_terms}  none yet: {empty}  not on Cellar: {absent}")
    print(f"[INFO] descriptor URIs not in eurovoc_concepts: {len(unknown_uris)} {sorted(unknown_uris)[:8]}")
    print(f"[INFO] domains: {domains.most_common(22)}")
    if not args.apply:
        print("[INFO] rehearsal only, nothing written")
        return 0
    if rows and found == 0:
        print("[ERROR] Cellar returned none of the acts: a failure of this run, not an absence")
        return 1
    print("[OK] stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
