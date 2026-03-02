"""
User Model

SQLAlchemy model for Brubru users stored in Supabase.
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import json

from core.database import Base


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

    # Authentication
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    oauth_provider = Column(String(50), nullable=True)  # google, linkedin, eu_login

    # Personalisation fields
    first_name = Column(String(100), nullable=True)
    preferred_name = Column(String(100), nullable=True)
    timezone = Column(String(100), nullable=True)  # e.g., "Europe/Brussels"
    language = Column(String(10), nullable=True)   # e.g., "en", "fr"
    background_preference = Column(String(100), default="default", nullable=True)  # Background image filename

    # Profile info
    country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    policy_interests = Column(JSONB, nullable=True)  # JSON array

    # User preferences (tour progress, UI settings, etc.)
    preferences = Column(JSONB, nullable=True, default=dict)

    # Subscription info
    subscription_tier = Column(String(50), default="white")  # white, yellow, blue
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Stripe payment info
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_trainer = Column(Boolean, default=False)

    # Relationships
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    @property
    def policy_interests_list(self):
        """
        Get policy_interests as a list, handling both TEXT (JSON string) and JSONB formats.
        Provides backward compatibility during migration.
        """
        if self.policy_interests is None:
            return None

        # If it's already a list (JSONB), return it
        if isinstance(self.policy_interests, list):
            return self.policy_interests

        # If it's a string (old TEXT format), parse it
        if isinstance(self.policy_interests, str):
            try:
                return json.loads(self.policy_interests)
            except (json.JSONDecodeError, ValueError):
                return None

        return None

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
