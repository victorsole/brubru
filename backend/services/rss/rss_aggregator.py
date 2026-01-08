"""
RSS Feed Aggregation Service

Centralized service for aggregating RSS feeds from all EU institutions and news media:
- European Parliament (33+ feeds)
- EUR-Lex (7+ feeds)
- OEIL (6 feeds)
- Council of EU (17+ feeds)
- Think Tank (20+ feeds)
- News Media (3 feeds: Euractiv, Politico Europe, Euronews)

Features:
- Concurrent feed fetching
- Deduplication across sources
- Priority-based updates
- Feed health monitoring
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio

from ..api_clients.european_parliament_client import EuropeanParliamentClient
from ..api_clients.eurlex_client import EURLexClient
from ..api_clients.oeil_client import OEILClient
from ..api_clients.council_rss_client import CouncilRSSClient
from ..api_clients.think_tank_rss_client import ThinkTankRSSClient
from ..api_clients.news_rss_client import NewsRSSClient
from ..api_clients.base_rss_client import RSSEntry

logger = logging.getLogger(__name__)


@dataclass
class AggregatedFeedEntry:
    """Unified feed entry from any source"""
    id: str
    title: str
    link: str
    published: datetime
    summary: str
    content: str
    source: str  # e.g., "european_parliament", "eurlex"
    feed_name: str  # e.g., "press_releases", "official_journal"
    categories: List[str] = field(default_factory=list)
    language: Optional[str] = None
    author: str = ""


class RSSAggregator:
    """
    Centralized RSS feed aggregator for all EU institutions and news media

    Manages 85+ RSS feeds with:
    - Concurrent fetching
    - Deduplication
    - Priority scheduling
    - Health monitoring
    """

    def __init__(self):
        """Initialize RSS aggregator"""
        # Initialize all clients
        self.ep_client = EuropeanParliamentClient()
        self.eurlex_client = EURLexClient()
        self.oeil_client = OEILClient()
        self.council_client = CouncilRSSClient()
        self.think_tank_client = ThinkTankRSSClient()
        self.news_client = NewsRSSClient()

        # Track last fetch times
        self._last_fetch: Dict[str, datetime] = {}

        # Feed priorities (higher = more frequent updates)
        self._feed_priorities = {
            "european_parliament": 3,
            "eurlex": 3,
            "news_media": 3,  # News media needs frequent updates for breaking news
            "council": 2,
            "oeil": 2,
            "think_tank": 1
        }

        logger.info("Initialized RSS Aggregator with news media sources")

    async def fetch_all_feeds(
        self,
        since: Optional[datetime] = None
    ) -> List[AggregatedFeedEntry]:
        """
        Fetch all RSS feeds from all sources concurrently

        Args:
            since: Only fetch entries after this date

        Returns:
            List of aggregated feed entries
        """
        logger.info("Fetching all RSS feeds from all sources including news media")

        # Fetch all feeds concurrently
        tasks = [
            self._fetch_european_parliament_feeds(since),
            self._fetch_eurlex_feeds(since),
            self._fetch_oeil_feeds(since),
            self._fetch_council_feeds(since),
            self._fetch_think_tank_feeds(since),
            self._fetch_news_media_feeds(since)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine all entries
        all_entries = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch failed: {str(result)}")
                continue
            all_entries.extend(result)

        # Deduplicate by link
        seen_links = set()
        unique_entries = []
        for entry in all_entries:
            if entry.link not in seen_links:
                seen_links.add(entry.link)
                unique_entries.append(entry)

        # Sort by published date
        unique_entries.sort(key=lambda x: x.published, reverse=True)

        logger.info(f"Fetched {len(unique_entries)} unique entries from all feeds")
        return unique_entries

    async def _fetch_european_parliament_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch European Parliament RSS feeds"""
        logger.debug("Fetching European Parliament feeds")

        feeds = await self.ep_client.get_all_rss_feeds(since=since)

        entries = []
        for feed in feeds:
            for entry in feed.entries:
                entries.append(AggregatedFeedEntry(
                    id=entry.id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    summary=entry.summary,
                    content=entry.content,
                    source="european_parliament",
                    feed_name=self._extract_feed_name(entry.feed_source),
                    categories=entry.categories,
                    language=entry.language,
                    author=entry.author
                ))

        return entries

    async def _fetch_eurlex_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch EUR-Lex RSS feeds"""
        logger.debug("Fetching EUR-Lex feeds")

        entries = []
        feed_names = list(self.eurlex_client.RSS_FEEDS.keys())

        for feed_name in feed_names:
            try:
                feed = await self.eurlex_client.get_rss_feed(feed_name, since=since)

                for entry in feed.entries:
                    entries.append(AggregatedFeedEntry(
                        id=entry.id,
                        title=entry.title,
                        link=entry.link,
                        published=entry.published,
                        summary=entry.summary,
                        content=entry.content,
                        source="eurlex",
                        feed_name=feed_name,
                        categories=entry.categories,
                        language=entry.language,
                        author=entry.author
                    ))
            except Exception as e:
                logger.error(f"Failed to fetch EUR-Lex feed {feed_name}: {str(e)}")

        return entries

    async def _fetch_oeil_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch OEIL RSS feeds"""
        logger.debug("Fetching OEIL feeds")

        feeds = await self.oeil_client.get_all_rss_feeds(since=since)

        entries = []
        for feed in feeds:
            for entry in feed.entries:
                entries.append(AggregatedFeedEntry(
                    id=entry.id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    summary=entry.summary,
                    content=entry.content,
                    source="oeil",
                    feed_name=self._extract_feed_name(entry.feed_source),
                    categories=entry.categories,
                    language=entry.language,
                    author=entry.author
                ))

        return entries

    async def _fetch_council_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch Council RSS feeds"""
        logger.debug("Fetching Council feeds")

        feeds = await self.council_client.get_all_feeds(since=since)

        entries = []
        for feed in feeds:
            for entry in feed.entries:
                entries.append(AggregatedFeedEntry(
                    id=entry.id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    summary=entry.summary,
                    content=entry.content,
                    source="council",
                    feed_name=self._extract_feed_name(entry.feed_source),
                    categories=entry.categories,
                    language=entry.language,
                    author=entry.author
                ))

        return entries

    async def _fetch_think_tank_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch Think Tank RSS feeds"""
        logger.debug("Fetching Think Tank feeds")

        feeds = await self.think_tank_client.get_all_feeds(since=since)

        entries = []
        for feed in feeds:
            for entry in feed.entries:
                entries.append(AggregatedFeedEntry(
                    id=entry.id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    summary=entry.summary,
                    content=entry.content,
                    source="think_tank",
                    feed_name=self._extract_feed_name(entry.feed_source),
                    categories=entry.categories,
                    language=entry.language,
                    author=entry.author
                ))

        return entries

    async def _fetch_news_media_feeds(
        self,
        since: Optional[datetime]
    ) -> List[AggregatedFeedEntry]:
        """Fetch News Media RSS feeds (Euractiv, Politico, Euronews)"""
        logger.debug("Fetching News Media feeds")

        feeds = await self.news_client.get_all_feeds(since=since)

        entries = []

        # Map feed URLs to source names
        source_map = {
            "https://www.euractiv.com/?feed=mcfeed": "euractiv",
            "https://www.politico.eu/feed/": "politico_europe",
            "https://www.euronews.com/rss?format=mrss&level=vertical&name=my-europe": "euronews_europe"
        }

        for feed in feeds:
            # Determine specific news source from feed URL
            news_source = source_map.get(feed.url, "news_media")

            for entry in feed.entries:
                entries.append(AggregatedFeedEntry(
                    id=entry.id,
                    title=entry.title,
                    link=entry.link,
                    published=entry.published,
                    summary=entry.summary,
                    content=entry.content,
                    source=news_source,
                    feed_name="news",
                    categories=entry.categories,
                    language=entry.language,
                    author=entry.author
                ))

        return entries

    def _extract_feed_name(self, feed_url: str) -> str:
        """Extract feed name from URL"""
        # Simple extraction from URL
        parts = feed_url.rstrip('/').split('/')
        if parts:
            name = parts[-1].replace('.xml', '').replace('rss_', '').replace('rss', '')
            return name or "unknown"
        return "unknown"

    async def fetch_by_source(
        self,
        source: str,
        since: Optional[datetime] = None
    ) -> List[AggregatedFeedEntry]:
        """
        Fetch feeds from specific source

        Args:
            source: Source name (european_parliament, eurlex, oeil, council, think_tank, news_media, euractiv, politico_europe, euronews_europe)
            since: Only fetch entries after this date

        Returns:
            List of entries from source
        """
        logger.info(f"Fetching feeds from source: {source}")

        if source == "european_parliament":
            return await self._fetch_european_parliament_feeds(since)
        elif source == "eurlex":
            return await self._fetch_eurlex_feeds(since)
        elif source == "oeil":
            return await self._fetch_oeil_feeds(since)
        elif source == "council":
            return await self._fetch_council_feeds(since)
        elif source == "think_tank":
            return await self._fetch_think_tank_feeds(since)
        elif source in ["news_media", "euractiv", "politico_europe", "euronews_europe"]:
            # Fetch all news media feeds, then filter if specific source requested
            all_news = await self._fetch_news_media_feeds(since)
            if source == "news_media":
                return all_news
            else:
                # Filter to specific news source
                return [entry for entry in all_news if entry.source == source]
        else:
            raise ValueError(f"Unknown source: {source}")

    async def fetch_by_category(
        self,
        category: str,
        since: Optional[datetime] = None
    ) -> List[AggregatedFeedEntry]:
        """
        Fetch feeds filtered by category/topic

        Args:
            category: Category name
            since: Only fetch entries after this date

        Returns:
            Filtered entries
        """
        logger.info(f"Fetching feeds for category: {category}")

        all_entries = await self.fetch_all_feeds(since=since)

        # Filter by category
        category_lower = category.lower()
        filtered = [
            entry for entry in all_entries
            if any(category_lower in cat.lower() for cat in entry.categories)
        ]

        logger.info(f"Found {len(filtered)} entries for category '{category}'")
        return filtered

    async def fetch_latest(
        self,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[AggregatedFeedEntry]:
        """
        Fetch latest entries from all sources

        Args:
            hours: Get entries from last N hours
            limit: Maximum number of entries

        Returns:
            Latest entries
        """
        since = datetime.now() - timedelta(hours=hours)
        entries = await self.fetch_all_feeds(since=since)

        if limit:
            entries = entries[:limit]

        return entries

    async def search_entries(
        self,
        query: str,
        since: Optional[datetime] = None,
        sources: Optional[List[str]] = None
    ) -> List[AggregatedFeedEntry]:
        """
        Search entries by keyword

        Args:
            query: Search query
            since: Only search entries after this date
            sources: Filter by specific sources

        Returns:
            Matching entries
        """
        logger.info(f"Searching entries for: {query}")

        # Fetch entries from specified sources or all
        if sources:
            all_entries = []
            for source in sources:
                entries = await self.fetch_by_source(source, since=since)
                all_entries.extend(entries)
        else:
            all_entries = await self.fetch_all_feeds(since=since)

        # Search in title and summary
        query_lower = query.lower()
        results = [
            entry for entry in all_entries
            if (query_lower in entry.title.lower() or
                query_lower in entry.summary.lower())
        ]

        logger.info(f"Found {len(results)} entries matching '{query}'")
        return results

    def get_feed_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about available feeds

        Returns:
            Feed statistics
        """
        return {
            "total_feeds": 85,
            "sources": {
                "european_parliament": len(self.ep_client.RSS_FEEDS),
                "eurlex": len(self.eurlex_client.RSS_FEEDS),
                "oeil": len(self.oeil_client.RSS_FEEDS),
                "council": len(self.council_client.RSS_FEEDS),
                "think_tank": len(self.think_tank_client.RSS_FEEDS),
                "news_media": len(self.news_client.RSS_FEEDS)
            },
            "last_fetch": self._last_fetch
        }

    async def close(self):
        """Close all clients"""
        await self.ep_client.close()
        await self.eurlex_client.close()
        await self.oeil_client.close()
        await self.council_client.close()
        await self.think_tank_client.close()
        await self.news_client.close()
        logger.info("Closed RSS Aggregator")
