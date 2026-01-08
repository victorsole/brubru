"""
RSS Feed Schemas

Pydantic schemas for RSS feed operations.
Part of My EU Bubble - Phase 1: RSS Feed Infrastructure
"""

from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import re


# ============================================================================
# Helper Functions
# ============================================================================

def strip_html_tags(text: Optional[str]) -> Optional[str]:
    """
    Remove HTML tags from text while preserving content.
    Handles common RSS feed HTML like <img>, <a>, <p>, <br>, etc.
    """
    if not text:
        return text

    # Remove HTML tags
    clean_text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    clean_text = clean_text.replace('&nbsp;', ' ')
    clean_text = clean_text.replace('&lt;', '<')
    clean_text = clean_text.replace('&gt;', '>')
    clean_text = clean_text.replace('&amp;', '&')
    clean_text = clean_text.replace('&quot;', '"')
    clean_text = clean_text.replace('&#39;', "'")

    # Clean up whitespace
    clean_text = ' '.join(clean_text.split())

    return clean_text.strip() if clean_text else None


# ============================================================================
# RSS Feed Schemas
# ============================================================================

class RSSFeedBase(BaseModel):
    """Base schema for RSS Feed"""
    name: str = Field(..., max_length=200, description="Human-readable feed name")
    url: str = Field(..., max_length=1000, description="RSS feed URL")
    source: str = Field(..., max_length=100, description="Institution name (e.g., 'european_parliament')")
    category: Optional[str] = Field(None, max_length=100, description="Feed category")
    description: Optional[str] = Field(None, description="Feed description")
    language: str = Field(default="en", max_length=5, description="ISO 639-1 language code")
    update_frequency_minutes: int = Field(default=60, ge=15, le=1440, description="Update frequency in minutes")
    is_active: bool = Field(default=True, description="Whether feed is actively monitored")


class RSSFeedCreate(RSSFeedBase):
    """Schema for creating a new RSS feed"""
    pass


class RSSFeedUpdate(BaseModel):
    """Schema for updating an RSS feed"""
    name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None
    update_frequency_minutes: Optional[int] = Field(None, ge=15, le=1440)
    priority: Optional[int] = Field(None, ge=1, le=10)


class RSSFeedResponse(RSSFeedBase):
    """Schema for RSS feed response"""
    id: UUID
    last_fetched_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    last_entry_date: Optional[datetime] = None
    total_entries: int = 0
    is_healthy: bool = True
    error_rate: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# RSS Entry Schemas
# ============================================================================

class RSSEntryBase(BaseModel):
    """Base schema for RSS Entry"""
    title: str = Field(..., max_length=500, description="Entry title")
    link: str = Field(..., max_length=1000, description="Entry URL")
    summary: Optional[str] = Field(None, description="Entry summary")
    content: Optional[str] = Field(None, description="Full content")
    author: Optional[str] = Field(None, max_length=200, description="Author name")
    categories: Optional[List[str]] = Field(None, description="Entry categories")
    published_at: Optional[datetime] = Field(None, description="Publication date")


class RSSEntryResponse(RSSEntryBase):
    """Schema for RSS entry response"""
    id: UUID
    feed_id: UUID
    guid: Optional[str] = None
    image_url: Optional[str] = None
    language: str = "en"

    # Source information
    institution: Optional[str] = None

    # AI enrichment fields (Phase 4)
    ai_summary: Optional[str] = None
    ai_sentiment: Optional[str] = None
    ai_topics: Optional[List[str]] = None

    # Engagement metrics
    view_count: int = 0
    save_count: int = 0

    # User-specific fields (set by API)
    is_read: Optional[bool] = None
    is_saved: Optional[bool] = None

    created_at: datetime
    published_at: Optional[datetime] = None

    @field_validator('summary', mode='before')
    @classmethod
    def clean_summary(cls, v):
        """Strip HTML tags from summary"""
        return strip_html_tags(v)

    @field_validator('ai_summary', mode='before')
    @classmethod
    def clean_ai_summary(cls, v):
        """Strip HTML tags from AI summary"""
        return strip_html_tags(v)

    class Config:
        from_attributes = True


