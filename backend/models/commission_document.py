"""
Commission Document Database Models.

SQLAlchemy models for EC Register of Commission Documents
(COM, SWD, SEC, C, JOIN, OJ, PV).

Created: February 2026
"""

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from core.database import Base


class CommissionDocTypeEnum(str, enum.Enum):
    """Types of documents in the Register of Commission Documents."""
    COM = "COM"
    SWD = "SWD"
    SEC = "SEC"
    C = "C"
    JOIN = "JOIN"
    OJ = "OJ"
    PV = "PV"


class CommissionDocument(Base):
    """
    A document from the EC Register of Commission Documents.

    Covers legislative proposals (COM), staff working documents (SWD),
    delegated/implementing acts (C), joint documents (JOIN),
    Official Journal items (OJ), and Commission meeting minutes (PV).
    """
    __tablename__ = "commission_documents"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identifiers
    reference = Column(String, nullable=False, unique=True)  # e.g. "COM(2025) 87"
    title = Column(String, nullable=False)

    # Classification
    doc_type = Column(
        SQLEnum(
            'COM', 'SWD', 'SEC', 'C', 'JOIN', 'OJ', 'PV',
            name='commission_doc_type_enum',
            create_type=False
        ),
        nullable=False
    )

    # Metadata
    publication_date = Column(DateTime)
    dg_responsible = Column(String)  # DG code e.g. "CNECT"
    procedure_ref = Column(String)   # OEIL cross-ref e.g. "2021/0106(COD)"
    languages = Column(ARRAY(String), default=[])
    portal_url = Column(String)      # EUR-Lex or RegDoc landing page URL
    pdf_url = Column(Text, nullable=True)  # Direct PDF asset URL when available (migration 040)
    document_register_category = Column(String(50), nullable=True)  # AGENDA_COM_MEETING / TENTAT_AGENDA_COM_MEETING / OPIN_IMPACT_ASSESS / ...
    source_url = Column(Text, nullable=True)  # Commission Transparency Register search URL or other origin
    celex = Column(String)           # CELEX number for adopted acts
    common_name = Column(String)     # Colloquial name e.g. "Digital Omnibus Act"
    # Body text backfilled from Cellar (migration 051). XHTML-stripped plain
    # text for SWDs / opinions; PDF-extracted text for JOIN/RES/DEC.
    text_body = Column(Text, nullable=True)
    # HTML body added in migration 067 — Cellar XHTML manifestation (EN) for
    # CELEX-bearing rows. Null when Cellar has no XHTML representation.
    body_html = Column(Text, nullable=True)

    # Cross-references
    legislative_carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id"),
        nullable=True
    )

    # Temporal tracking
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    legislative_carriage = relationship(
        "LegislativeCarriage",
        foreign_keys=[legislative_carriage_id]
    )
    user_tracks = relationship(
        "UserCommissionDocTrack",
        back_populates="commission_document",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index('ix_commission_documents_reference', 'reference'),
        Index('ix_commission_documents_doc_type', 'doc_type'),
        Index('ix_commission_documents_publication_date', 'publication_date'),
        Index('ix_commission_documents_procedure_ref', 'procedure_ref'),
        Index('ix_commission_documents_celex', 'celex'),
    )

    def __repr__(self):
        return f"<CommissionDocument {self.reference}: {self.title[:50]}>"


class UserCommissionDocTrack(Base):
    """
    User subscription to a Commission document.

    Allows users to track specific Commission documents.
    """
    __tablename__ = "user_commission_doc_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    commission_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("commission_documents.id"),
        nullable=False
    )

    # Tracking metadata
    notify_on_new_documents = Column(Boolean, default=True)
    tracked_since = Column(DateTime, default=datetime.now, nullable=False)
    notes = Column(Text)

    # Archive (migration 041): NULL = active, non-null = archived.
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archived_reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("User")
    commission_document = relationship("CommissionDocument", back_populates="user_tracks")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'commission_document_id',
            name='uq_user_commission_doc_track'
        ),
        Index('ix_user_commission_doc_track_user_id', 'user_id'),
        Index('ix_user_commission_doc_track_doc_id', 'commission_document_id'),
    )

    def __repr__(self):
        return f"<UserCommissionDocTrack user={self.user_id} doc={self.commission_document_id}>"
