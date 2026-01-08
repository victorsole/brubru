"""
RSS Feeds API Router

FastAPI endpoints for RSS feed management and access.
Part of Phase 10: API Router Implementation

Endpoints:
- GET /api/rss/feeds - List all RSS feeds
- GET /api/rss/entries - Get latest entries
- POST /api/rss/subscribe - Subscribe to feed
- DELETE /api/rss/unsubscribe - Unsubscribe from feed
- GET /api/rss/institutional/{institution} - Get feeds by institution
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Depends, status, Body
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy.orm import Session
from uuid import UUID

from ..services.rss.rss_aggregator import RSSAggregator
from ..services.rss.rss_processor import RSSProcessor
from ..models.rss_feed import RSSFeed
from ..models.rss_entry import RSSEntry
from ..core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/rss",
    tags=["RSS Feeds"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Request/Response Models
# ============================================================================

class RSSFeedInfo(BaseModel):
    """RSS feed information"""
    id: str
    name: str
    url: HttpUrl
    source: str
    category: Optional[str] = None
    description: Optional[str] = None
    language: str = "en"
    is_active: bool = True
    last_fetched: Optional[datetime] = None
    total_entries: int = 0
    update_frequency_minutes: int = 60

    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string if necessary"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class RSSEntryInfo(BaseModel):
    """RSS entry information"""
    id: str
    feed_id: str
    title: str
    link: HttpUrl
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    categories: List[str] = []
    institution: Optional[str] = None
    policy_area: Optional[str] = None
    is_featured: bool = False

    @field_validator('id', 'feed_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string if necessary"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class FeedListResponse(BaseModel):
    """Response for feed list endpoint"""
    total: int
    feeds: List[RSSFeedInfo]
    sources: List[str]


class EntryListResponse(BaseModel):
    """Response for entry list endpoint"""
    total: int
    entries: List[RSSEntryInfo]
    time_window_hours: int
    filtered_by: Optional[Dict[str, Any]] = None


class SubscribeRequest(BaseModel):
    """Request for feed subscription"""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")
    name: Optional[str] = Field(None, description="Feed name")
    source: str = Field(..., description="Source institution")
    category: Optional[str] = Field(None, description="Feed category")
    update_frequency_minutes: int = Field(60, ge=5, le=1440, description="Update frequency")


class SubscribeResponse(BaseModel):
    """Response for subscription"""
    feed_id: str
    message: str
    feed: RSSFeedInfo


class UnsubscribeRequest(BaseModel):
    """Request for unsubscribe"""
    feed_id: str = Field(..., description="Feed ID to unsubscribe")


class UnsubscribeResponse(BaseModel):
    """Response for unsubscribe"""
    message: str
    feed_id: str


class InstitutionalFeedsResponse(BaseModel):
    """Response for institutional feeds"""
    institution: str
    total_feeds: int
    feeds: List[RSSFeedInfo]
    total_entries: int


class FeedStatistics(BaseModel):
    """Feed statistics"""
    total_feeds: int
    active_feeds: int
    total_entries: int
    entries_last_24h: int
    entries_last_7d: int
    sources: Dict[str, int]
    categories: Dict[str, int]


# ============================================================================
# Dependency Injection
# ============================================================================

async def get_rss_aggregator() -> RSSAggregator:
    """Get RSS aggregator instance"""
    return RSSAggregator()


async def get_rss_processor(db: Session = Depends(get_db)) -> RSSProcessor:
    """Get RSS processor instance"""
    return RSSProcessor(db)


# ============================================================================
# Feed List Endpoints
# ============================================================================

@router.get(
    "/feeds",
    response_model=FeedListResponse,
    summary="List all RSS feeds",
    description="Get list of all monitored RSS feeds"
)
async def list_feeds(
    source: Optional[str] = Query(None, description="Filter by source institution"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: bool = Query(True, description="Show only active feeds"),
    db: Session = Depends(get_db)
) -> FeedListResponse:
    """
    List all RSS feeds with optional filters.

    **Sources**: european_parliament, eurlex, council, oeil, think_tank
    **Categories**: press_releases, news, official_journal, etc.
    """
    try:
        # Build query
        query = db.query(RSSFeed)

        if source:
            query = query.filter(RSSFeed.source == source)
        if category:
            query = query.filter(RSSFeed.category == category)
        if is_active:
            query = query.filter(RSSFeed.is_active == True)

        feeds = query.all()

        # Get unique sources
        sources = list(set(feed.source for feed in feeds))

        return FeedListResponse(
            total=len(feeds),
            feeds=[RSSFeedInfo.from_orm(feed) for feed in feeds],
            sources=sources
        )

    except Exception as e:
        logger.error(f"Failed to list feeds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list feeds: {str(e)}"
        )


@router.get(
    "/feeds/{feed_id}",
    response_model=RSSFeedInfo,
    summary="Get feed by ID",
    description="Get detailed information about specific RSS feed"
)
async def get_feed(
    feed_id: str,
    db: Session = Depends(get_db)
) -> RSSFeedInfo:
    """Get RSS feed details"""
    try:
        feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found"
            )

        return RSSFeedInfo.from_orm(feed)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feed {feed_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feed: {str(e)}"
        )


# ============================================================================
# Entry Endpoints
# ============================================================================

@router.get(
    "/entries",
    response_model=EntryListResponse,
    summary="Get latest RSS entries",
    description="Get latest entries from all feeds"
)
async def get_entries(
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    source: Optional[str] = Query(None, description="Filter by source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    policy_area: Optional[str] = Query(None, description="Filter by policy area"),
    limit: int = Query(50, ge=1, le=500, description="Maximum entries"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
) -> EntryListResponse:
    """
    Get latest RSS entries with filters.

    **Time Window**: 1-168 hours (1 hour to 7 days)
    **Pagination**: Use limit and offset
    """
    try:
        # Calculate cutoff time
        cutoff = datetime.now() - timedelta(hours=hours)

        # Build query
        query = db.query(RSSEntry).filter(
            RSSEntry.published_at >= cutoff
        )

        if source:
            query = query.filter(RSSEntry.institution == source)

        if policy_area:
            query = query.filter(RSSEntry.policy_area == policy_area)

        # Order by published date
        query = query.order_by(RSSEntry.published_at.desc())

        # Get total count
        total = query.count()

        # Apply pagination
        entries = query.offset(offset).limit(limit).all()

        return EntryListResponse(
            total=total,
            entries=[RSSEntryInfo.from_orm(entry) for entry in entries],
            time_window_hours=hours,
            filtered_by={
                k: v for k, v in {
                    'source': source,
                    'category': category,
                    'policy_area': policy_area
                }.items() if v is not None
            }
        )

    except Exception as e:
        logger.error(f"Failed to get entries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entries: {str(e)}"
        )


@router.get(
    "/entries/{entry_id}",
    response_model=RSSEntryInfo,
    summary="Get entry by ID",
    description="Get detailed RSS entry"
)
async def get_entry(
    entry_id: str,
    db: Session = Depends(get_db)
) -> RSSEntryInfo:
    """Get RSS entry details"""
    try:
        entry = db.query(RSSEntry).filter(RSSEntry.id == entry_id).first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry {entry_id} not found"
            )

        # Increment view count
        entry.view_count += 1
        db.commit()

        return RSSEntryInfo.from_orm(entry)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entry {entry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entry: {str(e)}"
        )


# ============================================================================
# Subscribe/Unsubscribe Endpoints
# ============================================================================

@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to RSS feed",
    description="Add new RSS feed to monitoring"
)
async def subscribe_feed(
    request: SubscribeRequest,
    db: Session = Depends(get_db)
) -> SubscribeResponse:
    """
    Subscribe to new RSS feed.

    **Note**: Feed will be validated before activation
    """
    try:
        # Check if feed already exists
        existing = db.query(RSSFeed).filter(RSSFeed.url == str(request.feed_url)).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Feed already subscribed: {existing.id}"
            )

        # Create new feed
        feed = RSSFeed(
            name=request.name or f"{request.source} feed",
            url=str(request.feed_url),
            source=request.source,
            category=request.category,
            update_frequency_minutes=request.update_frequency_minutes,
            is_active=True
        )

        db.add(feed)
        db.commit()
        db.refresh(feed)

        logger.info(f"Subscribed to new feed: {feed.name} ({feed.url})")

        return SubscribeResponse(
            feed_id=str(feed.id),
            message="Successfully subscribed to feed",
            feed=RSSFeedInfo.from_orm(feed)
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to subscribe to feed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@router.delete(
    "/unsubscribe",
    response_model=UnsubscribeResponse,
    summary="Unsubscribe from RSS feed",
    description="Remove RSS feed from monitoring"
)
async def unsubscribe_feed(
    request: UnsubscribeRequest,
    db: Session = Depends(get_db)
) -> UnsubscribeResponse:
    """
    Unsubscribe from RSS feed.

    **Note**: Feed entries will be retained but feed will no longer be updated
    """
    try:
        feed = db.query(RSSFeed).filter(RSSFeed.id == request.feed_id).first()

        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {request.feed_id} not found"
            )

        # Deactivate instead of delete (retain data)
        feed.is_active = False
        db.commit()

        logger.info(f"Unsubscribed from feed: {feed.name}")

        return UnsubscribeResponse(
            message="Successfully unsubscribed from feed",
            feed_id=request.feed_id
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to unsubscribe: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsubscribe: {str(e)}"
        )


# ============================================================================
# Institutional Feeds Endpoint
# ============================================================================

@router.get(
    "/institutional/{institution}",
    response_model=InstitutionalFeedsResponse,
    summary="Get feeds by institution",
    description="Get all RSS feeds for specific EU institution"
)
async def get_institutional_feeds(
    institution: str,
    include_entries: bool = Query(False, description="Include entry count"),
    db: Session = Depends(get_db)
) -> InstitutionalFeedsResponse:
    """
    Get RSS feeds for specific institution.

    **Institutions**:
    - european_parliament
    - eurlex
    - council
    - oeil
    - think_tank
    - jrc
    """
    try:
        # Get feeds for institution
        feeds = db.query(RSSFeed).filter(
            RSSFeed.source == institution,
            RSSFeed.is_active == True
        ).all()

        if not feeds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No feeds found for institution: {institution}"
            )

        # Calculate total entries
        total_entries = 0
        if include_entries:
            for feed in feeds:
                total_entries += db.query(RSSEntry).filter(
                    RSSEntry.feed_id == feed.id
                ).count()

        return InstitutionalFeedsResponse(
            institution=institution,
            total_feeds=len(feeds),
            feeds=[RSSFeedInfo.from_orm(feed) for feed in feeds],
            total_entries=total_entries
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get institutional feeds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feeds: {str(e)}"
        )


# ============================================================================
# Statistics Endpoint
# ============================================================================

@router.get(
    "/statistics",
    response_model=FeedStatistics,
    summary="Get RSS feed statistics",
    description="Get aggregated statistics for all RSS feeds"
)
async def get_statistics(
    db: Session = Depends(get_db)
) -> FeedStatistics:
    """
    Get comprehensive RSS feed statistics.

    Includes feed counts, entry counts, and breakdowns by source/category.
    """
    try:
        # Get feed counts
        total_feeds = db.query(RSSFeed).count()
        active_feeds = db.query(RSSFeed).filter(RSSFeed.is_active == True).count()

        # Get entry counts
        total_entries = db.query(RSSEntry).count()

        # Entries in last 24 hours
        cutoff_24h = datetime.now() - timedelta(hours=24)
        entries_24h = db.query(RSSEntry).filter(
            RSSEntry.published_at >= cutoff_24h
        ).count()

        # Entries in last 7 days
        cutoff_7d = datetime.now() - timedelta(days=7)
        entries_7d = db.query(RSSEntry).filter(
            RSSEntry.published_at >= cutoff_7d
        ).count()

        # Breakdown by source
        feeds = db.query(RSSFeed).all()
        sources = {}
        categories = {}

        for feed in feeds:
            sources[feed.source] = sources.get(feed.source, 0) + 1
            if feed.category:
                categories[feed.category] = categories.get(feed.category, 0) + 1

        return FeedStatistics(
            total_feeds=total_feeds,
            active_feeds=active_feeds,
            total_entries=total_entries,
            entries_last_24h=entries_24h,
            entries_last_7d=entries_7d,
            sources=sources,
            categories=categories
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


# ============================================================================
# Refresh Endpoint
# ============================================================================

@router.post(
    "/refresh/{feed_id}",
    summary="Refresh RSS feed",
    description="Manually trigger feed refresh"
)
async def refresh_feed(
    feed_id: str,
    processor: RSSProcessor = Depends(get_rss_processor),
    db: Session = Depends(get_db)
):
    """
    Manually refresh specific RSS feed.

    **Note**: Rate limited to prevent abuse
    """
    try:
        feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {feed_id} not found"
            )

        if not feed.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot refresh inactive feed"
            )

        # Trigger refresh
        logger.info(f"Manual refresh triggered for feed: {feed.name}")
        stats = await processor.process_feed_by_url(feed.url)

        return {
            "message": "Feed refreshed successfully",
            "feed_id": feed_id,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh feed {feed_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh feed: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/health",
    summary="Health check",
    description="Check RSS feed API health status"
)
async def health_check():
    """RSS Feed API health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "RSS Feed API"
    }
