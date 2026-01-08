"""
Feedback System Schemas

Pydantic models for feedback system API requests and responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


# Enums
class FeedbackType(str):
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"
    OTHER = "other"


class FeedbackStatus(str):
    NEW = "new"
    IN_REVIEW = "in_review"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"


class Priority(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Request Schemas
class FeedbackCreate(BaseModel):
    """Schema for creating new feedback"""
    feedback_type: str = Field(..., description="Type: bug, feature_request, general, other")
    title: str = Field(..., min_length=5, max_length=200, description="Feedback title")
    description: str = Field(..., min_length=10, description="Detailed description")
    category: Optional[str] = Field(None, description="Category (e.g., 'UI/UX', 'Performance')")
    affected_feature: Optional[str] = Field(None, description="Feature affected by bug")
    browser_info: Optional[Dict[str, Any]] = Field(None, description="Browser and OS info")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    screenshot_url: Optional[str] = Field(None, description="URL to uploaded screenshot")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Array of attachments")


class FeedbackUpdate(BaseModel):
    """Schema for updating feedback (admin only)"""
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    admin_notes: Optional[str] = None
    admin_response: Optional[str] = None
    assigned_to: Optional[UUID] = None


class CommentCreate(BaseModel):
    """Schema for creating a comment"""
    comment_text: str = Field(..., min_length=1, description="Comment text")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Attachments")


# Response Schemas
class FeedbackUserInfo(BaseModel):
    """User info for feedback responses"""
    id: UUID
    email: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


class CommentResponse(BaseModel):
    """Schema for comment response"""
    id: UUID
    feedback_id: UUID
    user_id: Optional[UUID]
    user: Optional[FeedbackUserInfo] = None
    is_admin_response: bool
    comment_text: str
    attachments: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedbackResponse(BaseModel):
    """Schema for feedback response"""
    id: UUID
    user_id: Optional[UUID]
    user: Optional[FeedbackUserInfo] = None
    feedback_type: str
    title: str
    description: str
    priority: str
    status: str
    category: Optional[str]
    affected_feature: Optional[str]
    browser_info: Optional[Dict[str, Any]]
    device_info: Optional[Dict[str, Any]]
    screenshot_url: Optional[str]
    attachments: Optional[List[Dict[str, Any]]]
    admin_notes: Optional[str]
    admin_response: Optional[str]
    assigned_to: Optional[UUID]
    assigned_admin: Optional[FeedbackUserInfo] = None
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    comments: List[CommentResponse] = []

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    """Schema for paginated feedback list"""
    total: int
    page: int
    page_size: int
    feedback_items: List[FeedbackResponse]


class FeedbackStats(BaseModel):
    """Feedback statistics for admin dashboard"""
    total_feedback: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    recent_feedback: int  # Last 7 days
    unresolved_count: int


class ChatFeedbackCreate(BaseModel):
    """Schema for quick chat message feedback"""
    chat_id: str = Field(..., description="Chat conversation ID")
    message_id: str = Field(..., description="Specific message ID being rated")
    rating: str = Field(..., description="Rating: 'positive', 'negative', or 'hallucination'")
    message_content: Optional[str] = Field(None, description="The message content for context", max_length=500)
    feedback_text: Optional[str] = Field(None, description="User's correction or explanation (for hallucination reports)", max_length=500)


class ChatFeedbackResponse(BaseModel):
    """Response for chat feedback submission"""
    success: bool
    feedback_id: UUID
    message: str