class RSSEntryListResponse(BaseModel):
    """Schema for paginated RSS entry list"""
    entries: List[RSSEntryResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================================
# User Feed Subscription Schemas
# ============================================================================

class UserFeedSubscriptionCreate(BaseModel):
    """Schema for creating a feed subscription"""
    feed_id: UUID = Field(..., description="RSS feed ID to subscribe to")
    notification_enabled: bool = Field(default=False, description="Enable notifications for new entries")


class UserFeedSubscriptionUpdate(BaseModel):
    """Schema for updating a feed subscription"""
    is_active: Optional[bool] = None
    notification_enabled: Optional[bool] = None


class UserFeedSubscriptionResponse(BaseModel):
    """Schema for feed subscription response"""
    id: UUID
    user_id: UUID
    feed_id: UUID
    is_active: bool
    notification_enabled: bool
    subscribed_at: datetime
    last_viewed_at: Optional[datetime] = None

    # Include feed details
    feed: Optional[RSSFeedResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# User Feed Read Schemas
# ============================================================================

class MarkAsReadRequest(BaseModel):
    """Schema for marking entry as read"""
    reading_time_seconds: Optional[int] = Field(None, ge=0, description="Time spent reading in seconds")
    clicked_link: bool = Field(default=False, description="Whether user clicked through to source")


class UserFeedReadResponse(BaseModel):
    """Schema for feed read response"""
    id: UUID
    user_id: UUID
    rss_entry_id: UUID
    reading_time_seconds: Optional[int] = None
    read_count: int
    first_read_at: datetime
    last_read_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# User Saved Entry Schemas
# ============================================================================

class SaveEntryRequest(BaseModel):
    """Schema for saving/bookmarking an entry"""
    notes: Optional[str] = Field(None, description="Personal notes about this entry")
    tags: Optional[List[str]] = Field(None, max_length=20, description="User-defined tags")
    collection_name: Optional[str] = Field(None, max_length=100, description="Collection/folder name")
    is_starred: bool = Field(default=False, description="Mark as starred/important")

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v is not None and len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        return v


class UpdateSavedEntryRequest(BaseModel):
    """Schema for updating a saved entry"""
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    collection_name: Optional[str] = None
    is_starred: Optional[bool] = None

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v is not None and len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        return v


class UserSavedEntryResponse(BaseModel):
    """Schema for saved entry response"""
    id: UUID
    user_id: UUID
    rss_entry_id: UUID
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    collection_name: Optional[str] = None
    is_starred: bool
    saved_at: datetime
    updated_at: datetime
    last_viewed_at: Optional[datetime] = None

    # Include entry details
    entry: Optional[RSSEntryResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# Feed Query/Filter Schemas
# ============================================================================

class FeedFilterParams(BaseModel):
    """Schema for filtering RSS feed entries"""
    sources: Optional[List[str]] = Field(None, description="Filter by sources (e.g., ['european_parliament', 'euractiv'])")
    policy_areas: Optional[List[str]] = Field(None, description="Filter by policy areas")
    feed_ids: Optional[List[UUID]] = Field(None, description="Filter by specific feed IDs")
    search: Optional[str] = Field(None, max_length=200, description="Search in title and content")
    from_date: Optional[datetime] = Field(None, description="Filter entries published after this date")
    to_date: Optional[datetime] = Field(None, description="Filter entries published before this date")
    unread_only: bool = Field(default=False, description="Show only unread entries")
    saved_only: bool = Field(default=False, description="Show only saved entries")
    limit: int = Field(default=50, ge=1, le=200, description="Number of entries to return")
    offset: int = Field(default=0, ge=0, description="Number of entries to skip")


# ============================================================================
# Feed Statistics Schemas
# ============================================================================

class FeedStatsResponse(BaseModel):
    """Schema for feed statistics"""
    total_entries: int
    unread_count: int
    saved_count: int
    entries_today: int
    entries_this_week: int
    most_active_sources: List[dict]
    reading_time_total_minutes: int


class UserEngagementStats(BaseModel):
    """Schema for user engagement statistics"""
    total_subscriptions: int
    active_subscriptions: int
    total_reads: int
    total_saves: int
    average_reading_time_seconds: Optional[float] = None
    favorite_sources: List[str]
    most_read_categories: List[str]
