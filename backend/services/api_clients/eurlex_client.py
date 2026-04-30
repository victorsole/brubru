"""
EUR-Lex API Client

Provides access to EUR-Lex (Official Journal of the European Union):
- Cellar REST API - Document metadata, full texts, relationships
- SPARQL Endpoint - Semantic queries on legal documents
- SOAP API - Advanced search (requires authentication)
- RSS Feeds - Latest publications by topic

Documentation:
- Cellar API: https://op.europa.eu/en/web/cellar
- SPARQL: http://publications.europa.eu/webapi/rdf/sparql
- EUR-Lex Portal: https://eur-lex.europa.eu/
"""

import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_sparql_client import BaseSPARQLClient, SPARQLQuery, SPARQLQueryType, SPARQLResultFormat
from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class EURLexDocumentType(Enum):
    """EUR-Lex document types"""
    REGULATION = "regulation"
    DIRECTIVE = "directive"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    OPINION = "opinion"
    TREATY = "treaty"
    CASE_LAW = "case_law"
    NATIONAL_IMPL = "national_implementation"
    PROPOSAL = "proposal"


class EURLexSubjectMatter(Enum):
    """Major EU policy areas"""
    AGRICULTURE = "01"
    CUSTOMS_UNION = "02"
    TAXATION = "03"
    COMPETITION = "04"
    EMPLOYMENT = "05"
    SOCIAL_POLICY = "06"
    TRANSPORT = "07"
    FREE_MOVEMENT = "08"
    ECONOMIC_POLICY = "09"
    COMMERCIAL_POLICY = "10"
    ENVIRONMENT = "15"
    CONSUMER_PROTECTION = "16"
    ENERGY = "17"
    INDUSTRY = "18"
    DIGITAL = "19"
    JUSTICE = "20"


