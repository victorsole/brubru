"""
Base API Client for EU Institutional APIs

Abstract base class providing common functionality for all API clients:
- HTTP methods (GET, POST, PUT, DELETE)
- Authentication handling (EU Login, API keys, Bearer tokens)
- Rate limiting per API
- Response parsing (JSON, XML, RDF, Turtle)
- Error handling with retry logic
- Logging and monitoring
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union
from enum import Enum
import httpx
import time
from functools import wraps

logger = logging.getLogger(__name__)


class ResponseFormat(Enum):
    """Supported response formats"""
    JSON = "application/json"
    XML = "application/xml"
    RDF_XML = "application/rdf+xml"
    TURTLE = "text/turtle"
    JSON_LD = "application/ld+json"
    CSV = "text/csv"
    HTML = "text/html"


class AuthType(Enum):
    """Supported authentication types"""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer"
    BASIC_AUTH = "basic"
    EU_LOGIN = "eu_login"


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 2.0):
    """
    Decorator for retrying failed API calls with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (2.0 means 1s, 2s, 4s, ...)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    wait_time = backoff_factor ** retries
                    logger.warning(
                        f"Retry {retries}/{max_retries} for {func.__name__} "
                        f"after {wait_time}s due to: {str(e)}"
                    )
                    time.sleep(wait_time)
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code

                    # Retry on 429 (Too Many Requests) with special handling
                    if status_code == 429:
                        retries += 1
                        if retries >= max_retries:
                            raise
                        # Check for Retry-After header
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait_time = float(retry_after)
                            except ValueError:
                                wait_time = 60.0  # Default 60s for rate limits
                        else:
                            wait_time = max(60.0, backoff_factor ** retries * 10)  # Longer wait for rate limits
                        logger.warning(
                            f"Rate limited (429). Retry {retries}/{max_retries} for {func.__name__} "
                            f"after {wait_time}s"
                        )
                        time.sleep(wait_time)
                    # Retry on server errors (5xx)
                    elif status_code >= 500:
                        retries += 1
                        if retries >= max_retries:
                            raise
                        wait_time = backoff_factor ** retries
                        logger.warning(
                            f"Retry {retries}/{max_retries} for {func.__name__} "
                            f"after {wait_time}s due to HTTP {status_code}"
                        )
                        time.sleep(wait_time)
                    else:
                        raise
            return None
        return wrapper
    return decorator


class BaseAPIClient(ABC):
    """
    Abstract base class for all EU institutional API clients

    Provides common HTTP methods, authentication, rate limiting,
    and error handling functionality.
    """

    def __init__(
        self,
        base_url: str,
        auth_type: AuthType = AuthType.NONE,
        api_key: Optional[str] = None,
        rate_limit_calls: Optional[int] = None,
        rate_limit_period: int = 60,
        timeout: int = 30,
    ):
        """
        Initialize base API client

        Args:
            base_url: Base URL for the API
            auth_type: Type of authentication required
            api_key: API key if auth_type is API_KEY
            rate_limit_calls: Maximum calls per rate_limit_period (None = no limit)
            rate_limit_period: Time period in seconds for rate limiting
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.auth_type = auth_type
        self.api_key = api_key
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        self.timeout = timeout

        # Rate limiting state
        self._call_timestamps: list[float] = []

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )

        logger.info(f"Initialized {self.__class__.__name__} for {base_url}")

    def _check_rate_limit(self):
        """Check if we're within rate limits, wait if necessary"""
        if not self.rate_limit_calls:
            return

        current_time = time.time()
        # Remove timestamps older than rate_limit_period
        self._call_timestamps = [
            ts for ts in self._call_timestamps
            if current_time - ts < self.rate_limit_period
        ]

        # If we've hit the limit, wait until the oldest call expires
        if len(self._call_timestamps) >= self.rate_limit_calls:
            oldest_call = self._call_timestamps[0]
            wait_time = self.rate_limit_period - (current_time - oldest_call)
            if wait_time > 0:
                logger.info(
                    f"Rate limit reached ({self.rate_limit_calls} calls/{self.rate_limit_period}s). "
                    f"Waiting {wait_time:.2f}s"
                )
                time.sleep(wait_time)

        # Record this call
        self._call_timestamps.append(current_time)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on auth_type"""
        headers = {}

        if self.auth_type == AuthType.API_KEY and self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.auth_type == AuthType.BEARER_TOKEN and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _get_accept_header(self, format: ResponseFormat) -> str:
        """Get Accept header for desired response format"""
        return format.value

    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> httpx.Response:
        """
        Perform GET request

        Args:
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            headers: Additional headers
            response_format: Expected response format

        Returns:
            HTTP response object
        """
        self._check_rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Merge headers
        request_headers = {
            **self._get_auth_headers(),
            "Accept": self._get_accept_header(response_format),
            "User-Agent": "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)",
            **(headers or {})
        }

        logger.debug(f"GET {url} with params={params}")

        response = await self.client.get(url, params=params, headers=request_headers)
        response.raise_for_status()

        return response

    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> httpx.Response:
        """
        Perform POST request

        Args:
            endpoint: API endpoint (relative to base_url)
            data: Form data
            json: JSON body
            headers: Additional headers
            response_format: Expected response format

        Returns:
            HTTP response object
        """
        self._check_rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Merge headers
        request_headers = {
            **self._get_auth_headers(),
            "Accept": self._get_accept_header(response_format),
            "User-Agent": "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)",
            **(headers or {})
        }

        if json:
            request_headers["Content-Type"] = "application/json"

        logger.debug(f"POST {url}")

        response = await self.client.post(
            url,
            data=data,
            json=json,
            headers=request_headers
        )
        response.raise_for_status()

        return response

    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> httpx.Response:
        """Perform PUT request"""
        self._check_rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        request_headers = {
            **self._get_auth_headers(),
            "Accept": self._get_accept_header(response_format),
            "User-Agent": "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)",
            **(headers or {})
        }

        if json:
            request_headers["Content-Type"] = "application/json"

        logger.debug(f"PUT {url}")

        response = await self.client.put(
            url,
            data=data,
            json=json,
            headers=request_headers
        )
        response.raise_for_status()

        return response

    @retry_on_failure(max_retries=3, backoff_factor=2.0)
    async def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Perform DELETE request"""
        self._check_rate_limit()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        request_headers = {
            **self._get_auth_headers(),
            "User-Agent": "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)",
            **(headers or {})
        }

        logger.debug(f"DELETE {url}")

        response = await self.client.delete(url, headers=request_headers)
        response.raise_for_status()

        return response

    async def close(self):
        """Close the HTTP client connection pool"""
        await self.client.aclose()
        logger.info(f"Closed {self.__class__.__name__} HTTP client")

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the API is accessible and responding

        Returns:
            True if API is healthy, False otherwise
        """
        pass
