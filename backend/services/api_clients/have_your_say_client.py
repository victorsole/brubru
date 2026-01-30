"""
Have Your Say API Client.

HTTP client for the European Commission "Have Your Say" public consultations portal.
Portal URL: https://ec.europa.eu/info/law/better-regulation/have-your-say

Technical Investigation Findings (January 2026):
- Portal is an SPA (Angular) that loads data via JSON API
- JSON API endpoint: /brpapi/searchInitiatives
- Rate limiting: Conservative 3-second delay recommended

Created: January 2026
"""

import asyncio
import logging
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from schemas.scrapers.public_consultation_schemas import (
    ScrapedConsultationItem,
    ScrapedConsultationDetail,
    ScrapedConsultationDocument,
    ScrapedRelatedLegislation,
    ConsultationType,
    ConsultationStatus,
    DocumentType,
)
from knowledge_base.ec_consultations import (
    HAVE_YOUR_SAY_BASE_URL,
    DG_BY_CODE,
    PolicyArea,
    get_dg_full_name,
)

logger = logging.getLogger(__name__)


class HaveYourSayClient:
    """
    HTTP client for the EC Have Your Say portal JSON API.

    Features:
    - Async HTTP requests with aiohttp
    - Rate limiting (3-second delay)
    - Response caching
    - JSON API parsing
    - Pagination handling
    """

    BASE_URL = "https://ec.europa.eu/info/law/better-regulation"
    API_BASE = "https://ec.europa.eu/info/law/better-regulation/brpapi"
    PORTAL_URL = "https://ec.europa.eu/info/law/better-regulation/have-your-say"

    # Rate limiting
    RATE_LIMIT_DELAY = 3.0  # EC sites need slower rate
    TIMEOUT = 30  # seconds

    # User agent
    USER_AGENT = "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)"

    def __init__(self):
        self._last_request_time: Optional[float] = None
        self._request_lock = asyncio.Lock()
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._cache_ttl = 21600  # 6 hours

        logger.info(f"[START] HaveYourSayClient initialized (JSON API mode)")

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._request_lock:
            if self._last_request_time is not None:
                elapsed = asyncio.get_event_loop().time() - self._last_request_time
                if elapsed < self.RATE_LIMIT_DELAY:
                    wait_time = self.RATE_LIMIT_DELAY - elapsed
                    logger.debug(f"Rate limiting, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key in self._cache:
            cached_at, data = self._cache[cache_key]
            if (datetime.now() - cached_at).total_seconds() < self._cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return data
            else:
                del self._cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, data: Any):
        """Save data to cache."""
        self._cache[cache_key] = (datetime.now(), data)

    async def _fetch_json(
        self,
        url: str,
        params: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch URL and parse JSON response.

        Args:
            url: URL to fetch
            params: Query parameters
            use_cache: Whether to use cached response

        Returns:
            Parsed JSON as dict
        """
        # Check cache
        cache_key = f"{url}:{str(params)}"
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                return cached

        await self._rate_limit()

        headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        timeout = ClientTimeout(total=self.TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Fetching {url}")
                async with session.get(url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if use_cache:
                        self._save_to_cache(cache_key, data)

                    logger.info(f"[OK] Fetched {url}")
                    return data

        except aiohttp.ClientError as e:
            logger.error(f"[ERROR] Failed to fetch {url}: {e}")
            raise

    async def get_open_consultations(
        self,
        page: int = 0,
        limit: int = 20
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch currently open consultations.

        Args:
            page: Page number (0-indexed)
            limit: Items per page

        Returns:
            List of open consultation items
        """
        return await self._get_consultations(
            receiving_feedback_status="OPEN",
            page=page,
            limit=limit
        )

    async def get_closed_consultations(
        self,
        page: int = 0,
        limit: int = 20
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch closed consultations.

        Args:
            page: Page number (0-indexed)
            limit: Items per page

        Returns:
            List of closed consultation items
        """
        return await self._get_consultations(
            receiving_feedback_status="CLOSED",
            page=page,
            limit=limit
        )

    async def get_consultations_with_outcome(
        self,
        page: int = 0,
        limit: int = 20
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch consultations with published outcomes.

        Args:
            page: Page number (0-indexed)
            limit: Items per page

        Returns:
            List of consultations with outcomes
        """
        return await self._get_consultations(
            front_end_stage="ADOPTION_WORKFLOW",
            page=page,
            limit=limit
        )

    async def _get_consultations(
        self,
        receiving_feedback_status: Optional[str] = None,
        front_end_stage: Optional[str] = None,
        topic: Optional[str] = None,
        search_text: Optional[str] = None,
        page: int = 0,
        limit: int = 20
    ) -> List[ScrapedConsultationItem]:
        """
        Fetch consultations from the JSON API.

        API endpoint: /brpapi/searchInitiatives

        Args:
            receiving_feedback_status: OPEN or CLOSED
            front_end_stage: Stage filter (PLANNING_WORKFLOW, OPC_LAUNCHED, etc.)
            topic: Policy area/topic filter
            search_text: Search query
            page: Page number
            limit: Items per page

        Returns:
            List of consultation items
        """
        url = f"{self.API_BASE}/searchInitiatives"

        params = {
            'size': limit,
            'page': page,
            'language': 'EN',
        }

        if receiving_feedback_status:
            params['receivingFeedbackStatus'] = receiving_feedback_status
        if front_end_stage:
            params['frontEndStage'] = front_end_stage
        if topic:
            params['topic'] = topic
        if search_text:
            params['searchText'] = search_text

        try:
            data = await self._fetch_json(url, params=params)
            return self._parse_api_response(data, receiving_feedback_status)
        except Exception as e:
            logger.error(f"[ERROR] Failed to get consultations: {e}")
            return []

    def _parse_api_response(
        self,
        data: Dict[str, Any],
        status_filter: Optional[str] = None
    ) -> List[ScrapedConsultationItem]:
        """Parse the JSON API response."""
        items = []

        # Navigate to the content array
        page_data = data.get('initiativeResultDtoPage', {})
        content = page_data.get('content', [])

        for initiative in content:
            try:
                item = self._parse_initiative(initiative, status_filter)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error parsing initiative: {e}")
                continue

        logger.info(f"[OK] Parsed {len(items)} initiatives from API")
        return items

    def _parse_initiative(
        self,
        data: Dict[str, Any],
        status_filter: Optional[str] = None
    ) -> Optional[ScrapedConsultationItem]:
        """Parse a single initiative from API response."""
        initiative_id = str(int(data.get('id', 0)))
        if not initiative_id or initiative_id == '0':
            return None

        # Get title (prefer English translation)
        title = data.get('shortTitle', '')
        translations = data.get('initiativeTranslations', [])
        for trans in translations:
            if trans.get('language') == 'EN' and trans.get('field') == 'SHORT_TITLE':
                title = trans.get('value', title)
                break

        if not title:
            return None

        # Get current status
        current_statuses = data.get('currentStatuses', [])
        status = ConsultationStatus.OPEN
        start_date = None
        end_date = None
        feedback_status = None

        for cs in current_statuses:
            if cs.get('isCurrent'):
                feedback_status = cs.get('receivingFeedbackStatus')
                front_end_stage = cs.get('frontEndStage', '')

                # Parse dates
                start_str = cs.get('feedbackStartDate')
                end_str = cs.get('feedbackEndDate')

                if start_str:
                    start_date = self._parse_date(start_str)
                if end_str:
                    end_date = self._parse_date(end_str)

                # Determine status
                if feedback_status == 'OPEN':
                    status = ConsultationStatus.OPEN
                elif feedback_status == 'CLOSED':
                    status = ConsultationStatus.CLOSED
                elif 'ADOPTION' in front_end_stage:
                    status = ConsultationStatus.OUTCOME_PUBLISHED

                break

        # Get consultation type from foreseenActType
        act_type = data.get('foreseenActType', '')
        consultation_type = self._map_act_type(act_type)

        # Get topics/policy areas
        topics = data.get('topics', [])
        policy_areas = [t.get('label', '') for t in topics if t.get('label')]

        # Build portal URL
        reference = data.get('reference', '')
        slug = self._slugify(title)
        portal_url = f"{self.PORTAL_URL}/initiatives/{initiative_id}-{slug}_en"

        # Try to extract DG from topic or other fields
        dg_responsible = self._extract_dg_from_topics(topics)

        return ScrapedConsultationItem(
            initiative_id=initiative_id,
            title=title,
            description=None,  # Full description requires detail fetch
            consultation_type=consultation_type,
            status=status,
            dg_responsible=dg_responsible,
            policy_areas=policy_areas,
            start_date=start_date,
            end_date=end_date,
            feedback_count=0,  # Not in list response
            portal_url=portal_url,
            scraped_at=datetime.now()
        )

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from API format (YYYY/MM/DD HH:mm:ss)."""
        if not date_str:
            return None
        try:
            # Format: "2026/01/29 10:08:00"
            dt = datetime.strptime(date_str.split()[0], '%Y/%m/%d')
            return dt.date()
        except ValueError:
            return None

    def _map_act_type(self, act_type: str) -> ConsultationType:
        """Map foreseenActType to ConsultationType."""
        mapping = {
            'REG': ConsultationType.PUBLIC_CONSULTATION,
            'DIR': ConsultationType.PUBLIC_CONSULTATION,
            'DEC': ConsultationType.PUBLIC_CONSULTATION,
            'SWD': ConsultationType.CALL_FOR_EVIDENCE,
            'EVL': ConsultationType.CALL_FOR_EVIDENCE,
            'COM': ConsultationType.INITIATIVE,
            'OTH': ConsultationType.INITIATIVE,
        }
        return mapping.get(act_type, ConsultationType.INITIATIVE)

    def _slugify(self, text: str) -> str:
        """Create URL slug from text."""
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug[:50].strip('-')

    def _extract_dg_from_topics(self, topics: List[Dict]) -> Optional[str]:
        """Try to extract DG code from topics."""
        topic_to_dg = {
            'TRANSPORT': 'MOVE',
            'DIGITAL': 'CNECT',
            'ENVIRONMENT': 'ENV',
            'CLIMATE': 'CLIMA',
            'ENERGY': 'ENER',
            'TRADE': 'TRADE',
            'COMPETITION': 'COMP',
            'AGRICULTURE': 'AGRI',
            'HEALTH': 'SANTE',
            'JUSTICE': 'JUST',
            'INTERNAL_MARKET': 'GROW',
            'FINANCE': 'FISMA',
            'TAXATION': 'TAXUD',
            'EMPLOYMENT': 'EMPL',
            'EDUCATION': 'EAC',
            'RESEARCH': 'RTD',
        }

        for topic in topics:
            code = topic.get('code', '')
            if code in topic_to_dg:
                return topic_to_dg[code]

        return None

    async def get_consultation_detail(
        self,
        initiative_id: str,
        portal_url: Optional[str] = None
    ) -> Optional[ScrapedConsultationDetail]:
        """
        Fetch full details for a consultation.

        Args:
            initiative_id: EC initiative ID
            portal_url: Optional direct URL

        Returns:
            Detailed consultation data or None
        """
        url = f"{self.API_BASE}/groupInitiativesByType/{initiative_id}"

        try:
            data = await self._fetch_json(url)
            return self._parse_detail_response(data, initiative_id, portal_url)
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch detail for {initiative_id}: {e}")
            return None

    def _parse_detail_response(
        self,
        data: Dict[str, Any],
        initiative_id: str,
        portal_url: Optional[str]
    ) -> Optional[ScrapedConsultationDetail]:
        """Parse detail API response."""
        # The API returns grouped data
        publications = data.get('publications', [])
        initiative_data = data.get('initiative', {})

        # Get title
        title = initiative_data.get('shortTitle', 'Unknown')
        translations = initiative_data.get('initiativeTranslations', [])
        for trans in translations:
            if trans.get('language') == 'EN' and trans.get('field') == 'SHORT_TITLE':
                title = trans.get('value', title)
                break

        # Get full description
        full_description = None
        for trans in translations:
            if trans.get('language') == 'EN' and trans.get('field') == 'OBJECTIVE':
                full_description = trans.get('value')
                break

        # Get dates and status
        current_statuses = initiative_data.get('currentStatuses', [])
        status = ConsultationStatus.OPEN
        start_date = None
        end_date = None

        for cs in current_statuses:
            if cs.get('isCurrent'):
                if cs.get('receivingFeedbackStatus') == 'OPEN':
                    status = ConsultationStatus.OPEN
                elif cs.get('receivingFeedbackStatus') == 'CLOSED':
                    status = ConsultationStatus.CLOSED

                start_str = cs.get('feedbackStartDate')
                end_str = cs.get('feedbackEndDate')
                if start_str:
                    start_date = self._parse_date(start_str)
                if end_str:
                    end_date = self._parse_date(end_str)
                break

        # Get topics
        topics = initiative_data.get('topics', [])
        policy_areas = [t.get('label', '') for t in topics if t.get('label')]

        # Get DG
        dg_responsible = self._extract_dg_from_topics(topics)

        # Get feedback count
        feedback_count = initiative_data.get('feedbackCount', 0)

        # Get documents from publications
        documents = []
        for pub in publications:
            docs = pub.get('documents', [])
            for doc in docs:
                doc_title = doc.get('title', 'Document')
                file_url = doc.get('downloadUrl', '')
                documents.append(ScrapedConsultationDocument(
                    title=doc_title[:200],
                    document_type=DocumentType.OTHER,
                    file_url=file_url
                ))

        # Build portal URL if not provided
        if not portal_url:
            slug = self._slugify(title)
            portal_url = f"{self.PORTAL_URL}/initiatives/{initiative_id}-{slug}_en"

        return ScrapedConsultationDetail(
            initiative_id=initiative_id,
            title=title,
            full_description=full_description,
            consultation_type=ConsultationType.PUBLIC_CONSULTATION,
            status=status,
            dg_responsible=dg_responsible,
            policy_areas=policy_areas,
            start_date=start_date,
            end_date=end_date,
            feedback_count=feedback_count,
            portal_url=portal_url,
            documents=documents,
            related_legislation=[],
            com_references=[],
            celex_numbers=[],
            scraped_at=datetime.now()
        )

    async def search_consultations(
        self,
        query: str,
        status: Optional[str] = None,
        policy_area: Optional[str] = None,
        limit: int = 20
    ) -> List[ScrapedConsultationItem]:
        """
        Search consultations by keyword.

        Args:
            query: Search query
            status: Optional status filter (OPEN, CLOSED)
            policy_area: Optional policy area filter
            limit: Maximum results

        Returns:
            List of matching consultations
        """
        return await self._get_consultations(
            receiving_feedback_status=status.upper() if status else None,
            topic=policy_area,
            search_text=query,
            limit=limit
        )

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        logger.info("[OK] HaveYourSayClient cache cleared")


# Singleton instance
_client: Optional[HaveYourSayClient] = None


def get_have_your_say_client() -> HaveYourSayClient:
    """Get or create singleton HaveYourSayClient instance."""
    global _client
    if _client is None:
        _client = HaveYourSayClient()
    return _client
