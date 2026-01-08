"""
OEIL API Client

OEIL (Observatoire législatif européen / Legislative Observatory):
- EU legislative procedures tracking
- Document status and timeline
- Amendments and votes
- Committee opinions
- RSS feeds for procedure updates

Documentation:
- OEIL Portal: https://oeil.secure.europarl.europa.eu/
- Data Export: https://oeil.secure.europarl.europa.eu/oeil/popups/sda.do
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class OEILClient(BaseAPIClient):
    """
    Client for OEIL Legislative Observatory

    Features:
    - Legislative procedure search
    - Procedure status and timeline
    - RSS feed monitoring
    - XML data export
    """

    BASE_URL = "https://oeil.secure.europarl.europa.eu/oeil"
    RSS_BASE = "https://oeil.secure.europarl.europa.eu/oeil/rss"
    EXPORT_URL = f"{BASE_URL}/popups/sda.do"

    # RSS Feeds by procedure type
    RSS_FEEDS = {
        "ordinary_legislative": f"{RSS_BASE}/rss_ordinarylegislativeprocedure.xml",
        "consultation": f"{RSS_BASE}/rss_consultation.xml",
        "consent": f"{RSS_BASE}/rss_consent.xml",
        "budgetary": f"{RSS_BASE}/rss_budgetary.xml",
        "non_legislative": f"{RSS_BASE}/rss_nonlegislative.xml",
        "all_procedures": f"{RSS_BASE}/rss_all.xml"
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
        Fetch specific OEIL RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.RSS_FEEDS.keys())}")

        feed_url = self.RSS_FEEDS[feed_name]
        logger.info(f"Fetching OEIL RSS feed: {feed_name}")

        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_all_rss_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch all OEIL RSS feeds

        Args:
            since: Only get entries after this date

        Returns:
            List of RSS feeds
        """
        logger.info(f"Fetching all {len(self.RSS_FEEDS)} OEIL RSS feeds")

        feed_urls = list(self.RSS_FEEDS.values())
        return await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

    async def get_latest_procedures(
        self,
        hours: int = 24,
        procedure_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get latest legislative procedures

        Args:
            hours: Get procedures from last N hours
            procedure_type: Specific procedure type feed

        Returns:
            List of procedures
        """
        since = datetime.now() - timedelta(hours=hours)

        if procedure_type and procedure_type in self.RSS_FEEDS:
            feeds = [await self.rss_client.fetch_feed(self.RSS_FEEDS[procedure_type], since=since)]
        else:
            feed_urls = list(self.RSS_FEEDS.values())
            feeds = await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

        # Aggregate entries
        procedures = []
        for feed in feeds:
            for entry in feed.entries:
                procedures.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "categories": entry.categories
                })

        # Sort by date
        procedures.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(procedures)} procedure updates")
        return procedures

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
        Check if OEIL API is accessible

        Returns:
            True if healthy
        """
        try:
            # Try to fetch RSS feed
            feed = await self.rss_client.fetch_feed(self.RSS_FEEDS["all_procedures"])
            return len(feed.entries) > 0
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.rss_client.close()
        logger.info("Closed OEIL client")
