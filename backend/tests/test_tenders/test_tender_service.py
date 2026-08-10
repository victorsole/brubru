"""
Tender Service Tests

Tests for the TenderService class.
Part of Tenderator Phase 9: Testing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from services.tenders.tender_service import TenderService
from models.tender import Tender, TenderProfile, TenderMatch


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def tender_service(mock_db):
    """TenderService instance with mocked database"""
    return TenderService(mock_db)


@pytest.fixture
def sample_tender():
    """Sample tender model"""
    return Tender(
        id=1,
        publication_number="1776-2025",
        title="IT Services for Cloud Infrastructure",
        official_name="European Commission",   # model column is official_name; buyer_name never existed
        buyer_country="BE",
        estimated_value=500000.0,
        estimated_value_currency="EUR",   # model column carries the estimated_value_ prefix
        cpv_main="72000000",
        procedure_type="open",
        status="open",
        submission_deadline=datetime.now() + timedelta(days=30),
        publication_date=datetime.now() - timedelta(days=5),
        description="Cloud infrastructure migration services",
        sme_suitability_score=75.0
    )


@pytest.fixture
def sample_profile():
    """Sample tender profile"""
    return TenderProfile(
        id=1,
        user_id=123,
        company_name="Test Company",
        company_size="small",
        annual_turnover=2000000.0,
        employee_count=25,
        cpv_categories=["72", "48"],
        countries_of_interest=["BE", "FR", "DE"],
        max_tender_value=1000000.0,
        min_deadline_days=14
    )


@pytest.fixture
def sample_match(sample_tender):
    """Sample tender match"""
    return TenderMatch(
        id=1,
        tender_id=sample_tender.id,
        user_id=123,
        match_score=85.5,
        match_reasons=["Matching CPV sector", "Country match", "Value within range"],
        is_viewed=False,
        is_saved=False,
        is_dismissed=False,
        is_applied=False
    )


# ============================================================================
# Search Tests
# ============================================================================

class TestTenderSearch:
    """Tests for tender search functionality"""

    def test_search_tenders_basic(self, tender_service, mock_db, sample_tender):
        """Test basic tender search"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_tender]
        mock_db.query.return_value = mock_query

        # Execute
        results = tender_service.search_tenders(query="IT Services", status="open")

        # Verify
        assert len(results) == 1
        assert results[0].title == "IT Services for Cloud Infrastructure"

    def test_search_tenders_with_country_filter(self, tender_service, mock_db, sample_tender):
        """Test tender search with country filter"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_tender]
        mock_db.query.return_value = mock_query

        results = tender_service.search_tenders(
            query="IT",
            countries=["BE", "FR"]
        )

        assert len(results) == 1

    def test_search_tenders_with_cpv_filter(self, tender_service, mock_db, sample_tender):
        """Test tender search with CPV filter"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_tender]
        mock_db.query.return_value = mock_query

        results = tender_service.search_tenders(
            cpv_codes=["72"]
        )

        assert len(results) == 1

    def test_search_tenders_with_value_range(self, tender_service, mock_db, sample_tender):
        """Test tender search with value range"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_tender]
        mock_db.query.return_value = mock_query

        results = tender_service.search_tenders(
            min_value=100000,
            max_value=1000000
        )

        assert len(results) == 1

    def test_search_tenders_empty_results(self, tender_service, mock_db):
        """Test tender search with no results"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        results = tender_service.search_tenders(query="nonexistent")

        assert len(results) == 0


# ============================================================================
# Tender Retrieval Tests
# ============================================================================

