"""
User Document Model

SQLAlchemy model for user-created documents in My EU Bubble.
Part of My EU Bubble - Phase 2: User Content Repository
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class UserDocument(Base):
    """
    User Document model.

    Stores user-created content in My EU Bubble:
    - Amendments
    - Policy analyses
    - Strategy documents
    - Meeting notes
    - Research notes
    """
    __tablename__ = "user_documents"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Document type and metadata
    document_type = Column(String(50), nullable=False, index=True)  # amendment, analysis, strategy, note, uploaded
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)  # Main content

    # Links to EU legislation/procedures
    celex_number = Column(String(100), nullable=True, index=True)  # Link to EU legislation
    procedure_reference = Column(String(100), nullable=True, index=True)  # Link to legislative procedure

    # Policy areas (for filtering and organization)
    policy_areas = Column(ARRAY(String(100)), nullable=True, index=True)  # Array of policy interests

    # Tags and categorization
    tags = Column(ARRAY(String(100)), nullable=True)  # User-defined tags

    # Amendment-specific fields (when document_type = 'amendment')
    amendment_target = Column(Text, nullable=True)  # Original text being amended
    amendment_justification = Column(Text, nullable=True)  # Justification for amendment
    amendment_status = Column(String(50), nullable=True)  # draft, submitted, adopted, rejected

    # Analysis-specific fields (when document_type = 'analysis')
    executive_summary = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    conclusions = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    # Strategy-specific fields (when document_type = 'strategy')
    objectives = Column(Text, nullable=True)
    action_plan = Column(Text, nullable=True)
    timeline = Column(String(500), nullable=True)
    stakeholders = Column(ARRAY(String(200)), nullable=True)

    # Flexible metadata storage
    doc_metadata = Column(JSONB, nullable=True)  # Additional document-specific data

    # Uploaded document fields (when document_type = 'uploaded')
    storage_document_id = Column(String(36), nullable=True, index=True)  # Links to filesystem uploads/{id}/
    original_filename = Column(String(500), nullable=True)
    file_content_type = Column(String(100), nullable=True)  # e.g., application/pdf
    file_size_bytes = Column(Integer, nullable=True)

    # AI context control
    include_in_ai_context = Column(Boolean, default=False)  # True for uploaded docs by default

    # Privacy and sharing
    is_private = Column(Boolean, default=True)  # Private by default
    shared_with = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # User IDs with access

    # Version control
    version = Column(Integer, default=1)
    parent_document_id = Column(UUID(as_uuid=True), ForeignKey("user_documents.id", ondelete="SET NULL"), nullable=True)

    # Search and discovery
    is_featured = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="documents")
    versions = relationship("UserDocument", backref="parent", remote_side=[id])

    def __repr__(self):
        return f"<UserDocument(id={self.id}, type={self.document_type}, title={self.title[:50]})>"

    @property
    def word_count(self) -> int:
        """Calculate word count of content"""
        if not self.content:
            return 0
        return len(self.content.split())

    @property
    def is_amendment(self) -> bool:
        """Check if document is an amendment"""
        return self.document_type == "amendment"

    @property
    def is_analysis(self) -> bool:
        """Check if document is an analysis"""
        return self.document_type == "analysis"

    @property
    def is_strategy(self) -> bool:
        """Check if document is a strategy"""
        return self.document_type == "strategy"

    @property
    def is_note(self) -> bool:
        """Check if document is a note"""
        return self.document_type == "note"

    @property
    def is_uploaded(self) -> bool:
        """Check if document is an uploaded file"""
        return self.document_type == "uploaded"

    @property
    def has_eu_link(self) -> bool:
        """Check if document is linked to EU legislation or procedure"""
        return bool(self.celex_number or self.procedure_reference)

    def increment_view_count(self):
        """Increment view count"""
        from datetime import datetime, timezone
        self.view_count += 1
        self.last_accessed_at = datetime.now(timezone.utc)

    def create_new_version(self, session) -> 'UserDocument':
        """
        Create a new version of this document.

        Args:
            session: SQLAlchemy session

        Returns:
            New version of the document
        """
        # Create copy with incremented version
        new_doc = UserDocument(
            user_id=self.user_id,
            document_type=self.document_type,
            title=self.title,
            content=self.content,
            celex_number=self.celex_number,
            procedure_reference=self.procedure_reference,
            policy_areas=self.policy_areas,
            tags=self.tags,
            amendment_target=self.amendment_target,
            amendment_justification=self.amendment_justification,
            amendment_status=self.amendment_status,
            executive_summary=self.executive_summary,
            methodology=self.methodology,
            conclusions=self.conclusions,
            recommendations=self.recommendations,
            objectives=self.objectives,
            action_plan=self.action_plan,
            timeline=self.timeline,
            stakeholders=self.stakeholders,
            doc_metadata=self.doc_metadata,
            is_private=self.is_private,
            version=self.version + 1,
            parent_document_id=self.id
        )

        session.add(new_doc)
        return new_doc
