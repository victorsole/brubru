"""
European Parliament API Client

Provides access to European Parliament data sources:
- Open Data Portal (ODP) - Legislative documents, votes, amendments
- Registry API - MEPs, committees, sessions, documents
- Activity Stream - Real-time parliamentary activities
- RSS Feeds (33+ feeds) - News, debates, press releases
- Europarl API - Document metadata and full texts

Documentation:
- Open Data Portal: https://data.europarl.europa.eu/
- MEP Registry: https://www.europarl.europa.eu/meps/en/directory/xml/
- RSS Feeds: https://www.europarl.europa.eu/rss/
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class EPDocumentType(Enum):
    """European Parliament document types"""
    AMENDMENT = "amendment"
    MOTION_RESOLUTION = "motion_resolution"
    REPORT = "report"
    QUESTION = "question"
    DEBATE = "debate"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    RESOLUTION = "resolution"


class EPCommittee(Enum):
    """Major European Parliament committees"""
    AFET = "Foreign Affairs"
    DEVE = "Development"
    INTA = "International Trade"
    BUDG = "Budgets"
    CONT = "Budgetary Control"
    ECON = "Economic and Monetary Affairs"
    EMPL = "Employment and Social Affairs"
    ENVI = "Environment, Public Health and Food Safety"
    ITRE = "Industry, Research and Energy"
    IMCO = "Internal Market and Consumer Protection"
    TRAN = "Transport and Tourism"
    REGI = "Regional Development"
    AGRI = "Agriculture and Rural Development"
    PECH = "Fisheries"
    CULT = "Culture and Education"
    JURI = "Legal Affairs"
    LIBE = "Civil Liberties, Justice and Home Affairs"
    AFCO = "Constitutional Affairs"
    FEMM = "Women's Rights and Gender Equality"
    PETI = "Petitions"


class EuropeanParliamentClient(BaseAPIClient):
    """
    Client for European Parliament APIs and data sources

    Features:
    - MEP directory and profiles
    - Committee information
    - Legislative documents
    - Plenary sessions and votes
    - Parliamentary questions
    - RSS feed aggregation
    """

    # API Endpoints (v2 REST API)
    BASE_URL = "https://data.europarl.europa.eu/api/v2"
    ODP_SPARQL = "https://data.europarl.europa.eu/sparql"  # Legacy
    MEP_REGISTRY_URL = "https://www.europarl.europa.eu/meps/en"  # Legacy
    RSS_BASE_URL = "https://www.europarl.europa.eu/rss"

    # Rate limit: 500 requests per 5 minutes
    RATE_LIMIT_REQUESTS = 500
    RATE_LIMIT_WINDOW = 300  # seconds

    # Key RSS Feeds
    RSS_FEEDS = {
        "press_releases": f"{RSS_BASE_URL}/press-releases/en.xml",
        "plenary_news": f"{RSS_BASE_URL}/plenary/en.xml",
        "committees_news": f"{RSS_BASE_URL}/committees/en.xml",
        "priorities": f"{RSS_BASE_URL}/priorities/en.xml",

        # Committee-specific feeds
        "afet_news": f"{RSS_BASE_URL}/committee/cj17/en.xml",
        "econ_news": f"{RSS_BASE_URL}/committee/cj05/en.xml",
        "envi_news": f"{RSS_BASE_URL}/committee/cj08/en.xml",
        "itre_news": f"{RSS_BASE_URL}/committee/cj09/en.xml",
        "libe_news": f"{RSS_BASE_URL}/committee/cj16/en.xml",

        # Topics
        "climate_change": f"{RSS_BASE_URL}/topic/cc01/en.xml",
        "economy": f"{RSS_BASE_URL}/topic/cc02/en.xml",
        "digital": f"{RSS_BASE_URL}/topic/cc03/en.xml",
        "migration": f"{RSS_BASE_URL}/topic/cc04/en.xml",
        "foreign_affairs": f"{RSS_BASE_URL}/topic/cc05/en.xml",
    }

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize European Parliament client

        Args:
            endpoint_url: Override base URL
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.NONE,  # Public API
            timeout=timeout
        )

        # RSS client for feed aggregation
        self.rss_client = BaseRSSClient(
            cache_ttl=900,  # 15 minutes
            timeout=timeout
        )

        logger.info("Initialized European Parliament API client")

    async def search_documents(
        self,
        query: str,
        document_type: Optional[EPDocumentType] = None,
        committee: Optional[EPCommittee] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        language: str = "en",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search parliamentary documents via Open Data Portal

        Args:
            query: Search query text
            document_type: Filter by document type
            committee: Filter by committee
            date_from: Start date filter
            date_to: End date filter
            language: Language code (en, fr, de, etc.)
            limit: Maximum results

        Returns:
            List of document metadata
        """
        logger.info(f"Searching EP documents: {query}")

        # Build SPARQL query for ODP
        sparql_query = f"""
        PREFIX ep: <http://data.europarl.europa.eu/def/ep-entities#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?doc ?title ?date ?type ?committee
        WHERE {{
            ?doc dcterms:title ?title .
            ?doc dcterms:date ?date .
            ?doc a ?type .

            FILTER(LANG(?title) = "{language}")
            FILTER(CONTAINS(LCASE(?title), LCASE("{query}")))

            {f'FILTER(?date >= "{date_from.isoformat()}"^^xsd:date)' if date_from else ''}
            {f'FILTER(?date <= "{date_to.isoformat()}"^^xsd:date)' if date_to else ''}

            OPTIONAL {{ ?doc ep:hasCommittee ?committee }}
        }}
        ORDER BY DESC(?date)
        LIMIT {limit}
        """

        try:
            response = await self.get(
                "sparql",
                params={"query": sparql_query},
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            documents = []

            if "results" in results and "bindings" in results["results"]:
                for binding in results["results"]["bindings"]:
                    documents.append({
                        "id": binding.get("doc", {}).get("value"),
                        "title": binding.get("title", {}).get("value"),
                        "date": binding.get("date", {}).get("value"),
                        "type": binding.get("type", {}).get("value"),
                        "committee": binding.get("committee", {}).get("value"),
                        "language": language
                    })

            logger.info(f"Found {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Document search failed: {str(e)}")
            return []

    async def get_mep_list(
        self,
        country: Optional[str] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of Members of European Parliament using REST API v2

        Args:
            country: Filter by country code (e.g., "ES", "DE", "FR")
            group: Filter by political group (e.g., "PPE", "S-D", "RENEW")
            name: Search by MEP name
            limit: Number of results (default: 100, max: 500)
            offset: Pagination offset (default: 0)

        Returns:
            List of MEP information
        """
        logger.info(f"Fetching MEP list via REST API (limit={limit}, offset={offset})")

        # Build query parameters
        params = {
            "limit": min(limit, 500),  # API max
            "offset": offset,
            "format": "application/ld+json"
        }

        if country:
            params["country-of-representation"] = country
        if group:
            params["political-group"] = group

        # Add User-Agent header (recommended by API)
        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/meps",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            meps = []

            if "data" in results and isinstance(results["data"], list):
                for mep_data in results["data"]:
                    meps.append({
                        "id": mep_data.get("identifier", mep_data.get("id")),
                        "name": mep_data.get("label", ""),
                        "given_name": mep_data.get("givenName", ""),
                        "family_name": mep_data.get("familyName", ""),
                        "sort_label": mep_data.get("sortLabel", ""),
                        "type": mep_data.get("type", "Person")
                    })

            logger.info(f"✓ Found {len(meps)} MEPs")
            return meps

        except Exception as e:
            logger.error(f"MEP list fetch failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def get_mep_profile(self, mep_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed profile for a specific MEP

        Args:
            mep_id: MEP identifier

        Returns:
            MEP profile data
        """
        logger.info(f"Fetching MEP profile: {mep_id}")

        sparql_query = f"""
        PREFIX ep: <http://data.europarl.europa.eu/def/ep-entities#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT ?name ?country ?group ?email ?birthDate ?photo
        WHERE {{
            <{mep_id}> foaf:name ?name .
            <{mep_id}> ep:represents ?country .

            OPTIONAL {{ <{mep_id}> ep:memberOf ?group }}
            OPTIONAL {{ <{mep_id}> foaf:mbox ?email }}
            OPTIONAL {{ <{mep_id}> ep:birthDate ?birthDate }}
            OPTIONAL {{ <{mep_id}> foaf:depiction ?photo }}
        }}
        """

        try:
            response = await self.get(
                "sparql",
                params={"query": sparql_query},
                response_format=ResponseFormat.JSON
            )

            results = response.json()

            if "results" in results and "bindings" in results["results"]:
                if results["results"]["bindings"]:
                    binding = results["results"]["bindings"][0]
                    return {
                        "id": mep_id,
                        "name": binding.get("name", {}).get("value"),
                        "country": binding.get("country", {}).get("value"),
                        "group": binding.get("group", {}).get("value"),
                        "email": binding.get("email", {}).get("value"),
                        "birth_date": binding.get("birthDate", {}).get("value"),
                        "photo": binding.get("photo", {}).get("value")
                    }

            return None

        except Exception as e:
            logger.error(f"MEP profile fetch failed: {str(e)}")
            return None

    async def get_committee_info(
        self,
        committee_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get information about parliamentary committees

        Args:
            committee_code: Specific committee code (e.g., "ENVI", "ECON")

        Returns:
            List of committee information
        """
        logger.info(f"Fetching committee info: {committee_code or 'all'}")

        sparql_query = """
        PREFIX ep: <http://data.europarl.europa.eu/def/ep-entities#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?committee ?code ?label ?description
        WHERE {
            ?committee a ep:Committee .
            ?committee skos:notation ?code .
            ?committee rdfs:label ?label .

            OPTIONAL { ?committee dcterms:description ?description }

            FILTER(LANG(?label) = "en")
        """

        if committee_code:
            sparql_query += f'\n    FILTER(?code = "{committee_code}")'

        sparql_query += "\n}\nORDER BY ?code"

        try:
            response = await self.get(
                "sparql",
                params={"query": sparql_query},
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            committees = []

            if "results" in results and "bindings" in results["results"]:
                for binding in results["results"]["bindings"]:
                    committees.append({
                        "id": binding.get("committee", {}).get("value"),
                        "code": binding.get("code", {}).get("value"),
                        "name": binding.get("label", {}).get("value"),
                        "description": binding.get("description", {}).get("value")
                    })

            logger.info(f"Found {len(committees)} committees")
            return committees

        except Exception as e:
            logger.error(f"Committee info fetch failed: {str(e)}")
            return []

    async def get_plenary_sessions(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get plenary session information

        Args:
            date_from: Start date
            date_to: End date

        Returns:
            List of plenary sessions
        """
        logger.info("Fetching plenary sessions")

        if not date_from:
            date_from = datetime.now() - timedelta(days=365)
        if not date_to:
            date_to = datetime.now()

        sparql_query = f"""
        PREFIX ep: <http://data.europarl.europa.eu/def/ep-entities#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?session ?date ?location ?agenda
        WHERE {{
            ?session a ep:PlenarySession .
            ?session dcterms:date ?date .

            OPTIONAL {{ ?session ep:location ?location }}
            OPTIONAL {{ ?session ep:agenda ?agenda }}

            FILTER(?date >= "{date_from.isoformat()}"^^xsd:date)
            FILTER(?date <= "{date_to.isoformat()}"^^xsd:date)
        }}
        ORDER BY DESC(?date)
        """

        try:
            response = await self.get(
                "sparql",
                params={"query": sparql_query},
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            sessions = []

            if "results" in results and "bindings" in results["results"]:
                for binding in results["results"]["bindings"]:
                    sessions.append({
                        "id": binding.get("session", {}).get("value"),
                        "date": binding.get("date", {}).get("value"),
                        "location": binding.get("location", {}).get("value"),
                        "agenda": binding.get("agenda", {}).get("value")
                    })

            logger.info(f"Found {len(sessions)} plenary sessions")
            return sessions

        except Exception as e:
            logger.error(f"Plenary sessions fetch failed: {str(e)}")
            return []

    async def get_rss_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch specific RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed with entries
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.RSS_FEEDS.keys())}")

        feed_url = self.RSS_FEEDS[feed_name]
        logger.info(f"Fetching RSS feed: {feed_name}")

        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_all_rss_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch all RSS feeds concurrently

        Args:
            since: Only get entries after this date

        Returns:
            List of all RSS feeds
        """
        logger.info(f"Fetching all {len(self.RSS_FEEDS)} RSS feeds")

        feed_urls = list(self.RSS_FEEDS.values())
        return await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

    async def get_procedures(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get legislative procedures using REST API v2

        Args:
            limit: Number of results (default: 100, max: 500)
            offset: Pagination offset (default: 0)

        Returns:
            List of legislative procedures
        """
        logger.info(f"Fetching procedures via REST API (limit={limit})")

        params = {
            "limit": min(limit, 500),
            "offset": offset,
            "format": "application/ld+json"
        }

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/procedures",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            procedures = []

            if "data" in results and isinstance(results["data"], list):
                for proc in results["data"]:
                    procedures.append({
                        "id": proc.get("identifier", proc.get("id")),
                        "label": proc.get("label", ""),
                        "reference": proc.get("procedureReference", ""),
                        "type": proc.get("type", "Procedure")
                    })

            logger.info(f"✓ Found {len(procedures)} procedures")
            return procedures

        except Exception as e:
            logger.error(f"Procedures fetch failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def get_adopted_texts(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get adopted texts using REST API v2

        Args:
            limit: Number of results (default: 100, max: 500)
            offset: Pagination offset (default: 0)

        Returns:
            List of adopted texts
        """
        logger.info(f"Fetching adopted texts via REST API (limit={limit})")

        params = {
            "limit": min(limit, 500),
            "offset": offset,
            "format": "application/ld+json"
        }

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/adopted-texts",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            texts = []

            if "data" in results and isinstance(results["data"], list):
                for text in results["data"]:
                    texts.append({
                        "id": text.get("identifier", text.get("id")),
                        "label": text.get("label", ""),
                        "type": text.get("type", "AdoptedText")
                    })

            logger.info(f"✓ Found {len(texts)} adopted texts")
            return texts

        except Exception as e:
            logger.error(f"Adopted texts fetch failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def get_latest_news(
        self,
        hours: int = 24,
        feed_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get latest news from RSS feeds

        Args:
            hours: Get news from last N hours
            feed_names: Specific feeds to check (None = all)

        Returns:
            Aggregated news entries
        """
        since = datetime.now() - timedelta(hours=hours)

        if feed_names:
            feeds_to_fetch = {k: v for k, v in self.RSS_FEEDS.items() if k in feed_names}
        else:
            feeds_to_fetch = self.RSS_FEEDS

        logger.info(f"Fetching latest news from {len(feeds_to_fetch)} feeds")

        feed_urls = list(feeds_to_fetch.values())
        feeds = await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

        # Aggregate entries
        all_entries = []
        for feed in feeds:
            for entry in feed.entries:
                all_entries.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "feed_source": entry.feed_source,
                    "categories": entry.categories
                })

        # Sort by date
        all_entries.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(all_entries)} news entries")
        return all_entries

    async def health_check(self) -> bool:
        """
        Check if European Parliament API is accessible

        Returns:
            True if healthy
        """
        try:
            # Try to fetch a simple SPARQL query
            response = await self.get(
                "sparql",
                params={"query": "ASK { ?s ?p ?o } LIMIT 1"},
                response_format=ResponseFormat.JSON
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.rss_client.close()
        logger.info("Closed European Parliament client")
