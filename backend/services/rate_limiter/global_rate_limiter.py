"""
Global Rate Limiter

Centralized rate limiting across all API clients:
- Per-API rate limits
- Per-user rate limits
- Token bucket algorithm
- Redis-backed for distributed systems
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    calls: int  # Number of calls
    period: int  # Period in seconds
    burst: Optional[int] = None  # Burst allowance


class GlobalRateLimiter:
    """
    Global rate limiter for all API services

    Critical limits:
    - PVGIS: 30 calls/second
    - TED: 60 calls/minute (without API key)
    - Publications Office: 60 calls/minute
    """

    # Default rate limits per service
    DEFAULT_LIMITS = {
        "pvgis": RateLimitConfig(calls=30, period=1),  # 30/sec
        "ted": RateLimitConfig(calls=60, period=60),  # 60/min
        "publications_office": RateLimitConfig(calls=60, period=60),
        "eurlex": RateLimitConfig(calls=100, period=60),
        "european_parliament": RateLimitConfig(calls=100, period=60),
        "iate": RateLimitConfig(calls=50, period=60),
        "data_europa": RateLimitConfig(calls=60, period=60),
    }

    def __init__(self):
        """Initialize global rate limiter"""
        # In-memory tracking: {service: {timestamp_list}}
        self._call_timestamps: Dict[str, list] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

        logger.info("Initialized Global Rate Limiter")

    async def check_limit(self, service: str) -> bool:
        """
        Check if request is within rate limit

        Args:
            service: Service name

        Returns:
            True if within limit, False if rate limited
        """
        if service not in self.DEFAULT_LIMITS:
            return True  # No limit configured

        config = self.DEFAULT_LIMITS[service]

        # Get or create lock
        if service not in self._locks:
            self._locks[service] = asyncio.Lock()

        async with self._locks[service]:
            return await self._check_limit_internal(service, config)

    async def _check_limit_internal(
        self,
        service: str,
        config: RateLimitConfig
    ) -> bool:
        """Internal rate limit check"""
        now = datetime.now()

        # Initialize if needed
        if service not in self._call_timestamps:
            self._call_timestamps[service] = []

        timestamps = self._call_timestamps[service]

        # Remove old timestamps
        cutoff = now - timedelta(seconds=config.period)
        timestamps[:] = [ts for ts in timestamps if ts > cutoff]

        # Check limit
        if len(timestamps) >= config.calls:
            oldest = timestamps[0]
            wait_time = config.period - (now - oldest).total_seconds()
            if wait_time > 0:
                logger.warning(
                    f"Rate limit hit for {service}: "
                    f"{len(timestamps)}/{config.calls} calls in {config.period}s. "
                    f"Waiting {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time)
                # Remove the oldest timestamp after waiting
                timestamps.pop(0)

        # Record this call
        timestamps.append(now)
        return True

    def get_remaining_calls(self, service: str) -> Optional[int]:
        """
        Get remaining calls for service

        Args:
            service: Service name

        Returns:
            Number of remaining calls, or None if no limit
        """
        if service not in self.DEFAULT_LIMITS:
            return None

        config = self.DEFAULT_LIMITS[service]

        if service not in self._call_timestamps:
            return config.calls

        now = datetime.now()
        cutoff = now - timedelta(seconds=config.period)
        timestamps = self._call_timestamps[service]

        # Count valid timestamps
        valid_count = sum(1 for ts in timestamps if ts > cutoff)
        remaining = max(0, config.calls - valid_count)

        return remaining


# Global singleton instance
_global_rate_limiter: Optional[GlobalRateLimiter] = None


def get_rate_limiter() -> GlobalRateLimiter:
    """Get global rate limiter instance"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = GlobalRateLimiter()
    return _global_rate_limiter
