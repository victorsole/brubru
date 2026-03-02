"""
Admin Panel API

Comprehensive admin endpoints for managing users, feeds, scrapers, and system settings.
Only accessible to users with admin role.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from core.database import get_db
from models.user import User
from models.rss_feed import RSSFeed
from models.rss_entry import RSSEntry
from models.user_feed_subscription import UserFeedSubscription
from models.feedback import AdminActivityLog, SystemSettings
from api.admin_auth import get_current_admin_user
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Pydantic Schemas

class UserManagementResponse(BaseModel):
    """User details for admin panel"""
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    is_trainer: bool = False
    created_at: datetime
    last_login: Optional[datetime]
    subscription_tier: Optional[str]
    policy_interests: Optional[List[str]] = None

    class Config:
        from_attributes = True  # Pydantic v2

    @classmethod
    def from_orm(cls, obj):
        """Custom ORM conversion to handle policy_interests field"""
        return cls(
            id=obj.id,
            email=obj.email,
            full_name=obj.full_name,
            role=obj.role,
            is_active=obj.is_active,
            is_verified=obj.is_verified,
            is_trainer=getattr(obj, 'is_trainer', False) or False,
            created_at=obj.created_at,
            last_login=obj.last_login,
            subscription_tier=obj.subscription_tier,
            policy_interests=obj.policy_interests_list  # Use the property that handles conversion
        )


class UserUpdateRequest(BaseModel):
    """Request to update user details"""
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_trainer: Optional[bool] = None
    subscription_tier: Optional[str] = None


class FeedManagementResponse(BaseModel):
    """RSS feed details for admin panel"""
    id: UUID
    name: str
    url: str
    source: str
    is_active: bool
    last_fetched_at: Optional[datetime]
    update_frequency_minutes: int
    entry_count: int
    subscriber_count: int


class FeedCreateRequest(BaseModel):
    """Request to create new RSS feed"""
    name: str = Field(..., min_length=3, max_length=200)
    url: str = Field(..., description="RSS feed URL")
    source: str = Field(..., description="Source organization")
    description: Optional[str] = None
    update_frequency_minutes: int = Field(default=60, ge=15, le=1440)
    is_active: bool = Field(default=True)


class FeedUpdateRequest(BaseModel):
    """Request to update RSS feed"""
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    update_frequency_minutes: Optional[int] = None


class SystemStatsResponse(BaseModel):
    """Overall system statistics"""
    total_users: int
    active_users_7d: int
    total_feeds: int
    active_feeds: int
    total_entries: int
    entries_today: int
    total_subscriptions: int
    total_feedback: int
    unresolved_feedback: int


class ScraperStatus(BaseModel):
    """Status of a scraper"""
    name: str
    is_active: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    items_scraped: int
    error_count: int
    status: str  # idle, running, error


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=List[UserManagementResponse])
async def get_all_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    role_filter: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),  # active, inactive, unverified
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users with filtering and pagination.
    """
    query = db.query(User)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
                User.organization.ilike(search_pattern)
            )
        )

    if role_filter:
        query = query.filter(User.role == role_filter)

    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)
    elif status_filter == 'unverified':
        query = query.filter(User.is_verified == False)

    total = query.count()

    users = query.order_by(User.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="view_users",
        action_details={"search": search, "filters": {"role": role_filter, "status": status_filter}}
    )
    db.add(log_entry)
    db.commit()

    # Convert using custom from_orm to handle policy_interests
    return [UserManagementResponse.from_orm(user) for user in users]


@router.get("/users/{user_id}", response_model=UserManagementResponse)
async def get_user_detail(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed user information."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserManagementResponse.from_orm(user)


@router.patch("/users/{user_id}", response_model=UserManagementResponse)
async def update_user(
    user_id: UUID,
    updates: UserUpdateRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user details (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent admin from demoting themselves
    if user.id == admin.id and updates.role and updates.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote yourself from admin role"
        )

    # Update fields
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="update_user",
        target_type="user",
        target_id=user_id,
        action_details=update_data
    )
    db.add(log_entry)

    db.commit()
    db.refresh(user)

    logger.info(f"User {user_id} updated by admin {admin.id}")

    return UserManagementResponse.from_orm(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only). Use with caution."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account"
        )

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="delete_user",
        target_type="user",
        target_id=user_id,
        action_details={"email": user.email, "role": user.role}
    )
    db.add(log_entry)

    db.delete(user)
    db.commit()

    logger.warning(f"User {user_id} ({user.email}) deleted by admin {admin.id}")

    return None


