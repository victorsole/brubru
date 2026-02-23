"""
MEP Amendment Database Models.

SQLAlchemy models for scraped EP committee amendments
(draft reports, amendments tabled in committee, committee reports).

Separate from the existing Amendment model which stores user-authored amendments.

Created: February 2026
"""

from sqlalchemy import (
    Column, String, Boolean, Integer, Float, DateTime, Date, Text,
    Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from core.database import Base


class AmendmentDocument(Base):
    """
    Tracks EP amendment documents that have been fetched and parsed.

    Each row represents one PE-numbered document from the EP documentation
    gateway (e.g. JURI-AM-753448_EN.docx).
    """
    __tablename__ = "amendment_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    procedure_reference = Column(String(50), nullable=False, index=True)  # "2023/0089(COD)"
    committee_code = Column(String(10), nullable=False)                   # "JURI"
    pe_reference = Column(String(20), nullable=False, unique=True)        # "PE753.448"
    document_type = Column(String(10), nullable=False)                    # "PR", "AM", "RD", "AD", "PA"
    document_date = Column(Date, nullable=True)
    doceo_url = Column(String(500), nullable=False)
    rapporteur_name = Column(String(200), nullable=True)                  # For PR documents
    total_amendments = Column(Integer, default=0)
    status = Column(String(20), default="pending")                        # "pending", "fetched", "parsed", "failed"
    error_message = Column(Text, nullable=True)
    ep_identifier = Column(String(100), nullable=True, unique=True)       # EP Open Data identifier (e.g. "LIBE-AM-779775")
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('ix_amendment_documents_procedure', 'procedure_reference'),
        Index('ix_amendment_documents_committee', 'committee_code'),
    )

    def __repr__(self):
        return f"<AmendmentDocument {self.pe_reference} ({self.document_type}) for {self.procedure_reference}>"


class MEPAmendment(Base):
    """
    A single scraped amendment from an EP committee document.

    Each amendment is a discrete proposal by one or more MEPs to change
    a specific element (article, recital, annex, etc.) of the legislative text.
    """
    __tablename__ = "mep_amendments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Procedure identification
    procedure_reference = Column(String(50), nullable=False, index=True)  # "2023/0089(COD)"
    committee_code = Column(String(10), nullable=False, index=True)       # "JURI"
    pe_reference = Column(String(20), nullable=False)                     # "PE753.448"

    # Amendment identification
    amendment_number = Column(Integer, nullable=False)                    # 1, 2, 3...

    # Author(s)
    author_names = Column(ARRAY(String), nullable=False)                 # ["Axel Voss", "Jens Gieseke"]
    political_group = Column(String(30), nullable=True)                  # "EPP"
    on_behalf_of_group = Column(Boolean, default=False)                  # group amendment vs personal
    mep_ids = Column(ARRAY(Integer), nullable=True)                      # EP MEP IDs if resolved

    # Legislative element
    element_type = Column(String(50), nullable=False)                    # "article", "recital", etc.
    element_number = Column(String(50), nullable=True)                   # "3(2)(a)"
    element_reference = Column(String(300), nullable=False)              # "Article 3, paragraph 2"

    # Amendment content
    amendment_type = Column(String(20), nullable=False)                  # "modification", "suppression", "addition"
    original_text = Column(Text, nullable=False)
    proposed_text = Column(Text, nullable=False)
    justification = Column(Text, nullable=True)
    original_language = Column(String(5), default="en")

    # Source tracking
    source_url = Column(String(500), nullable=False)                     # doceo URL
    source_format = Column(String(10), default="docx")                   # "docx" or "pdf"
    parsing_confidence = Column(Float, default=1.0)

    # Timestamps
    document_date = Column(Date, nullable=True)                          # When amendments were tabled
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Unique constraint: one amendment number per PE document
    __table_args__ = (
        UniqueConstraint('pe_reference', 'amendment_number', name='uq_mep_amendment_pe_num'),
        Index('ix_mep_amendment_procedure_committee', 'procedure_reference', 'committee_code'),
        Index('ix_mep_amendment_author_group', 'political_group'),
    )

    def __repr__(self):
        return f"<MEPAmendment AM{self.amendment_number} by {', '.join(self.author_names or [])} ({self.political_group})>"
