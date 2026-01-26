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
from schemas.scrapers.ep_schemas import (
    EPVoteResult, EPMepVote, EPDecision, EPMeeting,
    EPSpeech, EPParliamentaryQuestion, EPProcedureEvent,
    EPMepDeclaration, EPVotingRecord, EPProcedureTimeline
)

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
    SPARQL_URL = "https://data.europarl.europa.eu/sparql"  # Separate from REST API
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

    async def _execute_sparql(self, query: str) -> Dict[str, Any]:
        """
        DEPRECATED: EP SPARQL endpoint was converted to a frontend app in 2024.

        The direct SPARQL endpoint is no longer available. Use REST API v2 methods:
        - get_mep_list() for MEPs
        - get_procedures() for procedures
        - get_meetings() for sessions

        Args:
            query: SPARQL query string

        Returns:
            Empty results dict (SPARQL no longer available)
        """
        logger.warning(
            "EP SPARQL endpoint no longer provides direct SPARQL access. "
            "Use REST API v2 methods instead (get_mep_list, get_procedures, etc.)"
        )
        # Return empty results to avoid breaking existing code
        return {"results": {"bindings": []}}

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
            results = await self._execute_sparql(sparql_query)
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
            results = await self._execute_sparql(sparql_query)

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
            results = await self._execute_sparql(sparql_query)
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
            results = await self._execute_sparql(sparql_query)
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

    # =========================================================================
    # Meetings & Vote Results (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_meetings(
        self,
        meeting_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EPMeeting]:
        """
        Get parliamentary meetings (plenary sessions, committee meetings)

        Args:
            meeting_type: Filter by type (plenary-sitting, committee-meeting)
            start_date: Filter meetings from this date
            end_date: Filter meetings until this date
            limit: Maximum results (default: 100, max: 500)
            offset: Pagination offset

        Returns:
            List of EPMeeting objects
        """
        logger.info(f"Fetching meetings via REST API (type={meeting_type})")

        params = {
            "limit": min(limit, 500),
            "offset": offset
        }

        if meeting_type:
            params["activity-type"] = meeting_type
        if start_date:
            params["start-date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end-date"] = end_date.strftime("%Y-%m-%d")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/meetings",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            meetings = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        meeting_date = None
                        date_str = item.get("activityDate") or item.get("date")
                        if date_str:
                            meeting_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        meetings.append(EPMeeting(
                            meeting_id=item.get("identifier") or item.get("id", ""),
                            meeting_type=item.get("activityType") or item.get("type", "unknown"),
                            date=meeting_date or datetime.now().date(),
                            location=item.get("hadLocation") or item.get("location"),
                            title=item.get("label") or item.get("title"),
                            has_vote_results=bool(item.get("hasVoteResults")),
                            has_decisions=bool(item.get("hasDecisions")),
                            source_url=f"https://data.europarl.europa.eu/api/v2/meetings/{item.get('identifier', '')}"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse meeting: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(meetings)} meetings")
            return meetings

        except Exception as e:
            logger.error(f"Meetings fetch failed: {str(e)}")
            return []

    async def get_meeting_vote_results(
        self,
        sitting_id: str
    ) -> List[EPVoteResult]:
        """
        Get vote results from a specific meeting/sitting

        Args:
            sitting_id: Meeting/sitting identifier

        Returns:
            List of EPVoteResult objects
        """
        logger.info(f"Fetching vote results for sitting: {sitting_id}")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                f"/meetings/{sitting_id}/vote-results",
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            votes = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        vote_date = None
                        date_str = item.get("voteDate") or item.get("activityDate")
                        if date_str:
                            vote_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        votes.append(EPVoteResult(
                            vote_id=item.get("identifier") or item.get("id"),
                            sitting_id=sitting_id,
                            sitting_date=vote_date or datetime.now().date(),
                            title=item.get("label") or item.get("title"),
                            procedure_reference=item.get("isAboutSubjectMatter") or item.get("procedureReference"),
                            document_reference=item.get("hadDocumentReferred") or item.get("documentReference"),
                            result=item.get("decisionOutcome") or item.get("result", "unknown"),
                            votes_for=item.get("numberVotesFor") or item.get("votesFor"),
                            votes_against=item.get("numberVotesAgainst") or item.get("votesAgainst"),
                            abstentions=item.get("numberAbstentions") or item.get("abstentions"),
                            vote_type=item.get("voteType"),
                            source_url=f"https://data.europarl.europa.eu/api/v2/meetings/{sitting_id}/vote-results"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse vote result: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(votes)} vote results")
            return votes

        except Exception as e:
            logger.error(f"Vote results fetch failed: {str(e)}")
            return []

    async def get_meeting_decisions(
        self,
        sitting_id: str
    ) -> List[EPDecision]:
        """
        Get decisions from a specific meeting/sitting

        Args:
            sitting_id: Meeting/sitting identifier

        Returns:
            List of EPDecision objects
        """
        logger.info(f"Fetching decisions for sitting: {sitting_id}")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                f"/meetings/{sitting_id}/decisions",
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            decisions = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        decision_date = None
                        date_str = item.get("decisionDate") or item.get("activityDate")
                        if date_str:
                            decision_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        decisions.append(EPDecision(
                            decision_id=item.get("identifier") or item.get("id"),
                            sitting_id=sitting_id,
                            sitting_date=decision_date or datetime.now().date(),
                            decision_type=item.get("decisionType") or item.get("type", "unknown"),
                            title=item.get("label") or item.get("title"),
                            description=item.get("description"),
                            procedure_reference=item.get("isAboutSubjectMatter"),
                            outcome=item.get("decisionOutcome"),
                            source_url=f"https://data.europarl.europa.eu/api/v2/meetings/{sitting_id}/decisions"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse decision: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(decisions)} decisions")
            return decisions

        except Exception as e:
            logger.error(f"Decisions fetch failed: {str(e)}")
            return []

    # =========================================================================
    # Procedure Events (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_procedure_by_reference(
        self,
        procedure_reference: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get procedure details by reference (e.g., 2025/0102(COD))

        Args:
            procedure_reference: Procedure reference number

        Returns:
            Procedure data or None
        """
        logger.info(f"Fetching procedure: {procedure_reference}")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            # Search procedures with the reference
            response = await self.get(
                "/procedures",
                params={"text": procedure_reference, "limit": 10},
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            data = results.get("data", results) if isinstance(results, dict) else results

            if isinstance(data, list):
                for proc in data:
                    # Check if reference matches
                    proc_ref = proc.get("procedureReference") or proc.get("notation") or ""
                    if procedure_reference in proc_ref or proc_ref in procedure_reference:
                        return proc

            return None

        except Exception as e:
            logger.error(f"Procedure fetch failed: {str(e)}")
            return None

    async def get_procedure_events(
        self,
        process_id: str
    ) -> List[EPProcedureEvent]:
        """
        Get events timeline for a legislative procedure

        Args:
            process_id: EP internal process identifier

        Returns:
            List of EPProcedureEvent objects
        """
        logger.info(f"Fetching procedure events for: {process_id}")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                f"/procedures/{process_id}/events",
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            events = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        event_date = None
                        date_str = item.get("activityDate") or item.get("date")
                        if date_str:
                            event_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        events.append(EPProcedureEvent(
                            event_id=item.get("identifier") or item.get("id"),
                            procedure_reference=item.get("isAboutSubjectMatter") or process_id,
                            event_date=event_date or datetime.now().date(),
                            event_type=item.get("activityType") or item.get("type", "unknown"),
                            title=item.get("label") or item.get("title"),
                            description=item.get("description"),
                            institution=item.get("wasGeneratedBy"),
                            outcome=item.get("decisionOutcome"),
                            source_url=f"https://data.europarl.europa.eu/api/v2/procedures/{process_id}/events"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse procedure event: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(events)} procedure events")
            return events

        except Exception as e:
            logger.error(f"Procedure events fetch failed: {str(e)}")
            return []

    # =========================================================================
    # Speeches (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_speeches(
        self,
        mep_id: Optional[str] = None,
        text: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        language: str = "en",
        limit: int = 50,
        offset: int = 0
    ) -> List[EPSpeech]:
        """
        Search MEP speeches/interventions

        Args:
            mep_id: Filter by MEP identifier
            text: Search in speech text
            start_date: Filter from date
            end_date: Filter until date
            language: Language filter (default: en)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of EPSpeech objects
        """
        logger.info(f"Fetching speeches (mep={mep_id}, text={text})")

        params = {
            "limit": min(limit, 500),
            "offset": offset,
            "language": language
        }

        if mep_id:
            params["author"] = mep_id
        if text:
            params["text"] = text
        if start_date:
            params["start-date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end-date"] = end_date.strftime("%Y-%m-%d")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/speeches",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            speeches = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        speech_date = None
                        date_str = item.get("activityDate") or item.get("date")
                        if date_str:
                            speech_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        speeches.append(EPSpeech(
                            speech_id=item.get("identifier") or item.get("id", ""),
                            mep_id=item.get("hasAuthor") or item.get("author") or mep_id or "",
                            mep_name=item.get("authorLabel"),
                            meeting_id=item.get("wasGeneratedBy"),
                            meeting_date=speech_date,
                            title=item.get("label") or item.get("title"),
                            text=item.get("text"),
                            language=item.get("language", language),
                            video_url=item.get("mediaUrl"),
                            source_url=f"https://data.europarl.europa.eu/api/v2/speeches/{item.get('identifier', '')}"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse speech: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(speeches)} speeches")
            return speeches

        except Exception as e:
            logger.error(f"Speeches fetch failed: {str(e)}")
            return []

    # =========================================================================
    # Parliamentary Questions (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_parliamentary_questions(
        self,
        author_mep_id: Optional[str] = None,
        text: Optional[str] = None,
        addressee: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        language: str = "en",
        limit: int = 50,
        offset: int = 0
    ) -> List[EPParliamentaryQuestion]:
        """
        Search parliamentary questions

        Args:
            author_mep_id: Filter by author MEP
            text: Search in question text
            addressee: Filter by addressee (Commission, Council)
            start_date: Filter from date
            end_date: Filter until date
            language: Language filter
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of EPParliamentaryQuestion objects
        """
        logger.info(f"Fetching parliamentary questions (author={author_mep_id}, text={text})")

        params = {
            "limit": min(limit, 500),
            "offset": offset,
            "language": language
        }

        if author_mep_id:
            params["author"] = author_mep_id
        if text:
            params["text"] = text
        if addressee:
            params["addressee"] = addressee
        if start_date:
            params["start-date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end-date"] = end_date.strftime("%Y-%m-%d")

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/parliamentary-questions",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            questions = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        submit_date = None
                        date_str = item.get("dateDocument") or item.get("date")
                        if date_str:
                            submit_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        questions.append(EPParliamentaryQuestion(
                            question_id=item.get("identifier") or item.get("id", ""),
                            question_reference=item.get("notation") or item.get("reference"),
                            question_type=item.get("workType") or item.get("type", "written"),
                            author_mep_ids=[item.get("hasAuthor")] if item.get("hasAuthor") else [],
                            author_names=[item.get("authorLabel")] if item.get("authorLabel") else [],
                            addressee=item.get("hasAddressee") or item.get("addressee", "Commission"),
                            title=item.get("label") or item.get("title", ""),
                            text=item.get("text"),
                            language=item.get("language", language),
                            date_submitted=submit_date,
                            source_url=f"https://data.europarl.europa.eu/api/v2/parliamentary-questions/{item.get('identifier', '')}"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse question: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(questions)} parliamentary questions")
            return questions

        except Exception as e:
            logger.error(f"Parliamentary questions fetch failed: {str(e)}")
            return []

    # =========================================================================
    # MEP Declarations (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_mep_declarations(
        self,
        mep_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[EPMepDeclaration]:
        """
        Get MEP declarations of financial interests

        Args:
            mep_id: Filter by MEP identifier
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of EPMepDeclaration objects
        """
        logger.info(f"Fetching MEP declarations (mep={mep_id})")

        params = {
            "limit": min(limit, 500),
            "offset": offset
        }

        if mep_id:
            params["author"] = mep_id

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/meps-declarations",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            declarations = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for item in data:
                    try:
                        decl_date = None
                        date_str = item.get("dateDocument") or item.get("date")
                        if date_str:
                            decl_date = datetime.fromisoformat(date_str.replace("Z", "")).date()

                        declarations.append(EPMepDeclaration(
                            declaration_id=item.get("identifier") or item.get("id"),
                            mep_id=item.get("hasAuthor") or mep_id or "",
                            mep_name=item.get("authorLabel"),
                            declaration_type=item.get("workType") or "financial_interests",
                            date_declared=decl_date,
                            content=item,
                            source_url=f"https://data.europarl.europa.eu/api/v2/meps-declarations/{item.get('identifier', '')}"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse declaration: {str(e)}")
                        continue

            logger.info(f"✓ Found {len(declarations)} MEP declarations")
            return declarations

        except Exception as e:
            logger.error(f"MEP declarations fetch failed: {str(e)}")
            return []

    # =========================================================================
    # Current MEPs (NEW - EP Open Data API v2)
    # =========================================================================

    async def get_current_meps(
        self,
        country: Optional[str] = None,
        political_group: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get current MEPs (as of today)

        Args:
            country: Filter by country code
            political_group: Filter by political group
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of current MEPs
        """
        logger.info("Fetching current MEPs via REST API")

        params = {
            "limit": min(limit, 500),
            "offset": offset
        }

        if country:
            params["country-of-representation"] = country
        if political_group:
            params["political-group"] = political_group

        headers = {
            "User-Agent": "Brubru-API-Client-1.0.0",
            "Accept": "application/ld+json"
        }

        try:
            response = await self.get(
                "/meps/show-current",
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            results = response.json()
            meps = []

            data = results.get("data", results) if isinstance(results, dict) else results
            if isinstance(data, list):
                for mep_data in data:
                    meps.append({
                        "id": mep_data.get("identifier", mep_data.get("id")),
                        "name": mep_data.get("label", ""),
                        "given_name": mep_data.get("givenName", ""),
                        "family_name": mep_data.get("familyName", ""),
                        "country": mep_data.get("countryOfRepresentation"),
                        "political_group": mep_data.get("hasPoliticalGroup"),
                        "type": mep_data.get("type", "Person")
                    })

            logger.info(f"✓ Found {len(meps)} current MEPs")
            return meps

        except Exception as e:
            logger.error(f"Current MEPs fetch failed: {str(e)}")
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
            # Use REST API v2 to check health (SPARQL no longer available)
            meps = await self.get_mep_list(limit=1)
            return len(meps) > 0
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.rss_client.close()
        logger.info("Closed European Parliament client")
