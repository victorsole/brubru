"""
File Position Snapshot model.

Cached aggregate positions for a legislative file (Commission / Parliament /
Council). Refreshed by services/positions/position_aggregator.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.database import Base


class FilePositionSnapshot(Base):
    __tablename__ = "file_position_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    procedure_ref = Column(String(50), nullable=False, index=True)

    commission_position = Column(JSONB, nullable=True)
    parliament_position = Column(JSONB, nullable=True)
    council_position = Column(JSONB, nullable=True)
    amendment_positions = Column(JSONB, nullable=True)

    data_completeness = Column(String(16), default="partial")
    confidence = Column(String(16), default="medium")
    sources = Column(JSONB, nullable=True)

    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    carriage = relationship("LegislativeCarriage")

    def __repr__(self) -> str:
        return f"<FilePositionSnapshot procedure={self.procedure_ref} at={self.generated_at.isoformat() if self.generated_at else '?'}>"
