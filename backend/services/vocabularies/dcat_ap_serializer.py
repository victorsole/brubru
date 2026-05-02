"""
DCAT-AP serializer — turn `brubru_dataset_catalog` rows into
DCAT-AP-conformant Turtle, RDF/XML, and JSON-LD.

DCAT-AP = "DCAT Application Profile for data portals in Europe"
Reference: https://op.europa.eu/en/web/eu-vocabularies/dcat-ap
Namespace: http://data.europa.eu/r5r/

Brubru is itself a data catalogue (Catalan EU laws DB, chat KB guides,
v1 API as a sellable surface, eu_laws TSVECTOR corpus, the europa.eu
source registry under data/europa_eu/). Phase 2 of
docs/applications/euvoc.md publishes a DCAT-AP description of those
datasets so data.europa.eu can harvest us.

Public surface:
    serialize(rows, *, format="turtle") -> bytes
    catalog_uri()                       -> str   (the dcat:Catalog IRI)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

# Lazy-import rdflib so missing-dep failures degrade gracefully —
# the rest of Brubru (chat, v1 API) keeps booting if rdflib isn't
# installed. The serialize() entry point will raise a clean
# RuntimeError instead of crashing the FastAPI app at import time.
try:
    from rdflib import BNode, Graph, Literal, Namespace, URIRef
    from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, SKOS, XSD
    _RDFLIB_AVAILABLE = True
except ImportError as _e:  # noqa: BLE001
    _RDFLIB_AVAILABLE = False
    _RDFLIB_IMPORT_ERROR = str(_e)
    BNode = Graph = Literal = Namespace = URIRef = None  # type: ignore[assignment]
    DCAT = DCTERMS = FOAF = RDF = SKOS = XSD = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Namespaces (DCAT-AP-aligned) — only constructed when rdflib is present
# ----------------------------------------------------------------------
if _RDFLIB_AVAILABLE:
    SPDX = Namespace("http://spdx.org/rdf/terms#")
    ADMS = Namespace("http://www.w3.org/ns/adms#")
    VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
else:
    SPDX = ADMS = VCARD = None  # type: ignore[assignment]

# Brubru's own publisher IRI.
BRUBRU_BASE = "https://brubru.beresol.eu"
PUBLISHER_IRI = URIRef(f"{BRUBRU_BASE}/.well-known/publisher")
CATALOG_IRI = URIRef(f"{BRUBRU_BASE}/.well-known/dcat-ap-catalog")
CONTACT_IRI = URIRef("mailto:hello@beresol.eu")

# DCAT-AP application profile pointer
DCAT_AP_AP = URIRef("http://data.europa.eu/r5r/")


def catalog_uri() -> str:
    return str(CATALOG_IRI)


def _bind_prefixes(g: Graph) -> None:
    g.bind("dcat", DCAT)
    g.bind("dct", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("skos", SKOS)
    g.bind("adms", ADMS)
    g.bind("vcard", VCARD)
    g.bind("xsd", XSD)


def _add_publisher(g: Graph) -> None:
    g.add((PUBLISHER_IRI, RDF.type, FOAF.Organization))
    g.add((PUBLISHER_IRI, FOAF.name, Literal("Beresol BV (Brubru)", lang="en")))
    g.add((PUBLISHER_IRI, FOAF.homepage, URIRef("https://brubru.beresol.eu")))
    g.add((PUBLISHER_IRI, FOAF.mbox, CONTACT_IRI))


def _add_contact_point(g: Graph) -> URIRef:
    contact = URIRef(f"{BRUBRU_BASE}/.well-known/contact")
    g.add((contact, RDF.type, VCARD.Kind))
    g.add((contact, VCARD.fn, Literal("Brubru / Beresol contact")))
    g.add((contact, VCARD.hasEmail, CONTACT_IRI))
    return contact


def _add_catalog(g: Graph, dataset_uris: Iterable[URIRef]) -> None:
    g.add((CATALOG_IRI, RDF.type, DCAT.Catalog))
    g.add((CATALOG_IRI, DCTERMS.title, Literal("Brubru data catalogue", lang="en")))
    g.add((CATALOG_IRI, DCTERMS.title, Literal("Catàleg de dades de Brubru", lang="ca")))
    g.add(
        (
            CATALOG_IRI,
            DCTERMS.description,
            Literal(
                "Brubru's published datasets — Catalan EU legislation, chat "
                "knowledge guides, the v1 REST API as a data service, the "
                "eu_laws TSVECTOR corpus, and the curated europa.eu source "
                "registry. Conformant with the DCAT-AP application profile.",
                lang="en",
            ),
        )
    )
    g.add((CATALOG_IRI, DCTERMS.publisher, PUBLISHER_IRI))
    g.add((CATALOG_IRI, DCTERMS.modified, Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))
    g.add((CATALOG_IRI, DCTERMS.conformsTo, DCAT_AP_AP))
    g.add((CATALOG_IRI, DCTERMS.language, URIRef("http://publications.europa.eu/resource/authority/language/ENG")))
    for ds_uri in dataset_uris:
        g.add((CATALOG_IRI, DCAT.dataset, ds_uri))


def _add_dataset(g: Graph, row: Dict[str, Any], contact: URIRef) -> URIRef:
    """Render one brubru_dataset_catalog row as a dcat:Dataset (or dcat:DataService)."""
    ds_uri_str = row.get("dcat_uri") or f"{BRUBRU_BASE}/datasets/{row.get('id')}"
    ds_uri = URIRef(ds_uri_str)

    # A v1 API route is a dcat:DataService; everything else is a dcat:Dataset.
    distribution = row.get("distribution") or []
    is_data_service = any(
        d.get("media_type") == "application/json" and "v1" in (d.get("access_url") or "")
        for d in distribution
    )
    g.add((ds_uri, RDF.type, DCAT.DataService if is_data_service else DCAT.Dataset))

    # Title (multi-lang from JSONB description.title or row.title)
    g.add((ds_uri, DCTERMS.title, Literal(row.get("title", "Untitled"), lang="en")))

    # Description (multi-lang from JSONB description)
    desc = row.get("description") or {}
    if isinstance(desc, dict):
        for lang_code, txt in desc.items():
            if txt:
                g.add((ds_uri, DCTERMS.description, Literal(txt, lang=lang_code)))
    elif isinstance(desc, str) and desc:
        g.add((ds_uri, DCTERMS.description, Literal(desc, lang="en")))

    g.add((ds_uri, DCTERMS.publisher, PUBLISHER_IRI))
    g.add((ds_uri, DCAT.contactPoint, contact))

    # Themes (EuroVoc concepts)
    for theme_uri in row.get("dcat_theme") or []:
        if isinstance(theme_uri, str) and theme_uri.startswith("http"):
            g.add((ds_uri, DCAT.theme, URIRef(theme_uri)))

    # Licence
    if row.get("license"):
        g.add((ds_uri, DCTERMS.license, URIRef(row["license"])))

    # Update frequency
    if row.get("accrual_periodicity"):
        g.add(
            (
                ds_uri,
                DCTERMS.accrualPeriodicity,
                Literal(row["accrual_periodicity"]),
            )
        )

    # Distributions
    for d in distribution:
        if not isinstance(d, dict):
            continue
        access_url = d.get("access_url")
        if not access_url:
            continue
        dist_node = BNode()
        g.add((dist_node, RDF.type, DCAT.Distribution))
        g.add((dist_node, DCAT.accessURL, URIRef(access_url)))
        if d.get("media_type"):
            g.add((dist_node, DCAT.mediaType, Literal(d["media_type"])))
        if d.get("format"):
            g.add((dist_node, DCTERMS["format"], Literal(d["format"])))
        if d.get("title"):
            g.add((dist_node, DCTERMS.title, Literal(d["title"], lang="en")))
        g.add((ds_uri, DCAT.distribution, dist_node))

    # ADMS-style identifier
    g.add((ds_uri, DCTERMS.identifier, Literal(str(row.get("id") or ds_uri_str))))

    return ds_uri


def serialize(rows: List[Dict[str, Any]], *, format: str = "turtle") -> bytes:
    """
    Render `rows` (each a brubru_dataset_catalog row dict) in the requested
    format. Supported formats: turtle, xml (RDF/XML), json-ld.

    Raises RuntimeError with a clean message if `rdflib` is not installed.
    The rest of Brubru continues working — DCAT-AP is a single endpoint,
    not a critical path.
    """
    if not _RDFLIB_AVAILABLE:
        raise RuntimeError(
            f"DCAT-AP serialiser unavailable — rdflib not installed "
            f"(import error: {_RDFLIB_IMPORT_ERROR}). Add rdflib to "
            "backend/requirements.txt and redeploy."
        )
    g = Graph()
    _bind_prefixes(g)
    _add_publisher(g)
    contact = _add_contact_point(g)

    dataset_uris: List[URIRef] = []
    for row in rows:
        try:
            dataset_uris.append(_add_dataset(g, row, contact))
        except Exception as e:  # noqa: BLE001
            logger.warning("dcat_ap_serializer: skipping row %s (%s)", row.get("dcat_uri"), e)

    _add_catalog(g, dataset_uris)

    fmt = format.lower()
    if fmt in ("turtle", "ttl"):
        return g.serialize(format="turtle").encode("utf-8")
    if fmt in ("xml", "rdf", "rdf/xml", "rdf+xml"):
        return g.serialize(format="xml").encode("utf-8")
    if fmt in ("json-ld", "jsonld", "json"):
        return g.serialize(format="json-ld").encode("utf-8")
    raise ValueError(f"unsupported DCAT-AP format: {format}")
