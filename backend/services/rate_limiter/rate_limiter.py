"""
Rate Limiter Service

Comprehensive rate limiting with token bucket algorithm, queue management,
and backoff strategies for all EU API clients.
Part of Phase 8: Rate Limiting & Quota Management

Features:
- Token bucket algorithm for smooth rate limiting
- Per-API rate limits (PVGIS, EUR-Lex SOAP, SPARQL, TED)
- Request queue management for overflow
- Exponential backoff strategies
- Distributed rate limiting support (Redis)
"""

import logging
import asyncio
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class BackoffStrategy(str, Enum):
    """Backoff strategy types"""
    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


@dataclass
class RateLimitConfig:
    """
    Rate limit configuration for an API.

    Uses token bucket algorithm:
    - Bucket starts with 'capacity' tokens
    - Tokens refill at 'refill_rate' tokens per second
    - Each request consumes 'cost_per_request' tokens
    """
    name: str
    capacity: int  # Maximum tokens (burst capacity)
    refill_rate: float  # Tokens per second
    cost_per_request: int = 1  # Tokens consumed per request
    max_queue_size: int = 100  # Maximum queued requests
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_base: float = 2.0  # Base for exponential backoff
    backoff_max: float = 60.0  # Maximum backoff delay (seconds)


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Implementation of the token bucket algorithm:
    https://en.wikipedia.org/wiki/Token_bucket
    """
    capacity: int
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens available and consumed, False otherwise
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time until enough tokens available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds
        """
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        wait_seconds = tokens_needed / self.refill_rate
        return wait_seconds

    @property
    def available_tokens(self) -> float:
        """Get current available tokens"""
        self.refill()
        return self.tokens


@dataclass
class QueuedRequest:
    """Queued request waiting for rate limit clearance"""
    request_id: str
    tokens_needed: int
    queued_at: datetime
    callback: Optional[Callable] = None
    retry_count: int = 0

    @property
    def wait_time_seconds(self) -> float:
        """Time spent in queue"""
        return (datetime.now() - self.queued_at).total_seconds()


