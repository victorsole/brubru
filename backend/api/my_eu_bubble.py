"""
My EU Bubble API Router

FastAPI endpoints for user's personalized EU intelligence hub.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure

Endpoints:
- GET /api/bubble/feeds - Get user's subscribed feeds with latest entries
- POST /api/bubble/subscriptions - Subscribe to feed
- DELETE /api/bubble/subscriptions/{subscription_id} - Unsubscribe
- GET /api/bubble/subscriptions - List user's subscriptions
- POST /api/bubble/entries/{entry_id}/read - Mark entry as read
- POST /api/bubble/entries/{entry_id}/save - Save/bookmark entry
- DELETE /api/bubble/saved/{saved_id} - Remove saved entry
- GET /api/bubble/saved - Get user's saved entries
- GET /api/bubble/stats - Get user's engagement statistics
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func

from models.user import User
from models.rss_feed import RSSFeed
from models.rss_entry import RSSEntry
from models.user_feed_subscription import UserFeedSubscription
from models.user_feed_read import UserFeedRead
from models.user_saved_entry import UserSavedEntry
from schemas.rss_schemas import (
    RSSEntryResponse,
    RSSEntryListResponse,
    UserFeedSubscriptionCreate,
    UserFeedSubscriptionResponse,
    MarkAsReadRequest,
    SaveEntryRequest,
    UpdateSavedEntryRequest,
    UserSavedEntryResponse,
    FeedFilterParams,
    FeedStatsResponse,
    UserEngagementStats,
)
from core.database import get_db
from api.auth_optional import get_current_user_dev as get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/bubble",
    tags=["My EU Bubble"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Feed Subscriptions
# ============================================================================

@router.post(
    "/subscriptions",
    response_model=UserFeedSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to RSS feed",
    description="Subscribe user to an RSS feed for My EU Bubble"
)
async def subscribe_to_feed(
    subscription: UserFeedSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserFeedSubscriptionResponse:
    """
    Subscribe to an RSS feed.

    The feed will appear in the user's My EU Bubble news sidebar.
    """
    try:
        # Check if feed exists
        feed = db.query(RSSFeed).filter(RSSFeed.id == subscription.feed_id).first()
        if not feed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed {subscription.feed_id} not found"
            )

        # Check if already subscribed
        existing = db.query(UserFeedSubscription).filter(
            and_(
                UserFeedSubscription.user_id == current_user.id,
                UserFeedSubscription.feed_id == subscription.feed_id
            )
        ).first()

        if existing:
            # Reactivate if previously deactivated
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
                return UserFeedSubscriptionResponse.from_orm(existing)

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Already subscribed to this feed"
            )

        # Create subscription
        new_subscription = UserFeedSubscription(
            user_id=current_user.id,
            feed_id=subscription.feed_id,
            is_active=True,
            notification_enabled=subscription.notification_enabled
        )

        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)

        logger.info(f"User {current_user.email} subscribed to feed {feed.name}")

        return UserFeedSubscriptionResponse.from_orm(new_subscription)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to subscribe: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@router.get(
    "/subscriptions",
    response_model=List[UserFeedSubscriptionResponse],
    summary="List user's subscriptions",
    description="Get all RSS feeds user is subscribed to"
)
async def list_subscriptions(
    active_only: bool = Query(True, description="Show only active subscriptions"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[UserFeedSubscriptionResponse]:
    """List user's feed subscriptions"""
    try:
        query = db.query(UserFeedSubscription).filter(
            UserFeedSubscription.user_id == current_user.id
        )

        if active_only:
            query = query.filter(UserFeedSubscription.is_active == True)

        subscriptions = query.all()

        # Load feed details for each subscription
        result = []
        for sub in subscriptions:
            sub_dict = UserFeedSubscriptionResponse.from_orm(sub)
            feed = db.query(RSSFeed).filter(RSSFeed.id == sub.feed_id).first()
            if feed:
                sub_dict.feed = feed
            result.append(sub_dict)

        return result

    except Exception as e:
        logger.error(f"Failed to list subscriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list subscriptions: {str(e)}"
        )


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=UserFeedSubscriptionResponse,
    summary="Update subscription",
    description="Update subscription settings"
)
async def update_subscription(
    subscription_id: UUID,
    is_active: Optional[bool] = None,
    notification_enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserFeedSubscriptionResponse:
    """Update subscription settings"""
    try:
        subscription = db.query(UserFeedSubscription).filter(
            and_(
                UserFeedSubscription.id == subscription_id,
                UserFeedSubscription.user_id == current_user.id
            )
        ).first()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        if is_active is not None:
            subscription.is_active = is_active
        if notification_enabled is not None:
            subscription.notification_enabled = notification_enabled

        db.commit()
        db.refresh(subscription)

        return UserFeedSubscriptionResponse.from_orm(subscription)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}"
        )


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe from feed",
    description="Remove feed subscription"
)
async def unsubscribe_from_feed(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unsubscribe from RSS feed"""
    try:
        subscription = db.query(UserFeedSubscription).filter(
            and_(
                UserFeedSubscription.id == subscription_id,
                UserFeedSubscription.user_id == current_user.id
            )
        ).first()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        db.delete(subscription)
        db.commit()

        logger.info(f"User {current_user.email} unsubscribed from feed")

        return None

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
# Feed Entries with Read/Unread Status
# ============================================================================

@router.get(
    "/feeds",
    response_model=RSSEntryListResponse,
    summary="Get user's feed entries",
    description="Get RSS entries from user's subscribed feeds with read/unread status"
)
async def get_user_feeds(
    sources: Optional[List[str]] = Query(None, description="Filter by sources"),
    unread_only: bool = Query(False, description="Show only unread entries"),
    from_date: Optional[datetime] = Query(None, description="Filter from date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> RSSEntryListResponse:
    """
    Get feed entries from user's subscribed feeds.

    Includes read/unread status for each entry.
    """
    try:
        # Get user's subscribed feed IDs
        subscribed_feeds = db.query(UserFeedSubscription.feed_id).filter(
            and_(
                UserFeedSubscription.user_id == current_user.id,
                UserFeedSubscription.is_active == True
            )
        ).all()

        feed_ids = [f[0] for f in subscribed_feeds]

        if not feed_ids:
            return RSSEntryListResponse(
                entries=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

        # Build query for entries
        query = db.query(RSSEntry).filter(RSSEntry.feed_id.in_(feed_ids))

        # Apply filters
        if sources:
            query = query.filter(RSSEntry.institution.in_(sources))

        if from_date:
            query = query.filter(RSSEntry.published_at >= from_date)

        # Filter unread if requested
        if unread_only:
            # Get read entry IDs
            read_entry_ids = db.query(UserFeedRead.rss_entry_id).filter(
                UserFeedRead.user_id == current_user.id
            ).all()
            read_ids = [r[0] for r in read_entry_ids]

            if read_ids:
                query = query.filter(~RSSEntry.id.in_(read_ids))

        # Order by published date
        query = query.order_by(RSSEntry.published_at.desc())

        # Get total count
        total = query.count()

        # Apply pagination
        entries = query.offset(offset).limit(limit).all()

        # Get read status for entries
        entry_ids = [e.id for e in entries]
        read_entries = db.query(UserFeedRead.rss_entry_id).filter(
            and_(
                UserFeedRead.user_id == current_user.id,
                UserFeedRead.rss_entry_id.in_(entry_ids)
            )
        ).all()
        read_entry_ids = {r[0] for r in read_entries}

        # Get saved status
        saved_entries = db.query(UserSavedEntry.rss_entry_id).filter(
            and_(
                UserSavedEntry.user_id == current_user.id,
                UserSavedEntry.rss_entry_id.in_(entry_ids)
            )
        ).all()
        saved_entry_ids = {s[0] for s in saved_entries}

        # Build response with status flags
        response_entries = []
        for entry in entries:
            entry_data = RSSEntryResponse.from_orm(entry)
            entry_data.is_read = entry.id in read_entry_ids
            entry_data.is_saved = entry.id in saved_entry_ids
            response_entries.append(entry_data)

        return RSSEntryListResponse(
            entries=response_entries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(entries)) < total
        )

    except Exception as e:
        logger.error(f"Failed to get user feeds: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feeds: {str(e)}"
        )


# ============================================================================
# Read Tracking
# ============================================================================

@router.post(
    "/entries/{entry_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark entry as read",
    description="Mark RSS entry as read by user"
)
async def mark_entry_as_read(
    entry_id: UUID,
    read_data: Optional[MarkAsReadRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark entry as read"""
    try:
        # Check if entry exists
        entry = db.query(RSSEntry).filter(RSSEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )

        # Check if already read
        existing = db.query(UserFeedRead).filter(
            and_(
                UserFeedRead.user_id == current_user.id,
                UserFeedRead.rss_entry_id == entry_id
            )
        ).first()

        if existing:
            # Update read count and reading time
            existing.increment_read_count()
            if read_data and read_data.reading_time_seconds:
                existing.reading_time_seconds = read_data.reading_time_seconds
            if read_data and read_data.clicked_link:
                existing.clicked_link = 1  # Integer type: 1 for True
        else:
            # Create new read record
            read_record = UserFeedRead(
                user_id=current_user.id,
                rss_entry_id=entry_id,
                reading_time_seconds=read_data.reading_time_seconds if read_data else None,
                clicked_link=1 if (read_data and read_data.clicked_link) else 0  # Integer type: 0 or 1
            )
            db.add(read_record)

            # Increment view count on entry
            entry.view_count += 1

        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to mark as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark as read: {str(e)}"
        )


