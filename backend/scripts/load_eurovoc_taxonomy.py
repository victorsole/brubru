"""
Backfill eurovoc_concepts: the full EuroVoc thesaurus tree from Cellar SPARQL.

  21 domains  ->  ~128 microthesauri  ->  ~7,029 descriptors  (+ skos:broader tree)

Labels loaded in en/es/fr/it/nl (EuroVoc's languages; Catalan is added later by
the Catalan-translation session, keyed by concept_uri). Idempotent upsert.

Run:  python3.12 scripts/load_eurovoc_taxonomy.py            # full backfill
      python3.12 scripts/load_eurovoc_taxonomy.py --dry-run  # counts only, no DB
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import requests
from psycopg2.extras import Json, execute_values

from core.config import settings

EP = "http://publications.europa.eu/webapi/rdf/sparql"
LANGS = ("en", "es", "fr", "it", "nl")
S_DOMAIN = "http://eurovoc.europa.eu/schema#Domain"
S_MT = "http://eurovoc.europa.eu/schema#MicroThesaurus"
EUROVOC_SCHEME = "http://eurovoc.europa.eu/100141"
LANG_FILTER = 'FILTER(lang(?label) IN ("en","es","fr","it","nl"))'


def sparql(query: str, tries: int = 4):
    for _ in range(tries):
        try:
            r = requests.get(EP, params={"query": query, "format": "application/sparql-results+json"},
                             headers={"Accept": "application/sparql-results+json", "User-Agent": "Mozilla/5.0"},
                             timeout=120)
            if r.status_code == 200:
                return r.json().get("results", {}).get("bindings", [])
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return []


def _notation(label: str) -> str:
    """MT/domain prefLabels are 'CODE name' (e.g. '2826 social affairs', '04 POLITICS')."""
    return (label or "").split(" ", 1)[0].strip()


def fetch_domains() -> dict:
    q = f"""PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
SELECT ?d ?label WHERE {{ ?d a <{S_DOMAIN}> . ?d skos:prefLabel ?label . {LANG_FILTER} }}"""
    out = defaultdict(lambda: {"labels": {}})
    for b in sparql(q):
        uri, lab = b["d"]["value"], b["label"]["value"]
        out[uri]["labels"][b["label"]["xml:lang"]] = lab
    for uri, d in out.items():
        d["notation"] = _notation(d["labels"].get("en", ""))
    return out


def fetch_microthesauri() -> dict:
    q = f"""PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
PREFIX euvoc:<http://publications.europa.eu/ontology/euvoc#>
SELECT ?m ?label ?domain WHERE {{
  ?m a <{S_MT}> . ?m skos:prefLabel ?label . {LANG_FILTER}
  OPTIONAL {{ ?m euvoc:domain ?domain }} }}"""
    out = defaultdict(lambda: {"labels": {}, "domain": None})
    for b in sparql(q):
        uri = b["m"]["value"]
        out[uri]["labels"][b["label"]["xml:lang"]] = b["label"]["value"]
        if b.get("domain"):
            out[uri]["domain"] = b["domain"]["value"]
    for uri, m in out.items():
        m["notation"] = _notation(m["labels"].get("en", ""))
    return out


def fetch_descriptor_structure(mt_uris: set) -> dict:
    """Each descriptor -> its microthesaurus (inScheme, filtered to MT set) and broader parent."""
    q = f"""PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?scheme ?broader WHERE {{
  ?c a skos:Concept ; skos:inScheme <{EUROVOC_SCHEME}> .
  OPTIONAL {{ ?c skos:inScheme ?scheme }}
  OPTIONAL {{ ?c skos:broader ?broader }} }}"""
    out = defaultdict(lambda: {"mt": None, "broader": None})
    for b in sparql(q):
        uri = b["c"]["value"]
        sch = b.get("scheme", {}).get("value")
        if sch in mt_uris:
            out[uri]["mt"] = sch
        if b.get("broader"):
            out[uri]["broader"] = b["broader"]["value"]
    return out


def fetch_descriptor_labels() -> dict:
    """All descriptor prefLabels, ONE LANGUAGE PER QUERY (a 5-language filter blows
    Cellar's ~10k result-row cap; per-language is ~7k rows, comfortably under it).
    Page each language too, in case a single language exceeds the cap."""
    labels = defaultdict(dict)
    for lg in LANGS:
        offset, page = 0, 10000
        while True:
            q = f"""PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?label WHERE {{
  ?c a skos:Concept ; skos:inScheme <{EUROVOC_SCHEME}> ; skos:prefLabel ?label .
  FILTER(lang(?label) = "{lg}")
}} ORDER BY ?c OFFSET {offset} LIMIT {page}"""
            rows = sparql(q)
            for b in rows:
                labels[b["c"]["value"]][lg] = b["label"]["value"]
            if len(rows) < page:
                break
            offset += page
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    print("[eurovoc] fetching domains...", flush=True)
    domains = fetch_domains()
    print(f"  domains: {len(domains)}")
    print("[eurovoc] fetching microthesauri...", flush=True)
    mts = fetch_microthesauri()
    print(f"  microthesauri: {len(mts)}")
    print("[eurovoc] fetching descriptor structure...", flush=True)
    struct = fetch_descriptor_structure(set(mts))
    print(f"  descriptors (structure): {len(struct)}")
    print("[eurovoc] fetching descriptor labels (paged)...", flush=True)
    labels = fetch_descriptor_labels()
    print(f"  descriptors (labelled): {len(labels)}")

    # assemble rows: (uri, notation, type, labels, alt, domain_uri, mt_uri, broader_uri)
    rows = []
    for uri, d in domains.items():
        rows.append((uri, d["notation"], "domain", Json(d["labels"]), None, None, None, None))
    for uri, m in mts.items():
        rows.append((uri, m["notation"], "microthesaurus", Json(m["labels"]), None, m["domain"], None, None))
    desc_uris = set(struct) | set(labels)
    for uri in desc_uris:
        lab = labels.get(uri, {})
        st = struct.get(uri, {})
        mt_uri = st.get("mt")
        dom_uri = mts.get(mt_uri, {}).get("domain") if mt_uri else None
        notation = uri.rstrip("/").split("/")[-1]
        rows.append((uri, notation, "descriptor", Json(lab), None, dom_uri, mt_uri, st.get("broader")))

    from collections import Counter
    print(f"\n[eurovoc] total rows: {len(rows)} | by type:",
          dict(Counter(r[2] for r in rows)))
    if a.dry_run:
        print("dry-run: not writing.")
        return

    conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); conn.autocommit = True
    cur = conn.cursor()
    execute_values(cur, """
        INSERT INTO eurovoc_concepts
          (concept_uri, notation, concept_type, labels, alt_labels, domain_uri, microthesaurus_uri, broader_uri)
        VALUES %s
        ON CONFLICT (concept_uri) DO UPDATE SET
          notation=EXCLUDED.notation, concept_type=EXCLUDED.concept_type,
          labels = eurovoc_concepts.labels || EXCLUDED.labels,   -- keep any 'ca' already added
          domain_uri=EXCLUDED.domain_uri, microthesaurus_uri=EXCLUDED.microthesaurus_uri,
          broader_uri=EXCLUDED.broader_uri, updated_at=NOW();
    """, rows, page_size=1000)
    cur.execute("SELECT concept_type, count(*) FROM eurovoc_concepts GROUP BY 1 ORDER BY 2 DESC")
    print("[eurovoc] eurovoc_concepts written:", cur.fetchall())
    conn.close()


if __name__ == "__main__":
    main()
