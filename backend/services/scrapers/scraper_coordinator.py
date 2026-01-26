"""
Scraper Coordinator

Centralized rate limiting and orchestration for all EU institutional scrapers.
Ensures that multiple scrapers hitting the same domain don't overwhelm servers.

Features:
- Per-domain rate limiting (global across all scrapers)
- Health monitoring and statistics
- Graceful degradation on errors
- Domain-specific configuration

Usage:
    from services.scrapers.scraper_coordinator import get_coordinator

    coordinator = get_coordinator()
    await coordinator.acquire("europarl.europa.eu")  # Wait for rate limit slot
    # ... make request ...
    coordinator.record_request("europarl.europa.eu", success=True)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ScraperHealth(str, Enum):
    """Scraper health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DomainConfig:
    """Configuration for a specific domain"""
    requests_per_minute: int = 30
    min_delay_seconds: float = 2.0
    max_concurrent: int = 2
    timeout_seconds: int = 30

    # Computed from requests_per_minute
    @property
    def delay_between_requests(self) -> float:
        """Minimum delay to stay within rate limit"""
        return max(self.min_delay_seconds, 60.0 / self.requests_per_minute)


@dataclass
class DomainStats:
    """Statistics for a specific domain"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes: int = 0
    last_request_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    avg_response_time_ms: float = 0.0

    # Rolling window for rate calculation
    recent_requests: List[datetime] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Success rate as percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def requests_last_minute(self) -> int:
        """Count requests in the last minute"""
        cutoff = datetime.now() - timedelta(minutes=1)
        self.recent_requests = [t for t in self.recent_requests if t > cutoff]
        return len(self.recent_requests)

    @property
    def health(self) -> ScraperHealth:
        """Determine health based on recent performance"""
        if self.total_requests == 0:
            return ScraperHealth.UNKNOWN
        if self.success_rate >= 95:
            return ScraperHealth.HEALTHY
        if self.success_rate >= 80:
            return ScraperHealth.DEGRADED
        return ScraperHealth.UNHEALTHY


class ScraperCoordinator:
    """
    Centralized coordinator for all scrapers.

    Provides:
    - Global rate limiting per domain
    - Cross-scraper coordination
    - Health monitoring
    - Statistics collection
    """

    # Default domain configurations
    DEFAULT_CONFIGS: Dict[str, DomainConfig] = {
        # European Parliament domains
        "europarl.europa.eu": DomainConfig(
            requests_per_minute=30,
            min_delay_seconds=2.0,
            max_concurrent=2
        ),
        "oeil.secure.europarl.europa.eu": DomainConfig(
            requests_per_minute=20,
            min_delay_seconds=3.0,
            max_concurrent=1
        ),
        "data.europarl.europa.eu": DomainConfig(
            requests_per_minute=60,
            min_delay_seconds=1.0,
            max_concurrent=3
        ),

        # EUR-Lex
        "eur-lex.europa.eu": DomainConfig(
            requests_per_minute=20,
            min_delay_seconds=3.0,
            max_concurrent=1
        ),

        # Council
        "consilium.europa.eu": DomainConfig(
            requests_per_minute=30,
            min_delay_seconds=2.0,
            max_concurrent=2
        ),

        # Commission domains
        "ec.europa.eu": DomainConfig(
            requests_per_minute=30,
            min_delay_seconds=2.0,
            max_concurrent=2
        ),
        "commission.europa.eu": DomainConfig(
            requests_per_minute=30,
            min_delay_seconds=2.0,
            max_concurrent=2
        ),

        # Data portal
        "data.europa.eu": DomainConfig(
            requests_per_minute=60,
            min_delay_seconds=1.0,
            max_concurrent=3
        ),

        # Publications Office
        "op.europa.eu": DomainConfig(
            requests_per_minute=30,
            min_delay_seconds=2.0,
            max_concurrent=2
        ),
    }

    # Default config for unknown domains
    DEFAULT_CONFIG = DomainConfig(
        requests_per_minute=20,
        min_delay_seconds=2.0,
        max_concurrent=1
    )

    def __init__(self):
        """Initialize the coordinator"""
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._domain_last_request: Dict[str, float] = {}
        self._domain_stats: Dict[str, DomainStats] = {}
        self._global_lock = asyncio.Lock()

        logger.info("ScraperCoordinator initialized")

    def _get_config(self, domain: str) -> DomainConfig:
        """Get configuration for a domain"""
        # Try exact match first
        if domain in self.DEFAULT_CONFIGS:
            return self.DEFAULT_CONFIGS[domain]

        # Try parent domain (e.g., oeil.secure.europarl.europa.eu -> europarl.europa.eu)
        parts = domain.split(".")
        for i in range(len(parts) - 2):
            parent = ".".join(parts[i+1:])
            if parent in self.DEFAULT_CONFIGS:
                return self.DEFAULT_CONFIGS[parent]

        return self.DEFAULT_CONFIG

    async def _get_lock(self, domain: str) -> asyncio.Lock:
        """Get or create a lock for a domain"""
        async with self._global_lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = asyncio.Lock()
            return self._domain_locks[domain]

    async def _get_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or create a semaphore for concurrent request limiting"""
        async with self._global_lock:
            if domain not in self._domain_semaphores:
                config = self._get_config(domain)
                self._domain_semaphores[domain] = asyncio.Semaphore(config.max_concurrent)
            return self._domain_semaphores[domain]

    def _get_stats(self, domain: str) -> DomainStats:
        """Get or create stats for a domain"""
        if domain not in self._domain_stats:
            self._domain_stats[domain] = DomainStats()
        return self._domain_stats[domain]

    async def acquire(self, domain: str) -> None:
        """
        Acquire a rate limit slot for a domain.

        Blocks until it's safe to make a request according to rate limits.

        Args:
            domain: The domain to make a request to (e.g., "europarl.europa.eu")
        """
        config = self._get_config(domain)
        lock = await self._get_lock(domain)
        semaphore = await self._get_semaphore(domain)

        # Wait for concurrent request slot
        await semaphore.acquire()

        # Enforce minimum delay between requests
        async with lock:
            now = asyncio.get_event_loop().time()
            last_request = self._domain_last_request.get(domain, 0)
            elapsed = now - last_request

            if elapsed < config.delay_between_requests:
                wait_time = config.delay_between_requests - elapsed
                logger.debug(f"ScraperCoordinator: {domain} - waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self._domain_last_request[domain] = asyncio.get_event_loop().time()

    def release(self, domain: str) -> None:
        """
        Release a rate limit slot for a domain.

        Call this after the request completes.

        Args:
            domain: The domain that was requested
        """
        if domain in self._domain_semaphores:
            self._domain_semaphores[domain].release()

    def record_request(
        self,
        domain: str,
        success: bool,
        response_time_ms: Optional[float] = None,
        bytes_received: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record statistics for a completed request.

        Args:
            domain: The domain that was requested
            success: Whether the request was successful
            response_time_ms: Response time in milliseconds
            bytes_received: Number of bytes received
            error_message: Error message if request failed
        """
        stats = self._get_stats(domain)
        stats.total_requests += 1
        stats.last_request_at = datetime.now()
        stats.recent_requests.append(datetime.now())

        if success:
            stats.successful_requests += 1
            stats.total_bytes += bytes_received
            if response_time_ms is not None:
                # Running average
                n = stats.successful_requests
                stats.avg_response_time_ms = (
                    (stats.avg_response_time_ms * (n - 1) + response_time_ms) / n
                )
        else:
            stats.failed_requests += 1
            stats.last_error_at = datetime.now()
            stats.last_error_message = error_message

    def get_domain_health(self, domain: str) -> Dict[str, Any]:
        """
        Get health status for a specific domain.

        Args:
            domain: The domain to check

        Returns:
            Dictionary with health information
        """
        stats = self._get_stats(domain)
        config = self._get_config(domain)

        return {
            "domain": domain,
            "health": stats.health.value,
            "total_requests": stats.total_requests,
            "success_rate": round(stats.success_rate, 1),
            "requests_last_minute": stats.requests_last_minute,
            "rate_limit": config.requests_per_minute,
            "avg_response_time_ms": round(stats.avg_response_time_ms, 1),
            "last_request_at": stats.last_request_at.isoformat() if stats.last_request_at else None,
            "last_error_at": stats.last_error_at.isoformat() if stats.last_error_at else None,
            "last_error_message": stats.last_error_message,
        }

    def get_all_health(self) -> Dict[str, Any]:
        """
        Get health status for all tracked domains.

        Returns:
            Dictionary with overall health and per-domain details
        """
        domains_health = {
            domain: self.get_domain_health(domain)
            for domain in self._domain_stats.keys()
        }

        # Calculate overall health
        if not domains_health:
            overall_health = ScraperHealth.UNKNOWN
        else:
            healths = [d["health"] for d in domains_health.values()]
            if all(h == ScraperHealth.HEALTHY.value for h in healths):
                overall_health = ScraperHealth.HEALTHY
            elif any(h == ScraperHealth.UNHEALTHY.value for h in healths):
                overall_health = ScraperHealth.UNHEALTHY
            else:
                overall_health = ScraperHealth.DEGRADED

        total_requests = sum(s.total_requests for s in self._domain_stats.values())
        total_errors = sum(s.failed_requests for s in self._domain_stats.values())

        return {
            "overall_health": overall_health.value,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "success_rate": round((total_requests - total_errors) / total_requests * 100, 1) if total_requests > 0 else 100.0,
            "domains_tracked": len(self._domain_stats),
            "domains": domains_health,
            "checked_at": datetime.now().isoformat(),
        }

    def reset_stats(self, domain: Optional[str] = None) -> None:
        """
        Reset statistics for a domain or all domains.

        Args:
            domain: Specific domain to reset, or None for all
        """
        if domain:
            if domain in self._domain_stats:
                self._domain_stats[domain] = DomainStats()
                logger.info(f"ScraperCoordinator: Reset stats for {domain}")
        else:
            self._domain_stats.clear()
            logger.info("ScraperCoordinator: Reset all stats")


# Singleton instance
_coordinator: Optional[ScraperCoordinator] = None


def get_coordinator() -> ScraperCoordinator:
    """
    Get the global ScraperCoordinator instance.

    Returns:
        The singleton ScraperCoordinator
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = ScraperCoordinator()
    return _coordinator


# Context manager for easier usage
class RateLimitContext:
    """
    Context manager for rate-limited requests.

    Usage:
        async with RateLimitContext("europarl.europa.eu") as ctx:
            response = await fetch(url)
            ctx.record(success=True, bytes_received=len(response))
    """

    def __init__(self, domain: str):
        self.domain = domain
        self.coordinator = get_coordinator()
        self._start_time: Optional[float] = None

    async def __aenter__(self):
        await self.coordinator.acquire(self.domain)
        self._start_time = asyncio.get_event_loop().time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.coordinator.release(self.domain)

        # Auto-record failure if exception occurred
        if exc_type is not None:
            elapsed_ms = (asyncio.get_event_loop().time() - self._start_time) * 1000
            self.coordinator.record_request(
                self.domain,
                success=False,
                response_time_ms=elapsed_ms,
                error_message=str(exc_val)
            )

        return False  # Don't suppress exceptions

    def record(
        self,
        success: bool = True,
        bytes_received: int = 0,
        error_message: Optional[str] = None
    ) -> None:
        """Record the request result"""
        elapsed_ms = (asyncio.get_event_loop().time() - self._start_time) * 1000
        self.coordinator.record_request(
            self.domain,
            success=success,
            response_time_ms=elapsed_ms,
            bytes_received=bytes_received,
            error_message=error_message
        )