class EURLexClient(BaseAPIClient):
    """
    Client for EUR-Lex APIs and data sources

    Features:
    - Search legal documents
    - Retrieve document metadata and full text
    - SPARQL queries on legal ontology
    - Document relationships (amendments, revisions, implementations)
    - RSS feed monitoring
    """

    # API Endpoints
    BASE_URL = "https://eur-lex.europa.eu"
    CELLAR_API = "https://publications.europa.eu/resource/cellar"
    SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
    SOAP_ENDPOINT = "https://eur-lex.europa.eu/EURLexWebService"
    RSS_BASE = "https://eur-lex.europa.eu/EN/rss"

    # Legacy RSS Feeds (may be deprecated)
    RSS_FEEDS = {
        "official_journal": f"{RSS_BASE}/rss_oj.xml",
        "competition": f"{RSS_BASE}/rss_competition.xml",
        "state_aid": f"{RSS_BASE}/rss_state_aid.xml",
        "environment": f"{RSS_BASE}/rss_environment.xml",
        "consumer_protection": f"{RSS_BASE}/rss_consumer.xml",
        "digital_economy": f"{RSS_BASE}/rss_digital.xml",
        "transport": f"{RSS_BASE}/rss_transport.xml",
    }

    # Predefined RSS Feeds (Official - January 2026)
    # These are the official EUR-Lex predefined RSS feeds that are actively maintained
    PREDEFINED_RSS_FEEDS = {
        "parliament_council_legislation": f"{BASE_URL}/EN/display-feed.rss?rssId=162",
        "court_caselaw_all": f"{BASE_URL}/EN/display-feed.rss?rssId=163",
        "court_ecj_caselaw": f"{BASE_URL}/EN/display-feed.rss?rssId=164",
        "commission_proposals": f"{BASE_URL}/EN/display-feed.rss?rssId=161",
        "official_journal_l": f"{BASE_URL}/EN/display-feed.rss?rssId=222",
        "official_journal_c": f"{BASE_URL}/EN/display-feed.rss?rssId=221",
    }

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        sparql_endpoint: Optional[str] = None,
        soap_username: Optional[str] = None,
        soap_password: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Initialize EUR-Lex client

        Args:
            endpoint_url: Override base URL
            sparql_endpoint: Override SPARQL endpoint
            soap_username: SOAP API username (optional)
            soap_password: SOAP API password (optional)
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.NONE,  # Most endpoints are public
            timeout=timeout
        )

        # SPARQL client
        self.sparql = BaseSPARQLClient(
            endpoint_url=sparql_endpoint or self.SPARQL_ENDPOINT,
            max_results=100000,  # EUR-Lex supports large result sets
            timeout=timeout
        )

        # RSS client
        self.rss_client = BaseRSSClient(
            cache_ttl=900,
            timeout=timeout
        )

        # SOAP credentials (for advanced features)
        self.soap_username = soap_username
        self.soap_password = soap_password
        self.soap_auth_available = bool(soap_username and soap_password)

        # In-memory EuroVoc cache: key -> (results, timestamp)
        # TTL: 24 hours, max 200 entries, LRU eviction
        self._eurovoc_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
        self._eurovoc_cache_ttl = 86400  # 24 hours
        self._eurovoc_cache_max = 200

        logger.info(f"Initialized EUR-Lex client (SOAP auth: {self.soap_auth_available})")

    async def search_documents(
        self,
        query: str,
        document_type: Optional[EURLexDocumentType] = None,
        subject_matter: Optional[EURLexSubjectMatter] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        language: str = "en",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search EUR-Lex documents via SPARQL

        Args:
            query: Search text
            document_type: Filter by document type
            subject_matter: Filter by subject matter code
            date_from: Start date
            date_to: End date
            language: Language code
            limit: Maximum results

        Returns:
            List of documents
        """
        logger.info(f"Searching EUR-Lex documents: {query}")

        # Build SPARQL query
        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        # Add common prefixes
        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        sparql_query.add_prefix("dcterms", "http://purl.org/dc/terms/")
        sparql_query.add_prefix("skos", "http://www.w3.org/2004/02/skos/core#")

        # Select variables
        sparql_query.select(["?doc", "?celex", "?title", "?date", "?type"])

        # Where clauses
        where_clauses = [
            "?doc cdm:resource_legal_id_celex ?celex .",
            "?doc cdm:work_date_document ?date .",
            "?doc a ?type ."
        ]

        # Optional title - not all documents have titles in all languages
        sparql_query.optional([
            f"?doc cdm:resource_legal_title ?title . FILTER(LANG(?title) = '{language}')"
        ])

        # Add filters
        filter_clauses = []

        # Only add query filter if query is not empty
        if query and query.strip():
            # Search in both title (if exists) and CELEX
            filter_clauses.append(
                f'(CONTAINS(LCASE(STR(?title)), LCASE("{query}")) || '
                f'CONTAINS(LCASE(STR(?celex)), LCASE("{query}")))'
            )

        if date_from:
            filter_clauses.append(f'?date >= "{date_from.isoformat()}"^^xsd:date')
        if date_to:
            filter_clauses.append(f'?date <= "{date_to.isoformat()}"^^xsd:date')

        sparql_query.where(where_clauses)
        for filter_clause in filter_clauses:
            sparql_query.filter(filter_clause)

        sparql_query.order_by("DESC(?date)")
        sparql_query.limit(limit)

        # Execute query
        try:
            results = await self.sparql.select(sparql_query)

            documents = []
            for row in results:
                documents.append({
                    "uri": row.get("doc"),
                    "celex": row.get("celex"),
                    "title": row.get("title"),
                    "date": row.get("date"),
                    "type": row.get("type"),
                    "language": language
                })

            logger.info(f"Found {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Document search failed: {str(e)}")
            return []

    async def get_document_by_celex(
        self,
        celex: str,
        language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """
        Get document metadata by CELEX number

        CELEX is the unique identifier for EU documents.
        Format: [sector][year][type][number] (e.g., "32023R1234")

        Args:
            celex: CELEX number
            language: Language code

        Returns:
            Document metadata
        """
        logger.info(f"Fetching document by CELEX: {celex}")

        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        sparql_query.add_prefix("dcterms", "http://purl.org/dc/terms/")

        sparql_query.select(["?doc", "?celexValue", "?title", "?date", "?type", "?subject", "?author"])

        sparql_query.where([
            "?doc cdm:resource_legal_id_celex ?celexValue .",
            "?doc cdm:work_date_document ?date .",
            "?doc a ?type ."
        ])

        sparql_query.optional([
            f"?doc cdm:resource_legal_title ?title . FILTER(LANG(?title) = '{language}')",
            "?doc cdm:work_has_subject-matter ?subject .",
            "?doc cdm:work_created_by_agent ?author ."
        ])

        # Use STR() for exact CELEX matching
        sparql_query.filter(f'STR(?celexValue) = "{celex}"')

        try:
            results = await self.sparql.select(sparql_query, limit=1)

            if results:
                doc = results[0]
                return {
                    "celex": celex,
                    "uri": doc.get("doc"),
                    "title": doc.get("title"),
                    "date": doc.get("date"),
                    "type": doc.get("type"),
                    "subject": doc.get("subject"),
                    "author": doc.get("author"),
                    "language": language
                }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch document {celex}: {str(e)}")
            return None

    async def get_document_html(
        self,
        celex: str,
        language: str = "EN"
    ) -> Optional[str]:
        """
        Get document HTML/XHTML page from the Publications Office Cellar API.

        Per CLAUDE.md learned rule (`feedback_cellar_needs_accept_language`):
        Cellar `/resource/celex/...` requires BOTH `Accept: application/xhtml+xml`
        AND `Accept-Language: en` (otherwise 400). EUR-Lex `/legal-content/...`
        is WAF-blocked for body scraping; we never call it for HTML body.

        Args:
            celex: CELEX number
            language: Language code (uppercase: EN, FR, DE, etc.)

        Returns:
            XHTML content of the document, or None if unavailable.
        """
        logger.info(f"Fetching XHTML for {celex} in {language} via Cellar API")

        cellar_url = f"https://publications.europa.eu/resource/celex/{celex}"
        headers = {
            "Accept": "application/xhtml+xml",
            "Accept-Language": language.lower(),
            "User-Agent": "Mozilla/5.0 (Brubru EU policy intelligence)",
        }

        try:
            response = await self.client.get(cellar_url, headers=headers)
            if response.status_code == 200 and response.text and len(response.text) > 5000:
                logger.info(f"Cellar fetch OK for {celex} ({len(response.text)} bytes)")
                return response.text

            # Some documents (e.g. agreements) only have alternative formats;
            # try the HTML notice URL as a last-resort fallback for metadata-only
            logger.warning(f"Cellar returned {response.status_code} / {len(response.text)} bytes for {celex}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch XHTML for {celex} via Cellar: {str(e)}")
            return None

    async def get_document_full_text(
        self,
        celex: str,
        language: str = "en"
    ) -> Optional[str]:
        """
        Get full text of a document from EUR-Lex HTML page

        This method fetches the HTML page and extracts the text content.
        For structured access to the document, use get_document_html() instead.

        Args:
            celex: CELEX number
            language: Language code

        Returns:
            Full text content (basic extraction from HTML)
        """
        html = await self.get_document_html(celex, language.upper())

        if html:
            # Basic text extraction - could be improved with BeautifulSoup
            # For now, return HTML as-is since it's the most complete representation
            return html

        return None

    async def get_document_relationships(
        self,
        celex: str
    ) -> Dict[str, List[str]]:
        """
        Get relationships for a document (amendments, revisions, implementations)

        Args:
            celex: CELEX number

        Returns:
            Dictionary of relationships
        """
        logger.info(f"Fetching relationships for {celex}")

        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")

        sparql_query.select(["?relation", "?relatedDoc", "?relatedCelex"])

        sparql_query.where([
            "?doc cdm:resource_legal_id_celex ?celexValue .",
            "?doc ?relation ?relatedDoc .",
            "?relatedDoc cdm:resource_legal_id_celex ?relatedCelex ."
        ])

        sparql_query.filter(f'STR(?celexValue) = "{celex}"')
        sparql_query.filter(
            '?relation IN (cdm:work_amended_by, cdm:work_amends, '
            'cdm:work_corrected_by, cdm:work_corrects, '
            'cdm:work_repealed_by, cdm:work_repeals, '
            'cdm:work_implemented_by)'
        )

        try:
            results = await self.sparql.select(sparql_query)

            relationships = {
                "amended_by": [],
                "amends": [],
                "corrected_by": [],
                "corrects": [],
                "repealed_by": [],
                "repeals": [],
                "implemented_by": []
            }

            for row in results:
                relation = row.get("relation", "")
                related_celex = row.get("relatedCelex")

                if "amended_by" in relation:
                    relationships["amended_by"].append(related_celex)
                elif "amends" in relation:
                    relationships["amends"].append(related_celex)
                elif "corrected_by" in relation:
                    relationships["corrected_by"].append(related_celex)
                elif "corrects" in relation:
                    relationships["corrects"].append(related_celex)
                elif "repealed_by" in relation:
                    relationships["repealed_by"].append(related_celex)
                elif "repeals" in relation:
                    relationships["repeals"].append(related_celex)
                elif "implemented_by" in relation:
                    relationships["implemented_by"].append(related_celex)

            return relationships

        except Exception as e:
            logger.error(f"Failed to fetch relationships for {celex}: {str(e)}")
            return {}

    async def get_documents_by_subject(
        self,
        subject_matter: EURLexSubjectMatter,
        date_from: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get documents by subject matter code

        Args:
            subject_matter: Subject matter enum
            date_from: Start date
            limit: Maximum results

        Returns:
            List of documents
        """
        logger.info(f"Fetching documents for subject: {subject_matter.name}")

        if not date_from:
            date_from = datetime.now() - timedelta(days=365)

        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        sparql_query.add_prefix("eurovoc", "http://eurovoc.europa.eu/")

        sparql_query.select(["?doc", "?celex", "?title", "?date"])

        sparql_query.where([
            "?doc cdm:resource_legal_id_celex ?celex .",
            "?doc cdm:resource_legal_title ?title .",
            "?doc cdm:work_date_document ?date .",
            f"?doc cdm:work_has_subject-matter eurovoc:{subject_matter.value} ."
        ])

        sparql_query.filter(f'?date >= "{date_from.isoformat()}"^^xsd:date')
        sparql_query.filter('LANG(?title) = "en"')

        sparql_query.order_by("DESC(?date)")
        sparql_query.limit(limit)

        try:
            results = await self.sparql.select(sparql_query)

            documents = []
            for row in results:
                documents.append({
                    "uri": row.get("doc"),
                    "celex": row.get("celex"),
                    "title": row.get("title"),
                    "date": row.get("date")
                })

            logger.info(f"Found {len(documents)} documents for {subject_matter.name}")
            return documents

        except Exception as e:
            logger.error(f"Subject matter search failed: {str(e)}")
            return []

    async def get_latest_official_journal(
        self,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get latest Official Journal publications

        Args:
            days: Number of days to look back

        Returns:
            List of OJ entries
        """
        since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching Official Journal entries from last {days} days")

        try:
            feed = await self.rss_client.fetch_feed(
                self.RSS_FEEDS["official_journal"],
                since=since
            )

            entries = []
            for entry in feed.entries:
                entries.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "categories": entry.categories
                })

            logger.info(f"Found {len(entries)} OJ entries")
            return entries

        except Exception as e:
            logger.error(f"Failed to fetch Official Journal RSS: {str(e)}")
            return []

    async def get_rss_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch specific EUR-Lex RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}")

        feed_url = self.RSS_FEEDS[feed_name]
        return await self.rss_client.fetch_feed(feed_url, since=since)

    # =========================================================================
    # Predefined RSS Feed Methods (Added January 2026)
    # =========================================================================

    async def get_predefined_rss_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch a predefined EUR-Lex RSS feed.

        Args:
            feed_name: Feed name from PREDEFINED_RSS_FEEDS dict:
                - 'parliament_council_legislation': All EP and Council acts
                - 'commission_proposals': COM documents and proposals
                - 'official_journal_l': OJ L series (legislation)
                - 'official_journal_c': OJ C series (information)
                - 'court_caselaw_all': All CJEU case law
                - 'court_ecj_caselaw': European Court of Justice case law
            since: Only get entries after this date

        Returns:
            RSS feed with entries
        """
        if feed_name not in self.PREDEFINED_RSS_FEEDS:
            valid_feeds = list(self.PREDEFINED_RSS_FEEDS.keys())
            raise ValueError(f"Unknown feed: {feed_name}. Valid feeds: {valid_feeds}")

        feed_url = self.PREDEFINED_RSS_FEEDS[feed_name]
        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_latest_legislation(
        self,
        since: Optional[datetime] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get latest Parliament and Council legislation from RSS feed.

        Args:
            since: Only get entries after this date
            days: If since not provided, get entries from last N days

        Returns:
            List of legislation items with CELEX numbers
        """
        import re

        if not since:
            since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching latest legislation since {since.date()}")

        try:
            feed = await self.get_predefined_rss_feed(
                "parliament_council_legislation",
                since=since
            )

            entries = []
            for entry in feed.entries:
                # Extract CELEX from title (format: "CELEX:32026R0147: Title...")
                celex_match = re.search(r'CELEX:(\d+[A-Z]+\d+)', entry.title)
                celex = celex_match.group(1) if celex_match else None

                # Clean title (remove CELEX prefix)
                title = entry.title
                if celex:
                    title = re.sub(r'^CELEX:\d+[A-Z]+\d+:\s*', '', title)

                # Determine document type from CELEX
                doc_type = None
                if celex:
                    type_code = re.search(r'\d{5}([A-Z]+)', celex)
                    if type_code:
                        type_map = {
                            'R': 'Regulation',
                            'L': 'Directive',
                            'D': 'Decision',
                            'H': 'Recommendation',
                            'C': 'Declaration',
                        }
                        doc_type = type_map.get(type_code.group(1), type_code.group(1))

                entries.append({
                    "celex": celex,
                    "title": title,
                    "link": entry.link,
                    "published": entry.published,
                    "doc_type": doc_type,
                    "creator": getattr(entry, 'creator', None),
                    "summary": entry.summary,
                })

            logger.info(f"Found {len(entries)} legislation entries")
            return entries

        except Exception as e:
            logger.error(f"Failed to fetch latest legislation: {str(e)}")
            return []

    async def get_latest_commission_proposals(
        self,
        since: Optional[datetime] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get latest Commission proposals and related documents.

        Args:
            since: Only get entries after this date
            days: If since not provided, get entries from last N days

        Returns:
            List of proposal items with CELEX numbers
        """
        import re

        if not since:
            since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching Commission proposals since {since.date()}")

        try:
            feed = await self.get_predefined_rss_feed(
                "commission_proposals",
                since=since
            )

            entries = []
            for entry in feed.entries:
                # Extract CELEX from title
                celex_match = re.search(r'CELEX:(\d+[A-Z]+\d+)', entry.title)
                celex = celex_match.group(1) if celex_match else None

                # Extract COM number if present
                com_match = re.search(r'COM\((\d{4})\)(\d+)', entry.title)
                com_number = f"COM({com_match.group(1)}){com_match.group(2)}" if com_match else None

                # Clean title
                title = entry.title
                if celex:
                    title = re.sub(r'^CELEX:\d+[A-Z]+\d+:\s*', '', title)

                entries.append({
                    "celex": celex,
                    "com_number": com_number,
                    "title": title,
                    "link": entry.link,
                    "published": entry.published,
                    "summary": entry.summary,
                })

            logger.info(f"Found {len(entries)} Commission proposal entries")
            return entries

        except Exception as e:
            logger.error(f"Failed to fetch Commission proposals: {str(e)}")
            return []

    async def get_all_predefined_feeds(
        self,
        since: Optional[datetime] = None,
        days: int = 7
    ) -> Dict[str, RSSFeed]:
        """
        Fetch all predefined RSS feeds at once.

        Args:
            since: Only get entries after this date
            days: If since not provided, get entries from last N days

        Returns:
            Dictionary with feed names as keys and RSSFeed objects as values
        """
        import asyncio

        if not since:
            since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching all predefined EUR-Lex feeds since {since.date()}")

        tasks = {}
        for feed_name in self.PREDEFINED_RSS_FEEDS:
            tasks[feed_name] = self.get_predefined_rss_feed(feed_name, since=since)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        feeds = {}
        for feed_name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {feed_name}: {result}")
                feeds[feed_name] = None
            else:
                feeds[feed_name] = result

        return feeds

    async def search_by_keyword(
        self,
        keyword: str,
        language: str = "en",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Simple keyword search across all documents

        Args:
            keyword: Search keyword
            language: Language code
            limit: Maximum results

        Returns:
            List of matching documents
        """
        return await self.search_documents(
            query=keyword,
            language=language,
            limit=limit
        )

    async def count_documents_by_type(
        self,
        date_from: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get count of documents by type

        Args:
            date_from: Start date

        Returns:
            Dictionary with document type counts
        """
        logger.info("Counting documents by type")

        if not date_from:
            date_from = datetime.now() - timedelta(days=365)

        sparql_query = SPARQLQuery(SPARQLQueryType.SELECT)

        sparql_query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")

        sparql_query.select(["?type", "(COUNT(?doc) as ?count)"])

        sparql_query.where([
            "?doc a ?type .",
            "?doc cdm:work_date_document ?date ."
        ])

        sparql_query.filter(f'?date >= "{date_from.isoformat()}"^^xsd:date')

        # Group by type
        query_str = sparql_query.build()
        query_str += "\nGROUP BY ?type\nORDER BY DESC(?count)"

        try:
            response = await self.sparql.query(query_str, SPARQLResultFormat.JSON)

            counts = {}
            if "results" in response and "bindings" in response["results"]:
                for binding in response["results"]["bindings"]:
                    doc_type = binding.get("type", {}).get("value", "unknown")
                    count = int(binding.get("count", {}).get("value", 0))
                    counts[doc_type] = count

            return counts

        except Exception as e:
            logger.error(f"Failed to count documents: {str(e)}")
            return {}

    def _get_eurovoc_cache_key(self, keywords: List[str]) -> str:
        """Generate a cache key from sorted normalised keywords."""
        return "|".join(sorted(k.lower().strip() for k in keywords))

    def _evict_eurovoc_cache(self):
        """Evict oldest entries if cache exceeds max size."""
        if len(self._eurovoc_cache) <= self._eurovoc_cache_max:
            return
        # Sort by timestamp (oldest first) and remove excess
        sorted_keys = sorted(self._eurovoc_cache.keys(),
                             key=lambda k: self._eurovoc_cache[k][1])
        to_remove = len(self._eurovoc_cache) - self._eurovoc_cache_max
        for key in sorted_keys[:to_remove]:
            del self._eurovoc_cache[key]

    async def search_by_eurovoc_keyword(
        self,
        keywords: List[str],
        date_from: Optional[str] = None,
        limit: int = 10,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Search CELLAR for legislation by EuroVoc topic keywords.

        Uses the SPARQL endpoint to find legislation tagged with EuroVoc
        concept labels matching the given keywords. Results are cached
        in-memory with 24h TTL.

        Args:
            keywords: List of topic keywords to search for (e.g., ["fisheries", "aquaculture"])
            date_from: ISO date string for minimum document date (default: 2020-01-01)
            limit: Maximum results per keyword (default: 10)
            language: Language for titles (default: "en")

        Returns:
            List of legislation dicts with celex, title, date fields
        """
        if not keywords:
            return []

        # Check cache
        cache_key = self._get_eurovoc_cache_key(keywords)
        if cache_key in self._eurovoc_cache:
            cached_results, cached_time = self._eurovoc_cache[cache_key]
            if time.time() - cached_time < self._eurovoc_cache_ttl:
                logger.debug(f"EuroVoc cache hit for: {keywords}")
                return cached_results

        if not date_from:
            date_from = "2020-01-01"

        logger.info(f"CELLAR EuroVoc search: {keywords} (from {date_from}, limit {limit})")

        all_results = []
        seen_celex = set()

        for keyword in keywords[:3]:  # Max 3 keywords per query
            # Build raw SPARQL query (the query builder doesn't support all patterns)
            sparql_text = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?celex ?title ?date WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  ?work cdm:work_is_about_concept_eurovoc ?concept .
  ?concept skos:prefLabel ?label .
  OPTIONAL {{ ?work cdm:resource_legal_title ?title . FILTER(LANG(?title) = "{language}") }}
  FILTER(CONTAINS(LCASE(STR(?label)), "{keyword.lower()}"))
  FILTER(?date >= "{date_from}"^^xsd:date)
}} ORDER BY DESC(?date) LIMIT {limit}
"""

            try:
                from .base_sparql_client import SPARQLResultFormat
                response = await self.sparql.query(sparql_text.strip(), SPARQLResultFormat.JSON)

                if "results" in response and "bindings" in response["results"]:
                    for binding in response["results"]["bindings"]:
                        celex = binding.get("celex", {}).get("value", "")
                        if celex and celex not in seen_celex:
                            seen_celex.add(celex)
                            all_results.append({
                                "celex": celex,
                                "title": binding.get("title", {}).get("value", ""),
                                "date": binding.get("date", {}).get("value", ""),
                                "eurovoc_keyword": keyword,
                                "source": "cellar_eurovoc"
                            })

            except Exception as e:
                logger.warning(f"CELLAR EuroVoc query failed for '{keyword}': {e}")

        # Cache results
        self._eurovoc_cache[cache_key] = (all_results, time.time())
        self._evict_eurovoc_cache()

        logger.info(f"CELLAR EuroVoc search returned {len(all_results)} results for {keywords}")
        return all_results

    async def health_check(self) -> bool:
        """
        Check if EUR-Lex APIs are accessible

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
        logger.info("Closed EUR-Lex client")
