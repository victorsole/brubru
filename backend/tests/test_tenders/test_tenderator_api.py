"""
Tenderator API Tests

Tests for the Tenderator API endpoints.
Part of Tenderator Phase 9: Testing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import models and schemas
from backend.models.tender import Tender, TenderProfile, TenderMatch
from backend.models.user import User


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_user():
    """Sample user for testing"""
    user = Mock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.subscription_tier = "blue"
    return user


@pytest.fixture
def sample_free_user():
    """Sample user without Blue tier"""
    user = Mock(spec=User)
    user.id = 2
    user.email = "free@example.com"
    user.subscription_tier = "free"
    return user


@pytest.fixture
def sample_tender():
    """Sample tender for testing"""
    tender = Mock(spec=Tender)
    tender.id = 1
    tender.publication_number = "1776-2025"
    tender.title = "IT Services Tender"
    tender.buyer_name = "European Commission"
    tender.buyer_country = "BE"
    tender.estimated_value = 500000.0
    tender.currency = "EUR"
    tender.cpv_main = "72000000"
    tender.cpv_additional = ["72100000", "72200000"]
    tender.procedure_type = "open"
    tender.status = "open"
    tender.submission_deadline = datetime.now() + timedelta(days=30)
    tender.publication_date = datetime.now() - timedelta(days=5)
    tender.description = "Cloud migration services"
    tender.sme_suitability_score = 75.0
    return tender


@pytest.fixture
def sample_profile():
    """Sample tender profile for testing"""
    profile = Mock(spec=TenderProfile)
    profile.id = 1
    profile.user_id = 1
    profile.company_name = "Test Company"
    profile.company_size = "small"
    profile.annual_turnover = 2000000.0
    profile.employee_count = 25
    profile.cpv_categories = ["72", "48"]
    profile.countries_of_interest = ["BE", "FR", "DE"]
    profile.max_tender_value = 1000000.0
    profile.min_deadline_days = 14
    profile.procedure_preferences = ["open", "restricted"]
    profile.created_at = datetime.now()
    profile.updated_at = datetime.now()
    return profile


@pytest.fixture
def sample_match(sample_tender):
    """Sample tender match for testing"""
    match = Mock(spec=TenderMatch)
    match.id = 1
    match.tender_id = sample_tender.id
    match.user_id = 1
    match.match_score = 85.5
    match.match_reasons = ["Matching CPV sector", "Country match", "Value within range"]
    match.match_details = {"cpv_match": 40, "country_match": 25, "value_match": 20.5}
    match.is_viewed = False
    match.is_saved = False
    match.is_dismissed = False
    match.is_applied = False
    match.user_notes = None
    match.user_rating = None
    match.notified_at = None
    match.created_at = datetime.now()
    match.updated_at = datetime.now()
    return match


# ============================================================================
# Blue Tier Access Tests
# ============================================================================

class TestBlueTierAccess:
    """Tests for Blue tier access control"""

    @pytest.mark.asyncio
    async def test_require_blue_tier_allows_blue_user(self, sample_user):
        """Test that Blue tier users are allowed"""
        from backend.api.tenderator import require_blue_tier

        result = await require_blue_tier(sample_user)
        assert result == sample_user

    @pytest.mark.asyncio
    async def test_require_blue_tier_blocks_free_user(self, sample_free_user):
        """Test that free users are blocked"""
        from backend.api.tenderator import require_blue_tier

        with pytest.raises(HTTPException) as exc_info:
            await require_blue_tier(sample_free_user)

        assert exc_info.value.status_code == 403
        assert "Blue tier" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_blue_tier_allows_admin(self):
        """Test that admin users are allowed"""
        from backend.api.tenderator import require_blue_tier

        admin_user = Mock(spec=User)
        admin_user.subscription_tier = "admin"

        result = await require_blue_tier(admin_user)
        assert result == admin_user


# ============================================================================
# Tender Search Endpoint Tests
# ============================================================================

class TestSearchEndpoint:
    """Tests for tender search endpoint"""

    @pytest.mark.asyncio
    async def test_search_tenders_basic(self, sample_tender):
        """Test basic tender search"""
        from backend.api.tenderator import search_tenders

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_db.query.return_value = mock_query

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.search_tenders.return_value = [sample_tender]

            result = await search_tenders(
                query="IT services",
                db=mock_db
            )

            assert result.total >= 0
            assert result.page == 1

    @pytest.mark.asyncio
    async def test_search_tenders_with_filters(self, sample_tender):
        """Test tender search with filters"""
        from backend.api.tenderator import search_tenders

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_db.query.return_value = mock_query

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.search_tenders.return_value = [sample_tender]

            result = await search_tenders(
                query="IT",
                countries="BE,FR",
                cpv_codes="72",
                min_value=100000,
                max_value=1000000,
                db=mock_db
            )

            assert result is not None


# ============================================================================
# Tender Detail Endpoint Tests
# ============================================================================

class TestTenderDetailEndpoint:
    """Tests for tender detail endpoint"""

    @pytest.mark.asyncio
    async def test_get_tender_found(self, sample_tender):
        """Test getting existing tender"""
        from backend.api.tenderator import get_tender

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_tender.return_value = sample_tender

            result = await get_tender(
                tender_id=1,
                service=mock_service
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_tender_not_found(self):
        """Test getting non-existent tender"""
        from backend.api.tenderator import get_tender

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_tender.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_tender(
                    tender_id=999,
                    service=mock_service
                )

            assert exc_info.value.status_code == 404


# ============================================================================
# Profile Endpoint Tests
# ============================================================================

class TestProfileEndpoints:
    """Tests for profile endpoints"""

    @pytest.mark.asyncio
    async def test_get_profile(self, sample_user, sample_profile):
        """Test getting user profile"""
        from backend.api.tenderator import get_my_profile

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_profile
        mock_db.query.return_value = mock_query

        result = await get_my_profile(
            current_user=sample_user,
            db=mock_db
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, sample_user):
        """Test getting non-existent profile"""
        from backend.api.tenderator import get_my_profile

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_my_profile(
                current_user=sample_user,
                db=mock_db
            )

        assert exc_info.value.status_code == 404


# ============================================================================
# Match Endpoint Tests
# ============================================================================

class TestMatchEndpoints:
    """Tests for match endpoints"""

    @pytest.mark.asyncio
    async def test_get_matches(self, sample_user, sample_match, sample_tender):
        """Test getting user matches"""
        from backend.api.tenderator import get_my_matches

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_db.query.return_value = mock_query

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_user_matches.return_value = [sample_match]
            mock_service.get_tender.return_value = sample_tender

            result = await get_my_matches(
                current_user=sample_user,
                service=mock_service,
                db=mock_db
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_save_match(self, sample_user, sample_match):
        """Test saving a match"""
        from backend.api.tenderator import save_match

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            sample_match.is_saved = True
            mock_service.save_match.return_value = sample_match

            result = await save_match(
                match_id=1,
                current_user=sample_user,
                service=mock_service
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_dismiss_match(self, sample_user, sample_match):
        """Test dismissing a match"""
        from backend.api.tenderator import dismiss_match

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            sample_match.is_dismissed = True
            mock_service.dismiss_match.return_value = sample_match

            result = await dismiss_match(
                match_id=1,
                current_user=sample_user,
                service=mock_service
            )

            assert result is not None


# ============================================================================
# Statistics Endpoint Tests
# ============================================================================

class TestStatisticsEndpoints:
    """Tests for statistics endpoints"""

    @pytest.mark.asyncio
    async def test_get_global_statistics(self):
        """Test getting global tender statistics"""
        from backend.api.tenderator import get_statistics
        from sqlalchemy import func

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.count.return_value = 1000
        mock_query.scalar.return_value = 500000.0
        mock_query.all.return_value = [("BE", 100), ("FR", 80)]
        mock_db.query.return_value = mock_query

        result = await get_statistics(db=mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_user_statistics(self, sample_user):
        """Test getting user-specific statistics"""
        from backend.api.tenderator import get_my_statistics
        from sqlalchemy import func

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.scalar.return_value = 75.5
        mock_db.query.return_value = mock_query

        result = await get_my_statistics(
            current_user=sample_user,
            db=mock_db
        )

        assert result is not None


# ============================================================================
# SME Score Endpoint Tests
# ============================================================================

class TestSMEScoreEndpoint:
    """Tests for SME score endpoint"""

    @pytest.mark.asyncio
    async def test_get_sme_score(self, sample_tender):
        """Test getting SME suitability score"""
        from backend.api.tenderator import get_sme_score

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_sme_score_for_tender.return_value = {
                'score': 75,
                'breakdown': {
                    'value_score': 20,
                    'procedure_score': 25,
                    'deadline_score': 15,
                    'lot_score': 15
                },
                'recommendations': ["Good fit for small companies"]
            }

            result = await get_sme_score(
                tender_id=1,
                company_size="small",
                service=mock_service
            )

            assert result is not None
            assert 'score' in result

    @pytest.mark.asyncio
    async def test_get_sme_score_tender_not_found(self):
        """Test SME score for non-existent tender"""
        from backend.api.tenderator import get_sme_score

        with patch('backend.api.tenderator.TenderService') as MockService:
            mock_service = MockService.return_value
            mock_service.get_sme_score_for_tender.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_sme_score(
                    tender_id=999,
                    company_size="small",
                    service=mock_service
                )

            assert exc_info.value.status_code == 404


# ============================================================================
# Health Check Tests
# ============================================================================

class TestHealthCheck:
    """Tests for health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check returns healthy status"""
        from backend.api.tenderator import health_check

        result = await health_check()

        assert result['status'] == 'healthy'
        assert 'timestamp' in result
        assert result['service'] == 'Tenderator API'
