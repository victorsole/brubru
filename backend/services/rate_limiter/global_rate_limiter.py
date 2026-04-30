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

    # Per-API-key limit for the Data Provider API (/api/v1/*). Soft sliding
    # window. Shared across all endpoints a single key hits.
    API_KEY_LIMIT = RateLimitConfig(calls=60, period=60)

    # Tier-based ceilings. The tier is read from ApiKey.api_tier (column added in
    # migration 045). Unknown / missing tier falls back to "free" (60/min).
    TIER_LIMITS = {
        "free": RateLimitConfig(calls=60, period=60),
        "pro": RateLimitConfig(calls=300, period=60),
        "enterprise": RateLimitConfig(calls=6000, period=60),
    }

    @classmethod
    def get_limit_for_tier(cls, tier: str | None) -> "RateLimitConfig":
        return cls.TIER_LIMITS.get((tier or "free").lower(), cls.TIER_LIMITS["free"])

    def __init__(self):
        """Initialize global rate limiter"""
        # In-memory tracking: {service: {timestamp_list}}
        self._call_timestamps: Dict[str, list] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        # Per-API-key sliding windows (separate map so key IDs don't collide with service names)
        self._api_key_timestamps: Dict[str, list] = {}
        self._api_key_locks: Dict[str, asyncio.Lock] = {}

        logger.info("Initialized Global Rate Limiter")

    async def check_api_key_limit(self, api_key_id: str, tier: str | None = None) -> tuple[bool, int]:
        """
        Sliding-window soft rate limit for a single API key.

        The ceiling is the tier-specific limit (see TIER_LIMITS). Unknown / missing
        tier falls back to "free" (60/min).

        Returns:
            (allowed, retry_after_seconds). retry_after is 0 when allowed.
        """
        if api_key_id not in self._api_key_locks:
            self._api_key_locks[api_key_id] = asyncio.Lock()

        async with self._api_key_locks[api_key_id]:
            cfg = self.get_limit_for_tier(tier)
            now = datetime.now()
            cutoff = now - timedelta(seconds=cfg.period)
            stamps = [t for t in self._api_key_timestamps.get(api_key_id, []) if t > cutoff]
            if len(stamps) >= cfg.calls:
                retry_after = int(cfg.period - (now - stamps[0]).total_seconds()) + 1
                self._api_key_timestamps[api_key_id] = stamps
                return False, max(1, retry_after)
            stamps.append(now)
            self._api_key_timestamps[api_key_id] = stamps
            return True, 0

    def get_remaining_api_key_calls(self, api_key_id: str, tier: str | None = None) -> int:
        """Calls remaining in the current 60s window for an API key (tier-aware)."""
        cfg = self.get_limit_for_tier(tier)
        now = datetime.now()
        cutoff = now - timedelta(seconds=cfg.period)
        stamps = [t for t in self._api_key_timestamps.get(api_key_id, []) if t > cutoff]
        return max(0, cfg.calls - len(stamps))

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
