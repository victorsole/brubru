"""
TenderFile — container row that groups all the user_documents the user writes
for ONE EU funding application (e.g. a single EIC Accelerator submission).

Programme / sub_instrument / topic_id / stage / funding_mode / deadline /
status / template_id / scaffold_version live here once, not duplicated on
every doc.

Schema is in migrations/146_tender_files.sql. See `docs/api/api_funds.md`
for the Tender Docs design (16 Jun 2026).
"""
from __future__ import annotations

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class TenderFile(Base):
    __tablename__ = "tender_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(Text, nullable=False)

    # Programme anchors
    programme = Column(Text, nullable=False, index=True)
    sub_instrument = Column(Text, nullable=True)
    stage = Column(Text, nullable=True)
    topic_id = Column(Text, nullable=True, index=True)
    topic_variant = Column(Text, nullable=True)
    funding_mode = Column(Text, nullable=True)

    # Process anchors
    deadline_iso = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default="drafting", index=True)

    # Template anchor
    template_id = Column(Text, nullable=False)
    scaffold_version = Column(Text, nullable=False)

    # Optional cross-link to a saved/tracked tender row (no FK by design)
    tender_track_id = Column(UUID(as_uuid=True), nullable=True)

    # Flex metadata
    extra = Column(JSONB, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships — user_documents.tender_file_id points back here
    user = relationship("User", backref="tender_files")

    def __repr__(self) -> str:
        return f"<TenderFile(id={self.id}, programme={self.programme}, sub={self.sub_instrument}, title={self.title[:40]})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "programme": self.programme,
            "sub_instrument": self.sub_instrument,
            "stage": self.stage,
            "topic_id": self.topic_id,
            "topic_variant": self.topic_variant,
            "funding_mode": self.funding_mode,
            "deadline_iso": self.deadline_iso.isoformat() if self.deadline_iso else None,
            "status": self.status,
            "template_id": self.template_id,
            "scaffold_version": self.scaffold_version,
            "tender_track_id": str(self.tender_track_id) if self.tender_track_id else None,
            "extra": self.extra or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
