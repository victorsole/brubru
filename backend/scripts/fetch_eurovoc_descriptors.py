"""One-time: fetch all EuroVoc descriptors (concept id + EN label) from the EU
SPARQL endpoint, cache to data/eu_vocabularies/eurovoc_descriptors.json. The
sentence-transformers EuroVoc classifier (Phase 2) embeds these labels."""
import json, sys
from pathlib import Path
import requests

ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
QUERY = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?label WHERE {
  ?c skos:inScheme <http://eurovoc.europa.eu/100141> ;
     skos:prefLabel ?label .
  FILTER(lang(?label) = "en")
}
"""
out = Path("data/eu_vocabularies/eurovoc_descriptors.json")
r = requests.get(ENDPOINT, params={"query": QUERY, "format": "application/sparql-results+json"},
                 headers={"Accept": "application/sparql-results+json"}, timeout=120)
r.raise_for_status()
rows = r.json()["results"]["bindings"]
descs = {}
for b in rows:
    uri = b["c"]["value"]
    cid = uri.rsplit("/", 1)[-1]
    label = b["label"]["value"]
    if cid.isdigit():
        descs[cid] = {"id": cid, "uri": uri, "label": label}
out.write_text(json.dumps(list(descs.values()), ensure_ascii=False))
print(f"[OK] {len(descs)} EuroVoc descriptors cached -> {out}")
print("sample:", list(descs.values())[:3])
