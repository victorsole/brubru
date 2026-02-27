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

    # RSS Feeds - epthinktank.eu (WordPress blog, always available)
    # Note: europarl.europa.eu/thinktank/en/rss.xml URLs returned 404 as of Feb 2026
    # The general feed contains all publication types; category feeds may be empty.
    # Items are categorised via <category> tags (e.g. "At a glance", "Briefings").
    RSS_FEEDS = {
        # Primary feed (contains all publication types, 10 items per page)
        "all_publications": "https://epthinktank.eu/feed/",

        # Category feeds (WordPress category archives -- may be empty, use general feed + filter)
        "at_a_glance": "https://epthinktank.eu/category/publications/at-a-glance/feed/",
        "briefings": "https://epthinktank.eu/category/publications/briefings/feed/",
        "in_depth_analysis": "https://epthinktank.eu/category/publications/in-depth-analysis/feed/",
        "studies": "https://epthinktank.eu/category/publications/studies/feed/",

        # Paginated general feed (WordPress supports ?paged=N)
        "page_2": "https://epthinktank.eu/feed/?paged=2",
        "page_3": "https://epthinktank.eu/feed/?paged=3",
        "page_4": "https://epthinktank.eu/feed/?paged=4",
        "page_5": "https://epthinktank.eu/feed/?paged=5",
        "page_6": "https://epthinktank.eu/feed/?paged=6",
        "page_7": "https://epthinktank.eu/feed/?paged=7",
        "page_8": "https://epthinktank.eu/feed/?paged=8",
        "page_9": "https://epthinktank.eu/feed/?paged=9",
        "page_10": "https://epthinktank.eu/feed/?paged=10",

        # Publications category (broader than type-specific)
        "publications": "https://epthinktank.eu/category/publications/feed/",
    }

    # Category tag values used to classify publications from the general feed
    TYPE_CATEGORIES = {
        "at_a_glance": ["At a glance", "At a glance EPRS"],
        "briefings": ["Briefing", "Briefings", "Briefing EPRS"],
        "in_depth_analysis": ["In-Depth Analysis", "In depth analysis"],
        "studies": ["Study", "Studies"],
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
        Get latest Think Tank publications.

        Uses paginated general feed and filters by category tags.
        Category-specific feeds may be empty, so we always use the
        general feed with post-fetch filtering.

        Args:
            days: Get publications from last N days
            publication_type: Filter by type (briefings, studies, etc.)

        Returns:
            List of publications
        """
        since = datetime.now() - timedelta(days=days)

        logger.info(f"Fetching latest Think Tank publications ({publication_type or 'all'}, last {days} days)")

        # Fetch paginated general feed to get enough items
        # Each page has ~10 items, so fetch enough pages for the requested time window
        max_pages = min(days // 3 + 1, 10)  # Rough: ~3 days per page of 10 items
        feeds = []

        # Page 1
        try:
            feed = await self.rss_client.fetch_feed(self.RSS_FEEDS["all_publications"], since=since)
            feeds.append(feed)
        except Exception as e:
            logger.error(f"Failed to fetch general feed: {str(e)}")

        # Additional pages if needed
        for page_num in range(2, max_pages + 1):
            page_key = f"page_{page_num}"
            if page_key not in self.RSS_FEEDS:
                break
            try:
                feed = await self.rss_client.fetch_feed(self.RSS_FEEDS[page_key], since=since)
                if not feed.entries:
                    break  # No more items
                feeds.append(feed)
            except Exception as e:
                logger.debug(f"Page {page_num} fetch failed (expected at end): {str(e)}")
                break

        publications = []
        seen_links = set()

        for feed in feeds:
            for entry in feed.entries:
                # Deduplicate
                if entry.link in seen_links:
                    continue
                seen_links.add(entry.link)

                pub = {
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published.isoformat(),
                    "summary": entry.summary,
                    "content": entry.content,
                    "categories": entry.categories,
                    "author": getattr(entry, 'author', None),
                }
                publications.append(pub)

        # Filter by publication type using category tags
        if publication_type and publication_type in self.TYPE_CATEGORIES:
            type_tags = [t.lower() for t in self.TYPE_CATEGORIES[publication_type]]
            publications = [
                p for p in publications
                if any(
                    cat.lower() in type_tags
                    for cat in p.get("categories", [])
                )
            ]

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
        Get research for specific policy area.

        Fetches general feed and filters by policy area keyword in categories.

        Args:
            policy_area: Policy area name (e.g., "environment", "digital")
            days: Get research from last N days

        Returns:
            List of research publications
        """
        logger.info(f"Fetching Think Tank research for {policy_area}")

        all_pubs = await self.get_latest_publications(days=days)

        # Filter by policy area keyword in categories
        policy_lower = policy_area.lower()
        research = [
            {**p, "policy_area": policy_area}
            for p in all_pubs
            if any(policy_lower in cat.lower() for cat in p.get("categories", []))
        ]

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
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Search publications by keyword in title or summary.

        Args:
            keyword: Search keyword
            days: Search within last N days (max ~90 days via RSS pagination)

        Returns:
            Matching publications
        """
        logger.info(f"Searching Think Tank publications for keyword: {keyword}")

        all_pubs = await self.get_latest_publications(days=days)

        keyword_lower = keyword.lower()
        results = [
            p for p in all_pubs
            if keyword_lower in p.get("title", "").lower()
            or keyword_lower in p.get("summary", "").lower()
        ]

        logger.info(f"Found {len(results)} publications matching '{keyword}'")
        return results

    async def get_aggregated_research(
        self,
        policy_areas: List[str],
        days: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get research from multiple policy areas.

        Args:
            policy_areas: List of policy area names
            days: Get research from last N days

        Returns:
            Dictionary with research grouped by policy area
        """
        logger.info(f"Fetching aggregated research for {len(policy_areas)} policy areas")

        all_pubs = await self.get_latest_publications(days=days)

        results = {}
        for area in policy_areas:
            area_lower = area.lower()
            area_pubs = [
                {**p, "policy_area": area}
                for p in all_pubs
                if any(area_lower in cat.lower() for cat in p.get("categories", []))
            ]
            results[area] = area_pubs

        return results

    async def close(self):
        """Close RSS client"""
        await self.rss_client.close()
        logger.info("Closed Think Tank RSS client")
