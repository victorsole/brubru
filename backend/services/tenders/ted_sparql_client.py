"""
TED SPARQL Client

Client for querying the TED Open Data SPARQL endpoint.
Used for bulk data retrieval, historical queries, and complex cross-referencing.

Endpoint: https://publications.europa.eu/webapi/rdf/sparql
Ontology: eProcurement Ontology (EPO)
Documentation: https://docs.ted.europa.eu/EPO/latest/index.html
"""

import logging
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from enum import Enum
from functools import lru_cache
import asyncio

from ..api_clients.base_sparql_client import BaseSPARQLClient, SPARQLQuery, SPARQLQueryType

logger = logging.getLogger(__name__)


class QueryCache:
    """Simple in-memory cache for SPARQL query results with TTL."""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def _make_key(self, query: str) -> str:
        """Generate cache key from query string."""
        return hashlib.md5(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        """Get cached result if not expired."""
        key = self._make_key(query)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.utcnow() < entry["expires_at"]:
                logger.debug(f"Cache hit for query key {key[:8]}...")
                return entry["data"]
            else:
                # Expired, remove it
                del self._cache[key]
        return None

    def set(self, query: str, data: Any, ttl: Optional[int] = None) -> None:
        """Cache query result with TTL."""
        key = self._make_key(query)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl or self.default_ttl)
        self._cache[key] = {
            "data": data,
            "expires_at": expires_at,
            "cached_at": datetime.utcnow()
        }
        logger.debug(f"Cached query result with key {key[:8]}...")

    def invalidate(self, query: Optional[str] = None) -> None:
        """Invalidate cache entry or entire cache."""
        if query:
            key = self._make_key(query)
            if key in self._cache:
                del self._cache[key]
        else:
            self._cache.clear()
            logger.info("SPARQL cache cleared")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.utcnow()
        valid_entries = sum(1 for e in self._cache.values() if now < e["expires_at"])
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries
        }


# eProcurement Ontology Prefixes
EPO_PREFIXES = {
    "epo": "http://data.europa.eu/a4g/ontology#",
    "epo-not": "http://data.europa.eu/a4g/ontology/notice#",
    "cccev": "http://data.europa.eu/m8g/",
    "dcterms": "http://purl.org/dc/terms/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "org": "http://www.w3.org/ns/org#",
    "locn": "http://www.w3.org/ns/locn#",
    "cpv": "http://data.europa.eu/cpv/cpv/",
    "at-voc": "http://publications.europa.eu/resource/authority/",
}