# ============================================================================
# Saved Entries / Bookmarks
# ============================================================================

@router.post(
    "/entries/{entry_id}/save",
    response_model=UserSavedEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save/bookmark entry",
    description="Save RSS entry to user's collection"
)
async def save_entry(
    entry_id: UUID,
    save_data: SaveEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserSavedEntryResponse:
    """Save/bookmark an RSS entry"""
    try:
        # Check if entry exists
        entry = db.query(RSSEntry).filter(RSSEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )

        # Check if already saved
        existing = db.query(UserSavedEntry).filter(
            and_(
                UserSavedEntry.user_id == current_user.id,
                UserSavedEntry.rss_entry_id == entry_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entry already saved"
            )

        # Create saved entry
        saved = UserSavedEntry(
            user_id=current_user.id,
            rss_entry_id=entry_id,
            notes=save_data.notes,
            tags=save_data.tags,
            collection_name=save_data.collection_name,
            is_starred=save_data.is_starred
        )

        db.add(saved)

        # Increment save count on entry
        entry.save_count += 1

        db.commit()
        db.refresh(saved)

        logger.info(f"User {current_user.email} saved entry {entry_id}")

        return UserSavedEntryResponse.from_orm(saved)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save entry: {str(e)}"
        )


@router.get(
    "/saved",
    response_model=List[UserSavedEntryResponse],
    summary="Get saved entries",
    description="Get user's saved/bookmarked entries"
)
async def get_saved_entries(
    collection: Optional[str] = Query(None, description="Filter by collection"),
    starred_only: bool = Query(False, description="Show only starred entries"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[UserSavedEntryResponse]:
    """Get user's saved entries"""
    try:
        query = db.query(UserSavedEntry).filter(
            UserSavedEntry.user_id == current_user.id
        )

        if collection:
            query = query.filter(UserSavedEntry.collection_name == collection)

        if starred_only:
            query = query.filter(UserSavedEntry.is_starred == True)

        if tags:
            # Filter by tags (PostgreSQL array contains)
            for tag in tags:
                query = query.filter(UserSavedEntry.tags.contains([tag]))

        query = query.order_by(UserSavedEntry.saved_at.desc())
        saved_entries = query.offset(offset).limit(limit).all()

        # Load entry details
        result = []
        for saved in saved_entries:
            saved_dict = UserSavedEntryResponse.from_orm(saved)
            entry = db.query(RSSEntry).filter(RSSEntry.id == saved.rss_entry_id).first()
            if entry:
                saved_dict.entry = RSSEntryResponse.from_orm(entry)
            result.append(saved_dict)

        return result

    except Exception as e:
        logger.error(f"Failed to get saved entries: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get saved entries: {str(e)}"
        )


@router.patch(
    "/saved/{saved_id}",
    response_model=UserSavedEntryResponse,
    summary="Update saved entry",
    description="Update notes, tags, or collection for saved entry"
)
async def update_saved_entry(
    saved_id: UUID,
    update_data: UpdateSavedEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserSavedEntryResponse:
    """Update saved entry metadata"""
    try:
        saved = db.query(UserSavedEntry).filter(
            and_(
                UserSavedEntry.id == saved_id,
                UserSavedEntry.user_id == current_user.id
            )
        ).first()

        if not saved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved entry not found"
            )

        if update_data.notes is not None:
            saved.notes = update_data.notes
        if update_data.tags is not None:
            saved.tags = update_data.tags
        if update_data.collection_name is not None:
            saved.collection_name = update_data.collection_name
        if update_data.is_starred is not None:
            saved.is_starred = update_data.is_starred

        db.commit()
        db.refresh(saved)

        return UserSavedEntryResponse.from_orm(saved)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update saved entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update saved entry: {str(e)}"
        )


@router.delete(
    "/saved/{saved_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove saved entry",
    description="Remove entry from saved collection"
)
async def delete_saved_entry(
    saved_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove saved entry"""
    try:
        saved = db.query(UserSavedEntry).filter(
            and_(
                UserSavedEntry.id == saved_id,
                UserSavedEntry.user_id == current_user.id
            )
        ).first()

        if not saved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved entry not found"
            )

        # Decrement save count on entry
        entry = db.query(RSSEntry).filter(RSSEntry.id == saved.rss_entry_id).first()
        if entry and entry.save_count > 0:
            entry.save_count -= 1

        db.delete(saved)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete saved entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete saved entry: {str(e)}"
        )


# ============================================================================
# User Statistics
# ============================================================================

@router.get(
    "/stats",
    response_model=UserEngagementStats,
    summary="Get user engagement statistics",
    description="Get statistics about user's RSS feed engagement"
)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserEngagementStats:
    """Get user's engagement statistics"""
    try:
        # Count subscriptions
        total_subs = db.query(UserFeedSubscription).filter(
            UserFeedSubscription.user_id == current_user.id
        ).count()

        active_subs = db.query(UserFeedSubscription).filter(
            and_(
                UserFeedSubscription.user_id == current_user.id,
                UserFeedSubscription.is_active == True
            )
        ).count()

        # Count reads and saves
        total_reads = db.query(UserFeedRead).filter(
            UserFeedRead.user_id == current_user.id
        ).count()

        total_saves = db.query(UserSavedEntry).filter(
            UserSavedEntry.user_id == current_user.id
        ).count()

        # Calculate average reading time
        avg_reading_time = db.query(
            func.avg(UserFeedRead.reading_time_seconds)
        ).filter(
            and_(
                UserFeedRead.user_id == current_user.id,
                UserFeedRead.reading_time_seconds.isnot(None)
            )
        ).scalar()

        # Get favorite sources (most read)
        favorite_sources_query = db.query(
            RSSEntry.institution,
            func.count(UserFeedRead.id).label('read_count')
        ).join(
            UserFeedRead,
            UserFeedRead.rss_entry_id == RSSEntry.id
        ).filter(
            UserFeedRead.user_id == current_user.id
        ).group_by(
            RSSEntry.institution
        ).order_by(
            func.count(UserFeedRead.id).desc()
        ).limit(5).all()

        favorite_sources = [source for source, count in favorite_sources_query if source]

        # Get most read categories
        most_read_categories_query = db.query(
            func.unnest(RSSEntry.categories).label('category'),
            func.count().label('read_count')
        ).join(
            UserFeedRead,
            UserFeedRead.rss_entry_id == RSSEntry.id
        ).filter(
            UserFeedRead.user_id == current_user.id
        ).group_by(
            'category'
        ).order_by(
            func.count().desc()
        ).limit(5).all()

        most_read_categories = [cat for cat, count in most_read_categories_query if cat]

        return UserEngagementStats(
            total_subscriptions=total_subs,
            active_subscriptions=active_subs,
            total_reads=total_reads,
            total_saves=total_saves,
            average_reading_time_seconds=float(avg_reading_time) if avg_reading_time else None,
            favorite_sources=favorite_sources,
            most_read_categories=most_read_categories
        )

    except Exception as e:
        logger.error(f"Failed to get user stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get(
    "/sources",
    response_model=List[str],
    summary="Get available feed sources",
    description="Get list of unique institutions from subscribed feeds"
)
async def get_available_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[str]:
    """
    Get list of unique sources (institutions) from RSS entries in user's subscribed feeds.
    Used to populate the source filter dropdown.
    """
    try:
        # Get user's subscribed feed IDs
        subscribed_feeds = db.query(UserFeedSubscription.feed_id).filter(
            and_(
                UserFeedSubscription.user_id == current_user.id,
                UserFeedSubscription.is_active == True
            )
        ).all()

        feed_ids = [f[0] for f in subscribed_feeds]

        if not feed_ids:
            return []

        # Get unique institutions from entries in subscribed feeds
        sources = db.query(RSSEntry.institution).distinct().filter(
            and_(
                RSSEntry.feed_id.in_(feed_ids),
                RSSEntry.institution.isnot(None)
            )
        ).all()

        # Extract source names and sort
        source_list = sorted([s[0] for s in sources if s[0]])

        return source_list

    except Exception as e:
        logger.error(f"Failed to get sources: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sources: {str(e)}"
        )


# ============================================================================
# Admin Operations
# ============================================================================

@router.post(
    "/admin/refresh-feeds",
    summary="Refresh RSS feeds database",
    description="Re-seed RSS feeds including EC Newsletters (admin operation)"
)
async def refresh_rss_feeds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh RSS feeds by re-running the seed script.
    This adds new feeds and updates existing ones.
    """
    try:
        from backend.scripts.seed_rss_feeds import seed_rss_feeds

        logger.info(f"User {current_user.email} triggered RSS feed refresh")

        # Run seed in a separate thread to avoid blocking
        import threading

        def run_seed():
            try:
                seed_rss_feeds()
                logger.info("RSS feed refresh completed successfully")
            except Exception as e:
                logger.error(f"RSS feed refresh failed: {str(e)}")

        thread = threading.Thread(target=run_seed)
        thread.start()

        return {
            "message": "RSS feed refresh started",
            "status": "processing",
            "note": "This may take a few moments. Refresh your feed list to see new sources."
        }

    except Exception as e:
        logger.error(f"Failed to start RSS feed refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh feeds: {str(e)}"
        )


# In-memory storage for legislative train scraping jobs
legislative_train_job = {
    "status": "idle",  # idle, running, completed, failed
    "progress": 0,  # 0-100
    "current_step": "",
    "trains_scraped": 0,
    "total_trains": 0,
    "carriages_scraped": 0,
    "total_carriages": 0,
    "started_at": None,
    "completed_at": None,
    "error": None
}


@router.post(
    "/admin/refresh-legislative-trains",
    summary="Refresh Legislative Train data",
    description="Trigger legislative train scraping (admin operation)"
)
async def refresh_legislative_trains(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger scraping of Legislative Train Schedule data.
    This populates the Legislative Tracker with EC priorities.
    """
    global legislative_train_job

    # Check if already running
    if legislative_train_job["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Legislative train scraping is already in progress"
        )

    try:
        from backend.services.scrapers.legislative_train_scheduler import LegislativeTrainScheduler
        from backend.core.database import SessionLocal
        import asyncio

        logger.info(f"User {current_user.email} triggered legislative train refresh")

        # Reset job status
        legislative_train_job.update({
            "status": "running",
            "progress": 0,
            "current_step": "Initializing...",
            "trains_scraped": 0,
            "total_trains": 7,
            "carriages_scraped": 0,
            "total_carriages": 50,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None
        })

        # Run scraper in a separate thread
        import threading

        def run_scraper():
            global legislative_train_job
            db = SessionLocal()

            try:
                from backend.services.scrapers.legislative_train_scraper import LegislativeTrainScraper

                # Create scraper instance
                scraper = LegislativeTrainScraper()

                # Phase 1: Scrape trains
                legislative_train_job["current_step"] = "Fetching legislative trains..."
                legislative_train_job["progress"] = 10

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                trains_data = loop.run_until_complete(scraper.get_all_trains())

                legislative_train_job["trains_scraped"] = len(trains_data)
                legislative_train_job["progress"] = 30

                # Phase 2: Scrape carriages
                legislative_train_job["current_step"] = "Fetching legislative files..."
                carriages_data = loop.run_until_complete(scraper.get_all_carriages())

                # Limit to first 50 for sample
                carriages_data = carriages_data[:50] if len(carriages_data) > 50 else carriages_data
                legislative_train_job["total_carriages"] = len(carriages_data)

                # Save to database
                from backend.models.legislative_train import LegislativeTrain, LegislativeCarriage

                legislative_train_job["current_step"] = "Saving to database..."
                legislative_train_job["progress"] = 50

                # Save trains
                for i, train_data in enumerate(trains_data, 1):
                    priority_number = train_data.get('priority_number')
                    if not priority_number:
                        continue

                    train = db.query(LegislativeTrain).filter(
                        LegislativeTrain.priority_number == priority_number
                    ).first()

                    if train:
                        train.name = train_data.get('name', train.name)
                        train.description = train_data.get('description', train.description)
                        train.total_files = train_data.get('total_files', 0)
                        train.files_by_status = train_data.get('files_by_status', {})
                        train.updated_at = datetime.now()
                    else:
                        train = LegislativeTrain(
                            priority_number=priority_number,
                            name=train_data.get('name', f"Priority {priority_number}"),
                            description=train_data.get('description'),
                            total_files=train_data.get('total_files', 0),
                            files_by_status=train_data.get('files_by_status', {})
                        )
                        db.add(train)

                    legislative_train_job["progress"] = 50 + int((i / len(trains_data)) * 20)

                db.commit()

                # Save carriages
                legislative_train_job["current_step"] = "Saving legislative files..."
                for i, carriage_data in enumerate(carriages_data, 1):
                    file_id = carriage_data.get('id')
                    if not file_id:
                        continue

                    # Find the train this carriage belongs to
                    train_priority = carriage_data.get('train_priority')
                    train = None
                    if train_priority:
                        train = db.query(LegislativeTrain).filter(
                            LegislativeTrain.priority_number == train_priority
                        ).first()

                    carriage = db.query(LegislativeCarriage).filter(
                        LegislativeCarriage.file_id == file_id
                    ).first()

                    if carriage:
                        carriage.title = carriage_data.get('title', carriage.title)
                        carriage.description = carriage_data.get('description', carriage.description)
                        carriage.last_updated = datetime.now()
                        if train:
                            carriage.train_id = train.id
                    else:
                        carriage = LegislativeCarriage(
                            file_id=file_id,
                            train_id=train.id if train else None,
                            title=carriage_data.get('title', 'Untitled'),
                            description=carriage_data.get('description'),
                            current_status=carriage_data.get('status', 'announced')  # Default to 'announced' if no status
                        )
                        db.add(carriage)

                    legislative_train_job["carriages_scraped"] = i
                    legislative_train_job["progress"] = 70 + int((i / len(carriages_data)) * 30)

                db.commit()

                # Complete
                legislative_train_job["status"] = "completed"
                legislative_train_job["progress"] = 100
                legislative_train_job["current_step"] = "Completed successfully"
                legislative_train_job["completed_at"] = datetime.now().isoformat()

                logger.info(f"Legislative train refresh completed: {len(trains_data)} trains, {len(carriages_data)} carriages")

            except Exception as e:
                import traceback
                legislative_train_job["status"] = "failed"
                legislative_train_job["error"] = str(e)
                legislative_train_job["completed_at"] = datetime.now().isoformat()
                logger.error(f"Legislative train refresh failed: {str(e)}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
            finally:
                db.close()

        thread = threading.Thread(target=run_scraper)
        thread.start()

        return {
            "message": "Legislative train refresh started",
            "status": "processing",
            "note": "Check progress via the /admin/legislative-trains-status endpoint"
        }

    except Exception as e:
        legislative_train_job["status"] = "failed"
        legislative_train_job["error"] = str(e)
        logger.error(f"Failed to start legislative train refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh legislative trains: {str(e)}"
        )


@router.get(
    "/admin/legislative-trains-status",
    summary="Get legislative train scraping status",
    description="Check the progress of legislative train scraping"
)
async def get_legislative_trains_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current status and progress of legislative train scraping.
    """
    return legislative_train_job


@router.post(
    "/admin/fetch-entries",
    summary="Fetch new RSS entries",
    description="Fetch latest entries from all active RSS feeds (admin operation)"
)
async def fetch_rss_entries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch latest RSS entries from all active feeds.
    This populates the feed with fresh content.
    """
    try:
        import asyncio
        import feedparser

        logger.info(f"User {current_user.email} triggered RSS entry fetch")

        # Run fetching in a separate thread
        import threading

        def run_fetch():
            try:
                # Get all active feeds
                feeds = db.query(RSSFeed).filter(RSSFeed.is_active == True).all()
                total_entries = 0

                for feed in feeds:
                    try:
                        # Fetch feed
                        parsed = feedparser.parse(
                            feed.url,
                            agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        )

                        entries_added = 0

                        # Process latest 10 entries
                        for entry in parsed.entries[:10]:
                            title = entry.get('title', 'Untitled')
                            link = entry.get('link', '')
                            summary = entry.get('summary', entry.get('description', ''))

                            # Check if entry already exists
                            existing = db.query(RSSEntry).filter(RSSEntry.link == link).first()
                            if existing:
                                continue

                            # Parse published date
                            published_date = None
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                published_date = datetime(*entry.published_parsed[:6])

                            # Create entry
                            new_entry = RSSEntry(
                                feed_id=feed.id,
                                title=title,
                                link=link,
                                summary=summary,
                                content=summary,
                                published_at=published_date,
                                institution=feed.source,
                                categories=[feed.category] if feed.category else []
                            )

                            db.add(new_entry)
                            entries_added += 1

                        db.commit()

                        # Update feed stats
                        feed.last_fetched_at = datetime.now()
                        feed.total_entries += entries_added
                        feed.fetch_success_count += 1
                        db.commit()

                        total_entries += entries_added
                        logger.info(f"Added {entries_added} entries from {feed.name}")

                    except Exception as e:
                        logger.error(f"Error fetching {feed.name}: {str(e)}")
                        feed.fetch_error_count += 1
                        feed.last_error = str(e)
                        feed.last_error_at = datetime.now()
                        db.commit()

                logger.info(f"RSS entry fetch completed. Total entries added: {total_entries}")

            except Exception as e:
                logger.error(f"RSS entry fetch failed: {str(e)}")

        thread = threading.Thread(target=run_fetch)
        thread.start()

        return {
            "message": "RSS entry fetch started",
            "status": "processing",
            "note": "Fetching latest entries from all feeds. This may take a minute. Refresh the page to see new content."
        }

    except Exception as e:
        logger.error(f"Failed to start RSS entry fetch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch entries: {str(e)}"
        )


@router.post(
    "/admin/enrich-entries-ai",
    summary="AI Enrich RSS entries",
    description="Use Hugging Face AI to generate summaries and classify policy areas for RSS entries"
)
async def enrich_entries_with_ai(
    hours: int = Query(24, description="Process entries from last N hours"),
    limit: int = Query(50, description="Maximum entries to process"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Use Hugging Face AI to enrich RSS entries with:
    - AI-generated summaries
    - Policy area classification
    - Entity extraction

    This enhances the quality of content in My EU Bubble.
    """
    try:
        import asyncio
        from services.rss.rss_ai_enrichment import RSSAIEnricher

        logger.info(f"User {current_user.email} triggered AI enrichment (last {hours}h, limit {limit})")

        # Run enrichment asynchronously
        enricher = RSSAIEnricher()
        stats = await enricher.enrich_recent_entries(
            db=db,
            hours=hours,
            only_without_summary=True,
            limit=limit
        )

        logger.info(f"AI enrichment completed: {stats}")

        return {
            "message": f"AI enrichment completed successfully",
            "status": "completed",
            "stats": stats,
            "note": f"Processed {stats['processed']} entries, enriched {stats['enriched']}, failed {stats['failed']}"
        }

    except Exception as e:
        logger.error(f"AI enrichment failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enrich entries: {str(e)}"
        )


# ============================================================================
# LEGISLATIVE TRAINS ENDPOINTS
# ============================================================================

@router.get(
    "/legislative-trains",
    summary="Get all legislative trains",
    description="Fetch all EU Commission priority trains with their legislative files"
)
async def get_legislative_trains(
    include_files: bool = Query(True, description="Include legislative files"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all 7 EU Commission priority trains (2024-2029).

    Returns trains with statistics and optionally their legislative files.
    """
    try:
        from models.legislative_train import LegislativeTrain, LegislativeCarriage

        # Fetch all trains ordered by priority
        trains = db.query(LegislativeTrain).order_by(LegislativeTrain.priority_number).all()

        result = []
        for train in trains:
            train_data = {
                "id": str(train.id),
                "priority_number": train.priority_number,
                "name": train.name,
                "description": train.description,
                "commission_term": train.commission_term,
                "total_files": train.total_files,
                "files_by_status": train.files_by_status,
                "created_at": train.created_at.isoformat() if train.created_at else None,
                "updated_at": train.updated_at.isoformat() if train.updated_at else None,
            }

            if include_files:
                # Get all carriages for this train
                carriages = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.train_id == train.id
                ).all()

                train_data["files"] = [
                    {
                        "id": str(carriage.id),
                        "file_id": carriage.file_id,
                        "title": carriage.title,
                        "description": carriage.description,
                        "current_status": carriage.current_status.value if carriage.current_status else None,
                        "policy_areas": carriage.policy_areas,
                        "ai_summary": carriage.ai_summary,
                        "ai_policy_classifications": carriage.ai_policy_classifications,
                        "enriched_at": carriage.enriched_at.isoformat() if carriage.enriched_at else None,
                        "last_updated": carriage.last_updated.isoformat() if carriage.last_updated else None,
                    }
                    for carriage in carriages
                ]

            result.append(train_data)

        logger.info(f"Returning {len(result)} legislative trains")
        return {"trains": result}

    except Exception as e:
        logger.error(f"Failed to fetch legislative trains: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch legislative trains: {str(e)}"
        )


@router.get(
    "/legislative-files/{file_id}",
    summary="Get legislative file details",
    description="Fetch detailed information about a specific legislative file"
)
async def get_legislative_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a legislative file.

    Includes AI-enriched data, status history, and cross-references.
    """
    try:
        from models.legislative_train import LegislativeCarriage

        # Find carriage by file_id
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.file_id == file_id
        ).first()

        if not carriage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Legislative file {file_id} not found"
            )

        # Build comprehensive response
        result = {
            "id": str(carriage.id),
            "file_id": carriage.file_id,
            "train_id": str(carriage.train_id) if carriage.train_id else None,
            "title": carriage.title,
            "description": carriage.description,

            # Status
            "current_status": carriage.current_status.value if carriage.current_status else None,
            "status_history": carriage.status_history,
            "days_in_current_status": carriage.days_in_current_status,
            "is_blocked": carriage.is_blocked,

            # Cross-references
            "oeil_procedure_ref": carriage.oeil_procedure_ref,
            "celex_numbers": carriage.celex_numbers,
            "legal_text_url": carriage.legal_text_url,

            # Stakeholders
            "lead_committee": carriage.lead_committee,
            "opinion_committees": carriage.opinion_committees,
            "committees": carriage.committees,
            "rapporteur_mep_id": carriage.rapporteur_mep_id,

            # Policy areas
            "policy_areas": carriage.policy_areas,

            # AI enrichment
            "ai_summary": carriage.ai_summary,
            "ai_policy_classifications": carriage.ai_policy_classifications,
            "ai_entities": carriage.ai_entities,

            # Temporal data
            "first_seen": carriage.first_seen.isoformat() if carriage.first_seen else None,
            "last_updated": carriage.last_updated.isoformat() if carriage.last_updated else None,
            "enriched_at": carriage.enriched_at.isoformat() if carriage.enriched_at else None,
            "enrichment_quality": carriage.enrichment_quality,
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch legislative file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch legislative file: {str(e)}"
        )


@router.post(
    "/legislative-files/{file_id}/analyze",
    summary="AI analyze legislative file",
    description="Use Hugging Face AI to analyze a legislative file (British English)"
)
async def analyze_legislative_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    AI-analyze a legislative file using Hugging Face.

    Generates:
    - British English summary
    - Policy area classification (using Brubru's EU policy taxonomy)
    - Entity extraction (MEPs, committees, legislation)
    """
    try:
        from models.legislative_train import LegislativeCarriage
        from services.ai.legislative_file_ai_service import get_legislative_file_ai_service

        # Find carriage
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.file_id == file_id
        ).first()

        if not carriage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Legislative file {file_id} not found"
            )

        logger.info(f"Analyzing legislative file: {carriage.title}")

        # Get AI service
        ai_service = get_legislative_file_ai_service()

        # Perform analysis
        analysis = await ai_service.analyze_legislative_file(
            title=carriage.title,
            description=carriage.description,
            full_text=None  # Could fetch from EUR-Lex in future
        )

        # Update carriage with AI results
        carriage.ai_summary = analysis["ai_summary"]
        carriage.ai_policy_classifications = analysis["ai_policy_classifications"]
        carriage.ai_entities = analysis["ai_entities"]
        carriage.enriched_at = datetime.now()

        # Update policy_areas from top classification
        if analysis["ai_policy_classifications"]:
            top_policies = [
                c["label"] for c in analysis["ai_policy_classifications"]
            ]
            carriage.policy_areas = top_policies

        # Set enrichment quality based on results
        if analysis["ai_summary"] and len(analysis["ai_policy_classifications"]) > 0:
            carriage.enrichment_quality = "high"
        elif analysis["ai_summary"] or len(analysis["ai_policy_classifications"]) > 0:
            carriage.enrichment_quality = "medium"
        else:
            carriage.enrichment_quality = "low"

        db.commit()

        logger.info(f"Successfully analyzed legislative file {file_id}")

        return {
            "message": "Legislative file analyzed successfully",
            "file_id": file_id,
            "analysis": {
                "ai_summary": analysis["ai_summary"],
                "policy_classifications": analysis["ai_policy_classifications"],
                "entities": analysis["ai_entities"],
                "enrichment_quality": carriage.enrichment_quality,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze legislative file: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze legislative file: {str(e)}"
        )


@router.post(
    "/legislative-files/analyze-batch",
    summary="AI analyze multiple legislative files",
    description="Batch analyze multiple legislative files with Hugging Face"
)
async def analyze_legislative_files_batch(
    file_ids: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch analyze multiple legislative files.

    Allows users to select which files to enrich with AI.
    """
    try:
        from models.legislative_train import LegislativeCarriage
        from services.ai.legislative_file_ai_service import get_legislative_file_ai_service

        logger.info(f"Batch analyzing {len(file_ids)} legislative files")

        # Get AI service
        ai_service = get_legislative_file_ai_service()

        stats = {
            "total": len(file_ids),
            "processed": 0,
            "enriched": 0,
            "failed": 0,
            "errors": []
        }

        for file_id in file_ids:
            try:
                # Find carriage
                carriage = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.file_id == file_id
                ).first()

                if not carriage:
                    stats["failed"] += 1
                    stats["errors"].append(f"{file_id}: not found")
                    continue

                # Perform analysis
                analysis = await ai_service.analyze_legislative_file(
                    title=carriage.title,
                    description=carriage.description,
                    full_text=None
                )

                # Update carriage
                carriage.ai_summary = analysis["ai_summary"]
                carriage.ai_policy_classifications = analysis["ai_policy_classifications"]
                carriage.ai_entities = analysis["ai_entities"]
                carriage.enriched_at = datetime.now()

                if analysis["ai_policy_classifications"]:
                    top_policies = [c["label"] for c in analysis["ai_policy_classifications"]]
                    carriage.policy_areas = top_policies

                if analysis["ai_summary"] and len(analysis["ai_policy_classifications"]) > 0:
                    carriage.enrichment_quality = "high"
                elif analysis["ai_summary"] or len(analysis["ai_policy_classifications"]) > 0:
                    carriage.enrichment_quality = "medium"
                else:
                    carriage.enrichment_quality = "low"

                stats["processed"] += 1
                stats["enriched"] += 1

            except Exception as e:
                logger.error(f"Failed to analyze {file_id}: {str(e)}")
                stats["failed"] += 1
                stats["errors"].append(f"{file_id}: {str(e)}")

        db.commit()

        logger.info(f"Batch analysis complete: {stats}")

        return {
            "message": f"Batch analysis completed. Enriched {stats['enriched']} files.",
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Batch analysis failed: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch analyze files: {str(e)}"
        )
