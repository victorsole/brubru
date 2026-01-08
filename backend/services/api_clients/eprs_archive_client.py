"""
EPRS Archive Client

Phase 4: Historical Archive Building
Queries the EU Publications Office (Cellar) SPARQL endpoint to systematically
retrieve ALL EPRS Think Tank publications since 2009.

This client:
1. Builds specialized SPARQL queries for EPRS publications
2. Supports filtering by year, policy area, publication type
3. Handles pagination for large result sets
4. Returns structured metadata for bulk download

Why Cellar/SPARQL:
- Official EU data source (stable, documented)
- Complete historical archive (2009-present)
- Rich structured metadata (CELEX, procedures, dates, authors)
- Designed for bulk operations
- Better than web scraping (more robust)

Documentation:
- SPARQL endpoint: https://publications.europa.eu/webapi/rdf/sparql
- CDM ontology: http://publications.europa.eu/ontology/cdm#
- Dublin Core terms: http://purl.org/dc/terms/
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from .base_sparql_client import BaseSPARQLClient, SPARQLQuery, SPARQLQueryType

logger = logging.getLogger(__name__)


class EPRSPublicationType(Enum):
    """EPRS publication types in Cellar"""
    AT_A_GLANCE = "at_a_glance"
    BRIEFING = "briefing"
    IN_DEPTH_ANALYSIS = "in_depth_analysis"
    STUDY = "study"
    BLOG_POST = "blog_post"
    ALL = "all"


class EPRSArchiveClient:
    """
    Client for querying EPRS publications from EU Publications Office (Cellar)

    Provides systematic access to 15+ years of EPRS Think Tank publications
    through SPARQL queries.

    Usage:
        client = EPRSArchiveClient()

        # Get all EPRS publications from 2023
        publications = await client.get_eprs_publications(
            year_from=2023,
            year_to=2023,
            limit=1000
        )

        # Get count of EPRS publications
        count = await client.count_eprs_publications(year_from=2009)

        # Get publications by policy area
        pubs = await client.get_eprs_publications_by_topic(
            topic="artificial intelligence",
            year_from=2020
        )
    """

    # SPARQL endpoint for EU Publications Office
    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

    # Common namespaces for EU publications
    NAMESPACES = {
        "cdm": "http://publications.europa.eu/ontology/cdm#",
        "dcterms": "http://purl.org/dc/terms/",
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "euvoc": "http://publications.europa.eu/ontology/euvoc#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    }

    # EPRS corporate body identifier in Cellar
    # EPRS is identified by corporate body code in the Publications Office
    EPRS_CORPORATE_BODY = "EP_THINK_TANK"  # European Parliament Research Service

    def __init__(
        self,
        sparql_endpoint: Optional[str] = None,
        timeout: int = 120,
        max_results: int = 100000
    ):
        """
        Initialize EPRS Archive client

        Args:
            sparql_endpoint: Override SPARQL endpoint URL
            timeout: Query timeout in seconds (default 120 for large queries)
            max_results: Maximum results per query
        """
        self.sparql = BaseSPARQLClient(
            endpoint_url=sparql_endpoint or self.SPARQL_ENDPOINT,
            timeout=timeout,
            max_results=max_results
        )

        logger.info(
            f"Initialized EPRS Archive client "
            f"(endpoint: {sparql_endpoint or self.SPARQL_ENDPOINT})"
        )

    def _build_base_query(self) -> SPARQLQuery:
        """
        Build base SPARQL query for EPRS publications

        Returns:
            SPARQLQuery with common prefixes and base patterns
        """
        query = SPARQLQuery(SPARQLQueryType.SELECT)

        # Add namespaces
        for prefix, namespace in self.NAMESPACES.items():
            query.add_prefix(prefix, namespace)

        return query

    async def get_eprs_publications(
        self,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        publication_type: Optional[EPRSPublicationType] = None,
        language: str = "en",
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get EPRS publications from Cellar

        Args:
            year_from: Start year (e.g., 2009)
            year_to: End year (e.g., 2024)
            publication_type: Filter by publication type
            language: Language code (default: "en")
            limit: Maximum results
            offset: Result offset for pagination

        Returns:
            List of EPRS publication metadata

        Example:
            # Get all briefings from 2023
            pubs = await client.get_eprs_publications(
                year_from=2023,
                year_to=2023,
                publication_type=EPRSPublicationType.BRIEFING
            )
        """
        logger.info(
            f"Querying EPRS publications "
            f"(year: {year_from}-{year_to}, type: {publication_type}, limit: {limit})"
        )

        query = self._build_base_query()

        # Select fields
        query.select([
            "?work",           # Publication URI
            "?title",          # Title
            "?date",           # Publication date
            "?type",           # Resource type
            "?celex",          # CELEX number (if applicable)
            "?isbn",           # ISBN
            "?url",            # PDF/HTML URL
            "?author",         # Author(s)
            "?subject"         # Subject/topic
        ])

        # WHERE clause - find EPRS publications
        where_clauses = [
            # Must be a work (not expression or manifestation)
            "?work a cdm:work .",

            # Must have a title
            "?work dcterms:title ?title .",

            # Must have a date
            "?work cdm:work_date_document ?date .",

            # Must be from EPRS (European Parliament Research Service)
            # This is the key filter for EPRS publications
            "?work cdm:work_created_by_agent ?creator .",
            "?creator cdm:corporate_body_id 'EP_EPRS' .",  # EPRS corporate body

            # Get resource type
            "?work cdm:resource_type ?typeUri .",
            "?typeUri skos:prefLabel ?type .",
        ]

        query.where(where_clauses)

        # OPTIONAL fields (may not always be present)
        optional_clauses = [
            # CELEX number (for legal acts)
            "?work cdm:id_celex ?celex .",

            # ISBN
            "?work cdm:isbn ?isbn .",

            # URL/manifestation
            "?work cdm:manifestation_type ?manifestation .",
            "?manifestation cdm:manifestation_url ?url .",

            # Author names
            "?work cdm:work_created_by_agent ?authorAgent .",
            "?authorAgent cdm:agent_name ?author .",

            # Subject/topic
            "?work cdm:work_is_about_concept_eurovoc ?subjectUri .",
            "?subjectUri skos:prefLabel ?subject .",
        ]

        query.optional(optional_clauses)

        # FILTER conditions
        filter_conditions = []

        # Language filter for title
        filter_conditions.append(f'LANG(?title) = "{language}"')

        # Year filter
        if year_from and year_to:
            filter_conditions.append(
                f'YEAR(?date) >= {year_from} && YEAR(?date) <= {year_to}'
            )
        elif year_from:
            filter_conditions.append(f'YEAR(?date) >= {year_from}')
        elif year_to:
            filter_conditions.append(f'YEAR(?date) <= {year_to}')

        # Publication type filter (if specified)
        if publication_type and publication_type != EPRSPublicationType.ALL:
            # Map to Cellar resource types
            type_mapping = {
                EPRSPublicationType.BRIEFING: "briefing",
                EPRSPublicationType.AT_A_GLANCE: "at a glance",
                EPRSPublicationType.IN_DEPTH_ANALYSIS: "in-depth analysis",
                EPRSPublicationType.STUDY: "study"
            }
            type_label = type_mapping.get(publication_type, "")
            if type_label:
                filter_conditions.append(f'CONTAINS(LCASE(?type), "{type_label}")')

        # Add all filters
        for condition in filter_conditions:
            query.filter(condition)

        # Order by date (newest first)
        query.order_by("DESC(?date)")

        # Pagination
        query.limit(limit)
        query.offset(offset)

        try:
            # Execute query
            results = await self.sparql.select(query)

            # Parse results
            publications = []
            for row in results:
                pub = {
                    "uri": row.get("work"),
                    "title": row.get("title"),
                    "date": row.get("date"),
                    "type": row.get("type"),
                    "celex": row.get("celex"),
                    "isbn": row.get("isbn"),
                    "url": row.get("url"),
                    "author": row.get("author"),
                    "subject": row.get("subject"),
                    "source": "cellar"
                }

                publications.append(pub)

            logger.info(f"Retrieved {len(publications)} EPRS publications from Cellar")
            return publications

        except Exception as e:
            logger.error(f"SPARQL query failed: {str(e)}")
            return []

    async def count_eprs_publications(
        self,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        publication_type: Optional[EPRSPublicationType] = None
    ) -> int:
        """
        Count EPRS publications in Cellar

        Args:
            year_from: Start year
            year_to: End year
            publication_type: Filter by type

        Returns:
            Total count
        """
        logger.info(f"Counting EPRS publications (year: {year_from}-{year_to})")

        query = self._build_base_query()

        query.select(["(COUNT(DISTINCT ?work) as ?count)"])

        where_clauses = [
            "?work a cdm:work .",
            "?work dcterms:title ?title .",
            "?work cdm:work_date_document ?date .",
            "?work cdm:work_created_by_agent ?creator .",
            "?creator cdm:corporate_body_id 'EP_EPRS' .",
        ]

        query.where(where_clauses)

        # Filters
        if year_from and year_to:
            query.filter(f'YEAR(?date) >= {year_from} && YEAR(?date) <= {year_to}')
        elif year_from:
            query.filter(f'YEAR(?date) >= {year_from}')
        elif year_to:
            query.filter(f'YEAR(?date) <= {year_to}')

        try:
            results = await self.sparql.select(query, limit=1)

            if results and len(results) > 0:
                count = int(results[0].get("count", 0))
                logger.info(f"Found {count} EPRS publications")
                return count

            return 0

        except Exception as e:
            logger.error(f"Count query failed: {str(e)}")
            return 0

    async def get_eprs_publications_by_topic(
        self,
        topic: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get EPRS publications about a specific topic

        Args:
            topic: Topic keyword (e.g., "artificial intelligence", "climate")
            year_from: Start year
            year_to: End year
            limit: Maximum results

        Returns:
            List of publications about the topic
        """
        logger.info(f"Searching EPRS publications about '{topic}'")

        query = self._build_base_query()

        query.select([
            "?work", "?title", "?date", "?type", "?url", "?subject"
        ])

        where_clauses = [
            "?work a cdm:work .",
            "?work dcterms:title ?title .",
            "?work cdm:work_date_document ?date .",
            "?work cdm:work_created_by_agent ?creator .",
            "?creator cdm:corporate_body_id 'EP_EPRS' .",
            "?work cdm:resource_type ?typeUri .",
            "?typeUri skos:prefLabel ?type .",
        ]

        query.where(where_clauses)

        # Optional subject
        query.optional([
            "?work cdm:work_is_about_concept_eurovoc ?subjectUri .",
            "?subjectUri skos:prefLabel ?subject .",
        ])

        # Topic filter (search in title and subject)
        query.filter(
            f'CONTAINS(LCASE(?title), LCASE("{topic}")) || '
            f'CONTAINS(LCASE(?subject), LCASE("{topic}"))'
        )

        # Language filter
        query.filter('LANG(?title) = "en"')

        # Year filter
        if year_from and year_to:
            query.filter(f'YEAR(?date) >= {year_from} && YEAR(?date) <= {year_to}')
        elif year_from:
            query.filter(f'YEAR(?date) >= {year_from}')

        query.order_by("DESC(?date)")
        query.limit(limit)

        try:
            results = await self.sparql.select(query)

            publications = []
            for row in results:
                publications.append({
                    "uri": row.get("work"),
                    "title": row.get("title"),
                    "date": row.get("date"),
                    "type": row.get("type"),
                    "url": row.get("url"),
                    "subject": row.get("subject"),
                    "source": "cellar"
                })

            logger.info(f"Found {len(publications)} publications about '{topic}'")
            return publications

        except Exception as e:
            logger.error(f"Topic search failed: {str(e)}")
            return []

    async def get_eprs_publication_years(self) -> List[int]:
        """
        Get list of years with EPRS publications

        Returns:
            List of years (sorted, oldest to newest)
        """
        logger.info("Fetching EPRS publication years")

        query = self._build_base_query()

        query.select(["(DISTINCT YEAR(?date) as ?year)"])

        where_clauses = [
            "?work a cdm:work .",
            "?work cdm:work_date_document ?date .",
            "?work cdm:work_created_by_agent ?creator .",
            "?creator cdm:corporate_body_id 'EP_EPRS' .",
        ]

        query.where(where_clauses)
        query.order_by("ASC(?year)")

        try:
            results = await self.sparql.select(query)

            years = []
            for row in results:
                year_str = row.get("year")
                if year_str:
                    try:
                        year = int(year_str)
                        years.append(year)
                    except (ValueError, TypeError):
                        continue

            logger.info(f"Found EPRS publications in {len(years)} years: {years[:5]}...{years[-5:]}")
            return sorted(years)

        except Exception as e:
            logger.error(f"Years query failed: {str(e)}")
            return []

    async def get_publication_full_metadata(
        self,
        work_uri: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a specific publication

        Args:
            work_uri: Publication URI from Cellar

        Returns:
            Full metadata including all available fields
        """
        logger.info(f"Fetching full metadata for {work_uri}")

        query = self._build_base_query()

        query.select([
            "?title", "?date", "?type", "?celex", "?isbn",
            "?url", "?author", "?subject", "?language",
            "?abstract", "?publisher", "?format"
        ])

        query.where([
            f"<{work_uri}> dcterms:title ?title .",
            f"<{work_uri}> cdm:work_date_document ?date .",
            f"<{work_uri}> cdm:resource_type ?typeUri .",
            "?typeUri skos:prefLabel ?type .",
        ])

        query.optional([
            f"<{work_uri}> cdm:id_celex ?celex .",
            f"<{work_uri}> cdm:isbn ?isbn .",
            f"<{work_uri}> cdm:manifestation_type ?manifestation .",
            "?manifestation cdm:manifestation_url ?url .",
            f"<{work_uri}> cdm:work_created_by_agent ?authorAgent .",
            "?authorAgent cdm:agent_name ?author .",
            f"<{work_uri}> cdm:work_is_about_concept_eurovoc ?subjectUri .",
            "?subjectUri skos:prefLabel ?subject .",
            f"<{work_uri}> dcterms:language ?language .",
            f"<{work_uri}> dcterms:abstract ?abstract .",
            f"<{work_uri}> dcterms:publisher ?publisher .",
            f"<{work_uri}> dcterms:format ?format .",
        ])

        query.filter('LANG(?title) = "en"')
        query.limit(1)

        try:
            results = await self.sparql.select(query)

            if results and len(results) > 0:
                data = results[0]
                return {
                    "uri": work_uri,
                    "title": data.get("title"),
                    "date": data.get("date"),
                    "type": data.get("type"),
                    "celex": data.get("celex"),
                    "isbn": data.get("isbn"),
                    "url": data.get("url"),
                    "author": data.get("author"),
                    "subject": data.get("subject"),
                    "language": data.get("language"),
                    "abstract": data.get("abstract"),
                    "publisher": data.get("publisher"),
                    "format": data.get("format"),
                    "source": "cellar"
                }

            return None

        except Exception as e:
            logger.error(f"Metadata query failed: {str(e)}")
            return None

    async def health_check(self) -> bool:
        """
        Check if Cellar SPARQL endpoint is accessible

        Returns:
            True if healthy
        """
        try:
            return await self.sparql.health_check()
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close SPARQL client"""
        await self.sparql.close()
        logger.info("Closed EPRS Archive client")


# Global singleton
_eprs_archive_client: Optional[EPRSArchiveClient] = None


def get_eprs_archive_client(
    sparql_endpoint: Optional[str] = None
) -> EPRSArchiveClient:
    """
    Get global EPRS Archive client instance

    Args:
        sparql_endpoint: Override SPARQL endpoint

    Returns:
        EPRSArchiveClient instance
    """
    global _eprs_archive_client

    if _eprs_archive_client is None:
        _eprs_archive_client = EPRSArchiveClient(
            sparql_endpoint=sparql_endpoint
        )

    return _eprs_archive_client