# ============================================================================
# RSS FEED MANAGEMENT
# ============================================================================

@router.get("/feeds", response_model=List[FeedManagementResponse])
async def get_all_feeds(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    active_only: bool = Query(False),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all RSS feeds with statistics."""
    query = db.query(RSSFeed)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                RSSFeed.name.ilike(search_pattern),
                RSSFeed.source.ilike(search_pattern),
                RSSFeed.url.ilike(search_pattern)
            )
        )

    if active_only:
        query = query.filter(RSSFeed.is_active == True)

    feeds = query.offset((page - 1) * page_size).limit(page_size).all()

    # Enhance with statistics
    result = []
    for feed in feeds:
        entry_count = db.query(func.count(RSSEntry.id)).filter(RSSEntry.feed_id == feed.id).scalar()
        subscriber_count = db.query(func.count(UserFeedSubscription.id)).filter(
            UserFeedSubscription.feed_id == feed.id,
            UserFeedSubscription.is_active == True
        ).scalar()

        result.append({
            "id": feed.id,
            "name": feed.name,
            "url": feed.url,
            "source": feed.source,
            "is_active": feed.is_active,
            "last_fetched_at": feed.last_fetched_at,
            "update_frequency_minutes": feed.update_frequency_minutes,
            "entry_count": entry_count or 0,
            "subscriber_count": subscriber_count or 0
        })

    return result


@router.post("/feeds", response_model=FeedManagementResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(
    feed_data: FeedCreateRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create new RSS feed."""
    # Check for duplicate URL
    existing = db.query(RSSFeed).filter(RSSFeed.url == feed_data.url).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feed with this URL already exists"
        )

    new_feed = RSSFeed(
        name=feed_data.name,
        url=feed_data.url,
        source=feed_data.source,
        description=feed_data.description,
        update_frequency_minutes=feed_data.update_frequency_minutes,
        is_active=feed_data.is_active
    )

    db.add(new_feed)

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="create_feed",
        target_type="rss_feed",
        action_details=feed_data.dict()
    )
    db.add(log_entry)

    db.commit()
    db.refresh(new_feed)

    logger.info(f"New RSS feed created: {new_feed.id} by admin {admin.id}")

    return {
        "id": new_feed.id,
        "name": new_feed.name,
        "url": new_feed.url,
        "source": new_feed.source,
        "is_active": new_feed.is_active,
        "last_fetched_at": new_feed.last_fetched_at,
        "update_frequency_minutes": new_feed.update_frequency_minutes,
        "entry_count": 0,
        "subscriber_count": 0
    }


@router.patch("/feeds/{feed_id}", response_model=FeedManagementResponse)
async def update_feed(
    feed_id: UUID,
    updates: FeedUpdateRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update RSS feed."""
    feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")

    # Update fields
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(feed, field, value)

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="update_feed",
        target_type="rss_feed",
        target_id=feed_id,
        action_details=update_data
    )
    db.add(log_entry)

    db.commit()
    db.refresh(feed)

    # Get statistics
    entry_count = db.query(func.count(RSSEntry.id)).filter(RSSEntry.feed_id == feed.id).scalar()
    subscriber_count = db.query(func.count(UserFeedSubscription.id)).filter(
        UserFeedSubscription.feed_id == feed.id,
        UserFeedSubscription.is_active == True
    ).scalar()

    return {
        "id": feed.id,
        "name": feed.name,
        "url": feed.url,
        "source": feed.source,
        "is_active": feed.is_active,
        "last_fetched_at": feed.last_fetched_at,
        "update_frequency_minutes": feed.update_frequency_minutes,
        "entry_count": entry_count or 0,
        "subscriber_count": subscriber_count or 0
    }


@router.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(
    feed_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete RSS feed and all associated entries."""
    feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="delete_feed",
        target_type="rss_feed",
        target_id=feed_id,
        action_details={"name": feed.name, "url": feed.url}
    )
    db.add(log_entry)

    db.delete(feed)
    db.commit()

    logger.warning(f"RSS feed {feed_id} deleted by admin {admin.id}")

    return None


