"""
EP Committee Minutes Database Model.

Stores metadata and extracted content from EP committee meeting minutes.
Minutes are published as PDFs on europarl.europa.eu after each committee meeting.

Created: April 2026
"""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, Text,
    Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from datetime import datetime
import uuid

from core.database import Base


class CommitteeMinutes(Base):
    """
    EP Committee meeting minutes record.

    One record per committee per meeting date.
    Contains metadata from the listing page + optionally extracted PDF content.
    """
    __tablename__ = "committee_minutes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core identifiers
    committee_code = Column(String(10), nullable=False)     # "LIBE", "AFET"
    meeting_date = Column(DateTime, nullable=False)          # Date of the meeting
    meeting_date_end = Column(DateTime, nullable=True)       # End date if multi-day
    pe_reference = Column(String, nullable=True)             # "PE779.658v01-00"
    document_reference = Column(String, nullable=True)       # "LIBE_PV(2025)11-10-1"

    # Content
    title = Column(String, nullable=False)                   # "MINUTES - Monday, 10 November 2025"

    # URLs
    pdf_url = Column(String)
    doc_url = Column(String)
    source_url = Column(String)

    # Extracted content (from PDF, optional)
    full_text = Column(Text)
    word_count = Column(Integer)
    page_count = Column(Integer)
    has_full_text = Column(Boolean, default=False)
    extraction_quality = Column(String)                      # "high", "medium", "low"

    # Structured extracted data (JSON)
    agenda_items = Column(JSON, default=list)                # [{number, title, procedure_ref, outcome}]
    votes = Column(JSON, default=list)                       # [{subject, for, against, abstain, result, procedure_ref}]
    decisions = Column(JSON, default=list)                   # [{text, type}]
    attendees_count = Column(Integer)
    related_procedure_refs = Column(ARRAY(String), default=list)

    # Temporal
    publication_date = Column(DateTime, nullable=True)       # When minutes were published (from subtitle)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('committee_code', 'meeting_date', name='uq_committee_minutes_code_date'),
        Index('ix_committee_minutes_committee_code', 'committee_code'),
        Index('ix_committee_minutes_meeting_date', 'meeting_date'),
    )

    def __repr__(self):
        return f"<CommitteeMinutes {self.committee_code} {self.meeting_date}>"
