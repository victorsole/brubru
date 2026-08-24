"""Social post model — Phase 4.2 open-tier content layer.

Recent posts fetched from mapped accounts via public keyless APIs (Bluesky / Mastodon /
YouTube RSS). Mirrors migrations/195_social_posts.sql. Hard platforms produce no rows (D1).
"""
from sqlalchemy import (
    Boolean,
    Column, BigInteger, Text, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from core.database import Base


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(BigInteger, ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False)
    platform = Column(Text, ForeignKey("social_platforms.code"), nullable=False)
    platform_post_id = Column(Text, nullable=False)   # native id/uri; dedup within account
    post_url = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    lang = Column(Text, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    like_count = Column(BigInteger, nullable=True)
    repost_count = Column(BigInteger, nullable=True)
    reply_count = Column(BigInteger, nullable=True)
    view_count = Column(BigInteger, nullable=True)
    # Repost provenance (migration 219, 24 Aug 2026). Without these, a repost is
    # indistinguishable from a statement the account made: 398 post bodies
    # appeared under more than one account in 30 days, and the database read as
    # though Thomas Pellerin-Carlin had declared for the French presidency when
    # he had reposted Raphael Glucksmann. Never cite a row with is_repost = True
    # as evidence of what THIS actor said.
    is_repost = Column(Boolean, nullable=False, default=False, server_default="false")
    original_author = Column(Text, nullable=True)
    media = Column(JSONB, nullable=False, default=list)
    extra = Column(JSONB, nullable=False, default=dict)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "platform_post_id", name="social_posts_account_post_uq"),
        Index("idx_social_posts_account", "account_id"),
        Index("idx_social_posts_posted", "posted_at"),
        Index("idx_social_posts_platform", "platform"),
    )
