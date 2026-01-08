"""
Publications Office API Client

Provides access to EU Publications Office services:
- TED (Tenders Electronic Daily) - Public procurement notices
- Publications search API - Books, reports, statistics
- SPARQL endpoint - Linked open data
- RSS feeds - Latest publications

Documentation:
- TED: https://ted.europa.eu/en/
- TED API: https://ted.europa.eu/api/
- Publications Office: https://op.europa.eu/en/
- SPARQL: https://publications.europa.eu/webapi/rdf/sparql
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_sparql_client import BaseSPARQLClient, SPARQLQuery, SPARQLQueryType
from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class TEDNoticeType(Enum):
    """TED notice types"""
    CONTRACT_NOTICE = "contract_notice"
    CONTRACT_AWARD = "contract_award"
    PRIOR_INFORMATION = "prior_information"
    CONCESSION = "concession"
    DESIGN_CONTEST = "design_contest"
    BUYER_PROFILE = "buyer_profile"


class TEDProcedureType(Enum):
    """TED procedure types"""
    OPEN = "open"
    RESTRICTED = "restricted"
    NEGOTIATED = "negotiated"
    COMPETITIVE_DIALOGUE = "competitive_dialogue"
    INNOVATION_PARTNERSHIP = "innovation_partnership"


class PublicationsOfficeClient(BaseAPIClient):
    """
    Client for EU Publications Office APIs

    Features:
    - TED procurement notices search
    - Publications catalog search
    - Document metadata retrieval
    - SPARQL queries
    - RSS feed monitoring
    """

    # API Endpoints
    BASE_URL = "https://op.europa.eu/api"
    TED_API_URL = "https://ted.europa.eu/api"
    TED_SEARCH_URL = "https://ted.europa.eu/api/v3/notices/search"
    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
    RSS_BASE = "https://op.europa.eu/en/web/general-publications"

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        ted_api_key: Optional[str] = None,
        sparql_endpoint: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize Publications Office client

        Args:
            endpoint_url: Override base URL
            ted_api_key: TED API key (optional, for higher rate limits)
            sparql_endpoint: Override SPARQL endpoint
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL

        # Determine auth type
        auth_type = AuthType.API_KEY if ted_api_key else AuthType.NONE

        super().__init__(
            base_url=base_url,
            auth_type=auth_type,
            api_key=ted_api_key,
            rate_limit_calls=60 if not ted_api_key else None,  # 60 calls/min without key
            rate_limit_period=60,
            timeout=timeout
        )

        self.ted_api_key = ted_api_key

        # SPARQL client
        self.sparql = BaseSPARQLClient(
            endpoint_url=sparql_endpoint or self.SPARQL_ENDPOINT,
            max_results=100000,
            timeout=timeout
        )

        # RSS client
        self.rss_client = BaseRSSClient(
            cache_ttl=1800,  # 30 minutes
            timeout=timeout
        )

        logger.info(f"Initialized Publications Office client (TED API key: {bool(ted_api_key)})")

    async def search_ted_notices(
        self,
        query: Optional[str] = None,
        notice_type: Optional[TEDNoticeType] = None,
        country: Optional[str] = None,
        cpv_code: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search TED procurement notices

        Args:
            query: Free text search
            notice_type: Type of notice
            country: Country code (e.g., "ES", "FR")
            cpv_code: Common Procurement Vocabulary code
            date_from: Publication date from
            date_to: Publication date to
            limit: Maximum results

        Returns:
            List of procurement notices
        """
        logger.info(f"Searching TED notices: {query or 'all'}")

        # Build query parameters
        params = {
            "limit": limit,
            "offset": 0
        }

        if query:
            params["q"] = query

        if notice_type:
            params["notice_type"] = notice_type.value

        if country:
            params["country"] = country

        if cpv_code:
            params["cpv"] = cpv_code

        if date_from:
            params["date_from"] = date_from.strftime("%Y-%m-%d")

        if date_to:
            params["date_to"] = date_to.strftime("%Y-%m-%d")

        try:
            # Use TED search endpoint directly
            headers = {}
            if self.ted_api_key:
                headers["X-API-Key"] = self.ted_api_key

            response = await self.client.get(
                self.TED_SEARCH_URL,
                params=params,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()

            notices = []
            if "notices" in data:
                for notice in data["notices"]:
                    notices.append({
                        "id": notice.get("id"),
                        "title": notice.get("title"),
                        "notice_type": notice.get("notice_type"),
                        "publication_date": notice.get("publication_date"),
                        "country": notice.get("country"),
                        "cpv_codes": notice.get("cpv_codes", []),
                        "contracting_authority": notice.get("contracting_authority"),
                        "value": notice.get("value"),
                        "currency": notice.get("currency"),
                        "url": notice.get("url")
                    })

            logger.info(f"Found {len(notices)} TED notices")
            return notices

        except Exception as e:
            logger.error(f"TED search failed: {str(e)}")
            return []

    async def get_ted_notice_by_id(
        self,
        notice_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get full details of a TED notice by ID

        Args:
            notice_id: TED notice identifier

        Returns:
            Notice details
        """
        logger.info(f"Fetching TED notice: {notice_id}")

        try:
            headers = {}
            if self.ted_api_key:
                headers["X-API-Key"] = self.ted_api_key

            response = await self.client.get(
                f"{self.TED_API_URL}/v3/notices/{notice_id}",
                headers=headers
            )
            response.raise_for_status()

            notice = response.json()

            return {
                "id": notice.get("id"),
                "title": notice.get("title"),
                "description": notice.get("description"),
                "notice_type": notice.get("notice_type"),
                "publication_date": notice.get("publication_date"),
                "deadline": notice.get("deadline"),
                "country": notice.get("country"),
                "cpv_codes": notice.get("cpv_codes", []),
                "contracting_authority": notice.get("contracting_authority", {}),
                "value": notice.get("value"),
                "currency": notice.get("currency"),
                "procedure_type": notice.get("procedure_type"),
                "award_criteria": notice.get("award_criteria"),
                "url": notice.get("url"),
                "documents": notice.get("documents", [])
            }

        except Exception as e:
            logger.error(f"Failed to fetch TED notice {notice_id}: {str(e)}")
            return None

    async def search_publications(
        self,
        query: str,
        publication_type: Optional[str] = None,
        year: Optional[int] = None,
        author: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search EU publications (books, reports, statistics)

        Args:
            query: Search query
            publication_type: Type of publication
            year: Publication year
            author: Author or institution
            limit: Maximum results

        Returns:
            List of publications
        """
        logger.info(f"Searching publications: {query}")

        # Build SPARQL query
        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        sparql_query.add_prefix("dcterms", "http://purl.org/dc/terms/")

        sparql_query.select(["?pub", "?title", "?date", "?author", "?type"])

        where_clauses = [
            "?pub dcterms:title ?title .",
            "?pub dcterms:date ?date .",
            "?pub a ?type ."
        ]

        filter_clauses = [
            'LANG(?title) = "en"',
            f'CONTAINS(LCASE(?title), LCASE("{query}"))'
        ]

        if year:
            filter_clauses.append(f'YEAR(?date) = {year}')

        sparql_query.where(where_clauses)

        sparql_query.optional([
            "?pub dcterms:creator ?author ."
        ])

        for filter_clause in filter_clauses:
            sparql_query.filter(filter_clause)

        sparql_query.order_by("DESC(?date)")
        sparql_query.limit(limit)

        try:
            results = await self.sparql.select(sparql_query)

            publications = []
            for row in results:
                publications.append({
                    "uri": row.get("pub"),
                    "title": row.get("title"),
                    "date": row.get("date"),
                    "author": row.get("author"),
                    "type": row.get("type")
                })

            logger.info(f"Found {len(publications)} publications")
            return publications

        except Exception as e:
            logger.error(f"Publication search failed: {str(e)}")
            return []

    async def get_publication_metadata(
        self,
        uri: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific publication

        Args:
            uri: Publication URI

        Returns:
            Publication metadata
        """
        logger.info(f"Fetching publication metadata: {uri}")

        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        sparql_query.add_prefix("dcterms", "http://purl.org/dc/terms/")

        sparql_query.select([
            "?title", "?date", "?author", "?publisher",
            "?isbn", "?description", "?language"
        ])

        sparql_query.where([
            f"<{uri}> dcterms:title ?title .",
            f"<{uri}> dcterms:date ?date ."
        ])

        sparql_query.optional([
            f"<{uri}> dcterms:creator ?author .",
            f"<{uri}> dcterms:publisher ?publisher .",
            f"<{uri}> cdm:isbn ?isbn .",
            f"<{uri}> dcterms:description ?description .",
            f"<{uri}> dcterms:language ?language ."
        ])

        sparql_query.filter('LANG(?title) = "en"')

        try:
            results = await self.sparql.select(sparql_query, limit=1)

            if results:
                data = results[0]
                return {
                    "uri": uri,
                    "title": data.get("title"),
                    "date": data.get("date"),
                    "author": data.get("author"),
                    "publisher": data.get("publisher"),
                    "isbn": data.get("isbn"),
                    "description": data.get("description"),
                    "language": data.get("language")
                }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch publication metadata: {str(e)}")
            return None

    async def get_ted_statistics(
        self,
        country: Optional[str] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get TED procurement statistics

        Args:
            country: Filter by country
            year: Filter by year

        Returns:
            Statistics summary
        """
        logger.info(f"Fetching TED statistics (country: {country}, year: {year})")

        # Build date range
        if year:
            date_from = datetime(year, 1, 1)
            date_to = datetime(year, 12, 31)
        else:
            date_from = datetime.now() - timedelta(days=365)
            date_to = datetime.now()

        # Search notices
        notices = await self.search_ted_notices(
            country=country,
            date_from=date_from,
            date_to=date_to,
            limit=1000
        )

        # Calculate statistics
        total_value = 0
        notice_types = {}
        cpv_codes = {}

        for notice in notices:
            # Count by notice type
            notice_type = notice.get("notice_type", "unknown")
            notice_types[notice_type] = notice_types.get(notice_type, 0) + 1

            # Sum values
            value = notice.get("value")
            if value:
                try:
                    total_value += float(value)
                except (ValueError, TypeError):
                    pass

            # Count CPV codes
            for cpv in notice.get("cpv_codes", []):
                cpv_codes[cpv] = cpv_codes.get(cpv, 0) + 1

        return {
            "total_notices": len(notices),
            "total_value": total_value,
            "period": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat()
            },
            "country": country,
            "notice_types": notice_types,
            "top_cpv_codes": dict(sorted(cpv_codes.items(), key=lambda x: x[1], reverse=True)[:10])
        }

    async def search_ted_by_cpv(
        self,
        cpv_code: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search TED notices by CPV code

        CPV (Common Procurement Vocabulary) is the EU classification for public procurement.

        Args:
            cpv_code: CPV code (e.g., "45000000" for construction work)
            limit: Maximum results

        Returns:
            List of notices
        """
        logger.info(f"Searching TED by CPV code: {cpv_code}")

        return await self.search_ted_notices(
            cpv_code=cpv_code,
            limit=limit
        )

    async def get_active_tenders(
        self,
        country: Optional[str] = None,
        cpv_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get currently active tenders (with future deadlines)

        Args:
            country: Filter by country
            cpv_code: Filter by CPV code

        Returns:
            List of active tenders
        """
        logger.info("Fetching active tenders")

        # Search contract notices from last 90 days
        date_from = datetime.now() - timedelta(days=90)

        notices = await self.search_ted_notices(
            notice_type=TEDNoticeType.CONTRACT_NOTICE,
            country=country,
            cpv_code=cpv_code,
            date_from=date_from,
            limit=200
        )

        # Filter for future deadlines
        active_tenders = []
        now = datetime.now()

        for notice in notices:
            deadline = notice.get("deadline")
            if deadline:
                try:
                    deadline_date = datetime.fromisoformat(deadline)
                    if deadline_date > now:
                        active_tenders.append(notice)
                except (ValueError, TypeError):
                    pass

        logger.info(f"Found {len(active_tenders)} active tenders")
        return active_tenders

    async def health_check(self) -> bool:
        """
        Check if Publications Office APIs are accessible

        Returns:
            True if healthy
        """
        try:
            # Test SPARQL endpoint
            is_healthy = await self.sparql.health_check()
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.sparql.close()
        await self.rss_client.close()
        logger.info("Closed Publications Office client")
