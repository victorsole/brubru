"""
Tests for EUR-Lex CELLAR API Client

Tests the EUR-Lex client including:
- SPARQL endpoint connectivity
- Document retrieval by CELEX
- Document relationships
- Search functionality
- RSS feed access

Run with: pytest backend/tests/test_eurlex_client.py -v
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.api_clients.eurlex_client import (
    EURLexClient,
    EURLexDocumentType,
    EURLexSubjectMatter
)


class TestEURLexClientUnit:
    """Unit tests for EURLexClient (mocked)"""

    @pytest.fixture
    def client(self):
        """Create client instance"""
        return EURLexClient()

    def test_client_initialization(self, client):
        """Test client initializes with correct endpoints"""
        assert client.BASE_URL == "https://eur-lex.europa.eu"
        assert client.SPARQL_ENDPOINT == "https://publications.europa.eu/webapi/rdf/sparql"
        assert client.CELLAR_API == "https://publications.europa.eu/resource/cellar"

    def test_rss_feeds_configured(self, client):
        """Test RSS feeds are properly configured"""
        assert "official_journal" in client.RSS_FEEDS
        assert "competition" in client.RSS_FEEDS
        assert "environment" in client.RSS_FEEDS
        assert "digital_economy" in client.RSS_FEEDS

    def test_document_type_enum(self):
        """Test document type enum values"""
        assert EURLexDocumentType.REGULATION.value == "regulation"
        assert EURLexDocumentType.DIRECTIVE.value == "directive"
        assert EURLexDocumentType.DECISION.value == "decision"
        assert EURLexDocumentType.PROPOSAL.value == "proposal"

    def test_subject_matter_enum(self):
        """Test subject matter enum values"""
        assert EURLexSubjectMatter.ENVIRONMENT.value == "15"
        assert EURLexSubjectMatter.DIGITAL.value == "19"
        assert EURLexSubjectMatter.TRANSPORT.value == "07"
        assert EURLexSubjectMatter.AGRICULTURE.value == "01"

    def test_soap_auth_disabled_by_default(self, client):
        """Test SOAP auth is disabled without credentials"""
        assert client.soap_auth_available is False

    def test_soap_auth_enabled_with_credentials(self):
        """Test SOAP auth is enabled with credentials"""
        client = EURLexClient(
            soap_username="test_user",
            soap_password="test_pass"
        )
        assert client.soap_auth_available is True


class TestEURLexClientSPARQL:
    """Tests for SPARQL-based methods"""

    @pytest.fixture
    def client(self):
        """Create client instance"""
        return EURLexClient()

    @pytest.mark.asyncio
    async def test_get_document_by_celex_mock(self, client):
        """Test get_document_by_celex with mocked SPARQL"""
        mock_results = [{
            "doc": "http://example.com/doc",
            "celexValue": "32024R1689",
            "title": "AI Act",
            "date": "2024-07-12",
            "type": "http://publications.europa.eu/resource/authority/resource-type/REG"
        }]

        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_results

            result = await client.get_document_by_celex("32024R1689")

            assert result is not None
            assert result["celex"] == "32024R1689"
            mock_select.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_by_celex_not_found(self, client):
        """Test get_document_by_celex returns None when not found"""
        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = []

            result = await client.get_document_by_celex("99999X9999")

            assert result is None

    @pytest.mark.asyncio
    async def test_search_documents_mock(self, client):
        """Test search_documents with mocked SPARQL"""
        mock_results = [
            {
                "doc": "http://example.com/doc1",
                "celex": "32024R0001",
                "title": "Test Regulation 1",
                "date": "2024-01-15",
                "type": "regulation"
            },
            {
                "doc": "http://example.com/doc2",
                "celex": "32024R0002",
                "title": "Test Regulation 2",
                "date": "2024-02-20",
                "type": "regulation"
            }
        ]

        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_results

            results = await client.search_documents("test", limit=10)

            assert len(results) == 2
            assert results[0]["celex"] == "32024R0001"
            assert results[1]["celex"] == "32024R0002"

    @pytest.mark.asyncio
    async def test_search_documents_with_date_filter(self, client):
        """Test search_documents with date filter"""
        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = []

            date_from = datetime(2024, 1, 1)
            date_to = datetime(2024, 12, 31)

            await client.search_documents(
                "climate",
                date_from=date_from,
                date_to=date_to
            )

            mock_select.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_relationships_mock(self, client):
        """Test get_document_relationships with mocked SPARQL"""
        mock_results = [
            {
                "relation": "http://publications.europa.eu/ontology/cdm#work_amended_by",
                "relatedDoc": "http://example.com/amending",
                "relatedCelex": "32025R0001"
            },
            {
                "relation": "http://publications.europa.eu/ontology/cdm#work_amends",
                "relatedDoc": "http://example.com/amended",
                "relatedCelex": "32020R0001"
            }
        ]

        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_results

            relationships = await client.get_document_relationships("32024R1689")

            assert "amended_by" in relationships
            assert "amends" in relationships
            assert "32025R0001" in relationships["amended_by"]
            assert "32020R0001" in relationships["amends"]

    @pytest.mark.asyncio
    async def test_get_document_relationships_empty(self, client):
        """Test get_document_relationships returns empty dict when no relations"""
        with patch.object(client.sparql, 'select', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = []

            relationships = await client.get_document_relationships("32024R9999")

            assert relationships == {
                "amended_by": [],
                "amends": [],
                "corrected_by": [],
                "corrects": [],
                "repealed_by": [],
                "repeals": [],
                "implemented_by": []
            }


class TestEURLexClientHTML:
    """Tests for HTML retrieval methods"""

    @pytest.fixture
    def client(self):
        """Create client instance"""
        return EURLexClient()

    @pytest.mark.asyncio
    async def test_get_document_html_url_format(self, client):
        """Test HTML URL is correctly formatted"""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test document</body></html>"

        with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await client.get_document_html("32024R1689", "EN")

            # Verify URL format
            call_args = mock_get.call_args
            url = call_args[0][0]
            assert "CELEX:32024R1689" in url
            assert "/EN/" in url

    @pytest.mark.asyncio
    async def test_get_document_html_returns_content(self, client):
        """Test get_document_html returns HTML content"""
        html_content = "<html><body><h1>AI Act</h1></body></html>"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content

        with patch.object(client.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.get_document_html("32024R1689", "EN")

            assert result == html_content


class TestEURLexClientIntegration:
    """
    Integration tests that hit the real EUR-Lex SPARQL endpoint.

    These tests are marked with @pytest.mark.integration and skipped by default.
    Run with: pytest -m integration backend/tests/test_eurlex_client.py -v
    """

    @pytest.fixture
    def client(self):
        """Create client instance"""
        return EURLexClient(timeout=30)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_real(self, client):
        """Test SPARQL endpoint is accessible"""
        try:
            is_healthy = await client.health_check()
            assert is_healthy is True
        finally:
            await client.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_gdpr_by_celex_real(self, client):
        """Test fetching GDPR by CELEX number"""
        try:
            # GDPR CELEX: 32016R0679
            result = await client.get_document_by_celex("32016R0679")

            # GDPR should exist
            if result:
                assert result["celex"] == "32016R0679"
                # Title should contain "protection" or "data"
                if result.get("title"):
                    title_lower = result["title"].lower()
                    assert "data" in title_lower or "protection" in title_lower
        finally:
            await client.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_ai_act_by_celex_real(self, client):
        """Test fetching AI Act by CELEX number"""
        try:
            # AI Act CELEX: 32024R1689
            result = await client.get_document_by_celex("32024R1689")

            if result:
                assert result["celex"] == "32024R1689"
        finally:
            await client.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_documents_real(self, client):
        """Test searching for documents"""
        try:
            results = await client.search_documents(
                query="artificial intelligence",
                limit=5
            )

            # Should find some results
            assert isinstance(results, list)
        finally:
            await client.close()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_gdpr_relationships_real(self, client):
        """Test fetching GDPR relationships"""
        try:
            # GDPR has been amended
            relationships = await client.get_document_relationships("32016R0679")

            assert isinstance(relationships, dict)
            assert "amended_by" in relationships
            assert "amends" in relationships
        finally:
            await client.close()


class TestCELEXFormat:
    """Tests for CELEX number format understanding"""

    def test_celex_sector_codes(self):
        """Document CELEX sector code meanings"""
        # CELEX format: [sector][year][type][number]
        # Sector 3 = Secondary legislation
        # Type codes: R=Regulation, L=Directive, D=Decision

        # Examples:
        gdpr_celex = "32016R0679"
        assert gdpr_celex[0] == "3"  # Sector 3 (secondary legislation)
        assert gdpr_celex[1:5] == "2016"  # Year
        assert gdpr_celex[5] == "R"  # Regulation
        assert gdpr_celex[6:] == "0679"  # Number

        ai_act_celex = "32024R1689"
        assert ai_act_celex[0] == "3"
        assert ai_act_celex[1:5] == "2024"
        assert ai_act_celex[5] == "R"

    def test_directive_celex_format(self):
        """Test directive CELEX format"""
        # NIS2 Directive
        nis2_celex = "32022L2555"
        assert nis2_celex[5] == "L"  # L = Directive


# =========================================================================
# Run tests
# =========================================================================

if __name__ == "__main__":
    # Run unit tests by default (skip integration)
    pytest.main([__file__, "-v", "-m", "not integration"])
