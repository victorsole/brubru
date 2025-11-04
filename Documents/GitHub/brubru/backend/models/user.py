"""
User Model

SQLAlchemy model for Brubru users stored in Supabase.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from ..core.database import Base


class User(Base):
    """
    User model matching Supabase auth.users structure.

    Note: Supabase manages auth.users table automatically.
    This model is for your custom user data in the public schema.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=True)
    organization = Column(String(200), nullable=True)
    role = Column(String(50), default="user")  # user, admin
    avatar_url = Column(String(500), nullable=True)

    # Profile info
    country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    policy_interests = Column(Text, nullable=True)  # JSON array as text

    # Subscription info
    subscription_tier = Column(String(50), default="free")  # free, professional, team, enterprise
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
