"""
Password Reset Token Model

Backs the "I forgot my password" flow on the login page.
See backend/migrations/211_password_reset_tokens.sql for the schema rationale,
in particular why only the sha256 of the token is stored.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # sha256 hex digest of the raw token. The raw token exists only in the email.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    request_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def is_redeemable(self) -> bool:
        """True when the token has not been used and has not expired."""
        if self.used_at is not None:
            return False
        expires = self.expires_at
        # Postgres gives us tz-aware values; be defensive if a naive one appears.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > datetime.now(timezone.utc)
