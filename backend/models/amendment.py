"""
Amendment Model

SQLAlchemy model for legislative amendments created in the Amendator feature.
"""

from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..core.database import Base


class Amendment(Base):
    """
    Amendment model for tracking legislative amendments.

    Each amendment represents a change (suppression, addition, or modification)
    to a specific legislative element within a document.
    """
    __tablename__ = "amendments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Document reference
    document_id = Column(String(255), nullable=False, index=True)
    document_filename = Column(String(500), nullable=True)

    # Legislative element identification
    element_index = Column(Integer, nullable=False)
    element_type = Column(String(50), nullable=False)  # recital, article, point, paragraph, subparagraph
    element_number = Column(String(20), nullable=True)  # "1", "3a", "a", "i", etc.
    position_text = Column(String(500), nullable=False)  # "Recital 15", "Article 3, point 2"

    # Amendment details
    amendment_type = Column(String(50), nullable=False)  # suppression, addition, modification
    original_text = Column(Text, nullable=False)
    proposed_text = Column(Text, nullable=False)

    # For additions: which element to insert after
    insert_after = Column(Integer, nullable=True)

    # Optional metadata
    justification = Column(Text, nullable=True)
    group_label = Column(String(200), nullable=True)  # Political group or committee
    author = Column(String(200), nullable=True)
    amendment_number = Column(String(50), nullable=True)  # AM 1, AM 2, etc.

    # Status tracking
    status = Column(String(50), default="draft")  # draft, candidate, tabled, withdrawn, adopted, rejected

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="amendments")

    def __repr__(self):
        return f"<Amendment(id={self.id}, type={self.amendment_type}, position={self.position_text})>"

    def to_dict(self):
        """Convert amendment to dictionary for API responses"""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'document_id': self.document_id,
            'document_filename': self.document_filename,
            'element_index': self.element_index,
            'element_type': self.element_type,
            'element_number': self.element_number,
            'position_text': self.position_text,
            'amendment_type': self.amendment_type,
            'original_text': self.original_text,
            'proposed_text': self.proposed_text,
            'insert_after': self.insert_after,
            'justification': self.justification,
            'group_label': self.group_label,
            'author': self.author,
            'amendment_number': self.amendment_number,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
