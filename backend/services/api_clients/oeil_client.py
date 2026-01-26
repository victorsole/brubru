"""
OEIL API Client

OEIL (Observatoire législatif européen / Legislative Observatory):
- EU legislative procedures tracking
- Document status and timeline
- Amendments and votes
- Committee opinions

UPDATED January 2026:
- XML export feeds discovered and integrated
- Supports latest-procedures, latest-information-documents, latest-committees-reports

Documentation:
- OEIL Portal: https://oeil.europarl.europa.eu/oeil/en/home
- EP Open Data API: https://data.europarl.europa.eu/
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


@dataclass
class OEILFeedItem:
    """Item from OEIL XML export feed"""
    reference: str
    title: str
    link: str
    last_pub_date: Optional[datetime] = None
    committees: List[str] = field(default_factory=list)
    rapporteurs: List[str] = field(default_factory=list)

    @property
    def procedure_type(self) -> Optional[str]:
        """Extract procedure type from reference (COD, INI, RSP, etc.)"""
        match = re.search(r'\(([A-Z]{3})\)', self.reference)
        return match.group(1) if match else None

    @property
    def is_legislative(self) -> bool:
        """Check if this is a legislative procedure"""
        return self.procedure_type in ['COD', 'CNS', 'APP', 'NLE']

    @property
    def is_com_document(self) -> bool:
        """Check if this is a COM document"""
        return self.reference.startswith('COM(') or self.reference.startswith('SWD(')


class OEILClient(BaseAPIClient):
    """
    Client for OEIL Legislative Observatory

    Features:
    - Legislative procedure search
    - Procedure status and timeline
    - XML feed export (latest procedures, documents, reports)

    XML Feed Endpoints (discovered January 2026):
    - latest-procedures: New legislative procedures
    - latest-information-documents: COM/SWD documents
    - latest-committees-reports-tabled: Committee reports
    """

    # Base URLs
    BASE_URL = "https://oeil.europarl.europa.eu/oeil"
    EXPORT_URL = f"{BASE_URL}/popups/sda.do"

    # XML Export Feed URLs (discovered January 2026)
    XML_FEEDS = {
        "latest_procedures": "/en/predefined-search/latest-procedures/export/XML",
        "latest_documents": "/en/predefined-search/latest-information-documents/export/XML",
        "latest_reports": "/en/predefined-search/latest-committees-reports-tabled/export/XML",
    }

    # Default parameters for XML feeds
    DEFAULT_FEED_PARAMS = {
        "latest_procedures": {"maxDays": 7},
        "latest_documents": {"maxCount": 50, "maxDays": 7},
        "latest_reports": {"maxDays": 30},
    }

    # RSS Feeds - DEPRECATED (removed by EU Parliament in late 2024)
    RSS_FEEDS_DEPRECATED = {
        "ordinary_legislative": "REMOVED",
        "consultation": "REMOVED",
        "consent": "REMOVED",
        "budgetary": "REMOVED",
        "non_legislative": "REMOVED",
        "all_procedures": "REMOVED"
    }

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize OEIL client

        Args:
            endpoint_url: Override base URL
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL

        super().__init__(
            base_url=base_url,
            auth_type=AuthType.NONE,
            timeout=timeout
        )

        # RSS client
        self.rss_client = BaseRSSClient(
            cache_ttl=900,
            timeout=timeout
        )

        logger.info("Initialized OEIL client")

    async def get_rss_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        DEPRECATED: OEIL RSS feeds were removed by EU Parliament in late 2024.

        Use OEILScraper.get_procedure_full() or EuropeanParliamentClient instead.

        Args:
            feed_name: Feed name (no longer supported)
            since: Only get entries after this date

        Returns:
            Empty RSSFeed
        """
        logger.warning(
            f"OEIL RSS feeds are no longer available (removed by EU Parliament). "
            f"Use OEILScraper or EuropeanParliamentClient for procedure updates."
        )
        # Return empty feed to avoid breaking existing code
        return RSSFeed(
            url=self.BASE_URL,
            title=f"OEIL {feed_name} (DEPRECATED)",
            description="RSS feeds removed by EU Parliament",
            entries=[]
        )

    async def get_all_rss_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        DEPRECATED: OEIL RSS feeds were removed by EU Parliament in late 2024.

        Use OEILScraper.get_procedure_full() or EuropeanParliamentClient instead.

        Returns:
            Empty list
        """
        logger.warning(
            "OEIL RSS feeds are no longer available (removed by EU Parliament). "
            "Use OEILScraper or EuropeanParliamentClient for procedure updates."
        )
        return []

    async def get_latest_procedures(
        self,
        hours: int = 24,
        procedure_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        DEPRECATED: OEIL RSS feeds were removed by EU Parliament in late 2024.

        For latest procedures, use:
        - EuropeanParliamentClient.get_procedures() for REST API
        - OEILScraper.get_procedure_full() for specific procedure details

        Returns:
            Empty list with deprecation warning
        """
        logger.warning(
            "OEIL RSS feeds are no longer available (removed by EU Parliament). "
            "Use EuropeanParliamentClient.get_procedures() for latest procedures."
        )
        return []

    async def export_procedure_data(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Export procedure data as XML

        Args:
            date_from: Start date
            date_to: End date

        Returns:
            XML data
        """
        if not date_from:
            date_from = datetime.now() - timedelta(days=365)
        if not date_to:
            date_to = datetime.now()

        logger.info(f"Exporting OEIL data ({date_from.date()} to {date_to.date()})")

        params = {
            "dateFrom": date_from.strftime("%d/%m/%Y"),
            "dateTo": date_to.strftime("%d/%m/%Y"),
            "format": "xml"
        }

        try:
            response = await self.get(
                "/popups/sda.do",
                params=params,
                response_format=ResponseFormat.XML
            )

            return response.text

        except Exception as e:
            logger.error(f"OEIL data export failed: {str(e)}")
            return None

    async def health_check(self) -> bool:
        """
        Check if OEIL website is accessible

        Returns:
            True if healthy
        """
        try:
            # Check if OEIL home page is accessible (follows redirects)
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(f"{self.BASE_URL}/en")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.rss_client.close()
        logger.info("Closed OEIL client")

    # =========================================================================
    # XML Feed Methods (Added January 2026)
    # =========================================================================

    async def fetch_xml_feed(
        self,
        feed_name: str,
        max_days: Optional[int] = None,
        max_count: Optional[int] = None
    ) -> List[OEILFeedItem]:
        """
        Fetch and parse an OEIL XML export feed.

        Args:
            feed_name: Feed name ('latest_procedures', 'latest_documents', 'latest_reports')
            max_days: Override default maxDays parameter
            max_count: Override default maxCount parameter (for documents feed)

        Returns:
            List of OEILFeedItem objects

        Example:
            items = await client.fetch_xml_feed('latest_procedures', max_days=7)
            for item in items:
                print(f"{item.reference}: {item.title}")
        """
        if feed_name not in self.XML_FEEDS:
            logger.error(f"Unknown feed: {feed_name}. Valid feeds: {list(self.XML_FEEDS.keys())}")
            return []

        feed_path = self.XML_FEEDS[feed_name]
        params = dict(self.DEFAULT_FEED_PARAMS.get(feed_name, {}))

        # Override defaults if provided
        if max_days is not None:
            params["maxDays"] = max_days
        if max_count is not None:
            params["maxCount"] = max_count

        logger.info(f"Fetching OEIL XML feed: {feed_name} with params {params}")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                url = f"{self.BASE_URL}{feed_path}"
                response = await client.get(url, params=params)
                response.raise_for_status()

                xml_content = response.text
                items = self._parse_xml_feed(xml_content)

                logger.info(f"Parsed {len(items)} items from {feed_name} feed")
                return items

        except Exception as e:
            logger.error(f"Failed to fetch XML feed {feed_name}: {str(e)}")
            return []

    def _parse_xml_feed(self, xml_content: str) -> List[OEILFeedItem]:
        """
        Parse OEIL XML feed content.

        XML Structure:
        <procedureList>
            <generatedOn>Fri Jan 23 18:35:45 CET 2026</generatedOn>
            <items count="N">
                <item>
                    <reference>2026/0013(COD)</reference>
                    <link>https://oeil.../</link>
                    <title>...</title>
                    <lastpubdate>Fri Jan 23 2026</lastpubdate>
                    <committee><committee>Committee Name</committee></committee>
                    <rapporteur><rapporteur>NAME (Group)</rapporteur></rapporteur>
                </item>
            </items>
        </procedureList>
        """
        items = []

        try:
            root = ET.fromstring(xml_content)

            # Find all item elements
            for item_elem in root.findall('.//item'):
                reference = self._get_text(item_elem, 'reference')
                title = self._get_text(item_elem, 'title')
                link = self._get_text(item_elem, 'link')

                if not reference or not title:
                    continue

                # Parse date
                date_str = self._get_text(item_elem, 'lastpubdate')
                pub_date = self._parse_oeil_date(date_str) if date_str else None

                # Parse committees (can have multiple)
                committees = []
                committee_elem = item_elem.find('committee')
                if committee_elem is not None:
                    for c in committee_elem.findall('committee'):
                        if c.text:
                            committees.append(c.text.strip())

                # Parse rapporteurs (can have multiple)
                rapporteurs = []
                rapporteur_elem = item_elem.find('rapporteur')
                if rapporteur_elem is not None:
                    for r in rapporteur_elem.findall('rapporteur'):
                        if r.text:
                            rapporteurs.append(r.text.strip())

                items.append(OEILFeedItem(
                    reference=reference,
                    title=title,
                    link=link or f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={reference}",
                    last_pub_date=pub_date,
                    committees=committees,
                    rapporteurs=rapporteurs
                ))

        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        except Exception as e:
            logger.error(f"Error parsing XML feed: {e}")

        return items

    def _get_text(self, elem: ET.Element, tag: str) -> Optional[str]:
        """Get text content of a child element"""
        child = elem.find(tag)
        return child.text.strip() if child is not None and child.text else None

    def _parse_oeil_date(self, date_str: str) -> Optional[datetime]:
        """Parse OEIL date format: 'Fri Jan 23 2026' or 'Fri Jan 23 18:35:45 CET 2026'"""
        try:
            # Try full format with time
            if ':' in date_str:
                # Remove timezone abbreviation for parsing
                date_str = re.sub(r'\s+[A-Z]{3,4}\s+', ' ', date_str)
                return datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y")
            else:
                # Short format without time
                return datetime.strptime(date_str, "%a %b %d %Y")
        except ValueError:
            logger.debug(f"Could not parse date: {date_str}")
            return None

    async def get_latest_procedures_xml(
        self,
        max_days: int = 7,
        filter_types: Optional[List[str]] = None
    ) -> List[OEILFeedItem]:
        """
        Get latest legislative procedures from XML feed.

        Args:
            max_days: Number of days to look back
            filter_types: Optional list of procedure types to include (e.g., ['COD', 'INI'])

        Returns:
            List of procedure items
        """
        items = await self.fetch_xml_feed('latest_procedures', max_days=max_days)

        if filter_types:
            items = [i for i in items if i.procedure_type in filter_types]

        return items

    async def get_latest_documents_xml(
        self,
        max_days: int = 7,
        max_count: int = 50
    ) -> List[OEILFeedItem]:
        """
        Get latest COM/SWD documents from XML feed.

        Args:
            max_days: Number of days to look back
            max_count: Maximum number of documents to return

        Returns:
            List of document items
        """
        return await self.fetch_xml_feed(
            'latest_documents',
            max_days=max_days,
            max_count=max_count
        )

    async def get_latest_reports_xml(
        self,
        max_days: int = 30
    ) -> List[OEILFeedItem]:
        """
        Get latest committee reports tabled from XML feed.

        Args:
            max_days: Number of days to look back

        Returns:
            List of report items
        """
        return await self.fetch_xml_feed('latest_reports', max_days=max_days)

    async def get_all_latest_xml(
        self,
        procedures_days: int = 7,
        documents_days: int = 7,
        reports_days: int = 30
    ) -> Dict[str, List[OEILFeedItem]]:
        """
        Fetch all XML feeds at once.

        Returns:
            Dictionary with 'procedures', 'documents', 'reports' keys
        """
        import asyncio

        procedures_task = self.get_latest_procedures_xml(max_days=procedures_days)
        documents_task = self.get_latest_documents_xml(max_days=documents_days)
        reports_task = self.get_latest_reports_xml(max_days=reports_days)

        results = await asyncio.gather(
            procedures_task,
            documents_task,
            reports_task,
            return_exceptions=True
        )

        return {
            'procedures': results[0] if not isinstance(results[0], Exception) else [],
            'documents': results[1] if not isinstance(results[1], Exception) else [],
            'reports': results[2] if not isinstance(results[2], Exception) else [],
        }
