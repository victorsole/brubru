"""
API Key Model

SQLAlchemy model for API keys used by the Brubru Data Provider API (/api/v1/*).

Design:
- Plaintext key format: "brubru_live_" + 48 hex chars (192 bits entropy)
- Only the SHA-256 hash is persisted; plaintext is shown ONCE at creation
- key_prefix stores 4 hex chars for human display ("ends in ...a3f9")
- Self-serve mints choose a scope set + 180-day default expiry
- Admin mints default to scopes=["*"] (blanket) + no expiry, for back-compat
- A single is_sandbox=TRUE row powers the public /api/docs "Try it" experience
  and bills against the shared sandbox pool (api_sandbox_pool), not user balance.

Auth gating (post-Phase A):
  - subscription_tier check REMOVED. API access is now gated by:
      1. A valid, non-revoked, non-expired key (auth_api_key.py)
      2. Scope match for the requested path (services/api_keys/scopes.py)
      3. Positive euro balance OR sandbox key (Phase B billing middleware)
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import Boolean, CHAR, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


KEY_PREFIX = "brubru_live_"
_RANDOM_BYTES = 24  # 192 bits of entropy; token_hex(24) returns 48 hex chars
DEFAULT_SELF_SERVE_EXPIRY_DAYS = 180


class ApiKey(Base):
    """API key issued to a Brubru user for /api/v1/* access."""

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
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_sandbox = Column(Boolean, nullable=False, default=False)
    # Per-key rate-limit tier. Enforced in services/rate_limiter/global_rate_limiter.py.
    # free=60/min, pro=300/min, enterprise=6000/min. Default free for any new key.
    api_tier = Column(String(20), nullable=False, default="free")

    user = relationship("User", backref="api_keys")

    @property
    def is_expired(self) -> bool:
        """True iff expires_at is set and in the past."""
        if self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        # Some legacy rows may carry naive datetimes; normalise.
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp < now

    @property
    def is_active(self) -> bool:
        """True iff the key is not revoked and not expired."""
        return self.revoked_at is None and not self.is_expired

    @property
    def has_scope(self) -> bool:
        """Sentinel for callers to detect wildcard. Use grants_scope() for actual checks."""
        return bool(self.scopes)

    def grants_scope(self, required: Optional[str]) -> bool:
        """Return True if this key is permitted to access an endpoint requiring `required`.

        - `required` of None means a free/public endpoint — always allowed.
        - A scope list containing "*" is the wildcard (admin / back-compat) — allowed.
        - Otherwise the exact required scope must be present in the list.
        """
        if required is None:
            return True
        scopes = self.scopes or []
        if "*" in scopes:
            return True
        return required in scopes

    @classmethod
    def generate(
        cls,
        user_id: uuid.UUID,
        name: str,
        scopes: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        is_sandbox: bool = False,
    ) -> Tuple[str, "ApiKey"]:
        """Create a new API key.

        Args:
            user_id: Owner.
            name: Human label, 1-100 chars (enforced both by Pydantic and a DB check).
            scopes: List of scope strings. None means ["*"] (back-compat for admin path).
                    Self-serve callers pass an explicit list.
            expires_in_days: None means never expires (admin path). Self-serve callers pass
                             a positive int (default 180) so we get the column populated.
            is_sandbox: Mark the row as Brubru's single public-sandbox key. There can be
                        at most one active sandbox row (enforced by unique partial index).

        Returns:
            (plaintext, instance). The plaintext is shown ONCE to the caller and never
            persisted. Add the instance to the session and commit.
        """
        random_part = secrets.token_hex(_RANDOM_BYTES)
        plaintext = f"{KEY_PREFIX}{random_part}"
        key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

        resolved_scopes = scopes if scopes is not None else ["*"]
        expires_at: Optional[datetime] = None
        if expires_in_days is not None:
            if expires_in_days <= 0:
                raise ValueError("expires_in_days must be positive")
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        instance = cls(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=random_part[:4],
            name=name,
            scopes=resolved_scopes,
            expires_at=expires_at,
            is_sandbox=is_sandbox,
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
