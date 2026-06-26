"""One-time: fetch all EuroVoc descriptors (concept id + EN label + microthesaurus
domain code) from the EU SPARQL endpoint, cache to
data/eu_vocabularies/eurovoc_descriptors.json. The sentence-transformers EuroVoc
classifier (Phase 2) embeds the labels and uses the microthesaurus code (`mt`) to
exclude organisation / institution / treaty NAMES from subject classification.

The `mt` field is load-bearing: without it the classifier's _keep() filter degrades
to keeping every descriptor, and organisation names ("Pacific Islands Forum") and
treaty names ("EAEC Treaty") leak back into the subject tags. Always regenerate with
this script so the field is preserved."""
import json
from pathlib import Path
import requests

ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
EUROVOC = "<http://eurovoc.europa.eu/100141>"

# 1) descriptor id + EN label
QUERY_LABELS = f"""
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?label WHERE {{
  ?c skos:inScheme {EUROVOC} ; skos:prefLabel ?label .
  FILTER(lang(?label) = "en")
}}
"""

# 2) descriptor -> its microthesaurus (the second inScheme, a domain-scheme with a label)
QUERY_MT = f"""
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?mt WHERE {{
  ?c skos:inScheme {EUROVOC} ; skos:inScheme ?mt .
  ?mt skos:prefLabel ?mtl .
  FILTER(?mt != {EUROVOC})
}}
"""

# 3) microthesaurus uri -> "NNNN <name>" (we keep the leading 4-digit domain code)
QUERY_MT_LABELS = f"""
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?mt ?l WHERE {{
  ?d skos:inScheme {EUROVOC} ; skos:inScheme ?mt .
  ?mt skos:prefLabel ?l . FILTER(lang(?l)="en") FILTER(?mt != {EUROVOC})
}} GROUP BY ?mt ?l
"""


def _run(query):
    r = requests.get(ENDPOINT, params={"query": query, "format": "application/sparql-results+json"},
                     headers={"Accept": "application/sparql-results+json"}, timeout=180)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def main():
    out = Path("data/eu_vocabularies/eurovoc_descriptors.json")

    descs = {}
    for b in _run(QUERY_LABELS):
        uri = b["c"]["value"]
        cid = uri.rsplit("/", 1)[-1]
        if cid.isdigit():
            descs[cid] = {"id": cid, "uri": uri, "label": b["label"]["value"], "mt": None}

    mt_code = {b["mt"]["value"].rsplit("/", 1)[-1]: b["l"]["value"].split()[0]
               for b in _run(QUERY_MT_LABELS)}  # 100xxx -> "7616"
    enriched = 0
    for b in _run(QUERY_MT):
        cid = b["c"]["value"].rsplit("/", 1)[-1]
        mt = mt_code.get(b["mt"]["value"].rsplit("/", 1)[-1])
        if cid in descs and mt:
            descs[cid]["mt"] = mt
            enriched += 1

    out.write_text(json.dumps(list(descs.values()), ensure_ascii=False))
    print(f"[OK] {len(descs)} EuroVoc descriptors cached ({enriched} with microthesaurus) -> {out}")
    print("sample:", list(descs.values())[:3])


if __name__ == "__main__":
    main()
