"""
TED REST API Client Unit Tests

Tests for the TED API client functionality.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, patch
import httpx

from services.tenders.ted_client import (
    TEDClient,
    NoticeType,
    ProcedureType,
    SortField
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def ted_client():
    """Create a TED client instance"""
    return TEDClient()


@pytest.fixture
def mock_response():
    """Mock HTTP response"""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    # TED API v3 returns totalNoticeCount, not "total"; the client reads that
    # key. The old fixture used the pre-v3 shape, so every assertion about
    # pagination was checking a number the client had defaulted to 0.
    response.json.return_value = {
        "notices": [
            {
                "ND": "1776-2025",
                "publication-number": "1776-2025",
                "TI": {"eng": "Test Tender"},
                "CY": ["BEL"],
                "PC": ["72000000"],
            }
        ],
        "totalNoticeCount": 1
    }
    return response


@pytest.fixture
def sample_notice_response():
    """Sample single notice response"""
    return {
        "id": "1776-2025",
        "title": "IT Services Contract",
        "buyer": {
            "name": "European Commission",
            "country": "BE"
        },
        "cpv": ["72000000", "72200000"],
        "procedure": "open",
        "estimatedValue": {
            "amount": 1000000,
            "currency": "EUR"
        },
        "deadline": "2025-03-15T12:00:00Z"
    }


# ============================================================================
# Initialization Tests
# ============================================================================

class TestTEDClientInit:
    """Tests for TEDClient initialization"""

    def test_default_initialization(self):
        """Test default client initialization"""
        client = TEDClient()
        assert client.base_url == "https://api.ted.europa.eu/v3"

    def test_custom_rate_limit(self):
        """Test custom rate limit initialization"""
        client = TEDClient(rate_limit_calls=100, rate_limit_period=30)
        assert client.rate_limit_calls == 100
        assert client.rate_limit_period == 30

    def test_custom_timeout(self):
        """Test custom timeout initialization"""
        client = TEDClient(timeout=60)
        assert client.timeout == 60


# ============================================================================
# Search Query Building Tests
# ============================================================================

class TestSearchQueryBuilding:
    """Tests for search query building.

    These assert the TED API v3 contract: a POST to notices/search carrying a
    JSON body whose "query" is an expert-search string. They previously patched
    `get` and asserted on `params["q"]`, which is the pre-v3 GET contract the
    client stopped using -- so the patch never intercepted anything, the real
    POST escaped to api.ted.europa.eu, and the assertions failed on a 400 from
    the live service. That is also why this file took minutes to run.
    """

    @staticmethod
    def _query_from(mock_post) -> str:
        """The expert-search string the client sent."""
        body = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
        return body["query"]

    @pytest.mark.asyncio
    async def test_search_with_text_query(self, ted_client, mock_response):
        """Free-text goes in as FT="..."."""
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(query="software development")
            assert 'FT="software development"' in self._query_from(mock_post)

    @pytest.mark.asyncio
    async def test_search_with_cpv_codes(self, ted_client, mock_response):
        """Every CPV code appears, OR-ed together."""
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(cpv_codes=["72000000", "48000000"])
            query = self._query_from(mock_post)
            assert 'PC="72000000"' in query
            assert 'PC="48000000"' in query

    @pytest.mark.asyncio
    async def test_search_converts_countries_to_alpha3(self, ted_client, mock_response):
        """TED v3 expects ISO alpha-3, so BE/FR must go out as BEL/FRA."""
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(countries=["BE", "FR"])
            query = self._query_from(mock_post)
            assert "CY=BEL" in query
            assert "CY=FRA" in query

    @pytest.mark.asyncio
    async def test_search_with_procedure_types(self, ted_client, mock_response):
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(
                procedure_types=[ProcedureType.OPEN, ProcedureType.RESTRICTED]
            )
            query = self._query_from(mock_post)
            assert 'PR="open"' in query
            assert 'PR="restricted"' in query

    @pytest.mark.asyncio
    async def test_notice_type_filter_is_not_applied(self, ted_client, mock_response):
        """notice_types is accepted but deliberately NOT sent.

        The TD filter values changed in v3 and the old ones ("cn-standard")
        return no results, so ted_client comments the filter out and narrows by
        procedure type instead. This test pins that down: it used to assert
        TD="cn-standard" WAS in the query, describing behaviour the client had
        already abandoned. If someone re-enables the filter, this fails and
        they will find the explanation here.
        """
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(notice_types=[NoticeType.COMPETITION])
            assert "TD=" not in self._query_from(mock_post)

    @pytest.mark.asyncio
    async def test_search_with_date_range(self, ted_client, mock_response):
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await ted_client.search_notices(
                publication_date_from=date(2024, 1, 1),
                publication_date_to=date(2024, 12, 31)
            )
            query = self._query_from(mock_post)
            assert "PD>=20240101" in query
            assert "PD<=20241231" in query


# ============================================================================
# Search Response Tests
# ============================================================================

class TestSearchResponse:
    """Tests for search response handling"""

    @pytest.mark.asyncio
    async def test_search_returns_notices(self, ted_client, mock_response):
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await ted_client.search_notices()
            assert "notices" in result
            assert len(result["notices"]) == 1
            assert result["notices"][0]["ND"] == "1776-2025"

    @pytest.mark.asyncio
    async def test_search_returns_pagination(self, ted_client, mock_response):
        with patch.object(ted_client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await ted_client.search_notices(page=1, page_size=20)
            assert result["page"] == 1
            assert result["page_size"] == 20
            assert result["total"] == 1          # read from totalNoticeCount
            assert result["total_pages"] == 1


# ============================================================================
# SME-Friendly Search Tests
# ============================================================================

class TestSMEFriendlySearch:
    """Tests for SME-friendly tender search"""

    @pytest.mark.asyncio
    async def test_sme_friendly_uses_open_procedure(self, ted_client, mock_response):
        """Test that SME-friendly search uses open procedure"""
        with patch.object(ted_client, 'search_notices', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"notices": [], "total": 0}

            await ted_client.search_sme_friendly(cpv_codes=["72000000"])

            call_args = mock_search.call_args
            assert ProcedureType.OPEN in call_args.kwargs.get('procedure_types', [])

    @pytest.mark.asyncio
    async def test_sme_friendly_uses_competition_type(self, ted_client, mock_response):
        """Test that SME-friendly search uses competition notice type"""
        with patch.object(ted_client, 'search_notices', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"notices": [], "total": 0}

            await ted_client.search_sme_friendly()

            call_args = mock_search.call_args
            assert NoticeType.COMPETITION in call_args.kwargs.get('notice_types', [])

    @pytest.mark.asyncio
    async def test_sme_friendly_filters_by_deadline(self, ted_client, mock_response):
        """Test that SME-friendly search filters by minimum deadline"""
        with patch.object(ted_client, 'search_notices', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"notices": [], "total": 0}

            await ted_client.search_sme_friendly(min_deadline_days=45)

            call_args = mock_search.call_args
            deadline_from = call_args.kwargs.get('deadline_from')
            assert deadline_from >= date.today() + timedelta(days=45)


# ============================================================================
# Notice Retrieval Tests
# ============================================================================

class TestNoticeRetrieval:
    """Tests for individual notice retrieval"""

    @pytest.mark.asyncio
    async def test_get_notice(self, ted_client, sample_notice_response):
        """Test getting a single notice.

        get_notice needs an API key: without one it logs and returns None
        before issuing a request. The old test never set one, so it was
        asserting on None -- and its sibling test_get_notice_not_found passed
        for the same wrong reason, returning None because there was no key
        rather than because of the 404 it claimed to exercise.
        """
        ted_client.ted_api_key = "test-key"
        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = sample_notice_response

        with patch.object(ted_client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await ted_client.get_notice("1776-2025")

            assert result["id"] == "1776-2025"
            mock_get.assert_called_once_with(
                "notices/1776-2025",
                headers={"Authorization": "Bearer test-key"},
            )

    @pytest.mark.asyncio
    async def test_get_notice_without_api_key_returns_none(self, ted_client):
        """No key configured means no request is made at all."""
        ted_client.ted_api_key = None
        with patch.object(ted_client, 'get', new_callable=AsyncMock) as mock_get:
            assert await ted_client.get_notice("1776-2025") is None
            mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_notice_not_found(self, ted_client):
        """A 404 from the API returns None."""
        ted_client.ted_api_key = "test-key"
        with patch.object(ted_client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=Mock(),
                response=Mock(status_code=404)
            )

            result = await ted_client.get_notice("nonexistent-2025")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_notice_xml(self, ted_client):
        """XML comes from the public TED website, not the authenticated API.

        get_notice_xml calls self.client.get() against
        ted.europa.eu/en/notice/<pub>/xml -- a different host and a different
        client from the API wrapper's own get(). Patching the wrapper meant the
        real request went out to the live site on every run.
        """
        mock_response = Mock(spec=httpx.Response)
        mock_response.text = "<ContractNotice>...</ContractNotice>"
        mock_response.raise_for_status = Mock(return_value=None)

        with patch.object(ted_client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await ted_client.get_notice_xml("1776-2025")

            assert mock_get.call_args.args[0] == (
                "https://ted.europa.eu/en/notice/1776-2025/xml"
            )

            assert result == "<ContractNotice>...</ContractNotice>"


# ============================================================================
# Bulk Package Tests
# ============================================================================

class TestBulkPackage:
    """Tests for bulk package operations"""

    @pytest.mark.asyncio
    async def test_build_daily_package_url(self, ted_client):
        """Test daily package URL construction"""
        # This is an indirect test through download_bulk_package behavior
        test_date = date(2024, 6, 15)

        with patch.object(ted_client, 'client', new_callable=Mock) as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=mock_response
            )
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await ted_client.download_bulk_package(test_date, "daily")

            # Should be None because of 404
            assert result is None

    def test_build_ted_url(self, ted_client):
        """Test TED URL construction"""
        url = ted_client.build_ted_url("1776-2025")
        assert "1776-2025" in url
        assert "ted.europa.eu" in url


# ============================================================================
# Health Check Tests
# ============================================================================

class TestHealthCheck:
    """Tests for API health check"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, ted_client, mock_response):
        """Test successful health check"""
        with patch.object(ted_client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await ted_client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ted_client):
        """Test failed health check"""
        with patch.object(ted_client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await ted_client.health_check()

            assert result is False


# ============================================================================
# Enum Tests
# ============================================================================

class TestEnums:
    """Tests for TED client enums"""

    def test_notice_type_values(self):
        """Test NoticeType enum values"""
        assert NoticeType.COMPETITION.value == "cn-standard"
        assert NoticeType.PLANNING.value == "pin-only"
        assert NoticeType.RESULT.value == "can-standard"
        assert NoticeType.MODIFICATION.value == "can-modif"

    def test_procedure_type_values(self):
        """Test ProcedureType enum values"""
        assert ProcedureType.OPEN.value == "open"
        assert ProcedureType.RESTRICTED.value == "restricted"
        assert ProcedureType.NEGOTIATED.value == "neg-w-call"
        assert ProcedureType.COMPETITIVE_DIALOGUE.value == "comp-dial"

    def test_sort_field_values(self):
        """Test SortField enum values"""
        assert SortField.PUBLICATION_DATE.value == "PD"
        assert SortField.DEADLINE.value == "TD"
        assert SortField.COUNTRY.value == "CY"
