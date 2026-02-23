"""
Amendment Alignment Score Model

Cached AI-generated alignment scores between a user's policy position
and MEP amendments. Keyed by (user_id, policy_position_hash, mep_amendment_id)
to avoid redundant AI calls.

Phase 4 of MEP Amendments feature.

Created: February 2026
"""

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, CheckConstraint,
    Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from core.database import Base


class AlignmentScore(Base):
    """
    Cached alignment score between a user's policy position and an MEP amendment.

    Score scale:
      +2 = strongly aligned
      +1 = partially aligned
       0 = neutral / unrelated
      -1 = partially opposed
      -2 = strongly opposed
    """
    __tablename__ = "amendment_alignment_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    procedure_reference = Column(String(50), nullable=False)
    policy_position_hash = Column(String(64), nullable=False)
    mep_amendment_id = Column(UUID(as_uuid=True), ForeignKey("mep_amendments.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)
    scored_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint('score BETWEEN -2 AND 2', name='ck_alignment_score_range'),
        Index('ix_alignment_user_proc', 'user_id', 'procedure_reference', 'policy_position_hash'),
        UniqueConstraint('user_id', 'policy_position_hash', 'mep_amendment_id', name='uq_alignment_score'),
    )

    def __repr__(self):
        return f"<AlignmentScore user={self.user_id} amendment={self.mep_amendment_id} score={self.score}>"
