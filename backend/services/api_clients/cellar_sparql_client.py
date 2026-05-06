"""
Cellar SPARQL Client

Dedicated SPARQL client for the EU Publications Office Cellar metadata graph.
Used for discovery and metadata queries on EU legislation (regulations, directives,
decisions, recommendations, opinions, treaties, case law, proposals).

Endpoint: http://publications.europa.eu/webapi/rdf/sparql
Ontology: Common Data Model (CDM)
Reference: "Retrieving EUR-Lex documents in structured, machine-readable formats"
           (Publications Office, v1.00, 12 November 2025)

This client is the SPARQL counterpart to:
- backend/services/tenders/ted_sparql_client.py (TED procurement SPARQL)
- backend/services/api_clients/eurlex_client.py (mixed REST/RSS/SPARQL — legacy)

Use this client for:
- Delta discovery (what was published since date X)
- ELI URI lookup
- Consolidated-version tracking
- EuroVoc subject-matter queries
- In-force vs repealed status checks
- Corpus statistics

Schema notes (verified live against the endpoint, May 2026):
- CELEX is stored as a typed literal: filter via FILTER(STR(?celex) = "...")
- Dates are stored as plain strings (no xsd:date typing): use string comparison
- ELI is exposed via owl:sameAs, not a CDM predicate
- Relationship predicates begin with cdm:resource_legal_* or cdm:act_consolidated_*
- in-force literal is "1" (true) — also "0" exists; absence means "no info"
- end-of-validity = "9999-12-31" for in-force acts
"""

import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from services.api_clients.base_sparql_client import BaseSPARQLClient

logger = logging.getLogger(__name__)


CDM_PREFIXES = {
    "cdm": "http://publications.europa.eu/ontology/cdm#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "eurovoc": "http://eurovoc.europa.eu/",
}

# Resource-type authority URIs (subset of common values; see
# http://publications.europa.eu/resource/authority/resource-type)
RESOURCE_TYPE_AUTHORITY = "http://publications.europa.eu/resource/authority/resource-type/"

# Bidirectional relationship predicates discovered on the GDPR work
# (see scripts/probe_cellar_celex.py).
RELATIONSHIP_PREDICATES = [
    "cdm:resource_legal_repeals_resource_legal",
    "cdm:resource_legal_implicitly_repeals_resource_legal",
    "cdm:resource_legal_corrects_resource_legal",
    "cdm:resource_legal_amends_resource_legal",
    "cdm:resource_legal_implements_resource_legal",
    "cdm:resource_legal_adopts_resource_legal",
    "cdm:resource_legal_based_on_resource_legal",
    "cdm:act_consolidated_based_on_resource_legal",
    "cdm:act_consolidated_consolidates_resource_legal",
]


class _QueryCache:
    """In-memory TTL cache for SPARQL results. Mirrors TED's QueryCache."""

    def __init__(self, default_ttl: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def _key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        k = self._key(query)
        if k in self._cache:
            entry = self._cache[k]
            if datetime.utcnow() < entry["expires_at"]:
                return entry["data"]
            del self._cache[k]
        return None

    def set(self, query: str, data: Any, ttl: Optional[int] = None) -> None:
        k = self._key(query)
        self._cache[k] = {
            "data": data,
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl),
            "cached_at": datetime.utcnow(),
        }

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        now = datetime.utcnow()
        valid = sum(1 for e in self._cache.values() if now < e["expires_at"])
        return {"total": len(self._cache), "valid": valid, "expired": len(self._cache) - valid}


