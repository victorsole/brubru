"""
European Parliament Think Tank RSS Client

Monitors European Parliament Research Service (EPRS) Think Tank:
- Briefings and analysis
- At a Glance publications
- In-depth analysis
- Studies and research papers
- Policy area updates

Documentation:
- Think Tank: https://www.europarl.europa.eu/thinktank/en/home.html
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class ThinkTankRSSClient:
    """
    Client for European Parliament Think Tank RSS feeds

    Features:
    - Research briefings
    - Policy analysis
    - Topic-specific updates
    - Study publications
    """

    # RSS Feeds by topic/type
    RSS_FEEDS = {
        # Publication types
        "all_publications": "https://www.europarl.europa.eu/thinktank/en/rss.xml",
        "at_a_glance": "https://www.europarl.europa.eu/thinktank/en/rss.xml?type=AT_A_GLANCE",
        "briefings": "https://www.europarl.europa.eu/thinktank/en/rss.xml?type=BRIEFING",
        "in_depth_analysis": "https://www.europarl.europa.eu/thinktank/en/rss.xml?type=IN_DEPTH_ANALYSIS",
        "studies": "https://www.europarl.europa.eu/thinktank/en/rss.xml?type=STUDY",

        # Policy areas
        "agriculture": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=AGRI",
        "budgets": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=BUDG",
        "constitutional_affairs": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=AFCO",
        "culture_education": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=CULT",
        "development": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=DEVE",
        "economic_monetary": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=ECON",
        "employment_social": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=EMPL",
        "environment": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=ENVI",
        "fisheries": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=PECH",
        "foreign_affairs": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=AFET",
        "industry_energy": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=ITRE",
        "internal_market": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=IMCO",
        "international_trade": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=INTA",
        "justice_home_affairs": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=LIBE",
        "legal_affairs": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=JURI",
        "regional_development": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=REGI",
        "transport_tourism": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=TRAN",
        "womens_rights": "https://www.europarl.europa.eu/thinktank/en/rss.xml?topic=FEMM"
    }

    def __init__(
        self,
        cache_ttl: int = 1800,  # 30 minutes
        timeout: int = 30
    ):
        """
        Initialize Think Tank RSS client

        Args:
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout
        """
        self.rss_client = BaseRSSClient(
            cache_ttl=cache_ttl,
            timeout=timeout
        )

        logger.info("Initialized Think Tank RSS client")

    async def get_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch specific Think Tank RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.RSS_FEEDS.keys())}")

        feed_url = self.RSS_FEEDS[feed_name]
        logger.info(f"Fetching Think Tank RSS feed: {feed_name}")

        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_all_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch all Think Tank RSS feeds

        Args:
            since: Only get entries after this date

        Returns:
            List of RSS feeds
        """
        logger.info(f"Fetching all {len(self.RSS_FEEDS)} Think Tank RSS feeds")

        feed_urls = list(self.RSS_FEEDS.values())
        return await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

    async def get_latest_publications(
        self,
        days: int = 7,
        publication_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get latest Think Tank publications

        Args:
            days: Get publications from last N days
            publication_type: Filter by type (briefings, studies, etc.)

        Returns:
            List of publications
        """
        since = datetime.now() - timedelta(days=days)

        if publication_type and publication_type in self.RSS_FEEDS:
            feeds = [await self.rss_client.fetch_feed(self.RSS_FEEDS[publication_type], since=since)]
        else:
            # Get main feed
            feeds = [await self.rss_client.fetch_feed(self.RSS_FEEDS["all_publications"], since=since)]

        logger.info(f"Fetching latest Think Tank publications ({publication_type or 'all'})")

        publications = []
        for feed in feeds:
            for entry in feed.entries:
                publications.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "categories": entry.categories
                })

        # Sort by date
        publications.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(publications)} publications")
        return publications

    async def get_policy_area_research(
        self,
        policy_area: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get research for specific policy area

        Args:
            policy_area: Policy area name (e.g., "environment", "digital")
            days: Get research from last N days

        Returns:
            List of research publications
        """
        if policy_area not in self.RSS_FEEDS:
            raise ValueError(f"Unknown policy area: {policy_area}")

        since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching Think Tank research for {policy_area}")

        feed = await self.rss_client.fetch_feed(self.RSS_FEEDS[policy_area], since=since)

        research = []
        for entry in feed.entries:
            research.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "policy_area": policy_area,
                "categories": entry.categories
            })

        logger.info(f"Found {len(research)} research items for {policy_area}")
        return research

    async def get_briefings(
        self,
        days: int = 14
    ) -> List[Dict[str, Any]]:
        """
        Get latest briefings

        Args:
            days: Get briefings from last N days

        Returns:
            List of briefings
        """
        return await self.get_latest_publications(days=days, publication_type="briefings")

    async def get_at_a_glance(
        self,
        days: int = 14
    ) -> List[Dict[str, Any]]:
        """
        Get latest "At a Glance" publications

        Args:
            days: Get publications from last N days

        Returns:
            List of At a Glance publications
        """
        return await self.get_latest_publications(days=days, publication_type="at_a_glance")

    async def get_in_depth_analysis(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get latest in-depth analysis publications

        Args:
            days: Get publications from last N days

        Returns:
            List of in-depth analysis
        """
        return await self.get_latest_publications(days=days, publication_type="in_depth_analysis")

    async def get_studies(
        self,
        days: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get latest studies

        Args:
            days: Get studies from last N days

        Returns:
            List of studies
        """
        return await self.get_latest_publications(days=days, publication_type="studies")

    async def search_by_keyword(
        self,
        keyword: str,
        days: int = 365
    ) -> List[Dict[str, Any]]:
        """
        Search publications by keyword

        Args:
            keyword: Search keyword
            days: Search within last N days

        Returns:
            Matching publications
        """
        since = datetime.now() - timedelta(days=days)

        logger.info(f"Searching Think Tank publications for keyword: {keyword}")

        # Fetch all publications
        feed = await self.rss_client.fetch_feed(self.RSS_FEEDS["all_publications"], since=since)

        # Filter by keyword
        keyword_lower = keyword.lower()
        results = []

        for entry in feed.entries:
            if (keyword_lower in entry.title.lower() or
                keyword_lower in entry.summary.lower()):
                results.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "categories": entry.categories
                })

        logger.info(f"Found {len(results)} publications matching '{keyword}'")
        return results

    async def get_aggregated_research(
        self,
        policy_areas: List[str],
        days: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get research from multiple policy areas

        Args:
            policy_areas: List of policy area names
            days: Get research from last N days

        Returns:
            Dictionary with research grouped by policy area
        """
        since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching aggregated research for {len(policy_areas)} policy areas")

        results = {}

        for area in policy_areas:
            if area not in self.RSS_FEEDS:
                logger.warning(f"Unknown policy area: {area}")
                continue

            feed = await self.rss_client.fetch_feed(self.RSS_FEEDS[area], since=since)

            research_items = []
            for entry in feed.entries:
                research_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "categories": entry.categories
                })

            results[area] = research_items

        return results

    async def close(self):
        """Close RSS client"""
        await self.rss_client.close()
        logger.info("Closed Think Tank RSS client")
