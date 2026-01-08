"""
European Commission Newsletter Scraper

Scrapes newsletter content from EC Corporate Newsroom archives.
Supports RSS feeds where available, web scraping as primary method.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScraperError

logger = logging.getLogger(__name__)


class ECNewsletterScraper(BaseScraper):
    """
    Scraper for European Commission Newsletter archives.

    Handles:
    - Archive page scraping from ec.europa.eu/newsroom/[DG]/newsletter-archives
    - Individual newsletter issue extraction
    - Content parsing and metadata extraction
    - Deduplication via content fingerprinting

    Respects:
    - robots.txt directives
    - Rate limiting (2 second delay by default)
    - Polite scraping practices
    """

    NEWSROOM_BASE = "https://ec.europa.eu/newsroom"

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://ec.europa.eu",
            name="EC Newsletter Scraper",
            rate_limit_delay=2.0,  # Polite 2-second delay
            cache_ttl=3600,  # Cache for 1 hour
            **kwargs
        )
        logger.info("EC Newsletter Scraper initialized")

    async def scrape_newsletter_archive(
        self,
        dg_code: str,
        service_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape newsletter archive page for a specific DG.

        Args:
            dg_code: DG code (e.g., 'clima', 'comp', 'sante')
            service_id: Newsletter service ID (e.g., '1843', '2012')
            limit: Maximum number of newsletters to retrieve (None = all)

        Returns:
            List of newsletter items with metadata

        Raises:
            ScraperError: If archive page cannot be accessed or parsed
        """
        archive_url = f"{self.NEWSROOM_BASE}/{dg_code}/newsletter-archives/view/service/{service_id}"

        logger.info(f"Scraping newsletter archive: {archive_url}")

        try:
            html = await self._fetch(archive_url)
            soup = BeautifulSoup(html, 'html.parser')

            newsletters = self._parse_archive_page(soup, dg_code, service_id)

            if limit:
                newsletters = newsletters[:limit]

            logger.info(f"Found {len(newsletters)} newsletters in archive")
            return newsletters

        except Exception as e:
            logger.error(f"Failed to scrape archive {archive_url}: {str(e)}")
            raise ScraperError(f"Archive scraping failed: {str(e)}")

    def _parse_archive_page(
        self,
        soup: BeautifulSoup,
        dg_code: str,
        service_id: str
    ) -> List[Dict[str, Any]]:
        """
        Parse newsletter archive page HTML.

        EC Newsroom uses various HTML structures. This method attempts multiple
        parsing strategies to handle different template versions.

        Args:
            soup: BeautifulSoup parsed HTML
            dg_code: DG code for URL construction
            service_id: Service ID for URL construction

        Returns:
            List of parsed newsletter items
        """
        newsletters = []

        # Strategy 1: Look for newsletter item containers with common class patterns
        item_selectors = [
            'div.ecl-row.ecl-u-mb-l',  # Common ECL (Europa Component Library) pattern
            'div.item',
            'div.newsletter-item',
            'article',
            'div[class*="newsletter"]',
            'div.view-content > div',
        ]

        items = []
        for selector in item_selectors:
            items = soup.select(selector)
            if items:
                logger.debug(f"Found {len(items)} items using selector: {selector}")
                break

        if not items:
            logger.warning("No newsletter items found with standard selectors, trying fallback")
            # Fallback: find all links that look like newsletter URLs
            items = self._fallback_parse(soup)

        for item in items:
            try:
                newsletter = self._parse_newsletter_item(item, dg_code, service_id)
                if newsletter:
                    newsletters.append(newsletter)
            except Exception as e:
                logger.debug(f"Failed to parse newsletter item: {str(e)}")
                continue

        return newsletters

    def _parse_newsletter_item(
        self,
        item: BeautifulSoup,
        dg_code: str,
        service_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse individual newsletter item from HTML element.

        Args:
            item: BeautifulSoup element containing newsletter info
            dg_code: DG code
            service_id: Service ID

        Returns:
            Dictionary with newsletter metadata or None if parsing fails
        """
        # Extract title
        title = None
        title_selectors = ['h3', 'h2', 'h4', 'a.ecl-link', 'div.title', 'span.title']
        for selector in title_selectors:
            title_elem = item.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break

        if not title:
            return None

        # Extract link
        link = None
        link_elem = item.find('a')
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            # Make absolute URL
            if href.startswith('http'):
                link = href
            elif href.startswith('/'):
                link = urljoin(self.base_url, href)
            else:
                link = f"{self.NEWSROOM_BASE}/{dg_code}/{href}"

        # Extract date
        publication_date = None
        date_selectors = [
            'span.ecl-u-type-s',
            'span.date',
            'time',
            'div.date',
            'span[class*="date"]'
        ]
        for selector in date_selectors:
            date_elem = item.select_one(selector)
            if date_elem:
                date_str = date_elem.get_text(strip=True)
                publication_date = self._parse_date(date_str)
                if publication_date:
                    break

        # Extract summary/description
        summary = None
        summary_selectors = ['p', 'div.ecl-u-type-paragraph-m', 'div.description']
        for selector in summary_selectors:
            summary_elem = item.select_one(selector)
            if summary_elem:
                summary = summary_elem.get_text(strip=True)
                if len(summary) > 50:  # Only use if substantial
                    break

        # Generate content fingerprint for deduplication
        fingerprint_text = f"{title}:{summary or ''}"
        content_fingerprint = hashlib.sha256(fingerprint_text.encode()).hexdigest()

        newsletter_data = {
            'title': title,
            'link': link,
            'publication_date': publication_date,
            'summary': summary,
            'content_fingerprint': content_fingerprint,
            'dg_code': dg_code,
            'service_id': service_id,
        }

        return newsletter_data

    def _fallback_parse(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """
        Fallback parsing strategy: find all elements with newsletter-like links.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of elements that might contain newsletter items
        """
        items = []

        # Find all links that point to newsletter item pages
        links = soup.find_all('a', href=re.compile(r'/newsroom/[^/]+/items?/'))

        for link in links:
            # Get the parent container (usually a div or article)
            parent = link.find_parent(['div', 'article', 'section'])
            if parent and parent not in items:
                items.append(parent)

        logger.debug(f"Fallback parser found {len(items)} potential newsletter items")
        return items

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.

        EC uses various date formats:
        - "15 January 2025"
        - "15/01/2025"
        - "2025-01-15"
        - "15.01.2025"

        Args:
            date_str: Date string to parse

        Returns:
            datetime object or None if parsing fails
        """
        date_str = date_str.strip()

        # Date format patterns to try
        formats = [
            "%d %B %Y",      # "15 January 2025"
            "%d/%m/%Y",      # "15/01/2025"
            "%Y-%m-%d",      # "2025-01-15"
            "%d.%m.%Y",      # "15.01.2025"
            "%d-%m-%Y",      # "15-01-2025"
            "%B %d, %Y",     # "January 15, 2025"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

    async def scrape_newsletter_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape full content from individual newsletter detail page.

        Args:
            url: URL of newsletter detail page

        Returns:
            Dictionary with full newsletter content
        """
        try:
            html = await self._fetch(url)
            soup = BeautifulSoup(html, 'html.parser')

            # Extract main content
            content_selectors = [
                'div.ecl-row',
                'article',
                'div.content',
                'main',
                'div[class*="body"]'
            ]

            full_content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Remove scripts, styles, navigation
                    for tag in content_elem(['script', 'style', 'nav', 'header', 'footer']):
                        tag.decompose()

                    full_content = content_elem.get_text(separator='\n', strip=True)
                    if len(full_content) > 200:  # Ensure substantial content
                        break

            return {
                'url': url,
                'full_content': full_content,
                'scraped_at': datetime.now()
            }

        except Exception as e:
            logger.error(f"Failed to scrape newsletter detail {url}: {str(e)}")
            return None

    async def scrape_rss_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """
        Scrape RSS feed for newsletters that provide RSS.

        Args:
            feed_url: URL of RSS feed

        Returns:
            List of newsletter items from RSS
        """
        try:
            import feedparser

            # Fetch feed with rate limiting
            await self._rate_limit()
            feed = feedparser.parse(feed_url)

            newsletters = []
            for entry in feed.entries:
                newsletter = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'publication_date': self._parse_rss_date(entry),
                    'content_fingerprint': hashlib.sha256(
                        f"{entry.get('title', '')}:{entry.get('summary', '')}".encode()
                    ).hexdigest(),
                }
                newsletters.append(newsletter)

            logger.info(f"Scraped {len(newsletters)} items from RSS feed")
            return newsletters

        except Exception as e:
            logger.error(f"Failed to scrape RSS feed {feed_url}: {str(e)}")
            raise ScraperError(f"RSS feed scraping failed: {str(e)}")

    def _parse_rss_date(self, entry: Any) -> Optional[datetime]:
        """Parse date from RSS entry"""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            from time import struct_time
            return datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6])
        return None

    # Abstract methods implementation (required by BaseScraper)
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search newsletters by query.
        Not implemented for newsletters - use scrape_newsletter_archive instead.
        """
        raise NotImplementedError("Use scrape_newsletter_archive() for newsletter retrieval")

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get specific newsletter by URL.
        Not implemented for newsletters - use scrape_newsletter_detail instead.
        """
        raise NotImplementedError("Use scrape_newsletter_detail() for individual newsletters")

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest newsletter updates.
        Not implemented - use scrape_newsletter_archive with limit parameter.
        """
        raise NotImplementedError("Use scrape_newsletter_archive() with limit parameter")
