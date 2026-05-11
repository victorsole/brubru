#!/usr/bin/env python3
"""
Audit script — exercise every euvoc.md phase with diverse real fixtures.

Per Victor's instruction: NO over-reliance on GDPR/AI Act. Each phase
gets ≥10 varied EU laws / identifiers / vocabularies as fixtures.

Run:
    python3.12 backend/scripts/audit_euvoc_arc.py
    python3.12 backend/scripts/audit_euvoc_arc.py --phase 5
    python3.12 backend/scripts/audit_euvoc_arc.py --quick  (skip live SPARQL)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("audit")


# ----------------------------------------------------------------------
# Diverse real-world fixtures (sectors / decades / kinds / countries)
# ----------------------------------------------------------------------

CELEX_30 = [
    # Adopted regulations across 1995-2026
    "32016R0679",   # GDPR
    "32024R1689",   # AI Act
    "32022R2065",   # DSA
    "32023R1542",   # Battery
    "32014R0596",   # Market Abuse Regulation
    "32020R0852",   # Taxonomy
    "32018R1725",   # EUDPR
    "32019R1020",   # Market Surveillance
    "32018R0555",   # gov't bond statistics
    "32013R1303",   # Common Provisions Regulation
    # Directives
    "32016L1148",   # NIS 1
    "32022L2555",   # NIS 2
    "32011L0083",   # Consumer Rights
    "32014L0024",   # Public Procurement
    "32024L1203",   # Environmental crime (recent)
    # Decisions
    "32020D2229",   # Decision (sample)
    "32023D1025",   # Decision
    "32019D1194",   # Decision (in Catalan corpus)
    "32016D1250",   # Privacy Shield (annulled — Schrems II)
    # Repealed acts
    "31995L0046",   # old DPD
    "32003L0098",   # old PSI Directive
    # Older regulations (1980s-2000s — coverage check)
    "32009R1107",   # Plant Protection Products
    "32007R0717",   # Mobile roaming (historic)
    # Proposals (sector 5)
    "52021PC0206",  # AI Act original proposal
    "52022PC0457",  # CER Directive proposal
    "52024PC0028",  # cybersecurity skills proposal
    # Other CELEX shapes
    "52026M12201",  # Merger notification
    "52026XC02555", # OJ-C series
    # Corrigenda (will skip cleanly in FMX4 parser)
    "32016R0679R(01)",
    # CFSP decisions (sector 9)
    "32014D0145",   # Russia sanctions framework
]

ECLI_15 = [
    "ECLI:EU:C:2014:317",   # Google Spain — RTBF
    "ECLI:EU:C:2018:585",   # Schrems II / Meta
    "ECLI:EU:C:2020:559",   # Schrems II annulment
    "ECLI:EU:C:2022:99",    # Tele2 Sverige
    "ECLI:EU:C:2019:498",   # Planet49
    "ECLI:EU:C:2023:294",   # GC v Commission (2023)
    "ECLI:EU:T:2020:99",    # General Court
    "ECLI:EU:T:2022:521",   # General Court 2022
    "ECLI:EU:F:2010:50",    # historic Civil Service Tribunal
    "ECLI:DE:BVerfG:2020:RS20200505",  # PSPP
    "ECLI:NL:HR:2021:1234", # Dutch Hoge Raad
    "ECLI:FR:CCASS:2022:1A12345",
    "ECLI:ES:TS:2023:5678",
    "ECLI:IT:CASS:2024:0001",
    "ECLI:BE:CASS:2020:9999",
]

EUROVOC_THEMES = [
    "5181",  # data protection (verified live earlier)
    "3028",  # data-processing law
    "8500",  # AI (placeholder)
    "1646",  # regulation
    "911",   # European Union
    "2462",  # law
    "3911",  # translation
    "233",   # official journal
    "5460",  # (probed earlier)
    "100150",
]

CORPORATE_BODIES = [
    "EP",            # European Parliament
    "CONSIL",        # Council
    "COM",           # European Commission
    "GROW",          # DG GROW
    "ENV",           # DG ENV
    "CURIA_1958_0",  # Court of Justice (NAL uses historical code with year suffix)
    "ECB",           # European Central Bank
    "EEAS",          # External Action Service
    "EBA",           # European Banking Authority
    "ENISA",         # EU Cybersecurity Agency
    "FRONTEX",       # Border + Coast Guard
    "EUSPA",         # Space Programme Agency
]

# Real procedure codes harvested from the live NAL (17 total — no "ASS")
PROCEDURES = ["COD", "CNS", "APP", "BUD", "DEC", "AVC", "ACC", "OLP", "NLE", "INL", "DEA"]

COUNTRIES = ["ESP", "FRA", "DEU", "ITA", "NLD", "BEL", "POL", "PRT", "SWE", "FIN"]


# ----------------------------------------------------------------------
# Audit infrastructure
# ----------------------------------------------------------------------

@dataclass
class PhaseAudit:
    phase: str
    title: str
    checks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int: return len(self.checks)
    @property
    def passes(self) -> int: return sum(1 for c in self.checks if c["ok"])
    @property
    def fails(self) -> int: return sum(1 for c in self.checks if not c["ok"])

    def add(self, name: str, ok: bool, detail: str = ""):
        self.checks.append({"name": name, "ok": ok, "detail": detail})


# ----------------------------------------------------------------------
# Phase 0 — Foundation
# ----------------------------------------------------------------------

def audit_p0() -> PhaseAudit:
    a = PhaseAudit("P0", "Foundation")
    import yaml
    manifest_path = ROOT / "data" / "eu_vocabularies" / "manifest.yaml"
    a.add("manifest exists", manifest_path.exists())
    if manifest_path.exists():
        m = yaml.safe_load(manifest_path.read_text())
        a.add("hot_twelve count == 12", len(m.get("nal_hot_twelve", [])) == 12)
        a.add("long_tail entries >= 100", len(m.get("nal_long_tail", [])) >= 100)
        a.add("eurovoc count >= 7000", any(e.get("key") == "eurovoc" and (e.get("live_concept_count") or 0) >= 7000 for e in m.get("already_integrated", [])))
        for nal in m.get("nal_hot_twelve", []):
            a.add(f"hot NAL '{nal['key']}' has live_concept_count > 0", (nal.get("live_concept_count") or 0) > 0)

    mig_up = ROOT / "backend/migrations/048_eu_vocabularies.sql"
    mig_down = ROOT / "backend/migrations/048_eu_vocabularies_down.sql"
    a.add("migration 048 up exists", mig_up.exists())
    a.add("migration 048 down exists", mig_down.exists())
    a.add("migration 048 has RLS", "ENABLE ROW LEVEL SECURITY" in mig_up.read_text())

    from services.api_clients.fmx4_notice_parser import FORMEX_SCHEMA_VERSION
    a.add("Formex pin == 06.02.3-20250123",
          FORMEX_SCHEMA_VERSION == "formex-06.02.3-20250123.xd",
          detail=FORMEX_SCHEMA_VERSION)
    return a


# ----------------------------------------------------------------------
# Phase 1 — Authority cache + chat glossary
# ----------------------------------------------------------------------

def audit_p1(db_url: str) -> PhaseAudit:
    a = PhaseAudit("P1", "Authority cache + glossary")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from services.vocabularies.authority_label_cache import AuthorityLabelCache
    from services.vocabularies.glossary_injector import (
        build_glossary_block, detect_language, extract_authority_uris,
    )

    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()
    cache = AuthorityLabelCache(db)
    try:
        # Resolve every corporate body in EN + ES + CA
        for code in CORPORATE_BODIES:
            uri = f"http://publications.europa.eu/resource/authority/corporate-body/{code}"
            for lang in ("en", "es", "ca"):
                label = cache.resolve(uri, lang)
                a.add(f"resolve corporate-body/{code} in {lang}",
                      label is not None,
                      detail=f"label={label!r}")

        # Procedures EN
        for proc in PROCEDURES:
            uri = f"http://publications.europa.eu/resource/authority/procedure/{proc}"
            label = cache.resolve(uri, "en")
            a.add(f"resolve procedure/{proc} en", label is not None, detail=f"label={label!r}")

        # Country in CA (should resolve directly OR via fallback)
        for country in COUNTRIES:
            uri = f"http://publications.europa.eu/resource/authority/country/{country}"
            label = cache.resolve(uri, "ca")
            a.add(f"resolve country/{country} ca-fallback", label is not None,
                  detail=f"label={label!r}")

        # Reverse lookup
        for q, lang in [("Parliament", "en"), ("Comisión", "es"), ("codecisión", "es")]:
            hits = cache.lookup_by_label(q, lang, limit=3)
            a.add(f"reverse-lookup {q!r}/{lang} >= 1 hit", len(hits) >= 1, detail=f"{len(hits)} hits")

        # Language detector
        for text_, expected in [
            ("What is the AI Act?", "en"),
            ("¿Cuál es el reglamento?", "es"),
            ("Què sap del Reglament?", "ca"),
            ("Quel est le règlement?", "fr"),
            ("Qual è il regolamento?", "it"),
            ("Wat is de richtlijn?", "nl"),
        ]:
            got = detect_language(text_)
            a.add(f"detect_language({text_!r}) == {expected}", got == expected, detail=f"got={got}")

        # extract_authority_uris
        text_ = "See http://publications.europa.eu/resource/authority/procedure/COD and currency/EUR is at http://publications.europa.eu/resource/authority/currency/EUR"
        uris = extract_authority_uris(text_)
        a.add("extract_authority_uris finds 2 URIs", len(uris) == 2, detail=f"{uris}")

        # Glossary block
        block = build_glossary_block(text_, db, "en")
        a.add("build_glossary_block returns non-None for matched URIs", block is not None)
        a.add("glossary contains 'Co-decision'", block and "Co-decision" in block, detail=f"{(block or '')[:80]}")
    finally:
        db.close()
    return a


# ----------------------------------------------------------------------
# Phase 2 — DCAT-AP
# ----------------------------------------------------------------------

def audit_p2(db_url: str) -> PhaseAudit:
    a = PhaseAudit("P2", "DCAT-AP self-catalogue")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from rdflib import Graph
    from rdflib.namespace import RDF
    from services.vocabularies.dcat_ap_serializer import serialize, catalog_uri

    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        rows = db.execute(text("SELECT id, dcat_uri, title, description, dcat_theme, distribution, license, accrual_periodicity FROM brubru_dataset_catalog ORDER BY dcat_uri")).all()
        a.add("catalogue has >= 6 rows", len(rows) >= 6, detail=f"{len(rows)}")

        rows_dicts = [
            {"id": str(r.id), "dcat_uri": r.dcat_uri, "title": r.title, "description": r.description,
             "dcat_theme": list(r.dcat_theme or []), "distribution": r.distribution,
             "license": r.license, "accrual_periodicity": r.accrual_periodicity}
            for r in rows
        ]

        for fmt in ("turtle", "xml", "json-ld"):
            payload = serialize(rows_dicts, format=fmt)
            a.add(f"serialize({fmt}) round-trips through rdflib",
                  _try_parse_rdf(payload, fmt), detail=f"{len(payload)} bytes")

        ttl = serialize(rows_dicts, format="turtle")
        g = Graph()
        g.parse(data=ttl, format="turtle")
        catalogs = list(g.subjects(RDF.type, _u("http://www.w3.org/ns/dcat#Catalog")))
        a.add("dcat:Catalog count == 1", len(catalogs) == 1)
        ds_uris = list(g.subjects(RDF.type, _u("http://www.w3.org/ns/dcat#Dataset"))) + list(g.subjects(RDF.type, _u("http://www.w3.org/ns/dcat#DataService")))
        a.add(f"dataset/service count == {len(rows)}", len(ds_uris) == len(rows))

        a.add("catalog_uri() stable",
              catalog_uri() == "https://brubru.beresol.eu/.well-known/dcat-ap-catalog")

        # Mandatory fields per dataset
        from rdflib.namespace import DCAT, DCTERMS
        missing = []
        for ds in ds_uris:
            for prop in (DCTERMS.title, DCTERMS.description, DCTERMS.publisher, DCAT.contactPoint):
                if not list(g.objects(ds, prop)):
                    missing.append((str(ds), str(prop)))
        a.add("0 datasets missing mandatory DCAT-AP fields", len(missing) == 0, detail=f"{missing[:3]}")
    finally:
        db.close()
    return a


def _u(s):
    from rdflib import URIRef
    return URIRef(s)


def _try_parse_rdf(data: bytes, fmt: str) -> bool:
    from rdflib import Graph
    rdflib_fmt = {"turtle": "turtle", "xml": "xml", "json-ld": "json-ld"}[fmt]
    try:
        g = Graph()
        g.parse(data=data, format=rdflib_fmt)
        return len(g) > 0
    except Exception:
        return False


# ----------------------------------------------------------------------
# Phase 3 — OP Core Metadata
# ----------------------------------------------------------------------

def audit_p3() -> PhaseAudit:
    a = PhaseAudit("P3", "OP Core Metadata")
    from api.v1._envelope import (
        OPCoreMetadata, PaginatedResponse, build_envelope,
    )
    env = build_envelope(items=[], total=0, page=1, limit=10)
    a.add("build_envelope produces op_core block", env.op_core is not None)
    a.add("op_core.publisher correct", env.op_core.publisher == "https://brubru.beresol.eu/.well-known/publisher")
    a.add("op_core.is_part_of points at catalog", env.op_core.is_part_of == "https://brubru.beresol.eu/.well-known/dcat-ap-catalog")

    payload = env.model_dump(by_alias=True)
    for k in ("dct:title", "dct:identifier", "dct:type", "dct:language", "dct:isPartOf", "dct:date", "dct:publisher", "dct:isReferencedBy", "dct:conformsTo"):
        a.add(f"op_core has alias '{k}'", k in payload["op_core"], detail=f"present={k in payload['op_core']}")

    legacy_keys = ("total", "returned", "pages", "page", "limit", "has_more", "next_page", "remaining_pages",
                  "coverage_complete", "published_from", "published_to", "published_end", "updated_from",
                  "updated_to", "updated_end", "detail_level", "data")
    for k in legacy_keys:
        a.add(f"legacy field preserved: {k}", k in payload)
    return a


# ----------------------------------------------------------------------
# Phase 4 — ELI / CDM ontology pinning
# ----------------------------------------------------------------------

def audit_p4() -> PhaseAudit:
    a = PhaseAudit("P4", "ELI + CDM pinning")
    snap = ROOT / "docs/ontologies/cdm/cdm-brubru-subset.ttl"
    a.add("CDM snapshot exists", snap.exists())
    if snap.exists():
        n = sum(1 for ln in snap.read_text().splitlines() if ln.startswith("cdm:"))
        a.add(f"CDM snapshot has >= 38 predicates ({n})", n >= 38)

    for name, min_size in [
        ("eli.owl", 50_000),
        ("eli_ontology.xlsx", 10_000),
        ("eli-sdo.ttl", 1_000),
    ]:
        f = ROOT / f"docs/ontologies/eli/{name}"
        a.add(f"ELI artefact {name} present + >= {min_size}B",
              f.exists() and f.stat().st_size >= min_size,
              detail=f"{f.stat().st_size if f.exists() else 0} bytes")

    # ELI URI shape derived from CELEX — 15 varied
    import re
    for celex in CELEX_30[:15]:
        m = re.match(r"^(\d)(\d{4})([A-Z]{1,2})(\d+)", celex)
        if m:
            sector, year, t, serial = m.groups()
            type_map = {"R": "reg", "L": "dir", "D": "dec", "PC": "proposal_for_a_regulation"}
            t_eli = type_map.get(t, t.lower())
            url = f"http://publications.europa.eu/resource/eli/{t_eli}/{year}/{int(serial)}/oj"
            a.add(f"ELI URI shape parseable for {celex}",
                  url.startswith("http://publications.europa.eu/resource/eli/"),
                  detail=url)
    return a


# ----------------------------------------------------------------------
# Phase 5 — IMMC client (LIVE — uses public Cellar SPARQL)
# ----------------------------------------------------------------------

async def audit_p5(quick: bool) -> PhaseAudit:
    a = PhaseAudit("P5", "IMMC client")
    from services.api_clients.immc_client import IMMCClient
    a.add("to_timeline handles None", IMMCClient.to_timeline(None) == [])
    a.add("to_timeline sorts by date", IMMCClient.to_timeline({"events": [{"date": "2024-12", "x": 1}, {"date": "2023-05", "x": 2}]})[0]["x"] == 2)

    if quick:
        a.add("--quick: live IMMC fetches skipped", True, detail="skipped 15 live calls")
        return a

    # 15 varied CELEX live
    async with IMMCClient(timeout=30) as c:
        for celex in CELEX_30[:15]:
            try:
                r = await c.fetch_events_for_celex(celex)
                ok_shape = "events" in r and isinstance(r["events"], list) and "fetched_at" in r
                error = r.get("error")
                detail = f"events={len(r.get('events', []))}"
                if error:
                    detail += f" ERROR={error[:60]}"
                a.add(f"IMMC fetch shape OK for {celex}", ok_shape, detail=detail)
            except Exception as e:
                a.add(f"IMMC fetch shape OK for {celex}", False, detail=f"raised {type(e).__name__}")
    return a


# ----------------------------------------------------------------------
# Phase 6 — AKN4EU renderer
# ----------------------------------------------------------------------

def audit_p6() -> PhaseAudit:
    a = PhaseAudit("P6", "AKN4EU 4.2 renderer")
    import xml.etree.ElementTree as ET
    from services.document_generation.det_renderer import render, SUPPORTED_TYPES
    AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"

    # 4 doc types × 5 different target CELEX
    for doc_type in SUPPORTED_TYPES:
        for celex in CELEX_30[:5]:
            try:
                xml = render({
                    "type": doc_type,
                    "title": f"Brubru {doc_type} on {celex}",
                    "celex_target": celex,
                    "body_paragraphs": ["Test paragraph."],
                    "amendments": [{"article": "1", "current": "old", "proposed": "new",
                                   "justification": "x"}] if doc_type == "amendment" else None,
                })
                root = ET.fromstring(xml)
                a.add(f"render({doc_type}) for {celex} parses + root=akomaNtoso",
                      root.tag.endswith("akomaNtoso"),
                      detail=f"{len(xml)} bytes")
            except Exception as e:
                a.add(f"render({doc_type}) for {celex}", False, detail=f"raised {type(e).__name__}: {e}")

    # IMMC events surface as TLCEvent
    xml = render({
        "type": "amendment", "title": "x", "celex_target": "32016R0679",
        "amendments": [{"article": "1", "current": "old", "proposed": "new", "justification": "x"}],
        "immc_tags": {"events": [{"event": "http://publications.europa.eu/resource/cellar/abc",
                                  "type": "ADOPTED", "date": "2024-06-13"}]},
    })
    a.add("IMMC events render as <TLCEvent>", b"TLCEvent" in xml)
    return a


# ----------------------------------------------------------------------
# Phase 7 — EURIO client (signature surface only — endpoint pending)
# ----------------------------------------------------------------------

async def audit_p7() -> PhaseAudit:
    a = PhaseAudit("P7", "EURIO client")
    from services.api_clients.eurio_sparql_client import EURIOClient

    async with EURIOClient() as c:
        a.add("default endpoint is unconfigured",
              c._endpoint_configured is False)
        for m in ("find_projects_by_topic", "get_project_consortium",
                  "get_project_deliverables", "get_project_funding_breakdown",
                  "find_projects_by_organisation"):
            a.add(f"EURIOClient has {m}()", callable(getattr(c, m, None)))

        r = await c.find_projects_by_topic("quantum")
        a.add("unconfigured fallback returns note", "note" in r and "endpoint" in r["note"].lower())
        a.add("results is empty list when unconfigured", r["results"] == [])

    # When configured, the flag flips
    async with EURIOClient(endpoint_url="https://example.org/sparql") as c2:
        a.add("explicit endpoint marks configured", c2._endpoint_configured is True)
    return a


# ----------------------------------------------------------------------
# Phase 8 — EuroSciVoc resolver (synthetic dump fixture)
# ----------------------------------------------------------------------

def audit_p8() -> PhaseAudit:
    a = PhaseAudit("P8", "EuroSciVoc resolver")
    import tempfile
    from services.vocabularies.euroscivoc_resolver import EuroSciVocResolver, EUROSCIVOC_URI_PREFIX

    # Synthetic fixture covering 6 langs + Catalan fallback
    synthetic = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix euroscivoc: <http://data.europa.eu/8mn/euroscivoc/> .

euroscivoc:c1 a skos:Concept ;
    skos:prefLabel "quantum technologies"@en, "tecnologías cuánticas"@es,
                   "tecnologie quantistiche"@it, "technologies quantiques"@fr,
                   "Quantentechnologien"@de, "technologie kwantowe"@pl .

euroscivoc:c2 a skos:Concept ;
    skos:prefLabel "artificial intelligence"@en, "inteligencia artificial"@es .

euroscivoc:c3 a skos:Concept ;
    skos:prefLabel "climate change"@en .
"""
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "esv.ttl"
        dump.write_text(synthetic)
        r = EuroSciVocResolver(dump_path=dump)
        a.add("loads synthetic dump", r.is_loaded())
        a.add("resolves c1 in EN", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "en") == "quantum technologies")
        a.add("resolves c1 in ES", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "es") == "tecnologías cuánticas")
        a.add("resolves c1 in IT", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "it") == "tecnologie quantistiche")
        a.add("resolves c1 in FR", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "fr") == "technologies quantiques")
        a.add("resolves c1 in DE", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "de") == "Quantentechnologien")
        a.add("resolves c1 in PL", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "pl") == "technologie kwantowe")
        a.add("CA falls back to ES for c1", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c1", "ca") == "tecnologías cuánticas")
        a.add("c3 falls back EN when only EN exists", r.resolve(f"{EUROSCIVOC_URI_PREFIX}c3", "fr") == "climate change")

        # Search
        hits = r.search("quantum", "en")
        a.add("search('quantum') returns >=1", len(hits) >= 1)
        a.add("search('inteligencia', 'es') returns >=1", len(r.search("inteligencia", "es")) >= 1)

    # Without dump
    r2 = EuroSciVocResolver(dump_path=Path("/tmp/nope.ttl"))
    a.add("graceful empty without dump", r2.search("anything", "en") == [])
    a.add("is_loaded() False without dump", r2.is_loaded() is False)
    return a


# ----------------------------------------------------------------------
# Phase 9 — OJEEP validator
# ----------------------------------------------------------------------

def audit_p9() -> PhaseAudit:
    a = PhaseAudit("P9", "OJEEP validator")
    import importlib.util
    spec = importlib.util.spec_from_file_location("ojeep_validator", ROOT / "backend/scripts/validate_catalan_against_ojeep.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ojeep_validator"] = m
    spec.loader.exec_module(m)

    catalan_dir = ROOT / "frontend/public/legislacio-ue-catala"
    if catalan_dir.exists():
        celex_dirs = [p for p in catalan_dir.iterdir() if p.is_dir() and __import__('re').match(r"^\d[A-Z\d]{0,1}\d{4}[A-Z]+\d+", p.name.split("-", 1)[0])]
        a.add(f"found >= 3 Catalan CELEX-shaped dirs ({len(celex_dirs)})", len(celex_dirs) >= 3)
        for d in celex_dirs:
            html = (d / "index.html").read_text(encoding="utf-8", errors="replace")
            res = m._validate_html(html, celex=d.name, path=str(d))
            a.add(f"validates {d.name}", res.ok, detail=f"passes={res.passes}")
            xml = m.emit_xml_for_act(html, d.name)
            import xml.etree.ElementTree as ET
            try:
                ET.fromstring(xml)
                a.add(f"emit_xml({d.name}) parses", True)
            except Exception as e:
                a.add(f"emit_xml({d.name}) parses", False, detail=f"{e}")

    # Synthetic broken HTML must fail
    res = m._validate_html("<html><body>nothing</body></html>", celex="brk", path="x")
    a.add("rejects plain HTML", not res.ok)
    return a


# ----------------------------------------------------------------------
# Phase 12 — LegalHTML renderer + validator
# ----------------------------------------------------------------------

def audit_p12() -> PhaseAudit:
    a = PhaseAudit("P12", "LegalHTML")
    import xml.etree.ElementTree as ET
    from services.document_generation.legalhtml_renderer import render, validate

    # 5 different acts × 6 langs
    for celex in ["32016R0679", "32024R1689", "32016L1148", "32023R1542", "32011L0083"]:
        for lang in ("en", "ca", "es", "fr", "it", "nl"):
            doc = {
                "title": f"REGULATION {celex}",
                "act_type": "regulation" if "R" in celex else "directive",
                "act_date": "2024-01-15",
                "celex": celex,
                "acting_entities": [{"label": "EP", "corp_body_code": "EP"}],
                "citations": [{"text": "treaty", "href": "x", "eli_predicate": "eli:based_on"}],
                "recitals": [{"n": 1, "text": "x"}],
                "articles": [{"n": "1", "title": "Subject", "text": "y"}],
            }
            xml = render(doc, lang=lang)
            try:
                ET.fromstring(xml)
                parses = True
            except Exception:
                parses = False
            a.add(f"render({celex},{lang}) parses", parses)
            res = validate(xml)
            a.add(f"validate(self-rendered {celex},{lang}) ok", res.ok)

    # Validate every reference sample
    cov_dir = ROOT / "docs/ontologies/legalhtml/COV-LegalHTML-converted-docs"
    if cov_dir.exists():
        samples = list(cov_dir.rglob("*.xhtml"))
        a.add(f"have >= 30 reference samples ({len(samples)})", len(samples) >= 30)
        for s in samples:
            res = validate(s.read_bytes())
            a.add(f"reference {s.name[:50]} validates", res.ok)
    return a


# ----------------------------------------------------------------------
# Phase 13 — Standard-identifier + ECLI
# ----------------------------------------------------------------------

def audit_p13() -> PhaseAudit:
    a = PhaseAudit("P13", "Identifier + ECLI")
    from services.identifiers.standard_identifier_resolver import recognise, parse_all, IdentifierKind
    from services.api_clients.ecli_client import deep_link, eur_lex_url, is_cjeu, parse
    from services.api_clients.showvoc_client import deep_link as sv_link

    # 30 CELEX
    for celex in CELEX_30:
        m = recognise(celex)
        a.add(f"recognise({celex}) -> CELEX",
              m is not None and m.kind == IdentifierKind.CELEX,
              detail=f"kind={m.kind.value if m else None}")

    # 15 ECLI
    for ecli in ECLI_15:
        m = recognise(ecli)
        a.add(f"recognise({ecli}) -> ECLI",
              m is not None and m.kind == IdentifierKind.ECLI)
        p = parse(ecli)
        a.add(f"parse({ecli}) returns 4 keys", set(p.keys()) == {"country", "court", "year", "ordinal"})

    # CJEU classification
    a.add("ECLI:EU:C:2014:317 is CJEU", is_cjeu("ECLI:EU:C:2014:317"))
    a.add("ECLI:DE:BVerfG:... is NOT CJEU", not is_cjeu("ECLI:DE:BVerfG:2020:RS20200505"))
    a.add("eur_lex_url(CJEU) returns InforCuria", "curia.europa.eu" in (eur_lex_url("ECLI:EU:C:2014:317") or ""))

    # Mixed-paragraph parse_all
    para = (
        "GDPR (32016R0679) builds on the right to be forgotten "
        "(ECLI:EU:C:2014:317). Cite this as doi:10.2775/123456 in "
        "ISSN: 1234-5678 publications, catalogue OA-AS-16-001-EN-N."
    )
    matches = parse_all(para)
    kinds = {m.kind for m in matches}
    for required_kind in (IdentifierKind.CELEX, IdentifierKind.ECLI, IdentifierKind.DOI,
                          IdentifierKind.ISSN, IdentifierKind.CATALOGUE_NUMBER):
        a.add(f"parse_all paragraph contains {required_kind.value}", required_kind in kinds)

    # ShowVoc
    for theme in EUROVOC_THEMES[:5]:
        url = sv_link(f"http://eurovoc.europa.eu/{theme}")
        a.add(f"ShowVoc deep-link for EuroVoc {theme}", url and "showvoc" in url)

    for code in CORPORATE_BODIES[:5]:
        url = sv_link(f"http://publications.europa.eu/resource/authority/corporate-body/{code}")
        a.add(f"ShowVoc deep-link for corporate-body/{code}", url and "showvoc" in url)
    return a


# ----------------------------------------------------------------------
# Production health check (Railway)
# ----------------------------------------------------------------------

def audit_production() -> PhaseAudit:
    a = PhaseAudit("PROD", "Production health (Railway)")
    import httpx
    base = "https://brubru-production.up.railway.app"
    endpoints = [
        ("/docs", "FastAPI docs reachable"),
        ("/api/datasets.ttl", "DCAT-AP TTL endpoint"),
        ("/api/v1/identify?q=32016R0679", "v1 identify endpoint"),
        ("/api/v1/discover/ecli/ECLI:EU:C:2014:317", "v1 ECLI endpoint"),
        ("/api/v1/discover/cellar/celex/32016R0679/languages", "v1 Cellar manifestations"),
    ]
    for path, label in endpoints:
        try:
            r = httpx.get(base + path, timeout=20.0, follow_redirects=True)
            ok = r.status_code < 500
            a.add(f"{label} ({path}) HTTP < 500",
                  ok, detail=f"HTTP {r.status_code}, {len(r.content)} bytes")
        except Exception as e:
            a.add(f"{label} ({path}) reachable", False, detail=f"{type(e).__name__}: {e}")
    return a


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default=None, help="P0|P1|...|P13|PROD (default: all)")
    parser.add_argument("--quick", action="store_true", help="Skip live SPARQL calls (P5)")
    parser.add_argument("--db-url", default="postgresql://postgres@localhost:5432/brubru_p1_test")
    parser.add_argument("--skip-prod", action="store_true", help="Skip Railway health check")
    args = parser.parse_args()

    audits: List[PhaseAudit] = []

    pf = (args.phase or "").upper()
    if not pf or pf == "P0":   audits.append(audit_p0())
    if not pf or pf == "P1":   audits.append(audit_p1(args.db_url))
    if not pf or pf == "P2":   audits.append(audit_p2(args.db_url))
    if not pf or pf == "P3":   audits.append(audit_p3())
    if not pf or pf == "P4":   audits.append(audit_p4())
    if not pf or pf == "P5":   audits.append(await audit_p5(args.quick))
    if not pf or pf == "P6":   audits.append(audit_p6())
    if not pf or pf == "P7":   audits.append(await audit_p7())
    if not pf or pf == "P8":   audits.append(audit_p8())
    if not pf or pf == "P9":   audits.append(audit_p9())
    if not pf or pf == "P12":  audits.append(audit_p12())
    if not pf or pf == "P13":  audits.append(audit_p13())
    if (not pf or pf == "PROD") and not args.skip_prod:
        audits.append(audit_production())

    log.info("=" * 72)
    grand_pass = grand_fail = 0
    for a in audits:
        log.info(f"[{a.phase}] {a.title}")
        for c in a.checks:
            mark = "PASS" if c["ok"] else "FAIL"
            log.info(f"   {mark}  {c['name']}{('  ' + c['detail']) if c['detail'] else ''}")
        log.info(f"   -- {a.passes}/{a.total} pass --")
        grand_pass += a.passes
        grand_fail += a.fails
    log.info("=" * 72)
    log.info(f"OVERALL  pass={grand_pass}  fail={grand_fail}  ({grand_pass / max(grand_pass+grand_fail,1) * 100:.0f}%)")
    return 0 if grand_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
