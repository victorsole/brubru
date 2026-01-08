"""
EU News Media RSS Client

Monitors major EU policy news outlets:
- Euractiv - Pan-European policy news network
- Politico Europe - Brussels insider coverage
- Euronews My Europe - EU institutional affairs

Documentation:
- Euractiv: https://www.euractiv.com/
- Politico Europe: https://www.politico.eu/
- Euronews: https://www.euronews.com/my-europe
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .base_rss_client import BaseRSSClient, RSSFeed

logger = logging.getLogger(__name__)


class NewsRSSClient:
    """
    Client for EU news media RSS feeds

    Features:
    - Breaking EU news monitoring
    - Policy analysis and commentary
    - Stakeholder perspectives
    - Multi-source aggregation
    """

    # RSS Feeds
    RSS_FEEDS = {
        # Euractiv - Leading EU policy news
        "euractiv_main": "https://www.euractiv.com/?feed=mcfeed",

        # Politico Europe - Brussels insider news
        "politico_europe": "https://www.politico.eu/feed/",

        # Euronews - My Europe section (Media RSS format)
        "euronews_my_europe": "https://www.euronews.com/rss?format=mrss&level=vertical&name=my-europe"
    }

    def __init__(
        self,
        cache_ttl: int = 900,  # 15 minutes
        timeout: int = 30
    ):
        """
        Initialize News RSS client

        Args:
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout
        """
        self.rss_client = BaseRSSClient(
            cache_ttl=cache_ttl,
            timeout=timeout
        )

        logger.info("Initialized News RSS client")

    async def get_feed(
        self,
        feed_name: str,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch specific news RSS feed

        Args:
            feed_name: Feed name from RSS_FEEDS dict
            since: Only get entries after this date

        Returns:
            RSS feed
        """
        if feed_name not in self.RSS_FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.RSS_FEEDS.keys())}")

        feed_url = self.RSS_FEEDS[feed_name]
        logger.info(f"Fetching news RSS feed: {feed_name}")

        return await self.rss_client.fetch_feed(feed_url, since=since)

    async def get_all_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch all news media RSS feeds

        Args:
            since: Only get entries after this date

        Returns:
            List of RSS feeds
        """
        logger.info(f"Fetching all {len(self.RSS_FEEDS)} news media RSS feeds")

        feed_urls = list(self.RSS_FEEDS.values())
        return await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

    async def get_euractiv_news(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get latest Euractiv news

        Args:
            hours: Get news from last N hours

        Returns:
            List of news articles
        """
        since = datetime.now() - timedelta(hours=hours)

        logger.info(f"Fetching Euractiv news from last {hours} hours")

        feed = await self.rss_client.fetch_feed(
            self.RSS_FEEDS["euractiv_main"],
            since=since
        )

        articles = []
        for entry in feed.entries:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "source": "euractiv",
                "categories": entry.categories,
                "author": entry.author
            })

        logger.info(f"Found {len(articles)} Euractiv articles")
        return articles

    async def get_politico_news(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get latest Politico Europe news

        Args:
            hours: Get news from last N hours

        Returns:
            List of news articles
        """
        since = datetime.now() - timedelta(hours=hours)

        logger.info(f"Fetching Politico Europe news from last {hours} hours")

        feed = await self.rss_client.fetch_feed(
            self.RSS_FEEDS["politico_europe"],
            since=since
        )

        articles = []
        for entry in feed.entries:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "source": "politico_europe",
                "categories": entry.categories,
                "author": entry.author
            })

        logger.info(f"Found {len(articles)} Politico Europe articles")
        return articles

    async def get_euronews_my_europe(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get latest Euronews My Europe articles

        Args:
            hours: Get news from last N hours

        Returns:
            List of news articles (includes video content)
        """
        since = datetime.now() - timedelta(hours=hours)

        logger.info(f"Fetching Euronews My Europe from last {hours} hours")

        feed = await self.rss_client.fetch_feed(
            self.RSS_FEEDS["euronews_my_europe"],
            since=since
        )

        articles = []
        for entry in feed.entries:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published.isoformat(),
                "summary": entry.summary,
                "content": entry.content,  # May include video embeds
                "source": "euronews_europe",
                "categories": entry.categories,
                "author": entry.author
            })

        logger.info(f"Found {len(articles)} Euronews My Europe articles")
        return articles

    async def get_all_news(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated news from all sources

        Args:
            hours: Get news from last N hours

        Returns:
            Aggregated and sorted news from all sources
        """
        since = datetime.now() - timedelta(hours=hours)

        logger.info(f"Fetching aggregated news from all sources (last {hours} hours)")

        feeds = await self.rss_client.fetch_multiple_feeds(
            list(self.RSS_FEEDS.values()),
            since=since
        )

        all_news = []
        source_map = {
            self.RSS_FEEDS["euractiv_main"]: "euractiv",
            self.RSS_FEEDS["politico_europe"]: "politico_europe",
            self.RSS_FEEDS["euronews_my_europe"]: "euronews_europe"
        }

        for feed in feeds:
            source = source_map.get(feed.url, "unknown")
            for entry in feed.entries:
                all_news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "content": entry.content,
                    "source": source,
                    "categories": entry.categories,
                    "author": entry.author
                })

        # Sort by published date (most recent first)
        all_news.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(all_news)} total news articles across all sources")
        return all_news

    async def search_news(
        self,
        query: str,
        days: int = 7,
        sources: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search news articles by keyword

        Args:
            query: Search query
            days: Search within last N days
            sources: Filter by specific sources (euractiv, politico_europe, euronews_europe)

        Returns:
            Matching news articles
        """
        since = datetime.now() - timedelta(days=days)

        logger.info(f"Searching news for '{query}' in last {days} days")

        # Select feeds based on sources filter
        if sources:
            feed_urls = []
            source_map = {
                "euractiv": self.RSS_FEEDS["euractiv_main"],
                "politico_europe": self.RSS_FEEDS["politico_europe"],
                "euronews_europe": self.RSS_FEEDS["euronews_my_europe"]
            }
            for source in sources:
                if source in source_map:
                    feed_urls.append(source_map[source])
        else:
            feed_urls = list(self.RSS_FEEDS.values())

        feeds = await self.rss_client.fetch_multiple_feeds(feed_urls, since=since)

        # Search in titles and summaries
        query_lower = query.lower()
        results = []

        source_map = {
            self.RSS_FEEDS["euractiv_main"]: "euractiv",
            self.RSS_FEEDS["politico_europe"]: "politico_europe",
            self.RSS_FEEDS["euronews_my_europe"]: "euronews_europe"
        }

        for feed in feeds:
            source = source_map.get(feed.url, "unknown")
            for entry in feed.entries:
                if (query_lower in entry.title.lower() or
                    query_lower in entry.summary.lower()):
                    results.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.published.isoformat(),
                        "summary": entry.summary,
                        "source": source,
                        "categories": entry.categories,
                        "author": entry.author
                    })

        # Sort by published date
        results.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(results)} articles matching '{query}'")
        return results

    async def get_breaking_news(
        self,
        hours: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Get very recent breaking news (last few hours)

        Args:
            hours: Time window for breaking news (default: 6 hours)

        Returns:
            Recent breaking news articles
        """
        logger.info(f"Fetching breaking news from last {hours} hours")

        # Prioritize Politico for breaking news (updates most frequently)
        since = datetime.now() - timedelta(hours=hours)

        feeds = await self.rss_client.fetch_multiple_feeds(
            [
                self.RSS_FEEDS["politico_europe"],  # Check Politico first
                self.RSS_FEEDS["euractiv_main"],
                self.RSS_FEEDS["euronews_my_europe"]
            ],
            since=since
        )

        breaking_news = []
        source_map = {
            self.RSS_FEEDS["euractiv_main"]: "euractiv",
            self.RSS_FEEDS["politico_europe"]: "politico_europe",
            self.RSS_FEEDS["euronews_my_europe"]: "euronews_europe"
        }

        for feed in feeds:
            source = source_map.get(feed.url, "unknown")
            for entry in feed.entries:
                breaking_news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "source": source,
                    "categories": entry.categories,
                    "author": entry.author,
                    "age_hours": (datetime.now() - entry.published).total_seconds() / 3600
                })

        # Sort by most recent first
        breaking_news.sort(key=lambda x: x["published"], reverse=True)

        logger.info(f"Found {len(breaking_news)} breaking news articles")
        return breaking_news

    async def close(self):
        """Close RSS client"""
        await self.rss_client.close()
        logger.info("Closed News RSS client")
