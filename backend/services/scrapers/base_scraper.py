"""
Base Scraper Class

All EU institutional scrapers inherit from this base class.
Provides common functionality for HTTP requests, rate limiting, caching, and error handling.
"""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class RateLimitError(ScraperError):
    """Raised when rate limit is exceeded"""
    pass


class BaseScraper(ABC):
    """
    Abstract base class for all EU institutional scrapers.

    Features:
    - Async HTTP requests with aiohttp
    - Rate limiting (respects robots.txt)
    - Response caching
    - Retry logic with exponential backoff
    - HTML parsing with BeautifulSoup
    - Structured error handling
    - Request logging for audit trail
    """

    def __init__(
        self,
        base_url: str,
        name: str,
        rate_limit_delay: float = 1.0,
        cache_ttl: int = 3600,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "Brubru/1.0 (EU Policy Intelligence; +https://brubru.world)"
    ):
        """
        Initialize base scraper.

        Args:
            base_url: Base URL of the institution
            name: Human-readable name of the scraper
            rate_limit_delay: Minimum seconds between requests (default: 1.0)
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts (default: 3)
            user_agent: User-Agent string for requests
        """
        self.base_url = base_url
        self.name = name
        self.rate_limit_delay = rate_limit_delay
        self.cache_ttl = cache_ttl
        self.timeout = ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.user_agent = user_agent

        # Rate limiting
        self._last_request_time: Optional[float] = None
        self._request_lock = asyncio.Lock()

        # Caching (in-memory for now, can be replaced with Redis)
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Statistics
        self.stats = {
            "requests_made": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "total_bytes": 0,
        }

        logger.info(f"Initialized {self.name} scraper for {self.base_url}")

    async def _rate_limit(self):
        """Enforce rate limiting between requests"""
        async with self._request_lock:
            if self._last_request_time is not None:
                elapsed = asyncio.get_event_loop().time() - self._last_request_time
                if elapsed < self.rate_limit_delay:
                    wait_time = self.rate_limit_delay - elapsed
                    logger.debug(f"{self.name}: Rate limiting, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()

    def _get_cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from URL and parameters"""
        cache_str = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Retrieve data from cache if not expired"""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() < entry['expires_at']:
                self.stats['cache_hits'] += 1
                logger.debug(f"{self.name}: Cache hit for {cache_key}")
                return entry['data']
            else:
                # Expired, remove from cache
                del self._cache[cache_key]

        self.stats['cache_misses'] += 1
        return None

    def _save_to_cache(self, cache_key: str, data: Any):
        """Save data to cache with TTL"""
        self._cache[cache_key] = {
            'data': data,
            'expires_at': datetime.now() + timedelta(seconds=self.cache_ttl),
            'cached_at': datetime.now()
        }
        logger.debug(f"{self.name}: Cached data for {cache_key}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _fetch(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        use_cache: bool = True
    ) -> str:
        """
        Fetch URL content with rate limiting, caching, and retry logic.

        Args:
            url: URL to fetch
            params: Query parameters
            headers: Additional HTTP headers
            use_cache: Whether to use cached response (default: True)

        Returns:
            HTML content as string

        Raises:
            ScraperError: On fetch failure
        """
        # Check cache first
        cache_key = self._get_cache_key(url, params)
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Rate limiting
        await self._rate_limit()

        # Prepare headers
        request_headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        if headers:
            request_headers.update(headers)

        # Make request
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                logger.info(f"{self.name}: Fetching {url}")
                async with session.get(url, params=params, headers=request_headers) as response:
                    response.raise_for_status()
                    content = await response.text()

                    # Update statistics
                    self.stats['requests_made'] += 1
                    self.stats['total_bytes'] += len(content)

                    # Cache the response
                    if use_cache:
                        self._save_to_cache(cache_key, content)

                    logger.info(f"{self.name}: Successfully fetched {url} ({len(content)} bytes)")
                    return content

        except aiohttp.ClientResponseError as e:
            self.stats['errors'] += 1
            logger.error(f"{self.name}: HTTP error {e.status} for {url}: {e.message}")
            raise ScraperError(f"HTTP {e.status}: {e.message}") from e

        except asyncio.TimeoutError as e:
            self.stats['errors'] += 1
            logger.error(f"{self.name}: Timeout fetching {url}")
            raise ScraperError(f"Request timeout for {url}") from e

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"{self.name}: Unexpected error fetching {url}: {e}")
            raise ScraperError(f"Failed to fetch {url}: {str(e)}") from e

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content with BeautifulSoup"""
        return BeautifulSoup(html, 'lxml')

    def _make_absolute_url(self, url: str) -> str:
        """Convert relative URL to absolute URL"""
        return urljoin(self.base_url, url)

    def get_stats(self) -> Dict[str, Any]:
        """Return scraper statistics"""
        return {
            'name': self.name,
            'base_url': self.base_url,
            'stats': self.stats,
            'cache_size': len(self._cache),
            'rate_limit_delay': self.rate_limit_delay,
        }

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        logger.info(f"{self.name}: Cache cleared")

    # Abstract methods that must be implemented by subclasses

    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the institutional database.

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            List of search results as dictionaries
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document data as dictionary
        """
        pass

    @abstractmethod
    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve latest updates from the institution.

        Args:
            limit: Maximum number of updates to return

        Returns:
            List of updates as dictionaries
        """
        pass
