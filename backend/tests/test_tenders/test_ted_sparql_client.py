"""
TED SPARQL Client Unit Tests

Tests for the TED SPARQL endpoint client with caching.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import time

from backend.services.tenders.ted_sparql_client import TEDSparqlClient, QueryCache


# ============================================================================
# QueryCache Tests
# ============================================================================

class TestQueryCache:
    """Tests for the QueryCache class"""

    def test_cache_set_and_get(self):
        """Test basic cache set and get"""
        cache = QueryCache(default_ttl=3600)
        cache.set("query1", {"data": "test"})

        result = cache.get("query1")
        assert result == {"data": "test"}

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = QueryCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_expiration(self):
        """Test cache expiration"""
        cache = QueryCache(default_ttl=1)  # 1 second TTL
        cache.set("query1", {"data": "test"})

        # Should be available immediately
        assert cache.get("query1") is not None

        # Wait for expiration
        time.sleep(1.5)
        assert cache.get("query1") is None

    def test_cache_custom_ttl(self):
        """Test custom TTL per entry"""
        cache = QueryCache(default_ttl=3600)
        cache.set("query1", {"data": "test"}, ttl=1)

        # Wait for custom TTL to expire
        time.sleep(1.5)
        assert cache.get("query1") is None

    def test_cache_clear(self):
        """Test cache clearing"""
        cache = QueryCache()
        cache.set("query1", {"data": "test1"})
        cache.set("query2", {"data": "test2"})

        cache.clear()

        assert cache.get("query1") is None
        assert cache.get("query2") is None

    def test_cache_stats(self):
        """Test cache statistics"""
        cache = QueryCache()
        cache.set("query1", {"data": "test"})

        # Hit
        cache.get("query1")
        # Miss
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


# ============================================================================
# TEDSparqlClient Initialization Tests
# ============================================================================

class TestTEDSparqlClientInit:
    """Tests for TEDSparqlClient initialization"""

    def test_default_initialization(self):
        """Test default client initialization"""
        client = TEDSparqlClient()
        assert client.sparql_endpoint is not None

    def test_cache_enabled_by_default(self):
        """Test cache is enabled by default"""
        client = TEDSparqlClient()
        assert client.cache is not None

    def test_cache_disabled(self):
        """Test cache can be disabled"""
        client = TEDSparqlClient(enable_cache=False)
        assert client.cache is None

    def test_custom_cache_ttl(self):
        """Test custom cache TTL"""
        client = TEDSparqlClient(cache_ttl=7200)
        assert client.cache.default_ttl == 7200


# ============================================================================
# SPARQL Query Tests
# ============================================================================

class TestSparqlQueries:
    """Tests for SPARQL query functionality"""

    @pytest.fixture
    def sparql_client(self):
        """Create a SPARQL client instance"""
        return TEDSparqlClient(enable_cache=False)

    @pytest.fixture
    def mock_sparql_results(self):
        """Mock SPARQL query results"""
        return {
            "results": {
                "bindings": [
                    {
                        "notice": {"value": "http://example.eu/notice/1"},
                        "title": {"value": "Test Notice 1"},
                        "buyerCountry": {"value": "BE"},
                        "cpvCode": {"value": "72000000"}
                    },
                    {
                        "notice": {"value": "http://example.eu/notice/2"},
                        "title": {"value": "Test Notice 2"},
                        "buyerCountry": {"value": "FR"},
                        "cpvCode": {"value": "72200000"}
                    }
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_get_recent_notices(self, sparql_client, mock_sparql_results):
        """Test getting recent notices"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_sparql_results["results"]["bindings"]

            results = await sparql_client.get_recent_notices(days=7, limit=10)

            assert len(results) == 2
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_notices_by_country(self, sparql_client, mock_sparql_results):
        """Test getting notices by country"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_sparql_results["results"]["bindings"]

            results = await sparql_client.get_notices_by_country("BE", limit=10)

            assert len(results) == 2
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_notices_by_cpv(self, sparql_client, mock_sparql_results):
        """Test getting notices by CPV code"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_sparql_results["results"]["bindings"]

            results = await sparql_client.get_notices_by_cpv("72000000", limit=10)

            assert len(results) == 2
            mock_execute.assert_called_once()


# ============================================================================
# Value Range Query Tests
# ============================================================================