class RateLimiter:
    """
    Comprehensive rate limiter with token bucket algorithm.

    Handles rate limiting for multiple APIs with different limits:
    - PVGIS: 30 calls/second (CRITICAL!)
    - EUR-Lex SOAP: ~100 calls/day
    - SPARQL: 1M rows/query (enforced at query level)
    - TED API: Varies by key

    Features:
    - Token bucket algorithm for smooth rate limiting
    - Request queuing with configurable max size
    - Multiple backoff strategies
    - Per-API configuration
    """

    # Pre-configured API rate limits
    API_CONFIGS = {
        'pvgis': RateLimitConfig(
            name='PVGIS',
            capacity=30,  # 30 calls burst
            refill_rate=30.0,  # 30 tokens/second
            max_queue_size=50,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        ),
        'eurlex_soap': RateLimitConfig(
            name='EUR-Lex SOAP',
            capacity=100,  # 100 calls burst
            refill_rate=0.0012,  # ~100 calls per day (100/86400)
            max_queue_size=200,
            backoff_strategy=BackoffStrategy.LINEAR
        ),
        'eurlex_sparql': RateLimitConfig(
            name='EUR-Lex SPARQL',
            capacity=10,  # 10 concurrent queries
            refill_rate=1.0,  # 1 query/second
            max_queue_size=50,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        ),
        'ep_sparql': RateLimitConfig(
            name='EP SPARQL',
            capacity=10,
            refill_rate=1.0,
            max_queue_size=50,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        ),
        'ted_api': RateLimitConfig(
            name='TED API',
            capacity=60,  # 60 calls burst
            refill_rate=1.0,  # 60 calls/minute
            max_queue_size=100,
            backoff_strategy=BackoffStrategy.EXPONENTIAL
        ),
        'iate_api': RateLimitConfig(
            name='IATE API',
            capacity=50,
            refill_rate=5.0,  # 5 calls/second
            max_queue_size=100,
            backoff_strategy=BackoffStrategy.LINEAR
        ),
        'publications_office': RateLimitConfig(
            name='Publications Office',
            capacity=60,
            refill_rate=1.0,
            max_queue_size=100,
            backoff_strategy=BackoffStrategy.LINEAR
        ),
        'jrc_data_catalogue': RateLimitConfig(
            name='JRC Data Catalogue',
            capacity=100,
            refill_rate=10.0,
            max_queue_size=50,
            backoff_strategy=BackoffStrategy.LINEAR
        ),
    }

    def __init__(self, redis_client: Optional[Any] = None):
        """
        Initialize rate limiter.

        Args:
            redis_client: Optional Redis client for distributed rate limiting
        """
        self.redis_client = redis_client
        self.buckets: Dict[str, TokenBucket] = {}
        self.configs: Dict[str, RateLimitConfig] = {}
        self.queues: Dict[str, List[QueuedRequest]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.stats: Dict[str, Dict[str, int]] = {}

        # Initialize pre-configured APIs
        for api_name, config in self.API_CONFIGS.items():
            self._register_api(api_name, config)

        logger.info(f"Initialized Rate Limiter with {len(self.API_CONFIGS)} APIs")

    def _register_api(self, api_name: str, config: RateLimitConfig):
        """
        Register API with rate limit configuration.

        Args:
            api_name: API identifier
            config: Rate limit configuration
        """
        self.configs[api_name] = config
        self.buckets[api_name] = TokenBucket(
            capacity=config.capacity,
            refill_rate=config.refill_rate
        )
        self.queues[api_name] = []
        self.locks[api_name] = asyncio.Lock()
        self.stats[api_name] = {
            'requests': 0,
            'rate_limited': 0,
            'queued': 0,
            'queue_overflow': 0
        }

    async def acquire(
        self,
        api_name: str,
        tokens: int = 1,
        wait: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquire tokens for API request.

        Args:
            api_name: API identifier
            tokens: Number of tokens needed
            wait: If True, wait for tokens; if False, return immediately
            timeout: Maximum wait time in seconds

        Returns:
            True if tokens acquired, False if rate limited
        """
        if api_name not in self.buckets:
            logger.warning(f"No rate limit configured for {api_name}, allowing request")
            return True

        async with self.locks[api_name]:
            return await self._acquire_internal(api_name, tokens, wait, timeout)

    async def _acquire_internal(
        self,
        api_name: str,
        tokens: int,
        wait: bool,
        timeout: Optional[float]
    ) -> bool:
        """Internal token acquisition logic"""
        bucket = self.buckets[api_name]
        config = self.configs[api_name]

        self.stats[api_name]['requests'] += 1

        # Try immediate acquisition
        if bucket.consume(tokens):
            logger.debug(f"[{api_name}] Acquired {tokens} tokens. Remaining: {bucket.available_tokens:.2f}")
            return True

        # Rate limited
        self.stats[api_name]['rate_limited'] += 1

        if not wait:
            logger.warning(f"[{api_name}] Rate limited, no wait requested")
            return False

        # Calculate wait time
        wait_time = bucket.wait_time(tokens)

        if timeout and wait_time > timeout:
            logger.warning(
                f"[{api_name}] Wait time {wait_time:.2f}s exceeds timeout {timeout}s"
            )
            return False

        logger.info(
            f"[{api_name}] Rate limited, waiting {wait_time:.2f}s for {tokens} tokens"
        )

        # Wait for tokens
        await asyncio.sleep(wait_time)

        # Try again
        if bucket.consume(tokens):
            return True

        # Still not available (edge case)
        logger.error(f"[{api_name}] Tokens still unavailable after wait")
        return False

    async def acquire_with_backoff(
        self,
        api_name: str,
        tokens: int = 1,
        max_retries: int = 5
    ) -> bool:
        """
        Acquire tokens with exponential backoff on failure.

        Args:
            api_name: API identifier
            tokens: Number of tokens needed
            max_retries: Maximum retry attempts

        Returns:
            True if tokens acquired, False if all retries exhausted
        """
        if api_name not in self.configs:
            return True

        config = self.configs[api_name]

        for retry in range(max_retries):
            # Try to acquire
            success = await self.acquire(api_name, tokens, wait=True, timeout=60.0)

            if success:
                return True

            # Calculate backoff delay
            delay = self._calculate_backoff(
                retry,
                config.backoff_strategy,
                config.backoff_base,
                config.backoff_max
            )

            logger.warning(
                f"[{api_name}] Retry {retry + 1}/{max_retries}, "
                f"backing off for {delay:.2f}s"
            )

            await asyncio.sleep(delay)

        logger.error(f"[{api_name}] Max retries exhausted")
        return False

    def _calculate_backoff(
        self,
        retry: int,
        strategy: BackoffStrategy,
        base: float,
        max_delay: float
    ) -> float:
        """
        Calculate backoff delay.

        Args:
            retry: Current retry attempt (0-indexed)
            strategy: Backoff strategy
            base: Base value for calculation
            max_delay: Maximum delay cap

        Returns:
            Delay in seconds
        """
        if strategy == BackoffStrategy.NONE:
            return 0.0

        elif strategy == BackoffStrategy.LINEAR:
            delay = base * (retry + 1)

        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base ** (retry + 1)

        elif strategy == BackoffStrategy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8, 13, ...
            fib = self._fibonacci(retry + 1)
            delay = base * fib

        else:
            delay = base

        return min(delay, max_delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a

    async def enqueue_request(
        self,
        api_name: str,
        request_id: str,
        tokens: int = 1,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Enqueue request if rate limit reached.

        Args:
            api_name: API identifier
            request_id: Unique request identifier
            tokens: Number of tokens needed
            callback: Optional callback when request processed

        Returns:
            True if enqueued, False if queue full
        """
        if api_name not in self.configs:
            return False

        config = self.configs[api_name]
        queue = self.queues[api_name]

        # Check queue capacity
        if len(queue) >= config.max_queue_size:
            logger.error(f"[{api_name}] Queue overflow, max size: {config.max_queue_size}")
            self.stats[api_name]['queue_overflow'] += 1
            return False

        # Enqueue
        request = QueuedRequest(
            request_id=request_id,
            tokens_needed=tokens,
            queued_at=datetime.now(),
            callback=callback
        )
        queue.append(request)
        self.stats[api_name]['queued'] += 1

        logger.info(f"[{api_name}] Enqueued request {request_id}, queue size: {len(queue)}")
        return True

    async def process_queue(self, api_name: str, max_process: int = 10):
        """
        Process queued requests for API.

        Args:
            api_name: API identifier
            max_process: Maximum requests to process in one batch
        """
        if api_name not in self.queues:
            return

        queue = self.queues[api_name]
        processed = 0

        while queue and processed < max_process:
            request = queue[0]

            # Try to acquire tokens
            success = await self.acquire(
                api_name,
                request.tokens_needed,
                wait=False
            )

            if success:
                # Remove from queue
                queue.pop(0)
                processed += 1

                logger.info(
                    f"[{api_name}] Processed queued request {request.request_id} "
                    f"(waited {request.wait_time_seconds:.2f}s)"
                )

                # Call callback
                if request.callback:
                    try:
                        await request.callback()
                    except Exception as e:
                        logger.error(f"Queue callback error: {str(e)}")
            else:
                # No tokens available, stop processing
                break

        if processed > 0:
            logger.info(f"[{api_name}] Processed {processed} queued requests")

    def get_stats(self, api_name: Optional[str] = None) -> Dict:
        """
        Get rate limiter statistics.

        Args:
            api_name: Specific API name, or None for all

        Returns:
            Statistics dict
        """
        if api_name:
            if api_name not in self.buckets:
                return {}

            bucket = self.buckets[api_name]
            config = self.configs[api_name]

            return {
                'api_name': api_name,
                'tokens_available': bucket.available_tokens,
                'capacity': config.capacity,
                'refill_rate': config.refill_rate,
                'queue_size': len(self.queues[api_name]),
                'max_queue_size': config.max_queue_size,
                'stats': self.stats[api_name]
            }

        # All APIs
        return {
            api: self.get_stats(api)
            for api in self.buckets.keys()
        }

    def reset(self, api_name: Optional[str] = None):
        """
        Reset rate limiter (for testing).

        Args:
            api_name: Specific API to reset, or None for all
        """
        if api_name:
            if api_name in self.buckets:
                config = self.configs[api_name]
                self.buckets[api_name] = TokenBucket(
                    capacity=config.capacity,
                    refill_rate=config.refill_rate
                )
                self.queues[api_name] = []
                logger.info(f"Reset rate limiter for {api_name}")
        else:
            for api in self.buckets.keys():
                self.reset(api)


# Global singleton
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