class TestTenderRetrieval:
    """Tests for tender retrieval"""

    def test_get_tender_by_id(self, tender_service, mock_db, sample_tender):
        """Test getting tender by ID"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_tender
        mock_db.query.return_value = mock_query

        result = tender_service.get_tender(1)

        assert result is not None
        assert result.id == 1
        assert result.publication_number == "1776-2025"

    def test_get_tender_not_found(self, tender_service, mock_db):
        """Test getting non-existent tender"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        result = tender_service.get_tender(999)

        assert result is None

    def test_get_tender_by_publication(self, tender_service, mock_db, sample_tender):
        """Test getting tender by publication number"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_tender
        mock_db.query.return_value = mock_query

        result = tender_service.get_tender_by_publication("1776-2025")

        assert result is not None
        assert result.publication_number == "1776-2025"


# ============================================================================
# User Match Tests
# ============================================================================

class TestUserMatches:
    """Tests for user match functionality"""

    def test_get_user_matches(self, tender_service, mock_db, sample_match):
        """Test getting user matches"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_match]
        mock_db.query.return_value = mock_query

        results = tender_service.get_user_matches(user_id="123")

        assert len(results) == 1
        assert results[0].match_score == 85.5

    def test_get_user_matches_saved_only(self, tender_service, mock_db, sample_match):
        """Test getting only saved matches"""
        sample_match.is_saved = True
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_match]
        mock_db.query.return_value = mock_query

        results = tender_service.get_user_matches(
            user_id="123",
            saved_only=True
        )

        assert len(results) == 1
        assert results[0].is_saved is True

    def test_get_user_matches_exclude_dismissed(self, tender_service, mock_db):
        """Test excluding dismissed matches"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        results = tender_service.get_user_matches(
            user_id="123",
            include_dismissed=False
        )

        assert len(results) == 0

    def test_save_match(self, tender_service, mock_db, sample_match):
        """Test saving a match"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_match
        mock_db.query.return_value = mock_query

        result = tender_service.save_match(match_id=1, user_id="123")

        assert result is not None
        mock_db.commit.assert_called()

    def test_dismiss_match(self, tender_service, mock_db, sample_match):
        """Test dismissing a match"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_match
        mock_db.query.return_value = mock_query

        result = tender_service.dismiss_match(match_id=1, user_id="123")

        assert result is not None
        mock_db.commit.assert_called()


# ============================================================================
# SME Score Tests
# ============================================================================

class TestSMEScore:
    """Tests for SME suitability scoring"""

    def test_get_sme_score_basic(self, tender_service, mock_db, sample_tender):
        """Test basic SME score calculation"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_tender
        mock_db.query.return_value = mock_query

        result = tender_service.get_sme_score_for_tender(
            tender_id=1,
            company_size="small"
        )

        assert result is not None
        # The key is sme_suitability_score; there has never been a 'score'.
        assert 'sme_suitability_score' in result
        assert 0 <= result['sme_suitability_score'] <= 100
        assert 'score_breakdown' in result

    def test_get_sme_score_with_turnover(self, tender_service, mock_db, sample_tender):
        """Test SME score with annual turnover"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_tender
        mock_db.query.return_value = mock_query

        result = tender_service.get_sme_score_for_tender(
            tender_id=1,
            company_size="small",
            annual_turnover=2000000.0
        )

        assert result is not None
        assert 'sme_suitability_score' in result

    def test_get_sme_score_tender_not_found(self, tender_service, mock_db):
        """Test SME score for non-existent tender"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        result = tender_service.get_sme_score_for_tender(
            tender_id=999,
            company_size="small"
        )

        assert result is None


# ============================================================================
# Profile Tests
# ============================================================================

class TestTenderProfile:
    """Tests for tender profile operations"""

    def test_create_profile(self, tender_service, mock_db, sample_profile):
        """Test creating a tender profile"""
        # This would test profile creation
        # Implementation depends on actual service methods
        pass

    def test_update_profile(self, tender_service, mock_db, sample_profile):
        """Test updating a tender profile"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_profile
        mock_db.query.return_value = mock_query

        # Test profile update
        # Implementation depends on actual service methods


# ============================================================================
# Matching Algorithm Tests
# ============================================================================

class TestMatchingAlgorithm:
    """Tests for the tender matching algorithm"""

    def test_calculate_match_score(self, tender_service):
        """Test match score calculation"""
        # Test that match scores are calculated correctly
        # This would test the matching algorithm logic
        pass

    def test_match_score_cpv_weight(self, tender_service):
        """Test CPV category weight in matching"""
        # CPV match should have significant weight
        pass

    def test_match_score_country_weight(self, tender_service):
        """Test country weight in matching"""
        # Country match should contribute to score
        pass

    def test_match_score_value_range(self, tender_service):
        """Test value range contribution to matching"""
        # Value within range should increase score
        pass
