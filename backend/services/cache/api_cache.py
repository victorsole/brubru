"""
API Cache Service

Redis-based caching for API responses to reduce load and improve performance.
Part of Phase 6: Data Synchronization

Features:
- Response caching with TTL
- Cache invalidation strategies
- Cache warming for frequently accessed data
- Hit/miss rate tracking
- Automatic serialization/deserialization
"""

import logging
import json
import hashlib
from typing import Any, Optional, Dict, Union, List
from datetime import timedelta
from functools import wraps
import redis
from redis import Redis

logger = logging.getLogger(__name__)


class APICache:
    """
    Redis-based API response cache.

    Provides caching layer for expensive API calls with:
    - Automatic serialization/deserialization
    - Configurable TTL per endpoint
    - Cache key generation from parameters
    - Hit/miss statistics
    - Bulk operations
    """

    # Default TTL values for different data types (in seconds)
    DEFAULT_TTL = {
        'legislation': 3600 * 24,      # 24 hours - legislation changes infrequently
        'mep_profiles': 3600 * 6,      # 6 hours - MEP data relatively stable
        'press_releases': 3600,        # 1 hour - news updates frequently
        'rss_feeds': 1800,             # 30 minutes - RSS should be fresh
        'sparql_results': 3600 * 12,   # 12 hours - SPARQL results stable
        'search_results': 1800,        # 30 minutes - search results cache
        'document_content': 3600 * 24 * 7,  # 7 days - document content rarely changes
        'api_metadata': 3600 * 24 * 30,     # 30 days - metadata very stable
    }

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "brubru:api:",
        default_ttl: int = 3600
    ):
        """
        Initialize API cache.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all cache keys
            default_ttl: Default TTL in seconds
        """
        self.redis_client: Redis = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }

        # Test connection
        try:
            self.redis_client.ping()
            logger.info(f"Connected to Redis: {redis_url}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def _generate_key(self, namespace: str, *args, **kwargs) -> str:
        """
        Generate cache key from namespace and parameters.

        Args:
            namespace: Cache namespace (e.g., 'eurlex', 'mep_profile')
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create deterministic key from arguments
        key_parts = [namespace]

        # Add positional args
        key_parts.extend(str(arg) for arg in args)

        # Add sorted keyword args
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)

        # Hash if key is too long
        key_str = ":".join(key_parts)
        if len(key_str) > 200:
            key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
            key_str = f"{namespace}:hash:{key_hash}"

        return f"{self.key_prefix}{key_str}"

    def get(self, namespace: str, *args, **kwargs) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            namespace: Cache namespace
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            Cached value or None
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)
            value = self.redis_client.get(key)

            if value is not None:
                self.stats['hits'] += 1
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            else:
                self.stats['misses'] += 1
                logger.debug(f"Cache miss: {key}")
                return None

        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            self.stats['errors'] += 1
            return None

    def set(
        self,
        namespace: str,
        value: Any,
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Set value in cache.

        Args:
            namespace: Cache namespace
            value: Value to cache
            ttl: Time to live in seconds (None = default)
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            True if successful
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)

            # Use namespace-specific TTL or default
            if ttl is None:
                ttl = self.DEFAULT_TTL.get(namespace, self.default_ttl)

            # Serialize value
            serialized = json.dumps(value, default=str)

            # Set with TTL
            self.redis_client.setex(key, ttl, serialized)

            self.stats['sets'] += 1
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            self.stats['errors'] += 1
            return False

    def delete(self, namespace: str, *args, **kwargs) -> bool:
        """
        Delete value from cache.

        Args:
            namespace: Cache namespace
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            True if deleted
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)
            deleted = self.redis_client.delete(key)

            if deleted:
                self.stats['deletes'] += 1
                logger.debug(f"Cache delete: {key}")
                return True
            return False

        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            self.stats['errors'] += 1
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., 'brubru:api:mep:*')

        Returns:
            Number of keys deleted
        """
        try:
            full_pattern = f"{self.key_prefix}{pattern}"
            keys = self.redis_client.keys(full_pattern)

            if keys:
                deleted = self.redis_client.delete(*keys)
                self.stats['deletes'] += deleted
                logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0

        except Exception as e:
            logger.error(f"Cache delete pattern error: {str(e)}")
            self.stats['errors'] += 1
            return 0

    def exists(self, namespace: str, *args, **kwargs) -> bool:
        """
        Check if key exists in cache.

        Args:
            namespace: Cache namespace
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            True if exists
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)
            return bool(self.redis_client.exists(key))

        except Exception as e:
            logger.error(f"Cache exists error: {str(e)}")
            return False

    def get_ttl(self, namespace: str, *args, **kwargs) -> Optional[int]:
        """
        Get remaining TTL for key.

        Args:
            namespace: Cache namespace
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            TTL in seconds or None
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)
            ttl = self.redis_client.ttl(key)

            if ttl >= 0:
                return ttl
            return None

        except Exception as e:
            logger.error(f"Cache get TTL error: {str(e)}")
            return None

    def refresh_ttl(
        self,
        namespace: str,
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> bool:
        """
        Refresh TTL for existing key.

        Args:
            namespace: Cache namespace
            ttl: New TTL in seconds (None = default)
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            True if refreshed
        """
        try:
            key = self._generate_key(namespace, *args, **kwargs)

            if ttl is None:
                ttl = self.DEFAULT_TTL.get(namespace, self.default_ttl)

            return bool(self.redis_client.expire(key, ttl))

        except Exception as e:
            logger.error(f"Cache refresh TTL error: {str(e)}")
            return False

    def get_or_set(
        self,
        namespace: str,
        fetch_func,
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Get from cache or fetch and set if missing.

        Args:
            namespace: Cache namespace
            fetch_func: Function to call if cache miss
            ttl: TTL in seconds
            *args: Cache key arguments
            **kwargs: Cache key keyword arguments

        Returns:
            Cached or fetched value
        """
        # Try cache first
        cached = self.get(namespace, *args, **kwargs)
        if cached is not None:
            return cached

        # Fetch value
        try:
            value = fetch_func()
            if value is not None:
                self.set(namespace, value, ttl, *args, **kwargs)
            return value
        except Exception as e:
            logger.error(f"Fetch function error: {str(e)}")
            return None

    def batch_get(
        self,
        namespace: str,
        keys_params: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get multiple values at once.

        Args:
            namespace: Cache namespace
            keys_params: List of parameter dicts for key generation

        Returns:
            Dict mapping key params to values
        """
        results = {}

        try:
            # Generate all keys
            keys_map = {}
            for params in keys_params:
                key = self._generate_key(namespace, **params)
                keys_map[key] = params

            # Batch get
            if keys_map:
                values = self.redis_client.mget(keys_map.keys())

                for key, value in zip(keys_map.keys(), values):
                    params = keys_map[key]
                    params_str = json.dumps(params, sort_keys=True)

                    if value is not None:
                        results[params_str] = json.loads(value)
                        self.stats['hits'] += 1
                    else:
                        self.stats['misses'] += 1

        except Exception as e:
            logger.error(f"Batch get error: {str(e)}")
            self.stats['errors'] += 1

        return results

    def batch_set(
        self,
        namespace: str,
        items: List[Dict[str, Any]],
        ttl: Optional[int] = None
    ) -> int:
        """
        Set multiple values at once.

        Args:
            namespace: Cache namespace
            items: List of dicts with 'params' and 'value' keys
            ttl: TTL in seconds

        Returns:
            Number of items set
        """
        count = 0

        try:
            if ttl is None:
                ttl = self.DEFAULT_TTL.get(namespace, self.default_ttl)

            pipeline = self.redis_client.pipeline()

            for item in items:
                params = item.get('params', {})
                value = item.get('value')

                if value is not None:
                    key = self._generate_key(namespace, **params)
                    serialized = json.dumps(value, default=str)
                    pipeline.setex(key, ttl, serialized)
                    count += 1

            pipeline.execute()
            self.stats['sets'] += count
            logger.debug(f"Batch set: {count} items")

        except Exception as e:
            logger.error(f"Batch set error: {str(e)}")
            self.stats['errors'] += 1

        return count

    def clear_namespace(self, namespace: str) -> int:
        """
        Clear all keys in namespace.

        Args:
            namespace: Namespace to clear

        Returns:
            Number of keys deleted
        """
        return self.delete_pattern(f"{namespace}:*")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Statistics dict
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate': f"{hit_rate:.2f}%"
        }

    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }

    def flush_all(self) -> bool:
        """
        Flush all keys in cache.

        WARNING: This clears entire Redis database!

        Returns:
            True if successful
        """
        try:
            self.redis_client.flushdb()
            logger.warning("Flushed entire cache database")
            return True
        except Exception as e:
            logger.error(f"Flush error: {str(e)}")
            return False

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get Redis memory usage statistics.

        Returns:
            Memory info dict
        """
        try:
            info = self.redis_client.info('memory')
            return {
                'used_memory': info.get('used_memory_human'),
                'used_memory_peak': info.get('used_memory_peak_human'),
                'used_memory_rss': info.get('used_memory_rss_human'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio')
            }
        except Exception as e:
            logger.error(f"Memory usage error: {str(e)}")
            return {}

    def close(self):
        """Close Redis connection"""
        try:
            self.redis_client.close()
            logger.info("Closed Redis connection")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")


def cached(namespace: str, ttl: Optional[int] = None):
    """
    Decorator for caching function results.

    Args:
        namespace: Cache namespace
        ttl: TTL in seconds

    Example:
        @cached('mep_profile', ttl=3600)
        async def get_mep_profile(mep_id: str):
            # Expensive API call
            return data
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get cache instance from kwargs or create new
            cache: Optional[APICache] = kwargs.pop('_cache', None)

            if cache is None:
                # No cache available, just call function
                return await func(*args, **kwargs)

            # Try cache
            cached_value = cache.get(namespace, *args, **kwargs)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                cache.set(namespace, result, ttl, *args, **kwargs)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache: Optional[APICache] = kwargs.pop('_cache', None)

            if cache is None:
                return func(*args, **kwargs)

            cached_value = cache.get(namespace, *args, **kwargs)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)

            if result is not None:
                cache.set(namespace, result, ttl, *args, **kwargs)

            return result

        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
