"""
Feedback System Models

SQLAlchemy models for user feedback, bug reports, and admin panel functionality.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, TIMESTAMP, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from core.database import Base


class FeedbackSubmission(Base):
    """User feedback, bug reports, and feature requests"""
    __tablename__ = "feedback_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    feedback_type = Column(String(50), nullable=False)  # bug, feature_request, general, other
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default='medium')  # low, medium, high, critical
    status = Column(String(50), default='new')  # new, in_review, in_progress, resolved, closed, wont_fix
    category = Column(String(100), nullable=True)
    affected_feature = Column(String(100), nullable=True)
    browser_info = Column(JSONB, nullable=True)
    device_info = Column(JSONB, nullable=True)
    screenshot_url = Column(Text, nullable=True)
    attachments = Column(JSONB, nullable=True)
    admin_notes = Column(Text, nullable=True)
    admin_response = Column(Text, nullable=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="feedback_submissions")
    assigned_admin = relationship("User", foreign_keys=[assigned_to], backref="assigned_feedback")
    comments = relationship("FeedbackComment", back_populates="feedback", cascade="all, delete-orphan")


class FeedbackComment(Base):
    """Comments and conversation thread for feedback items"""
    __tablename__ = "feedback_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feedback_id = Column(UUID(as_uuid=True), ForeignKey('feedback_submissions.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_admin_response = Column(Boolean, default=False)
    comment_text = Column(Text, nullable=False)
    attachments = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    feedback = relationship("FeedbackSubmission", back_populates="comments")
    user = relationship("User", backref="feedback_comments")


class AdminActivityLog(Base):
    """Audit log of all admin actions"""
    __tablename__ = "admin_activity_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action_type = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    action_details = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    admin_user = relationship("User", backref="admin_actions")


class SystemSettings(Base):
    """System-wide configuration settings"""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    is_public = Column(Boolean, default=False)
    last_modified_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    modifier = relationship("User", backref="modified_settings")
