"""
Tender Context Provider Tests

Tests for the TenderContextProvider class used in AI chat integration.
Part of Tenderator Phase 9: Testing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from backend.services.ai.tender_context_provider import (
    TenderContextProvider,
    TenderIntent,
    TenderContextData,
    TENDER_INTENT_PATTERNS,
    COUNTRY_MAPPINGS,
    SECTOR_MAPPINGS
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def tender_context_provider():
    """TenderContextProvider instance with mocked database"""
    with patch('backend.services.ai.tender_context_provider.SessionLocal'):
        provider = TenderContextProvider()
        return provider


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.query = Mock()
    db.close = Mock()
    return db


# ============================================================================
# Intent Detection Tests
# ============================================================================

class TestIntentDetection:
    """Tests for tender intent detection"""

    def test_detect_search_intent(self, tender_context_provider):
        """Test detection of search intent"""
        queries = [
            "Find tenders for IT services in France",
            "Search for construction tenders in Belgium",
            "Show me tenders for consulting",
            "What tenders are available for healthcare?"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is True
            assert intent.intent_type == 'search', f"Failed for query: {query}"

    def test_detect_explain_intent(self, tender_context_provider):
        """Test detection of explain intent"""
        queries = [
            "Explain tender 1776-2025",
            "What is tender 123-2024?",
            "Tell me about tender 456/2025",
            "Details of tender 789-2024"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is True
            assert intent.intent_type == 'explain', f"Failed for query: {query}"
            assert intent.publication_number is not None

    def test_detect_match_intent(self, tender_context_provider):
        """Test detection of match intent"""
        queries = [
            "What are my matched tenders?",
            "Show me tenders matched to me",
            "New tenders for me this week",
            "Tenders I should bid on"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is True
            assert intent.intent_type == 'match', f"Failed for query: {query}"

    def test_detect_checklist_intent(self, tender_context_provider):
        """Test detection of checklist intent"""
        queries = [
            "What documents do I need for this tender?",
            "ESPD checklist requirements",
            "Bid preparation documents",
            "What do I need to apply for a tender?"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is True
            assert intent.intent_type == 'checklist', f"Failed for query: {query}"

    def test_detect_help_intent(self, tender_context_provider):
        """Test detection of help intent"""
        queries = [
            "Help me with tenders",
            "How does tenderator work?",
            "Tender advice",
            "What is a tender?"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is True
            assert intent.intent_type == 'help', f"Failed for query: {query}"

    def test_non_tender_query(self, tender_context_provider):
        """Test non-tender queries are not detected"""
        queries = [
            "What is the AI Act?",
            "Tell me about GDPR",
            "Who is the MEP for Germany?",
            "What is the weather today?"
        ]

        for query in queries:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.is_tender_query is False, f"False positive for: {query}"

    def test_extract_publication_number(self, tender_context_provider):
        """Test publication number extraction"""
        test_cases = [
            ("Tell me about tender 1776-2025", "1776-2025"),
            ("Details for 123/2024", "123-2024"),
            ("Tender 45678-2025 information", "45678-2025"),
        ]

        for query, expected in test_cases:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.publication_number == expected, f"Failed for: {query}"

    def test_extract_countries(self, tender_context_provider):
        """Test country extraction from queries"""
        test_cases = [
            ("Tenders in France", ["FR"]),
            ("Tenders for Germany and Belgium", ["DE", "BE"]),
            ("French tenders", ["FR"]),
            ("Italian and Spanish contracts", ["IT", "ES"]),
        ]

        for query, expected in test_cases:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.countries is not None
            for country in expected:
                assert country in intent.countries, f"Missing {country} for: {query}"

    def test_extract_sectors(self, tender_context_provider):
        """Test sector/CPV extraction from queries"""
        test_cases = [
            ("IT services tenders", ["72"]),
            ("Construction tenders", ["45"]),
            ("Healthcare and medical tenders", ["85", "33"]),
            ("Software development tenders", ["72"]),
        ]

        for query, expected_cpv in test_cases:
            intent = tender_context_provider.detect_tender_intent(query)
            assert intent.cpv_sectors is not None
            for cpv in expected_cpv:
                assert cpv in intent.cpv_sectors, f"Missing CPV {cpv} for: {query}"

    def test_confidence_score(self, tender_context_provider):
        """Test confidence scores are reasonable"""
        # Very specific query should have high confidence
        intent1 = tender_context_provider.detect_tender_intent("Explain tender 1776-2025")
        assert intent1.confidence >= 0.9

        # General tender query should have moderate confidence
        intent2 = tender_context_provider.detect_tender_intent("Find tenders")
        assert intent2.confidence >= 0.5


# ============================================================================
# Country Mapping Tests
# ============================================================================

class TestCountryMappings:
    """Tests for country name to code mappings"""

    def test_all_eu_countries_mapped(self):
        """Test that all EU27 countries are mapped"""
        eu_countries = {
            'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
            'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
            'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
        }
        mapped_codes = set(COUNTRY_MAPPINGS.values())
        assert eu_countries.issubset(mapped_codes)

    def test_country_names_lowercase(self):
        """Test that country names are lowercase for matching"""
        for name in COUNTRY_MAPPINGS.keys():
            assert name == name.lower()


# ============================================================================
# Sector Mapping Tests
# ============================================================================

class TestSectorMappings:
    """Tests for sector keyword to CPV code mappings"""

    def test_common_sectors_mapped(self):
        """Test that common sectors are mapped"""
        required_sectors = ['it', 'construction', 'healthcare', 'consulting', 'security']
        for sector in required_sectors:
            assert sector in SECTOR_MAPPINGS

    def test_cpv_codes_valid_format(self):
        """Test that CPV codes are valid 2-digit prefixes"""
        for cpv in SECTOR_MAPPINGS.values():
            assert len(cpv) == 2
            assert cpv.isdigit()


# ============================================================================
# Context Fetching Tests
# ============================================================================

class TestContextFetching:
    """Tests for tender context fetching"""

    @pytest.mark.asyncio
    async def test_fetch_context_for_search(self, tender_context_provider):
        """Test fetching context for search intent"""
        intent = TenderIntent(
            is_tender_query=True,
            intent_type='search',
            confidence=0.9,
            search_query="IT services",
            countries=["FR"]
        )

        # Mock the database and service
        with patch.object(tender_context_provider, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            with patch('backend.services.ai.tender_context_provider.TenderService') as MockService:
                mock_service = MockService.return_value
                mock_service.search_tenders.return_value = []

                context = await tender_context_provider.fetch_tender_context(intent)

                assert context is not None
                assert context.intent == intent
                assert context.formatted_context is not None

    @pytest.mark.asyncio
    async def test_fetch_context_for_checklist(self, tender_context_provider):
        """Test fetching context for checklist intent"""
        intent = TenderIntent(
            is_tender_query=True,
            intent_type='checklist',
            confidence=0.85
        )

        with patch.object(tender_context_provider, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            with patch('backend.services.ai.tender_context_provider.TenderService'):
                context = await tender_context_provider.fetch_tender_context(intent)

                assert context is not None
                assert context.checklist_info is not None
                assert 'parts' in context.checklist_info

    @pytest.mark.asyncio
    async def test_fetch_context_includes_statistics(self, tender_context_provider):
        """Test that context includes statistics"""
        intent = TenderIntent(
            is_tender_query=True,
            intent_type='help',
            confidence=0.7
        )

        with patch.object(tender_context_provider, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_query.count.return_value = 100
            mock_query.filter.return_value = mock_query
            mock_query.scalar.return_value = 500000.0
            mock_db.query.return_value = mock_query
            mock_get_db.return_value = mock_db

            with patch('backend.services.ai.tender_context_provider.TenderService'):
                context = await tender_context_provider.fetch_tender_context(intent)

                assert context is not None
                assert context.statistics is not None


# ============================================================================
# Context Formatting Tests
# ============================================================================

class TestContextFormatting:
    """Tests for context formatting"""

    def test_format_tender(self, tender_context_provider):
        """Test tender formatting for context"""
        mock_tender = Mock()
        mock_tender.id = 1
        mock_tender.publication_number = "1776-2025"
        mock_tender.title = "Test Tender"
        mock_tender.buyer_name = "Test Buyer"
        mock_tender.buyer_country = "BE"
        mock_tender.estimated_value = 500000.0
        mock_tender.currency = "EUR"
        mock_tender.cpv_main = "72000000"
        mock_tender.procedure_type = "open"
        mock_tender.status = "open"
        mock_tender.submission_deadline = datetime.now() + timedelta(days=30)
        mock_tender.description = "Test description"
        mock_tender.sme_suitability_score = 75.0

        formatted = tender_context_provider._format_tender(mock_tender)

        assert formatted['id'] == 1
        assert formatted['publication_number'] == "1776-2025"
        assert formatted['title'] == "Test Tender"
        assert formatted['ted_url'] is not None

    def test_get_checklist_template(self, tender_context_provider):
        """Test checklist template generation"""
        template = tender_context_provider._get_checklist_template()

        assert 'parts' in template
        assert len(template['parts']) == 2  # Part III and Part IV
        assert 'tips' in template

        # Check Part III structure
        part3 = template['parts'][0]
        assert 'Exclusion' in part3['name']

        # Check Part IV structure
        part4 = template['parts'][1]
        assert 'Selection' in part4['name']


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for tender context provider"""

    @pytest.mark.asyncio
    async def test_full_search_flow(self, tender_context_provider):
        """Test full search flow from query to context"""
        query = "Find IT tenders in France under 500k EUR"

        # Detect intent
        intent = tender_context_provider.detect_tender_intent(query)

        assert intent.is_tender_query is True
        assert intent.intent_type == 'search'
        assert 'FR' in intent.countries
        assert '72' in intent.cpv_sectors

    @pytest.mark.asyncio
    async def test_full_explain_flow(self, tender_context_provider):
        """Test full explain flow from query to context"""
        query = "Explain tender 1776-2025"

        # Detect intent
        intent = tender_context_provider.detect_tender_intent(query)

        assert intent.is_tender_query is True
        assert intent.intent_type == 'explain'
        assert intent.publication_number == "1776-2025"