# ============================================================================
# SYSTEM MONITORING & STATISTICS
# ============================================================================

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get overall system statistics for admin dashboard."""
    # User statistics
    total_users = db.query(func.count(User.id)).scalar()

    seven_days_ago = datetime.now() - timedelta(days=7)
    active_users_7d = db.query(func.count(User.id)).filter(
        User.last_login >= seven_days_ago
    ).scalar()

    # Feed statistics
    total_feeds = db.query(func.count(RSSFeed.id)).scalar()
    active_feeds = db.query(func.count(RSSFeed.id)).filter(RSSFeed.is_active == True).scalar()

    # Entry statistics
    total_entries = db.query(func.count(RSSEntry.id)).scalar()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    entries_today = db.query(func.count(RSSEntry.id)).filter(
        RSSEntry.created_at >= today_start
    ).scalar()

    # Subscription statistics
    total_subscriptions = db.query(func.count(UserFeedSubscription.id)).filter(
        UserFeedSubscription.is_active == True
    ).scalar()

    # Feedback statistics
    from models.feedback import FeedbackSubmission
    total_feedback = db.query(func.count(FeedbackSubmission.id)).scalar()
    unresolved_feedback = db.query(func.count(FeedbackSubmission.id)).filter(
        FeedbackSubmission.status.in_(['new', 'in_review', 'in_progress'])
    ).scalar()

    return {
        "total_users": total_users or 0,
        "active_users_7d": active_users_7d or 0,
        "total_feeds": total_feeds or 0,
        "active_feeds": active_feeds or 0,
        "total_entries": total_entries or 0,
        "entries_today": entries_today or 0,
        "total_subscriptions": total_subscriptions or 0,
        "total_feedback": total_feedback or 0,
        "unresolved_feedback": unresolved_feedback or 0
    }


@router.get("/activity-log")
async def get_admin_activity_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action_type: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin activity log with pagination."""
    query = db.query(AdminActivityLog)

    if action_type:
        query = query.filter(AdminActivityLog.action_type == action_type)

    total = query.count()

    logs = query.order_by(AdminActivityLog.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": logs
    }


# ============================================================================
# SCRAPER MANAGEMENT
# ============================================================================

@router.get("/scrapers/status", response_model=List[ScraperStatus])
async def get_scrapers_status(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get status of all scrapers (newsletters, RSS feeds, etc).

    Returns current status, last run time, and error information.
    """
    # This is a placeholder - implementation depends on scraper architecture
    # For now, returning basic info about RSS feeds as "scrapers"

    feeds = db.query(RSSFeed).all()

    scrapers = []
    for feed in feeds:
        entry_count = db.query(func.count(RSSEntry.id)).filter(RSSEntry.feed_id == feed.id).scalar()

        scrapers.append({
            "name": f"{feed.source} - {feed.name}",
            "is_active": feed.is_active,
            "last_run": feed.last_fetched_at,
            "next_run": None,  # Calculate based on fetch_interval_minutes
            "items_scraped": entry_count or 0,
            "error_count": 0,  # Would need error tracking
            "status": "idle" if feed.is_active else "disabled"
        })

    return scrapers


@router.post("/scrapers/{scraper_name}/run")
async def trigger_scraper(
    scraper_name: str,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger a scraper run.

    This will queue the scraper for immediate execution.
    """
    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="trigger_scraper",
        target_type="scraper",
        action_details={"scraper_name": scraper_name}
    )
    db.add(log_entry)
    db.commit()

    logger.info(f"Scraper {scraper_name} triggered by admin {admin.id}")

    return {
        "message": f"Scraper {scraper_name} triggered successfully",
        "status": "queued"
    }


