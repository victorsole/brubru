#!/usr/bin/env python3
"""Probe the Cellar SPARQL graph to discover the correct CELEX predicate pattern."""

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.api_clients.base_sparql_client import BaseSPARQLClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("probe")


PROBES = [
    ("V1: resource-type authority list (en)", """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?type ?label WHERE {
            ?type skos:prefLabel ?label .
            FILTER(STRSTARTS(STR(?type), "http://publications.europa.eu/resource/authority/resource-type/"))
            FILTER(LANG(?label) = "en")
        } LIMIT 30
    """),
    ("V2: corporate-body authority count", """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT (COUNT(DISTINCT ?body) AS ?n) WHERE {
            ?body skos:prefLabel ?label .
            FILTER(STRSTARTS(STR(?body), "http://publications.europa.eu/resource/authority/corporate-body/"))
        }
    """),
    ("V3: EuroVoc concept 'data protection' (5460)", """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?label ?lang WHERE {
            <http://eurovoc.europa.eu/5460> skos:prefLabel ?label .
            BIND(LANG(?label) AS ?lang)
            FILTER(?lang IN ("en", "fr", "es", "ca", "it", "nl"))
        }
    """),
    ("V4: language authority full list (en labels)", """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?lang ?label WHERE {
            ?lang skos:prefLabel ?label .
            FILTER(STRSTARTS(STR(?lang), "http://publications.europa.eu/resource/authority/language/"))
            FILTER(LANG(?label) = "en")
        } LIMIT 40
    """),
    ("V5: EuroVoc concept count", """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {
            ?c a skos:Concept .
            FILTER(STRSTARTS(STR(?c), "http://eurovoc.europa.eu/"))
        }
    """),
]

PROBES_OLD = [
    ("Probe K: Inverse — what amends/repeals/corrects GDPR", """
        SELECT ?p ?o WHERE {
            ?o ?p <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> .
            FILTER(REGEX(STR(?p), "amend|repeal|modif|correct|consoli|implement|annull|invalidat", "i"))
        } LIMIT 30
    """),
    ("Probe L: GDPR resource_type predicate (search 'type|kind')", """
        SELECT ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ?p ?o .
            FILTER(REGEX(STR(?p), "type|kind|resource-type|legislation", "i"))
        } LIMIT 30
    """),
    ("Probe F: GDPR all predicates (offset 80)", """
        SELECT ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ?p ?o .
        } LIMIT 200 OFFSET 80
    """),
    ("Probe G: GDPR predicates matching 'amend|repeal|modif|chang|consoli'", """
        SELECT ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ?p ?o .
            FILTER(REGEX(STR(?p), "amend|repeal|modif|chang|consoli|implement|correct|invalidat", "i"))
        } LIMIT 50
    """),
    ("Probe H: GDPR force-related predicates", """
        SELECT ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ?p ?o .
            FILTER(REGEX(STR(?p), "force|valid|current", "i"))
        } LIMIT 30
    """),
    ("Probe I: GDPR title via expression", """
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?expr ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ^cdm:expression_belongs_to_work ?expr .
            ?expr cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
            ?expr ?p ?o .
            FILTER(REGEX(STR(?p), "title", "i"))
        } LIMIT 10
    """),
    ("Probe J: A: STR() filter sanity", """
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?celex WHERE {
            ?work cdm:resource_legal_id_celex ?celex .
            FILTER(STR(?celex) = "32016R0679")
        } LIMIT 5
    """),
    ("Probe B: known GDPR cellar URI -> all predicates", """
        SELECT ?p ?o WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> ?p ?o .
        } LIMIT 80
    """),
    ("Probe C: any CELEX with date 2024 (sector 3)", """
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?celex ?date WHERE {
            ?work cdm:resource_legal_id_celex ?celex .
            ?work cdm:work_date_document ?date .
            FILTER(STR(?date) >= "2024-01-01")
            FILTER(STR(?date) < "2024-02-01")
        } LIMIT 10
    """),
    ("Probe D: count any work in graph", """
        SELECT (COUNT(DISTINCT ?work) AS ?n) WHERE {
            ?work a <http://publications.europa.eu/ontology/cdm#work> .
        }
    """),
    ("Probe E: GDPR via cellar URI -> celex predicate value", """
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?celex WHERE {
            <http://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1> cdm:resource_legal_id_celex ?celex .
        }
    """),
]


async def main():
    client = BaseSPARQLClient("https://publications.europa.eu/webapi/rdf/sparql", timeout=120)
    try:
        for label, q in PROBES:
            log.info(f"\n=== {label} ===")
            try:
                results = await client.select(q)
                log.info(f"   rows: {len(results)}")
                for r in results[:10]:
                    log.info(f"   {r}")
            except Exception as e:
                log.error(f"   FAIL: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
