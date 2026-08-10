"""
Test Configuration and Fixtures

Shared pytest fixtures for all tests.
Part of Phase 11: Testing
"""

import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from datetime import datetime

# Configure asyncio event loop for tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# HTTP Client Mocks
# ============================================================================

@pytest.fixture
def mock_http_response():
    """Mock HTTP response"""
    mock_response = Mock()
    mock_response.status = 200
    mock_response.headers = {'content-type': 'application/json'}

    async def json():
        return {'data': 'test'}

    async def text():
        return 'test response'

    mock_response.json = json
    mock_response.text = text
    return mock_response


@pytest.fixture
def mock_aiohttp_session(mock_http_response):
    """Mock aiohttp session"""
    session = AsyncMock(spec=aiohttp.ClientSession)

    async def mock_get(*args, **kwargs):
        return mock_http_response

    async def mock_post(*args, **kwargs):
        return mock_http_response

    session.get = mock_get
    session.post = mock_post
    session.close = AsyncMock()

    return session


# ============================================================================
# API Response Fixtures
# ============================================================================

@pytest.fixture
def sample_mep_data():
    """Sample MEP data"""
    return {
        'id': 'http://data.europarl.europa.eu/person/123',
        'name': 'Test MEP',
        'country': 'BE',
        'group': 'http://data.europarl.europa.eu/group/EPP'
    }


@pytest.fixture
def sample_eurlex_document():
    """Sample EUR-Lex document"""
    return {
        'uri': 'http://data.europa.eu/eli/reg/2016/679',
        'title': 'General Data Protection Regulation',
        'date': '2016-04-27',
        'subject': 'Data protection'
    }


@pytest.fixture
def sample_rss_feed():
    """Sample RSS feed XML"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.eu/feed</link>
            <item>
                <title>Test Article</title>
                <link>https://example.eu/article/1</link>
                <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                <description>Test description</description>
            </item>
        </channel>
    </rss>
    """


@pytest.fixture
def sample_sparql_results():
    """Sample SPARQL query results"""
    return """<?xml version="1.0"?>
    <sparql xmlns="http://www.w3.org/2005/sparql-results#">
        <head>
            <variable name="doc"/>
            <variable name="title"/>
        </head>
        <results>
            <result>
                <binding name="doc">
                    <uri>http://example.eu/doc/1</uri>
                </binding>
                <binding name="title">
                    <literal>Test Document</literal>
                </binding>
            </result>
        </results>
    </sparql>
    """


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    session.flush = Mock()
    return session


@pytest.fixture
def sample_rss_feed_model():
    """Sample RSSFeed model instance"""
    from models.rss_feed import RSSFeed
    from uuid import uuid4

    feed = RSSFeed(
        id=uuid4(),
        name="Test Feed",
        url="https://example.eu/feed.xml",
        source="test_source",
        category="test_category",
        is_active=True
    )
    return feed


@pytest.fixture
def sample_rss_entry_model():
    """Sample RSSEntry model instance"""
    from models.rss_entry import RSSEntry
    from uuid import uuid4

    entry = RSSEntry(
        id=uuid4(),
        feed_id=uuid4(),
        guid="test-guid-123",
        link="https://example.eu/article/1",
        title="Test Article",
        summary="Test summary",
        published_at=datetime.now()
    )
    return entry


# ============================================================================
# Service Fixtures
# ============================================================================

@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter"""
    limiter = AsyncMock()
    limiter.acquire = AsyncMock(return_value=True)
    limiter.get_stats = Mock(return_value={})
    return limiter


@pytest.fixture
def mock_cache():
    """Mock API cache"""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock(return_value=True)
    cache.delete = Mock(return_value=True)
    cache.get_stats = Mock(return_value={'hits': 0, 'misses': 0})
    return cache


@pytest.fixture
def mock_error_handler():
    """Mock error handler"""
    handler = AsyncMock()
    handler.handle_error = AsyncMock(return_value=(True, {'data': 'test'}, None))
    handler.get_error_statistics = Mock(return_value={})
    return handler


# ============================================================================
# Scraper Fixtures
# ============================================================================

@pytest.fixture
async def mock_ep_scraper():
    """Mock European Parliament scraper"""
    scraper = AsyncMock()
    scraper.get_all_meps = AsyncMock(return_value=[])
    scraper.get_mep_details = AsyncMock(return_value={})
    scraper.search = AsyncMock(return_value=[])
    scraper.close = AsyncMock()
    return scraper


@pytest.fixture
async def mock_eurlex_scraper():
    """Mock EUR-Lex scraper"""
    scraper = AsyncMock()
    scraper.get_document_by_celex = AsyncMock(return_value=None)
    scraper.search_legislation = AsyncMock(return_value=[])
    scraper.close = AsyncMock()
    return scraper


# ============================================================================
# Test Data Generators
# ============================================================================

def generate_mep_list(count: int = 10):
    """Generate list of test MEPs"""
    return [
        {
            'id': f'http://data.europarl.europa.eu/person/{i}',
            'name': f'Test MEP {i}',
            'country': 'BE',
            'group': 'http://data.europarl.europa.eu/group/EPP'
        }
        for i in range(count)
    ]


def generate_rss_entries(count: int = 50):
    """Generate list of test RSS entries"""
    from datetime import timedelta
    base_date = datetime.now()

    return [
        {
            'id': f'entry-{i}',
            'title': f'Test Article {i}',
            'link': f'https://example.eu/article/{i}',
            'published': (base_date - timedelta(hours=i)).isoformat(),
            'summary': f'Test summary {i}'
        }
        for i in range(count)
    ]


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as load test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
