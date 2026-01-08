"""
Simple In-Memory Cache Service

Provides TTL-based caching for API responses to improve performance.
Phase 1 Quick Win: Cache committee members, MEP profiles, and legislation details.
"""

import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL"""
    value: Any
    expires_at: datetime


class SimpleCache:
    """
    Simple in-memory cache with TTL support.

    Thread-safe for concurrent access.
    Can be upgraded to Redis later for production.
    """

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        logger.info("SimpleCache initialized")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                return None

            # Check if expired
            if datetime.now() > entry.expires_at:
                # Remove expired entry
                del self._cache[key]
                logger.debug(f"Cache expired: {key}")
                return None

            logger.debug(f"Cache hit: {key}")
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default: 1 hour)
        """
        with self._lock:
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")

    def delete(self, key: str):
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")

    def cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now > entry.expires_at
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"Cache cleanup: {len(expired_keys)} expired entries removed")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            now = datetime.now()
            active_entries = sum(
                1 for entry in self._cache.values()
                if now <= entry.expires_at
            )

            return {
                'total_entries': len(self._cache),
                'active_entries': active_entries,
                'expired_entries': len(self._cache) - active_entries
            }


# Global singleton
_cache: Optional[SimpleCache] = None


def get_cache() -> SimpleCache:
    """Get global cache instance"""
    global _cache

    if _cache is None:
        _cache = SimpleCache()

    return _cache


# Cache key generators for common use cases

def committee_cache_key(committee_code: str) -> str:
    """Generate cache key for committee details"""
    return f"committee:{committee_code}"


def mep_profile_cache_key(mep_id: str) -> str:
    """Generate cache key for MEP profile"""
    return f"mep:{mep_id}"


def legislation_cache_key(celex: str) -> str:
    """Generate cache key for legislation details"""
    return f"legislation:{celex}"


def procedure_cache_key(procedure_ref: str) -> str:
    """Generate cache key for procedure details"""
    return f"procedure:{procedure_ref}"
