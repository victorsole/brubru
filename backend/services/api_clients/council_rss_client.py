"""
European Council & Council of the EU RSS Client

Monitors RSS feeds from EU Council institutions:
- European Council (heads of state/government)
- Council of the EU (ministers)
- Press releases, statements, conclusions
- Meeting agendas and outcomes

Documentation:
- European Council: https://www.consilium.europa.eu/en/european-council/
- Council of EU: https://www.consilium.europa.eu/en/council-eu/
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class CouncilRSSClient:
    """
    Client for European Council and Council of the EU RSS feeds

    Features:
    - Press releases monitoring
    - Meeting conclusions
    - Council configurations updates
    - European Council summit news
    """

    # RSS Feeds
    RSS_FEEDS = {
        "press_releases_en": "https://www.consilium.europa.eu/en/press/press-releases/rss/",
        "press_releases_fr": "https://www.consilium.europa.eu/fr/press/press-releases/rss/",
        "press_releases_de": "https://www.consilium.europa.eu/de/press/press-releases/rss/",

        "statements_remarks": "https://www.consilium.europa.eu/en/press/statements-remarks/rss/",

        # Council configurations
        "general_affairs": "https://www.consilium.europa.eu/en/council-eu/configurations/gac/rss/",
        "foreign_affairs": "https://www.consilium.europa.eu/en/council-eu/configurations/fac/rss/",
        "economic_financial": "https://www.consilium.europa.eu/en/council-eu/configurations/ecofin/rss/",
        "justice_home": "https://www.consilium.europa.eu/en/council-eu/configurations/jha/rss/",
        "agriculture_fisheries": "https://www.consilium.europa.eu/en/council-eu/configurations/agrifish/rss/",
        "competitiveness": "https://www.consilium.europa.eu/en/council-eu/configurations/compet/rss/",
        "transport_telecom": "https://www.consilium.europa.eu/en/council-eu/configurations/tte/rss/",
        "environment": "https://www.consilium.europa.eu/en/council-eu/configurations/env/rss/",
        "education_youth": "https://www.consilium.europa.eu/en/council-eu/configurations/eycs/rss/",
        "employment_social": "https://www.consilium.europa.eu/en/council-eu/configurations/epsco/rss/",

        # European Council
        "european_council": "https://www.consilium.europa.eu/en/european-council/rss/",
        "euro_summit": "https://www.consilium.europa.eu/en/european-council/euro-summit/rss/"
    }

    def __init__(
        self,
        cache_ttl: int = 900,
        timeout: int = 30
    ):
        """
        Initialize Council RSS client

        Args:
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout
        """
        self.rss_client = BaseRSSClient(
            cache_ttl=cache_ttl,
            timeout=timeout
        )

        logger.info("Initialized Council RSS client")

    async def get_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch specific Council RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.RSS_FEEDS.keys())}")

        feed_url = self.RSS_FEEDS[feed_name]
        logger.info(f"Fetching Council RSS feed: {feed_name}")

        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_all_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch all Council RSS feeds

        Args:
            since: Only get entries after this date

        Returns:
            List of RSS feeds
        """
        logger.info(f"Fetching all {len(self.RSS_FEEDS)} Council RSS feeds")

        feed_urls = list(self.RSS_FEEDS.values())
        return await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

    async def get_latest_press_releases(
        self,
        hours: int = 24,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Get latest press releases

        Args:
            hours: Get releases from last N hours
            language: Language code (en, fr, de)

        Returns:
            List of press releases
        """
        since = datetime.now() - timedelta(hours=hours)
        feed_name = f"press_releases_{language}"

        if feed_name not in self.RSS_FEEDS:
            feed_name = "press_releases_en"

        logger.info(f"Fetching latest press releases ({language})")

        feed = await self.rss_client.fetch_feed(self.RSS_FEEDS[feed_name], since=since)

        releases = []
        for entry in feed.entries:
            releases.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "language": language
            })

        logger.info(f"Found {len(releases)} press releases")
        return releases

    async def get_council_configuration_news(
        self,
        configuration: str,
        hours: int = 168  # 1 week default
    ) -> List[Dict[str, Any]]:
        """
        Get news for specific Council configuration

        Args:
            configuration: Configuration name (e.g., "foreign_affairs", "environment")
            hours: Get news from last N hours

        Returns:
            List of news items
        """
        if configuration not in self.RSS_FEEDS:
            raise ValueError(f"Unknown configuration: {configuration}")

        since = datetime.now() - timedelta(hours=hours)

        logger.info(f"Fetching news for {configuration} Council")

        feed = await self.rss_client.fetch_feed(self.RSS_FEEDS[configuration], since=since)

        news = []
        for entry in feed.entries:
            news.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "configuration": configuration
            })

        logger.info(f"Found {len(news)} news items for {configuration}")
        return news

    async def get_european_council_news(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get European Council summit and meeting news

        Args:
            days: Get news from last N days

        Returns:
            List of European Council news
        """
        since = datetime.now() - timedelta(days=days)

        logger.info("Fetching European Council news")

        feeds = await self.rss_client.fetch_multiple_feeds(
            [
                self.RSS_FEEDS["european_council"],
                self.RSS_FEEDS["euro_summit"]
            ],
            since=since
        )

        news = []
        for feed in feeds:
            for entry in feed.entries:
                news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary
                })

        # Sort by date
        news.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(news)} European Council news items")
        return news

    async def get_aggregated_news(
        self,
        hours: int = 24,
        configurations: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated news from multiple sources

        Args:
            hours: Get news from last N hours
            configurations: Specific configurations to include (None = all)

        Returns:
            Aggregated and sorted news
        """
        since = datetime.now() - timedelta(hours=hours)

        # Select feeds
        if configurations:
            feed_urls = [self.RSS_FEEDS[conf] for conf in configurations if conf in self.RSS_FEEDS]
        else:
            feed_urls = list(self.RSS_FEEDS.values())

        logger.info(f"Fetching aggregated news from {len(feed_urls)} feeds")

        feeds = await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

        # Aggregate all entries
        all_news = []
        for feed in feeds:
            for entry in feed.entries:
                all_news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "feed_source": entry.feed_source
                })

        # Sort by date
        all_news.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(all_news)} total news items")
        return all_news

    async def close(self):
        """Close RSS client"""
        await self.rss_client.close()
        logger.info("Closed Council RSS client")