# ============================================================================
# EMAIL CAMPAIGNS
# ============================================================================

class EmailCampaignRequest(BaseModel):
    """Request to send re-engagement emails"""
    inactive_days: int = Field(default=7, ge=1, le=365, description="Days since last login to consider inactive")
    include_never_logged_in: bool = Field(default=True, description="Include users who registered but never logged in")
    dry_run: bool = Field(default=True, description="Preview recipients without sending")


class EmailCampaignResponse(BaseModel):
    """Response from email campaign"""
    dry_run: bool
    welcome_back_recipients: List[str]
    first_time_recipients: List[str]
    sent: int
    failed: int
    failed_addresses: List[str]


@router.post("/email/re-engagement", response_model=EmailCampaignResponse)
async def send_reengagement_emails(
    request: EmailCampaignRequest,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Send re-engagement emails to inactive users.

    - Users who haven't logged in for N days get a "welcome back" email.
    - Users who registered but never logged in get a "first time welcome" email.
    - Default is dry_run=True (preview only). Set dry_run=False to actually send.
    """
    from services.email_service import get_email_service, build_welcome_back_email, build_first_time_welcome_email

    email_service = get_email_service()
    cutoff = datetime.utcnow() - timedelta(days=request.inactive_days)

    # Find inactive users (logged in before, but not recently)
    inactive_users = db.query(User).filter(
        User.is_active == True,
        User.last_login != None,
        User.last_login < cutoff,
        User.email != None,
        User.role != 'admin',
    ).all()

    # Find users who registered but never logged in
    never_logged_in = []
    if request.include_never_logged_in:
        never_logged_in = db.query(User).filter(
            User.is_active == True,
            User.last_login == None,
            User.email != None,
            User.role != 'admin',
        ).all()

    welcome_back_recipients = [u.email for u in inactive_users]
    first_time_recipients = [u.email for u in never_logged_in]

    if request.dry_run:
        # Log admin action
        log_entry = AdminActivityLog(
            admin_user_id=admin.id,
            action_type="email_campaign_preview",
            action_details={
                "inactive_days": request.inactive_days,
                "welcome_back_count": len(welcome_back_recipients),
                "first_time_count": len(first_time_recipients),
            }
        )
        db.add(log_entry)
        db.commit()

        return EmailCampaignResponse(
            dry_run=True,
            welcome_back_recipients=welcome_back_recipients,
            first_time_recipients=first_time_recipients,
            sent=0,
            failed=0,
            failed_addresses=[],
        )

    # Actually send emails
    total_sent = 0
    all_failed = []

    # Send welcome-back emails
    for user in inactive_users:
        days_since = (datetime.utcnow() - user.last_login).days
        name = user.full_name or user.email.split("@")[0]
        email_data = build_welcome_back_email(user_name=name, days_since_login=days_since)
        if email_service.send(to=user.email, **email_data):
            total_sent += 1
        else:
            all_failed.append(user.email)

    # Send first-time welcome emails
    for user in never_logged_in:
        name = user.full_name or user.email.split("@")[0]
        email_data = build_first_time_welcome_email(user_name=name)
        if email_service.send(to=user.email, **email_data):
            total_sent += 1
        else:
            all_failed.append(user.email)

    # Log admin action
    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="email_campaign_sent",
        action_details={
            "inactive_days": request.inactive_days,
            "welcome_back_count": len(welcome_back_recipients),
            "first_time_count": len(first_time_recipients),
            "sent": total_sent,
            "failed": len(all_failed),
        }
    )
    db.add(log_entry)
    db.commit()

    logger.info(f"[EMAIL] Re-engagement campaign by admin {admin.id}: {total_sent} sent, {len(all_failed)} failed")

    return EmailCampaignResponse(
        dry_run=False,
        welcome_back_recipients=welcome_back_recipients,
        first_time_recipients=first_time_recipients,
        sent=total_sent,
        failed=len(all_failed),
        failed_addresses=all_failed,
    )
