"""
API Key Model

SQLAlchemy model for API keys used by the Brubru Data Provider API (/api/v1/*).

Design:
- Plaintext key format: "brubru_live_" + 48 hex chars (192 bits entropy)
- Only the SHA-256 hash is persisted; plaintext is shown ONCE at creation
- key_prefix stores 4 hex chars for admin display ("ends in ...a3f9")
- Gated at the auth layer on user.subscription_tier == "blue"
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Tuple

from sqlalchemy import Column, String, DateTime, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base


KEY_PREFIX = "brubru_live_"
_RANDOM_BYTES = 24  # 192 bits of entropy; token_hex(24) returns 48 hex chars


class ApiKey(Base):
    """API key issued to a Professional subscriber."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(CHAR(64), nullable=False, unique=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    scopes = Column(JSONB, nullable=False, default=list)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(INET, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="api_keys")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @classmethod
    def generate(cls, user_id: uuid.UUID, name: str) -> Tuple[str, "ApiKey"]:
        """
        Create a new API key.

        Returns (plaintext, api_key_instance). The plaintext is shown ONCE to
        the caller and never persisted. Add the instance to the session and
        commit.
        """
        random_part = secrets.token_hex(_RANDOM_BYTES)
        plaintext = f"{KEY_PREFIX}{random_part}"
        key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        instance = cls(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=random_part[:4],
            name=name,
            scopes=[],
        )
        return plaintext, instance

    @staticmethod
    def hash_plaintext(plaintext: str) -> str:
        """Stable SHA-256 hex digest used for lookup."""
        return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_plaintext(plaintext: str, stored_hash: str) -> bool:
        """Constant-time comparison of the computed hash against the stored hash."""
        candidate = ApiKey.hash_plaintext(plaintext)
        return hmac.compare_digest(candidate, stored_hash)