class CellarSPARQLClient(BaseSPARQLClient):
    """
    SPARQL client for the Publications Office Cellar.

    Endpoint: http://publications.europa.eu/webapi/rdf/sparql

    Example:
        async with CellarSPARQLClient() as client:
            recent = await client.discover_by_date_range(
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 30),
                limit=100,
            )
    """

    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    def __init__(
        self,
        max_results: int = 10000,
        timeout: int = 120,
        enable_cache: bool = True,
        cache_ttl: int = 3600,
    ):
        super().__init__(
            endpoint_url=self.SPARQL_ENDPOINT,
            max_results=max_results,
            timeout=timeout,
        )
        self.cache = _QueryCache(default_ttl=cache_ttl) if enable_cache else None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _cached_select(
        self, query: str, cache_ttl: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if self.cache:
            cached = self.cache.get(query)
            if cached is not None:
                logger.debug("Cellar SPARQL cache hit")
                return cached
        results = await self.select(query)
        if self.cache and results:
            self.cache.set(query, results, ttl=cache_ttl)
        return results

    def clear_cache(self) -> None:
        if self.cache:
            self.cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.cache.stats() if self.cache else {"caching_enabled": False}

    # ------------------------------------------------------------------
    # Discovery — date-range delta
    # ------------------------------------------------------------------

    async def discover_by_date_range(
        self,
        date_from: date,
        date_to: date,
        sectors: Optional[List[str]] = None,
        language: str = "ENG",
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Discover EU acts published in a date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            sectors: CELEX sector codes to include (e.g. ["3"] for legislation in force,
                     ["5"] for proposals). None = all sectors.
            language: ISO-3 language code uppercase for titles (ENG, FRA, DEU, …)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of dicts with keys: work, celex, date, title, type
        """
        sector_filter = ""
        if sectors:
            values = ", ".join([f'"{s}"' for s in sectors])
            sector_filter = f"FILTER(SUBSTR(STR(?celex), 1, 1) IN ({values}))"

        lang = language.upper()
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT DISTINCT ?work ?celex ?date ?title
        WHERE {{
            ?work cdm:resource_legal_id_celex ?celex .
            ?work cdm:work_date_document ?date .

            FILTER(STR(?date) >= "{date_from.isoformat()}")
            FILTER(STR(?date) <= "{date_to.isoformat()}")
            {sector_filter}

            OPTIONAL {{
                ?expr cdm:expression_belongs_to_work ?work .
                ?expr cdm:expression_uses_language
                      <http://publications.europa.eu/resource/authority/language/{lang}> .
                ?expr cdm:expression_title ?title .
            }}
        }}
        ORDER BY DESC(?date)
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            results = await self._cached_select(query, cache_ttl=1800)
            logger.info(
                f"Cellar SPARQL: {len(results)} acts in [{date_from} -> {date_to}] "
                f"sectors={sectors or 'ALL'}"
            )
            return results
        except Exception as e:
            logger.error(f"Cellar SPARQL date-range query failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Single-act metadata
    # ------------------------------------------------------------------

    async def get_celex_metadata(
        self, celex: str, language: str = "ENG"
    ) -> Optional[Dict[str, Any]]:
        """
        Full metadata for one CELEX number.

        Returns dict with: work, celex, date, title, resource_type_uri, eli, in_force,
        date_in_force, date_end_validity.
        """
        lang = language.upper()
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT ?work ?date ?title ?resourceTypeUri ?eli
               ?inForce ?dateInForce ?dateEnd
        WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")

            OPTIONAL {{ ?work cdm:work_date_document ?date . }}
            OPTIONAL {{ ?work cdm:work_has_resource-type ?resourceTypeUri . }}
            OPTIONAL {{ ?work cdm:resource_legal_in-force ?inForce . }}
            OPTIONAL {{ ?work cdm:resource_legal_date_entry-into-force ?dateInForce . }}
            OPTIONAL {{ ?work cdm:resource_legal_date_end-of-validity ?dateEnd . }}
            OPTIONAL {{
                ?work owl:sameAs ?eli .
                FILTER(STRSTARTS(STR(?eli), "http://publications.europa.eu/resource/eli/"))
            }}
            OPTIONAL {{
                ?expr cdm:expression_belongs_to_work ?work .
                ?expr cdm:expression_uses_language
                      <http://publications.europa.eu/resource/authority/language/{lang}> .
                ?expr cdm:expression_title ?title .
            }}
        }}
        LIMIT 1
        """

        try:
            results = await self._cached_select(query, cache_ttl=86400)
            if results:
                row = results[0]
                row["celex"] = celex
                # Normalise in_force to bool
                row["in_force"] = (row.get("inForce") or "").strip() == "1"
                return row
            logger.info(f"Cellar SPARQL: no metadata for CELEX {celex}")
            return None
        except Exception as e:
            logger.error(f"Cellar SPARQL metadata query failed for {celex}: {e}")
            return None

    async def get_eli(self, celex: str) -> Optional[str]:
        """Resolve a CELEX to its ELI URI (via owl:sameAs)."""
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?eli WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")
            ?work owl:sameAs ?eli .
            FILTER(STRSTARTS(STR(?eli), "http://publications.europa.eu/resource/eli/"))
        }} LIMIT 1
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return results[0]["eli"] if results else None
        except Exception as e:
            logger.error(f"Cellar SPARQL ELI lookup failed for {celex}: {e}")
            return None

    async def get_celex_from_eli(self, eli: str) -> Optional[str]:
        """Reverse lookup: ELI URI -> CELEX."""
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?celex WHERE {{
            ?work owl:sameAs <{eli}> .
            ?work cdm:resource_legal_id_celex ?celex .
        }} LIMIT 1
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return results[0]["celex"] if results else None
        except Exception as e:
            logger.error(f"Cellar SPARQL ELI->CELEX lookup failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def get_related_acts(self, celex: str) -> List[Dict[str, Any]]:
        """
        Get acts related to this CELEX (amendments, repeals, corrigenda,
        consolidations) — both directions.

        Returns list of dicts: relation, related_celex, direction ('outgoing'|'incoming').
        """
        rel_filter = "FILTER(?relation IN (" + ", ".join(RELATIONSHIP_PREDICATES) + "))"

        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT DISTINCT ?relation ?relatedCelex ?direction
        WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")

            {{
                ?work ?relation ?related .
                ?related cdm:resource_legal_id_celex ?relatedCelex .
                BIND("outgoing" AS ?direction)
                {rel_filter}
            }} UNION {{
                ?related ?relation ?work .
                ?related cdm:resource_legal_id_celex ?relatedCelex .
                BIND("incoming" AS ?direction)
                {rel_filter}
            }}
        }}
        """
        try:
            results = await self._cached_select(query, cache_ttl=3600)
            logger.info(
                f"Cellar SPARQL: {len(results)} related acts for {celex}"
            )
            return results
        except Exception as e:
            logger.error(f"Cellar SPARQL relationships query failed for {celex}: {e}")
            return []

    async def get_consolidated_versions(self, base_celex: str) -> List[Dict[str, Any]]:
        """
        Get all consolidated versions of a base act.
        E.g. base_celex = '32016R0679' (GDPR base) returns all dated consolidations.
        """
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT DISTINCT ?consolidated ?consolidatedCelex ?date
        WHERE {{
            ?base cdm:resource_legal_id_celex ?baseLit .
            FILTER(STR(?baseLit) = "{base_celex}")
            ?consolidated cdm:act_consolidated_consolidates_resource_legal ?base .
            OPTIONAL {{ ?consolidated cdm:resource_legal_id_celex ?consolidatedCelex . }}
            OPTIONAL {{ ?consolidated cdm:work_date_document ?date . }}
        }}
        ORDER BY DESC(?date)
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return results
        except Exception as e:
            logger.error(f"Cellar SPARQL consolidations query failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Subject matter / classification
    # ------------------------------------------------------------------

    async def get_acts_by_eurovoc(
        self,
        eurovoc_concept: str,
        date_from: Optional[date] = None,
        language: str = "ENG",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Acts tagged with a EuroVoc concept.

        Args:
            eurovoc_concept: EuroVoc concept ID (e.g. '5460' for 'data protection')
                             OR full URI (http://eurovoc.europa.eu/5460).
        """
        if not eurovoc_concept.startswith("http"):
            concept_uri = f"http://eurovoc.europa.eu/{eurovoc_concept}"
        else:
            concept_uri = eurovoc_concept

        date_filter = ""
        if date_from:
            date_filter = f'FILTER(STR(?date) >= "{date_from.isoformat()}")'

        lang = language.upper()
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT DISTINCT ?work ?celex ?date ?title
        WHERE {{
            ?work cdm:work_is_about_concept_eurovoc <{concept_uri}> .
            ?work cdm:resource_legal_id_celex ?celex .
            OPTIONAL {{ ?work cdm:work_date_document ?date . }}
            OPTIONAL {{
                ?expr cdm:expression_belongs_to_work ?work .
                ?expr cdm:expression_uses_language
                      <http://publications.europa.eu/resource/authority/language/{lang}> .
                ?expr cdm:expression_title ?title .
            }}
            {date_filter}
        }}
        ORDER BY DESC(?date)
        LIMIT {limit}
        """
        try:
            results = await self._cached_select(query, cache_ttl=3600)
            logger.info(
                f"Cellar SPARQL: {len(results)} acts for EuroVoc {eurovoc_concept}"
            )
            return results
        except Exception as e:
            logger.error(f"Cellar SPARQL EuroVoc query failed: {e}")
            return []

    # ------------------------------------------------------------------
    # In-force / repealed status
    # ------------------------------------------------------------------

    async def get_force_status(self, celex: str) -> Dict[str, Any]:
        """
        Returns {'in_force': bool, 'date_in_force': str|None, 'date_end_validity': str|None}.

        Cellar uses '1' for in-force, '0' for not-in-force; absence = no info.
        """
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?inForce ?dateInForce ?dateEnd WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")
            OPTIONAL {{ ?work cdm:resource_legal_in-force ?inForce . }}
            OPTIONAL {{ ?work cdm:resource_legal_date_entry-into-force ?dateInForce . }}
            OPTIONAL {{ ?work cdm:resource_legal_date_end-of-validity ?dateEnd . }}
        }} LIMIT 1
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            if results:
                row = results[0]
                return {
                    "in_force": (row.get("inForce") or "").strip() == "1",
                    "date_in_force": row.get("dateInForce"),
                    "date_end_validity": row.get("dateEnd"),
                }
            return {"in_force": False, "date_in_force": None, "date_end_validity": None}
        except Exception as e:
            logger.error(f"Cellar SPARQL force-status query failed for {celex}: {e}")
            return {"in_force": False, "date_in_force": None, "date_end_validity": None}

    # ------------------------------------------------------------------
    # Available languages
    # ------------------------------------------------------------------

    async def get_available_languages(self, celex: str) -> List[str]:
        """
        ISO-3 language codes (FRA, ENG, …) for which an expression of this CELEX exists.
        """
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?langCode WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")
            ?expr cdm:expression_belongs_to_work ?work .
            ?expr cdm:expression_uses_language ?langUri .
            BIND(REPLACE(STR(?langUri), ".*/", "") AS ?langCode)
        }}
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return sorted({r["langCode"] for r in results if r.get("langCode")})
        except Exception as e:
            logger.error(f"Cellar SPARQL languages query failed for {celex}: {e}")
            return []

    async def get_manifestations(self, celex: str, work_uri: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Full manifestation list for a CELEX: every (language, format, URL) tuple.

        Replaces the legacy FMX4 notice fetch (which hit EUR-Lex's slow async
        endpoint and routinely returned HTTP 202). This SPARQL query goes
        directly to the Cellar metadata graph and returns immediately.

        Args:
            celex: CELEX number (e.g. "32016R0679").
            work_uri: optional Cellar work URI when already known — skips the
                CELEX→work resolution step (much faster). Pass it from
                callers that already have meta["work"].

        Each row has:
            language  : ISO-3 code (e.g. "ENG", "FRA")
            format    : short type label ("fmx4", "xhtml", "pdfa1a", ...)
            url       : the actual download URL on Cellar
            identifier: filename/id of the manifestation
        """
        # When the caller knows the work URI, scope the query by that URI —
        # avoids the slow CELEX→work resolution and the join with all works.
        if work_uri:
            anchor = f"BIND(<{work_uri}> AS ?work)"
        else:
            anchor = (
                f'?work <http://publications.europa.eu/ontology/cdm#resource_legal_id_celex> ?celexLit .\n'
                f'FILTER(STR(?celexLit) = "{celex}")'
            )
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT DISTINCT ?manif ?langCode ?type WHERE {{
            {anchor}
            ?expr cdm:expression_belongs_to_work ?work .
            ?expr cdm:expression_uses_language ?langUri .
            BIND(REPLACE(STR(?langUri), ".*/", "") AS ?langCode)
            ?manif cdm:manifestation_manifests_expression ?expr .
            OPTIONAL {{ ?manif cdm:manifestation_type ?type . }}
        }}
        LIMIT 500
        """
        try:
            rows = await self._cached_select(query, cache_ttl=86400)
        except Exception as e:
            logger.error(f"Cellar SPARQL manifestations query failed for {celex}: {e}")
            return []

        # The Cellar manifestation URI itself IS the download URL when you
        # GET it with Accept: */*. Pass through the raw URI as ``url`` so
        # clients can fetch directly.
        out = []
        for r in rows:
            manif = r.get("manif")
            if not manif:
                continue
            lang = r.get("langCode")
            type_label = (r.get("type") or "").strip().lower() or None
            out.append({
                "language": lang,
                "format": type_label,
                "url": manif,
                "identifier": manif.rsplit("/", 1)[-1] if "/" in manif else manif,
            })
        return out

    # ------------------------------------------------------------------
    # EuroVoc concepts attached to a CELEX
    # ------------------------------------------------------------------

    async def get_eurovoc_concepts(self, celex: str) -> List[str]:
        """Return the EuroVoc concept URIs attached to a CELEX."""
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?concept WHERE {{
            ?work cdm:resource_legal_id_celex ?celexLit .
            FILTER(STR(?celexLit) = "{celex}")
            ?work cdm:work_is_about_concept_eurovoc ?concept .
        }}
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return [r["concept"] for r in results if r.get("concept")]
        except Exception as e:
            logger.error(f"Cellar SPARQL EuroVoc concepts query failed for {celex}: {e}")
            return []

    # ------------------------------------------------------------------
    # EU Vocabularies — authority-table label resolution
    # ------------------------------------------------------------------

    async def resolve_authority_label(
        self,
        authority_uri: str,
        language: str = "en",
    ) -> Optional[str]:
        """
        Resolve any Publications Office authority-table URI to its skos:prefLabel.

        Works for: resource-type, language, country, corporate-body, fund-type,
        procedure-type, currency, etc. — any URI starting with
        http://publications.europa.eu/resource/authority/...

        Args:
            authority_uri: Full URI (e.g. http://publications.europa.eu/resource/authority/resource-type/REG)
            language: ISO-2 lowercase tag for the label (en, fr, es, ca, it, nl)

        Returns:
            English-language preferred label or None.
        """
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?label WHERE {{
            <{authority_uri}> skos:prefLabel ?label .
            FILTER(LANG(?label) = "{language}")
        }} LIMIT 1
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return results[0]["label"] if results else None
        except Exception as e:
            logger.error(f"Cellar SPARQL authority-label lookup failed for {authority_uri}: {e}")
            return None

    async def resolve_resource_type(self, resource_type_uri: str, language: str = "en") -> Optional[str]:
        """Convenience wrapper: resolve a resource-type URI to its label (e.g. REG -> Regulation)."""
        return await self.resolve_authority_label(resource_type_uri, language=language)

    # ------------------------------------------------------------------
    # Cache-aware NAL resolvers (Phase 1 of docs/applications/euvoc.md).
    # Each one tries the local eu_authority_labels cache first; on miss,
    # falls through to resolve_authority_label() which hits SPARQL.
    # ------------------------------------------------------------------

    async def _cache_first_resolve(
        self,
        uri: str,
        language: str,
        cache: Optional[Any],
    ) -> Optional[str]:
        """Look up `uri` in the provided AuthorityLabelCache; on miss,
        fall through to live SPARQL via resolve_authority_label().

        `cache` is opaque (we accept any object exposing a .resolve(uri, lang)
        method) to avoid a hard import cycle between the SPARQL client and
        the vocabularies package.
        """
        if cache is not None:
            try:
                hit = cache.resolve(uri, language)
                if hit:
                    return hit
            except Exception as e:
                logger.warning("Cellar SPARQL: cache lookup failed for %s: %s", uri, e)
        return await self.resolve_authority_label(uri, language=language)

    async def resolve_corporate_body(
        self,
        uri: str,
        language: str = "en",
        cache: Optional[Any] = None,
    ) -> Optional[str]:
        """corporate-body URI -> long-form name (e.g. EP -> 'European Parliament')."""
        return await self._cache_first_resolve(uri, language, cache)

    async def resolve_procedure(
        self,
        uri: str,
        language: str = "en",
        cache: Optional[Any] = None,
    ) -> Optional[str]:
        """procedure URI -> label (e.g. COD -> 'Co-decision procedure (COD)')."""
        return await self._cache_first_resolve(uri, language, cache)

    async def resolve_directory_code(
        self,
        uri: str,
        language: str = "en",
        cache: Optional[Any] = None,
    ) -> Optional[str]:
        """dir-eu-legal-act URI -> Directory of EU Legal Acts label."""
        return await self._cache_first_resolve(uri, language, cache)

    async def resolve_modification_type(
        self,
        uri: str,
        language: str = "en",
        cache: Optional[Any] = None,
    ) -> Optional[str]:
        """modification-type URI -> label for amends/repeals/corrects/consolidates."""
        return await self._cache_first_resolve(uri, language, cache)

    async def resolve_eurovoc_concept(
        self,
        concept_uri_or_id: str,
        language: str = "en",
    ) -> Optional[str]:
        """
        Resolve a EuroVoc concept (e.g. 5460) to its preferred label.

        Args:
            concept_uri_or_id: Concept ID (string of digits) OR full URI.
            language: ISO-2 language tag.
        """
        if not concept_uri_or_id.startswith("http"):
            uri = f"http://eurovoc.europa.eu/{concept_uri_or_id}"
        else:
            uri = concept_uri_or_id
        return await self.resolve_authority_label(uri, language=language)

    async def search_eurovoc_concepts(
        self,
        keyword: str,
        language: str = "en",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Free-text search the EuroVoc thesaurus for concepts matching a keyword.

        Args:
            keyword: Search term (e.g. "data protection").
            language: Label language to search.
            limit: Max results.

        The query restricts to ``?concept a skos:Concept`` and the EuroVoc
        scheme so SPARQL doesn't have to scan every prefLabel triple in the
        endpoint (which timed out before the fix).
        """
        # Escape double quotes in the keyword to avoid SPARQL injection /
        # malformed query when the user types something like 'AI "Act"'.
        kw_safe = keyword.replace("\\", "\\\\").replace('"', '\\"')
        query = f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT DISTINCT ?concept ?label WHERE {{
            ?concept a skos:Concept ;
                     skos:inScheme <http://eurovoc.europa.eu/100141> ;
                     skos:prefLabel ?label .
            FILTER(LANG(?label) = "{language}")
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{kw_safe}")))
        }} LIMIT {limit}
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            return results
        except Exception as e:
            logger.error(f"Cellar SPARQL EuroVoc search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def count_by_year(self, year: int, sector: str = "3") -> int:
        """Count acts in a given CELEX sector for a year (default sector 3 = legislation)."""
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT (COUNT(DISTINCT ?work) AS ?n) WHERE {{
            ?work cdm:resource_legal_id_celex ?celex .
            ?work cdm:work_date_document ?date .
            FILTER(SUBSTR(STR(?celex), 1, 1) = "{sector}")
            FILTER(STR(?date) >= "{year}-01-01")
            FILTER(STR(?date) <= "{year}-12-31")
        }}
        """
        try:
            results = await self._cached_select(query, cache_ttl=86400)
            if results and results[0].get("n"):
                return int(results[0]["n"])
            return 0
        except Exception as e:
            logger.error(f"Cellar SPARQL count_by_year failed: {e}")
            return 0

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def is_healthy(self) -> bool:
        """Quick endpoint health check."""
        try:
            return await self.health_check()
        except Exception as e:
            logger.error(f"Cellar SPARQL health check failed: {e}")
            return False