class TEDSPARQLClient(BaseSPARQLClient):
    """
    SPARQL client for TED Open Data.

    Uses the eProcurement Ontology (EPO) to query procurement data.
    Suitable for:
    - Bulk historical data retrieval
    - Complex filtering across multiple fields
    - Cross-referencing related tenders
    - Aggregation and analytics

    Example usage:
        async with TEDSPARQLClient() as client:
            # Get recent tenders by country
            tenders = await client.get_tenders_by_country("Belgium", limit=100)

            # Get tenders by CPV code
            tenders = await client.get_tenders_by_cpv("72000000", limit=50)
    """

    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    def __init__(
        self,
        max_results: int = 10000,
        timeout: int = 120,  # SPARQL queries can be slow
        enable_cache: bool = True,
        cache_ttl: int = 3600  # 1 hour default
    ):
        """
        Initialize TED SPARQL client.

        Args:
            max_results: Maximum results per query
            timeout: Query timeout in seconds
            enable_cache: Enable result caching
            cache_ttl: Cache time-to-live in seconds
        """
        super().__init__(
            endpoint_url=self.SPARQL_ENDPOINT,
            max_results=max_results,
            timeout=timeout
        )
        self.enable_cache = enable_cache
        self.cache = QueryCache(default_ttl=cache_ttl) if enable_cache else None

    async def _cached_select(
        self,
        query: str,
        cache_ttl: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Execute SELECT query with caching."""
        if self.cache:
            cached = self.cache.get(query)
            if cached is not None:
                return cached

        results = await self.select(query)

        if self.cache and results:
            self.cache.set(query, results, ttl=cache_ttl)

        return results

    def clear_cache(self) -> None:
        """Clear all cached query results."""
        if self.cache:
            self.cache.invalidate()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.cache:
            return self.cache.stats()
        return {"caching_enabled": False}

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    def _build_base_query(self) -> SPARQLQuery:
        """Create base query with common prefixes"""
        query = SPARQLQuery(SPARQLQueryType.SELECT)
        for prefix, namespace in EPO_PREFIXES.items():
            query.add_prefix(prefix, namespace)
        return query

    async def get_tenders_by_country(
        self,
        country: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tenders by country name.

        Args:
            country: Country name in English (e.g., "Belgium", "France")
            limit: Maximum results
            offset: Result offset for pagination

        Returns:
            List of tender dictionaries
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate ?title ?buyerName ?procedureType
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                OPTIONAL {{
                    ?notice epo:refersToProcedure ?procedure .
                    ?procedure dcterms:title ?title .
                    ?procedure epo:hasProcedureType ?procedureType .
                }}

                OPTIONAL {{
                    ?notice epo:announcesRole ?buyerRole .
                    ?buyerRole a epo:Buyer ;
                               epo:playedBy ?buyer .
                    ?buyer epo:hasLegalName ?buyerName .
                }}

                ?notice epo:hasCountryOfBuyer ?countryUri .
            }}
            ?countryUri skos:prefLabel "{country}"@en .
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            results = await self.select(query)
            logger.info(f"Found {len(results)} tenders for {country}")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for country {country}: {e}")
            return []

    async def get_tenders_by_cpv(
        self,
        cpv_code: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tenders by CPV (Common Procurement Vocabulary) code.

        Args:
            cpv_code: CPV code (e.g., "72000000" for IT services)
            limit: Maximum results
            offset: Result offset

        Returns:
            List of tender dictionaries
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX cpv: <http://data.europa.eu/cpv/cpv/>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate ?title ?cpvCode ?cpvLabel
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                ?notice epo:refersToProcedure ?procedure .
                ?procedure dcterms:title ?title .
                ?procedure epo:hasMainCPVCode ?cpvUri .
            }}

            ?cpvUri skos:notation ?cpvCode .
            FILTER(STRSTARTS(STR(?cpvCode), "{cpv_code}"))

            OPTIONAL {{
                ?cpvUri skos:prefLabel ?cpvLabel .
                FILTER(LANG(?cpvLabel) = "en")
            }}
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            results = await self.select(query)
            logger.info(f"Found {len(results)} tenders for CPV {cpv_code}")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for CPV {cpv_code}: {e}")
            return []

    async def get_tenders_by_date_range(
        self,
        date_from: date,
        date_to: date,
        countries: Optional[List[str]] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tenders published within a date range with full details.

        Args:
            date_from: Start date
            date_to: End date
            countries: Optional list of country names to filter
            limit: Maximum results
            offset: Result offset

        Returns:
            List of tender dictionaries with CPV, value, deadline, etc.
        """
        country_filter = ""
        if countries:
            country_values = " ".join([f'"{c}"@en' for c in countries])
            country_filter = f"""
                FILTER(?countryName IN ({country_values}))
            """

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate ?title ?description
                        ?buyerName ?countryCode ?countryName ?nutsCode
                        ?cpvCode ?cpvLabel ?procedureType
                        ?estimatedValue ?currency ?submissionDeadline
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                FILTER(?publicationDate >= "{date_from.isoformat()}"^^xsd:date)
                FILTER(?publicationDate <= "{date_to.isoformat()}"^^xsd:date)

                # Procedure information
                OPTIONAL {{
                    ?notice epo:refersToProcedure ?procedure .
                    ?procedure dcterms:title ?title .

                    OPTIONAL {{
                        ?procedure dcterms:description ?description .
                    }}

                    OPTIONAL {{
                        ?procedure epo:hasProcedureType ?procedureTypeUri .
                        ?procedureTypeUri skos:prefLabel ?procedureType .
                        FILTER(LANG(?procedureType) = "en")
                    }}

                    # CPV code
                    OPTIONAL {{
                        ?procedure epo:hasMainCPVCode ?cpvUri .
                        ?cpvUri skos:notation ?cpvCode .
                        OPTIONAL {{
                            ?cpvUri skos:prefLabel ?cpvLabel .
                            FILTER(LANG(?cpvLabel) = "en")
                        }}
                    }}

                    # Estimated value
                    OPTIONAL {{
                        ?procedure epo:hasEstimatedValue ?valueNode .
                        ?valueNode epo:hasAmountValue ?estimatedValue .
                        OPTIONAL {{
                            ?valueNode epo:hasCurrency ?currencyUri .
                            ?currencyUri skos:notation ?currency .
                        }}
                    }}

                    # Submission deadline - try multiple predicates as TED uses different ones
                    OPTIONAL {{
                        ?procedure epo:hasSubmissionDeadline ?submissionDeadline .
                    }}
                    OPTIONAL {{
                        ?procedure epo:hasReceiptTenderDeadline ?submissionDeadline .
                    }}
                    OPTIONAL {{
                        ?procedure epo:hasTenderSubmissionDeadline ?submissionDeadline .
                    }}
                }}

                # Buyer information
                OPTIONAL {{
                    ?notice epo:announcesRole ?buyerRole .
                    ?buyerRole a epo:Buyer ;
                               epo:playedBy ?buyer .
                    ?buyer epo:hasLegalName ?buyerName .
                }}

                # Country information - try multiple predicates
                OPTIONAL {{
                    ?notice epo:hasCountryOfBuyer ?countryUri .
                    ?countryUri skos:notation ?countryCode .
                    OPTIONAL {{
                        ?countryUri skos:prefLabel ?countryName .
                        FILTER(LANG(?countryName) = "en")
                    }}
                }}
                # Try buyer's country from address
                OPTIONAL {{
                    ?buyer epo:hasAddress ?address .
                    ?address epo:hasCountryCode ?addrCountryUri .
                    ?addrCountryUri skos:notation ?countryCode .
                }}
                # Try from organization
                OPTIONAL {{
                    ?buyer epo:hasCountryOfOrigin ?orgCountryUri .
                    ?orgCountryUri skos:notation ?countryCode .
                }}

                # NUTS codes (contain country code as first 2 chars)
                OPTIONAL {{
                    ?procedure epo:hasPlaceOfPerformance ?place .
                    ?place epo:hasNUTSCode ?nutsUri .
                    ?nutsUri skos:notation ?nutsCode .
                }}
                OPTIONAL {{
                    ?procedure epo:hasMainPlaceOfPerformance ?mainPlace .
                    ?mainPlace skos:notation ?nutsCode .
                }}
                OPTIONAL {{
                    ?notice epo:hasPlaceOfPerformance ?noticePlace .
                    ?noticePlace skos:notation ?nutsCode .
                }}

                {country_filter}
            }}
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            results = await self.select(query)
            logger.info(f"Found {len(results)} tenders between {date_from} and {date_to}")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for date range: {e}")
            return []

    async def get_tender_details(
        self,
        publication_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific tender.

        Args:
            publication_number: TED publication number

        Returns:
            Tender details or None if not found
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?notice ?title ?description ?publicationDate
                        ?buyerName ?buyerCountry
                        ?procedureType ?cpvCode ?cpvLabel
                        ?estimatedValue ?currency
                        ?submissionDeadline
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasNoticePublicationNumber "{publication_number}" ;
                        epo:hasPublicationDate ?publicationDate .

                OPTIONAL {{
                    ?notice epo:refersToProcedure ?procedure .
                    ?procedure dcterms:title ?title .
                    ?procedure dcterms:description ?description .
                    ?procedure epo:hasProcedureType ?procedureTypeUri .

                    OPTIONAL {{
                        ?procedure epo:hasMainCPVCode ?cpvUri .
                        ?cpvUri skos:notation ?cpvCode .
                        ?cpvUri skos:prefLabel ?cpvLabel .
                        FILTER(LANG(?cpvLabel) = "en")
                    }}

                    OPTIONAL {{
                        ?procedure epo:hasEstimatedValue ?valueNode .
                        ?valueNode epo:hasAmountValue ?estimatedValue .
                        ?valueNode epo:hasCurrency ?currencyUri .
                        ?currencyUri skos:notation ?currency .
                    }}

                    # Submission deadline - try multiple predicates
                    OPTIONAL {{
                        ?procedure epo:hasSubmissionDeadline ?submissionDeadline .
                    }}
                    OPTIONAL {{
                        ?procedure epo:hasReceiptTenderDeadline ?submissionDeadline .
                    }}
                    OPTIONAL {{
                        ?procedure epo:hasTenderSubmissionDeadline ?submissionDeadline .
                    }}
                }}

                OPTIONAL {{
                    ?notice epo:announcesRole ?buyerRole .
                    ?buyerRole a epo:Buyer ;
                               epo:playedBy ?buyer .
                    ?buyer epo:hasLegalName ?buyerName .

                    OPTIONAL {{
                        ?buyer epo:hasCountryOfOrigin ?buyerCountryUri .
                        ?buyerCountryUri skos:prefLabel ?buyerCountry .
                        FILTER(LANG(?buyerCountry) = "en")
                    }}
                }}
            }}
        }}
        LIMIT 1
        """

        try:
            results = await self.select(query)
            if results:
                return results[0]
            logger.warning(f"No details found for tender {publication_number}")
            return None
        except Exception as e:
            logger.error(f"SPARQL query failed for tender details: {e}")
            return None

    async def get_buyer_tenders(
        self,
        buyer_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all tenders from a specific contracting authority.

        Args:
            buyer_name: Name of contracting authority
            limit: Maximum results

        Returns:
            List of tenders from this buyer
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate ?title
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                ?notice epo:announcesRole ?buyerRole .
                ?buyerRole a epo:Buyer ;
                           epo:playedBy ?buyer .
                ?buyer epo:hasLegalName ?buyerName .

                FILTER(CONTAINS(LCASE(?buyerName), LCASE("{buyer_name}")))

                OPTIONAL {{
                    ?notice epo:refersToProcedure ?procedure .
                    ?procedure dcterms:title ?title .
                }}
            }}
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        """

        try:
            results = await self.select(query)
            logger.info(f"Found {len(results)} tenders from buyer containing '{buyer_name}'")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for buyer search: {e}")
            return []

    async def get_statistics_by_country(
        self,
        year: int
    ) -> List[Dict[str, Any]]:
        """
        Get tender count statistics by country for a given year.

        Args:
            year: Year to get statistics for

        Returns:
            List of {country, count} dictionaries
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?countryName (COUNT(DISTINCT ?notice) as ?tenderCount)
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasCountryOfBuyer ?countryUri .

                FILTER(YEAR(?publicationDate) = {year})
            }}
            ?countryUri skos:prefLabel ?countryName .
            FILTER(LANG(?countryName) = "en")
        }}
        GROUP BY ?countryName
        ORDER BY DESC(?tenderCount)
        """

        try:
            results = await self.select(query)
            logger.info(f"Got statistics for {len(results)} countries in {year}")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for country statistics: {e}")
            return []

    async def get_statistics_by_cpv(
        self,
        year: int,
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get tender count statistics by CPV code for a given year.

        Args:
            year: Year to get statistics for
            top_n: Number of top CPV codes to return

        Returns:
            List of {cpvCode, cpvLabel, count} dictionaries
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?cpvCode ?cpvLabel (COUNT(DISTINCT ?notice) as ?tenderCount)
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:refersToProcedure ?procedure .

                ?procedure epo:hasMainCPVCode ?cpvUri .
                FILTER(YEAR(?publicationDate) = {year})
            }}

            ?cpvUri skos:notation ?cpvCode .
            OPTIONAL {{
                ?cpvUri skos:prefLabel ?cpvLabel .
                FILTER(LANG(?cpvLabel) = "en")
            }}
        }}
        GROUP BY ?cpvCode ?cpvLabel
        ORDER BY DESC(?tenderCount)
        LIMIT {top_n}
        """

        try:
            results = await self.select(query)
            logger.info(f"Got CPV statistics for {len(results)} codes in {year}")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for CPV statistics: {e}")
            return []

    async def get_awarded_contracts(
        self,
        date_from: date,
        date_to: date,
        countries: Optional[List[str]] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get awarded contracts within a date range.

        Useful for analyzing historical award data and winner patterns.

        Args:
            date_from: Start date
            date_to: End date
            countries: Optional country filter
            limit: Maximum results

        Returns:
            List of awarded contracts with winner information
        """
        country_filter = ""
        if countries:
            country_values = " ".join([f'"{c}"@en' for c in countries])
            country_filter = f"""
                ?notice epo:hasCountryOfBuyer ?countryUri .
                ?countryUri skos:prefLabel ?countryName .
                FILTER(?countryName IN ({country_values}))
            """

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate
                        ?title ?winnerName ?awardValue ?currency
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:ContractAwardNotice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                FILTER(?publicationDate >= "{date_from.isoformat()}"^^xsd:date)
                FILTER(?publicationDate <= "{date_to.isoformat()}"^^xsd:date)

                OPTIONAL {{
                    ?notice epo:refersToProcedure ?procedure .
                    ?procedure dcterms:title ?title .
                }}

                OPTIONAL {{
                    ?notice epo:announcesAwardOutcome ?outcome .
                    ?outcome epo:hasWinner ?winner .
                    ?winner epo:hasLegalName ?winnerName .

                    OPTIONAL {{
                        ?outcome epo:hasAwardedValue ?valueNode .
                        ?valueNode epo:hasAmountValue ?awardValue .
                        ?valueNode epo:hasCurrency ?currencyUri .
                        ?currencyUri skos:notation ?currency .
                    }}
                }}

                {country_filter}
            }}
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        """

        try:
            results = await self.select(query)
            logger.info(f"Found {len(results)} awarded contracts")
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for awarded contracts: {e}")
            return []

    async def get_tenders_by_value_range(
        self,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        currency: str = "EUR",
        countries: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tenders within a specific value range.

        Useful for finding SME-appropriate tenders (lower values)
        or large contracts.

        Args:
            min_value: Minimum estimated value
            max_value: Maximum estimated value
            currency: Currency code (default EUR)
            countries: Optional country filter (English names)
            limit: Maximum results
            offset: Result offset for pagination

        Returns:
            List of tender dictionaries with value information
        """
        # Build value filters
        value_filters = []
        if min_value is not None:
            value_filters.append(f"?estimatedValue >= {min_value}")
        if max_value is not None:
            value_filters.append(f"?estimatedValue <= {max_value}")

        value_filter_clause = ""
        if value_filters:
            value_filter_clause = "FILTER(" + " && ".join(value_filters) + ")"

        # Build country filter
        country_filter = ""
        if countries:
            country_values = " ".join([f'"{c}"@en' for c in countries])
            country_filter = f"""
                ?notice epo:hasCountryOfBuyer ?countryUri .
                ?countryUri skos:prefLabel ?countryName .
                FILTER(?countryName IN ({country_values}))
            """

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT DISTINCT ?notice ?publicationNumber ?publicationDate ?title
                        ?buyerName ?estimatedValue ?currency
        WHERE {{
            GRAPH ?g {{
                ?notice a epo:Notice ;
                        epo:hasPublicationDate ?publicationDate ;
                        epo:hasNoticePublicationNumber ?publicationNumber .

                ?notice epo:refersToProcedure ?procedure .
                ?procedure dcterms:title ?title .

                # Value information
                ?procedure epo:hasEstimatedValue ?valueNode .
                ?valueNode epo:hasAmountValue ?estimatedValue .
                ?valueNode epo:hasCurrency ?currencyUri .
                ?currencyUri skos:notation ?currency .

                FILTER(?currency = "{currency}")
                {value_filter_clause}

                OPTIONAL {{
                    ?notice epo:announcesRole ?buyerRole .
                    ?buyerRole a epo:Buyer ;
                               epo:playedBy ?buyer .
                    ?buyer epo:hasLegalName ?buyerName .
                }}

                {country_filter}
            }}
        }}
        ORDER BY ?estimatedValue
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            # Use caching for value range queries (often repeated)
            results = await self._cached_select(query, cache_ttl=1800)  # 30 min cache
            logger.info(
                f"Found {len(results)} tenders in value range "
                f"{min_value or 0}-{max_value or 'unlimited'} {currency}"
            )
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed for value range: {e}")
            return []

    async def get_sme_friendly_tenders(
        self,
        max_value: float = 5_000_000,
        countries: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get SME-friendly tenders (lower value, suitable for small businesses).

        Convenience method that wraps get_tenders_by_value_range with
        SME-appropriate defaults.

        Args:
            max_value: Maximum tender value (default €5M)
            countries: Optional country filter
            limit: Maximum results

        Returns:
            List of SME-friendly tender dictionaries
        """
        return await self.get_tenders_by_value_range(
            min_value=None,
            max_value=max_value,
            currency="EUR",
            countries=countries,
            limit=limit
        )