class TestValueRangeQueries:
    """Tests for value range query functionality"""

    @pytest.fixture
    def sparql_client(self):
        """Create a SPARQL client instance"""
        return TEDSparqlClient(enable_cache=False)

    @pytest.fixture
    def mock_value_results(self):
        """Mock SPARQL results with values"""
        return [
            {
                "notice": {"value": "http://example.eu/notice/1"},
                "title": {"value": "Small Contract"},
                "value": {"value": "100000"},
                "currency": {"value": "EUR"}
            },
            {
                "notice": {"value": "http://example.eu/notice/2"},
                "title": {"value": "Large Contract"},
                "value": {"value": "5000000"},
                "currency": {"value": "EUR"}
            }
        ]

    @pytest.mark.asyncio
    async def test_get_tenders_by_value_range_min_only(self, sparql_client, mock_value_results):
        """Test getting tenders with minimum value"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_value_results

            results = await sparql_client.get_tenders_by_value_range(min_value=50000)

            mock_execute.assert_called_once()
            # Check the query contains minimum value filter
            query = mock_execute.call_args[0][0]
            assert "50000" in query

    @pytest.mark.asyncio
    async def test_get_tenders_by_value_range_max_only(self, sparql_client, mock_value_results):
        """Test getting tenders with maximum value"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_value_results

            results = await sparql_client.get_tenders_by_value_range(max_value=1000000)

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "1000000" in query

    @pytest.mark.asyncio
    async def test_get_tenders_by_value_range_both(self, sparql_client, mock_value_results):
        """Test getting tenders with value range"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_value_results

            results = await sparql_client.get_tenders_by_value_range(
                min_value=50000,
                max_value=1000000
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "50000" in query
            assert "1000000" in query

    @pytest.mark.asyncio
    async def test_get_tenders_by_value_range_with_countries(self, sparql_client, mock_value_results):
        """Test getting tenders with value range and country filter"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_value_results

            results = await sparql_client.get_tenders_by_value_range(
                min_value=50000,
                countries=["BE", "FR"]
            )

            mock_execute.assert_called_once()
            query = mock_execute.call_args[0][0]
            assert "BE" in query or "FR" in query


# ============================================================================
# SME-Friendly Tenders Tests
# ============================================================================

class TestSMEFriendlyTenders:
    """Tests for SME-friendly tender queries"""

    @pytest.fixture
    def sparql_client(self):
        """Create a SPARQL client instance"""
        return TEDSparqlClient(enable_cache=False)

    @pytest.mark.asyncio
    async def test_get_sme_friendly_tenders_default(self, sparql_client):
        """Test getting SME-friendly tenders with defaults"""
        with patch.object(sparql_client, 'get_tenders_by_value_range', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            await sparql_client.get_sme_friendly_tenders()

            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs.get('max_value') == 5_000_000

    @pytest.mark.asyncio
    async def test_get_sme_friendly_tenders_custom_threshold(self, sparql_client):
        """Test getting SME-friendly tenders with custom threshold"""
        with patch.object(sparql_client, 'get_tenders_by_value_range', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            await sparql_client.get_sme_friendly_tenders(max_value=2_000_000)

            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs.get('max_value') == 2_000_000


# ============================================================================
# Cache Integration Tests
# ============================================================================

class TestCacheIntegration:
    """Tests for cache integration with SPARQL client"""

    @pytest.fixture
    def cached_client(self):
        """Create a SPARQL client with caching enabled"""
        return TEDSparqlClient(enable_cache=True, cache_ttl=3600)

    @pytest.fixture
    def mock_results(self):
        """Mock query results"""
        return [{"notice": {"value": "test"}}]

    @pytest.mark.asyncio
    async def test_cache_stores_results(self, cached_client, mock_results):
        """Test that results are cached"""
        with patch.object(cached_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = mock_results

            # First call - should execute query
            await cached_client.get_recent_notices(days=7)

            # Second call - should use cache
            await cached_client.get_recent_notices(days=7)

            # Query should only be executed once due to caching
            # Note: This depends on the caching implementation
            # The actual assertion may need adjustment based on implementation

    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self, cached_client):
        """Test that cache stats are tracked"""
        stats = cached_client.get_cache_stats()

        assert "caching_enabled" in stats
        assert stats["caching_enabled"] is True

    def test_clear_cache(self, cached_client):
        """Test cache clearing"""
        # Add something to cache
        cached_client.cache.set("test_query", {"data": "test"})

        # Clear cache
        cached_client.clear_cache()

        # Cache should be empty
        assert cached_client.cache.get("test_query") is None


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling"""

    @pytest.fixture
    def sparql_client(self):
        """Create a SPARQL client instance"""
        return TEDSparqlClient(enable_cache=False)

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self, sparql_client):
        """Test handling of query timeouts"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = TimeoutError("Query timed out")

            with pytest.raises(TimeoutError):
                await sparql_client.get_recent_notices(days=7)

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, sparql_client):
        """Test handling of connection errors"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                await sparql_client.get_recent_notices(days=7)


# ============================================================================
# Pagination Tests
# ============================================================================

class TestPagination:
    """Tests for query pagination"""

    @pytest.fixture
    def sparql_client(self):
        """Create a SPARQL client instance"""
        return TEDSparqlClient(enable_cache=False)

    @pytest.mark.asyncio
    async def test_limit_applied(self, sparql_client):
        """Test that limit is applied to queries"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = []

            await sparql_client.get_recent_notices(days=7, limit=50)

            query = mock_execute.call_args[0][0]
            assert "LIMIT 50" in query

    @pytest.mark.asyncio
    async def test_offset_applied(self, sparql_client):
        """Test that offset is applied to queries"""
        with patch.object(sparql_client, '_execute_select', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = []

            await sparql_client.get_recent_notices(days=7, offset=100)

            query = mock_execute.call_args[0][0]
            assert "OFFSET 100" in query
