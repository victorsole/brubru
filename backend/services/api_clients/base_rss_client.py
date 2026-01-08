"""
Base RSS Client for EU Institutional RSS Feeds

Provides functionality for:
- RSS/ATOM feed parsing
- Support RSS 2.0 and ATOM formats
- Feed caching with TTL
- Update detection (new entries only)
- Language support (24 EU languages)
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import feedparser
import httpx
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RSSEntry:
    """Represents a single RSS/ATOM feed entry"""
    id: str
    title: str
    link: str
    published: datetime
    summary: str = ""
    content: str = ""
    author: str = ""
    categories: List[str] = field(default_factory=list)
    language: Optional[str] = None
    feed_source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "published": self.published.isoformat(),
            "summary": self.summary,
            "content": self.content,
            "author": self.author,
            "categories": self.categories,
            "language": self.language,
            "feed_source": self.feed_source,
        }


@dataclass
class RSSFeed:
    """Represents an RSS/ATOM feed"""
    url: str
    title: str = ""
    description: str = ""
    language: Optional[str] = None
    last_updated: Optional[datetime] = None
    last_fetched: Optional[datetime] = None
    entries: List[RSSEntry] = field(default_factory=list)


class BaseRSSClient:
    """
    Base client for fetching and parsing RSS/ATOM feeds

    Supports:
    - RSS 2.0 and ATOM 1.0 formats
    - Caching with configurable TTL
    - New entry detection
    - Multiple language support
    """

    def __init__(
        self,
        cache_ttl: int = 900,  # 15 minutes default
        timeout: int = 30,
        user_agent: str = "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)"
    ):
        """
        Initialize RSS client

        Args:
            cache_ttl: Cache time-to-live in seconds
            timeout: HTTP request timeout
            user_agent: User agent string for requests
        """
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.user_agent = user_agent

        # In-memory cache: {feed_url: (RSSFeed, fetch_timestamp)}
        self._cache: Dict[str, tuple[RSSFeed, datetime]] = {}

        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent}
        )

        logger.info(f"Initialized BaseRSSClient with cache TTL={cache_ttl}s")

    def _generate_entry_id(self, entry: Any, feed_url: str) -> str:
        """
        Generate unique ID for RSS entry

        Args:
            entry: Feedparser entry object
            feed_url: Source feed URL

        Returns:
            Unique ID string
        """
        # Try to use entry's guid/id
        if hasattr(entry, 'id') and entry.id:
            return entry.id

        # Fallback: hash of (feed_url + link + published)
        unique_string = f"{feed_url}{entry.link}{entry.get('published', '')}"
        return hashlib.md5(unique_string.encode()).hexdigest()

    def _parse_date(self, entry: Any) -> datetime:
        """
        Parse publication date from entry

        Args:
            entry: Feedparser entry object

        Returns:
            Publication datetime
        """
        # Try different date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                time_struct = getattr(entry, field)
                try:
                    return datetime(*time_struct[:6])
                except (TypeError, ValueError):
                    continue

        # Fallback to current time if no date found
        logger.warning(f"No date found for entry {entry.get('link', 'unknown')}, using current time")
        return datetime.now()

    def _parse_entry(self, entry: Any, feed_url: str, feed_language: Optional[str] = None) -> RSSEntry:
        """
        Parse feedparser entry into RSSEntry object

        Args:
            entry: Feedparser entry object
            feed_url: Source feed URL
            feed_language: Feed language code

        Returns:
            RSSEntry object
        """
        # Extract content (prefer content over summary)
        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].get('value', '')
        elif hasattr(entry, 'summary'):
            content = entry.summary

        # Extract categories/tags
        categories = []
        if hasattr(entry, 'tags'):
            categories = [tag.get('term', '') for tag in entry.tags]

        return RSSEntry(
            id=self._generate_entry_id(entry, feed_url),
            title=entry.get('title', 'No title'),
            link=entry.get('link', ''),
            published=self._parse_date(entry),
            summary=entry.get('summary', ''),
            content=content,
            author=entry.get('author', ''),
            categories=categories,
            language=feed_language,
            feed_source=feed_url
        )

    async def fetch_feed(
        self,
        feed_url: str,
        force_refresh: bool = False,
        since: Optional[datetime] = None
    ) -> RSSFeed:
        """
        Fetch and parse RSS/ATOM feed

        Args:
            feed_url: URL of the RSS/ATOM feed
            force_refresh: Bypass cache and fetch fresh data
            since: Only return entries published after this date

        Returns:
            RSSFeed object with parsed entries
        """
        # Check cache
        if not force_refresh and feed_url in self._cache:
            cached_feed, fetch_time = self._cache[feed_url]
            cache_age = (datetime.now() - fetch_time).total_seconds()

            if cache_age < self.cache_ttl:
                logger.debug(f"Returning cached feed for {feed_url} (age: {cache_age:.0f}s)")

                # Filter by date if requested
                if since:
                    cached_feed.entries = [
                        e for e in cached_feed.entries
                        if e.published > since
                    ]

                return cached_feed

        # Fetch feed
        logger.info(f"Fetching RSS feed: {feed_url}")

        try:
            response = await self.client.get(feed_url)
            response.raise_for_status()
            feed_content = response.text
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch RSS feed {feed_url}: {str(e)}")
            raise

        # Parse feed
        parsed = feedparser.parse(feed_content)

        if parsed.bozo:  # Feedparser detected malformed feed
            logger.warning(f"Malformed RSS feed detected: {feed_url}")

        # Extract feed metadata
        feed_info = parsed.get('feed', {})
        feed_language = feed_info.get('language')

        # Parse entries
        entries = [
            self._parse_entry(entry, feed_url, feed_language)
            for entry in parsed.entries
        ]

        # Filter by date if requested
        if since:
            entries = [e for e in entries if e.published > since]

        # Create RSSFeed object
        rss_feed = RSSFeed(
            url=feed_url,
            title=feed_info.get('title', ''),
            description=feed_info.get('description', ''),
            language=feed_language,
            last_updated=self._parse_date(feed_info) if feed_info.get('updated_parsed') else None,
            last_fetched=datetime.now(),
            entries=entries
        )

        # Update cache
        self._cache[feed_url] = (rss_feed, datetime.now())

        logger.info(f"Fetched {len(entries)} entries from {feed_url}")
        return rss_feed

    async def fetch_multiple_feeds(
        self,
        feed_urls: List[str],
        force_refresh: bool = False,
        since: Optional[datetime] = None
    ) -> List[RSSFeed]:
        """
        Fetch multiple RSS feeds concurrently

        Args:
            feed_urls: List of feed URLs
            force_refresh: Bypass cache
            since: Only return entries after this date

        Returns:
            List of RSSFeed objects
        """
        import asyncio

        tasks = [
            self.fetch_feed(url, force_refresh, since)
            for url in feed_urls
        ]

        feeds = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_feeds = [
            feed for feed in feeds
            if isinstance(feed, RSSFeed)
        ]

        # Log exceptions
        for i, result in enumerate(feeds):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {feed_urls[i]}: {str(result)}")

        return valid_feeds

    def get_new_entries(
        self,
        feed_url: str,
        last_check: datetime
    ) -> List[RSSEntry]:
        """
        Get only new entries since last check

        Args:
            feed_url: Feed URL
            last_check: Datetime of last check

        Returns:
            List of new entries
        """
        if feed_url not in self._cache:
            logger.warning(f"Feed {feed_url} not in cache")
            return []

        cached_feed, _ = self._cache[feed_url]
        new_entries = [
            entry for entry in cached_feed.entries
            if entry.published > last_check
        ]

        logger.debug(f"Found {len(new_entries)} new entries in {feed_url} since {last_check}")
        return new_entries

    def clear_cache(self, feed_url: Optional[str] = None):
        """
        Clear feed cache

        Args:
            feed_url: Specific feed to clear, or None to clear all
        """
        if feed_url:
            if feed_url in self._cache:
                del self._cache[feed_url]
                logger.info(f"Cleared cache for {feed_url}")
        else:
            self._cache.clear()
            logger.info("Cleared all feed caches")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("Closed RSS client")
