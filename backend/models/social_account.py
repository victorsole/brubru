"""
Social account directory models — Phase 4, Wave 0.

SocialPlatform: extensible reference table (a new platform is one row, not a migration) that
also carries the content-fetch feasibility tier.

SocialAccount: polymorphic (entity_type, entity_key) mapping of EU entities to their social
accounts across all platforms. Account MAPPING only (Phase 4.1); content fetching (4.2) is
gated per-account by content_fetch_enabled. Schema mirrors migrations/193_social_accounts.sql.
"""

from sqlalchemy import (
    Column, BigInteger, Boolean, Text, Float, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from core.database import Base


class SocialPlatform(Base):
    __tablename__ = "social_platforms"

    code = Column(Text, primary_key=True)          # 'x', 'linkedin', 'mastodon', ...
    name = Column(Text, nullable=False)
    fetch_tier = Column(Text, nullable=False, default="none")  # open | gated | hard | none
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    entity_type = Column(Text, nullable=False)     # institution|ec_dg|...|mep|commissioner|...
    entity_key = Column(Text, nullable=False)      # natural id in the source table
    entity_name = Column(Text, nullable=True)

    platform = Column(Text, ForeignKey("social_platforms.code"), nullable=False)
    scope = Column(Text, nullable=False, default="central")  # central|country:DE|language:fr|...
    handle = Column(Text, nullable=True)
    account_url = Column(Text, nullable=False)     # canonical URL; the dedup key
    platform_account_id = Column(Text, nullable=True)

    status = Column(Text, nullable=False, default="candidate")  # candidate|verified|rejected|dormant
    verified = Column(Boolean, nullable=False, default=False)
    verification_source = Column(Text, nullable=True)
    discovery_source = Column(Text, nullable=False)  # wikidata|eu_directory|ep_page|official_site|eutr|manual
    confidence = Column(Float, nullable=True)

    follower_count = Column(BigInteger, nullable=True)
    content_fetch_enabled = Column(Boolean, nullable=False, default=False)

    extra = Column(JSONB, nullable=False, default=dict)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_url", name="social_accounts_url_uq"),
        Index("idx_social_accounts_entity", "entity_type", "entity_key"),
        Index("idx_social_accounts_platform", "platform"),
        Index("idx_social_accounts_status", "status"),
    )
