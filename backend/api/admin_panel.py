"""
Admin Panel API

Comprehensive admin endpoints for managing users, feeds, scrapers, and system settings.
Only accessible to users with admin role.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
    email: Optional[str]  # nullable since migration 148 (dormant profiles)
    full_name: Optional[str]
    organization: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    is_trainer: bool = False
    created_at: datetime
    last_login: Optional[datetime]
    subscription_tier: Optional[str]
    subscription_expires_at: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    policy_interests: Optional[List[str]] = None
    is_dormant: bool = False  # pre-provisioned, never claimed (migration 148)

    class Config:
        from_attributes = True  # Pydantic v2

    @classmethod
    def from_orm(cls, obj):
        """Custom ORM conversion to handle policy_interests field"""
        return cls(
            id=obj.id,
            email=obj.email,
            full_name=obj.full_name,
            organization=obj.organization,
            role=obj.role,
            is_active=obj.is_active,
            is_verified=obj.is_verified,
            is_trainer=getattr(obj, 'is_trainer', False) or False,
            created_at=obj.created_at,
            last_login=obj.last_login,
            subscription_tier=obj.subscription_tier,
            subscription_expires_at=obj.subscription_expires_at,
            stripe_subscription_id=obj.stripe_subscription_id,
            policy_interests=obj.policy_interests_list,  # Use the property that handles conversion
            is_dormant=bool(
                getattr(obj, 'pre_provisioned_at', None) and not getattr(obj, 'claimed_at', None)
            ),
        )


class UserListResponse(BaseModel):
    """Paginated user list envelope"""
    users: List[UserManagementResponse]
    total: int
    page: int
    page_size: int


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
    # Business metrics (added Jul 2026)
    signups_7d: int = 0
    signups_30d: int = 0
    paying_users: int = 0
    wapu_7d: int = 0  # Weekly Active Paid Users: paid tier + 1 core action in 7d
    dormant_profiles: int = 0  # pre-provisioned, never claimed (migration 148)
    sync_failures_24h: int = 0
    brief_sends_7d: int = 0


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.get("/users", response_model=UserListResponse)
def get_all_users(
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
    return UserListResponse(
        users=[UserManagementResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


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
def get_all_feeds(
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

    # --- Business metrics (added Jul 2026) ---
    from datetime import timezone
    from sqlalchemy import text

    now_utc = datetime.now(timezone.utc)
    seven_ago = now_utc - timedelta(days=7)
    thirty_ago = now_utc - timedelta(days=30)

    signups_7d = db.query(func.count(User.id)).filter(User.created_at >= seven_ago).scalar()
    signups_30d = db.query(func.count(User.id)).filter(User.created_at >= thirty_ago).scalar()

    paid_tiers = ('yellow', 'blue')
    paying_users = db.query(func.count(User.id)).filter(
        User.subscription_tier.in_(paid_tiers),
        User.role != 'admin',
    ).scalar()

    # WAPU: paid tier + at least one core action (chat, amendment, document) in 7d
    wapu_7d = 0
    try:
        from models.chat import Chat
        from models.amendment import Amendment
        from models.user_document import UserDocument

        active_ids = set()
        for uid, in db.query(Chat.user_id).filter(
            Chat.user_id.isnot(None), Chat.last_message_at >= seven_ago
        ).distinct():
            active_ids.add(uid)
        for uid, in db.query(Amendment.user_id).filter(Amendment.updated_at >= seven_ago).distinct():
            active_ids.add(uid)
        for uid, in db.query(UserDocument.user_id).filter(UserDocument.updated_at >= seven_ago).distinct():
            active_ids.add(uid)

        if active_ids:
            wapu_7d = db.query(func.count(User.id)).filter(
                User.id.in_(active_ids),
                User.subscription_tier.in_(paid_tiers),
                User.role != 'admin',
            ).scalar() or 0
    except Exception as exc:
        logger.warning("WAPU computation failed: %s", exc)

    dormant_profiles = db.query(func.count(User.id)).filter(
        User.pre_provisioned_at.isnot(None),
        User.claimed_at.is_(None),
    ).scalar()

    # Raw-SQL counters, fail-soft (tables managed outside ORM)
    def _scalar_sql(sql: str) -> int:
        try:
            return db.execute(text(sql)).scalar() or 0
        except Exception:
            db.rollback()
            return 0

    sync_failures_24h = _scalar_sql(
        "SELECT COUNT(*) FROM sync_runs WHERE status = 'failed' AND started_at >= now() - interval '24 hours'"
    )
    brief_sends_7d = _scalar_sql(
        "SELECT COUNT(*) FROM daily_brief_sends WHERE sent_at >= now() - interval '7 days'"
    )

    return {
        "total_users": total_users or 0,
        "active_users_7d": active_users_7d or 0,
        "total_feeds": total_feeds or 0,
        "active_feeds": active_feeds or 0,
        "total_entries": total_entries or 0,
        "entries_today": entries_today or 0,
        "total_subscriptions": total_subscriptions or 0,
        "total_feedback": total_feedback or 0,
        "unresolved_feedback": unresolved_feedback or 0,
        "signups_7d": signups_7d or 0,
        "signups_30d": signups_30d or 0,
        "paying_users": paying_users or 0,
        "wapu_7d": wapu_7d,
        "dormant_profiles": dormant_profiles or 0,
        "sync_failures_24h": sync_failures_24h,
        "brief_sends_7d": brief_sends_7d,
    }


@router.get("/subscriptions/overview")
def get_subscriptions_overview(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Server-side subscription overview across ALL users.

    Tier counts come from the database (internal gating tiers). Plan names and
    real MRR come from Stripe, the only source of plan identity: the webhook
    persists just subscription_tier on the user row, so per-plan revenue must
    be read from the active Stripe subscriptions.
    """
    # Tier counts over the whole user base (not just one page)
    tier_rows = db.query(User.subscription_tier, func.count(User.id)) \
        .group_by(User.subscription_tier).all()
    by_tier = {(tier or "white"): count for tier, count in tier_rows}

    total_users = sum(by_tier.values())
    paying_users = db.query(func.count(User.id)).filter(
        User.stripe_subscription_id.isnot(None),
        User.role != 'admin',
    ).scalar() or 0

    # Real MRR + plan breakdown from Stripe (fail-soft if not configured)
    mrr_eur = None
    by_plan: Dict[str, int] = {}
    stripe_error = None
    try:
        import stripe as stripe_lib
        from core.config import settings as app_settings
        from api.stripe_payment import PRICE_ID_TO_PLAN

        if not app_settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY not configured")

        stripe_lib.api_key = app_settings.STRIPE_SECRET_KEY
        mrr_cents = 0.0
        subs = stripe_lib.Subscription.list(status="active", limit=100)
        for sub in subs.auto_paging_iter():
            for item in sub["items"]["data"]:
                price = item["price"]
                plan = PRICE_ID_TO_PLAN.get(price["id"], "unknown")
                by_plan[plan] = by_plan.get(plan, 0) + 1
                amount = (price.get("unit_amount") or 0) * (item.get("quantity") or 1)
                interval = (price.get("recurring") or {}).get("interval", "month")
                mrr_cents += amount / 12 if interval == "year" else amount
        mrr_eur = round(mrr_cents / 100, 2)
    except Exception as exc:
        stripe_error = str(exc)
        logger.warning("Stripe MRR fetch failed: %s", exc)

    return {
        "total_users": total_users,
        "by_tier": by_tier,
        "paying_users": paying_users,
        "by_plan": by_plan,
        "mrr_eur": mrr_eur,
        "stripe_error": stripe_error,
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
# SYNC HEALTH (real sync_runs ledger, replaces the old faked scraper status)
# ============================================================================

@router.get("/sync/health")
def get_sync_health(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Freshness of every registered MEUB sync source plus recent failures.

    Reads the sync_runs ledger written by the cron tier endpoints via
    services.sync.freshness.record_run.
    """
    from sqlalchemy import text
    from services.sync.freshness import get_freshness

    sources = get_freshness(db)

    try:
        failures = db.execute(
            text(
                """
                SELECT source_key, tier, status, error, started_at, finished_at
                FROM sync_runs
                WHERE status = 'failed'
                ORDER BY started_at DESC
                LIMIT 25
                """
            )
        ).mappings().all()
        recent_failures = [
            {
                "source_key": f["source_key"],
                "tier": f["tier"],
                "error": f["error"],
                "started_at": f["started_at"].isoformat() if f["started_at"] else None,
                "finished_at": f["finished_at"].isoformat() if f["finished_at"] else None,
            }
            for f in failures
        ]
    except Exception as exc:
        logger.warning("sync_runs failures query failed: %s", exc)
        db.rollback()
        recent_failures = []

    stale = [s for s in sources if s.get("stale")]

    return {
        "sources": sources,
        "stale_count": len(stale),
        "recent_failures": recent_failures,
    }


async def _run_sync_tier_background(tier: str, admin_id: str):
    """Run every source of a MEUB cadence tier, recording freshness rows.

    Mirrors api/cron.py::cron_sync_tier but is fired from the admin panel as a
    FastAPI background task, so the HTTP response returns immediately.
    """
    from datetime import timezone as _tz
    from core.database import SessionLocal
    from services.sync.source_registry import sources_for_tier
    from services.sync.freshness import record_run
    from api.cron import _run_script_async

    db = SessionLocal()
    try:
        for spec in sources_for_tier(tier):
            started = datetime.now(_tz.utc)
            res = await _run_script_async(spec.key, spec.script, list(spec.args), timeout=spec.timeout)
            status_str = res.get("status", "failed")
            err = res.get("stderr_tail") or res.get("error") or res.get("reason")
            record_run(
                db,
                source_key=spec.key,
                tier=tier,
                status=status_str,
                error=(err if status_str != "success" else None),
                started_at=started,
                finished_at=datetime.now(_tz.utc),
            )
        logger.info("[ADMIN] Sync tier '%s' finished (triggered by admin %s)", tier, admin_id)
    except Exception as exc:
        logger.error("[ADMIN] Sync tier '%s' crashed: %s", tier, exc)
    finally:
        db.close()


@router.post("/sync/run/{tier}")
async def trigger_sync_tier(
    tier: str,
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Manually run a MEUB sync cadence tier ('fast' or 'warm') in the background.

    Same source registry the Railway cron uses; progress lands in the
    sync_runs ledger and is visible via GET /api/admin/sync/health.
    """
    from services.sync.source_registry import sources_for_tier

    if tier not in ("fast", "warm"):
        raise HTTPException(status_code=400, detail="tier must be 'fast' or 'warm'")

    specs = sources_for_tier(tier)

    log_entry = AdminActivityLog(
        admin_user_id=admin.id,
        action_type="trigger_sync_tier",
        target_type="sync",
        action_details={"tier": tier, "sources": [s.key for s in specs]}
    )
    db.add(log_entry)
    db.commit()

    background_tasks.add_task(_run_sync_tier_background, tier, str(admin.id))

    return {
        "message": f"Sync tier '{tier}' started in background ({len(specs)} sources)",
        "sources": [s.key for s in specs],
        "status": "started",
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
