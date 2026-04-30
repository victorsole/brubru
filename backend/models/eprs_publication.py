"""
EPRS Publication Database Models.

SQLAlchemy models for European Parliament Research Service publications
(At a Glance, Briefings, In-Depth Analyses, Studies).

EPRS data is chatbot-only -- no dedicated UI tab.
The context builder queries this table to inject plain-language
explainers into AI chat context alongside EUR-Lex and OEIL data.

Created: February 2026
"""

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    Index
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy import Enum as SQLEnum
from datetime import datetime
import uuid
import enum

from core.database import Base


class EPRSPublicationTypeEnum(str, enum.Enum):
    """Types of EPRS publications."""
    AT_A_GLANCE = "at_a_glance"
    BRIEFING = "briefing"
    IN_DEPTH_ANALYSIS = "in_depth_analysis"
    STUDY = "study"
    BLOG_POST = "blog_post"
    OTHER = "other"


class EPRSPublication(Base):
    """
    A publication from the European Parliament Research Service.

    Covers At a Glance notes (1-2 pages), Briefings (4-8 pages),
    In-Depth Analyses (13-36 pages), and Studies (50-100+ pages).

    These act as "jargon translators" -- plain-language explanations
    of complex EU legislation. The chatbot uses them to enrich
    responses when users ask about specific laws or procedures.
    """
    __tablename__ = "eprs_publications"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core identifiers
    publication_id = Column(String, nullable=False, unique=True)  # e.g. "EPRS_BRI(2024)762322"
    title = Column(String, nullable=False)

    # Classification
    publication_type = Column(
        SQLEnum(
            'at_a_glance', 'briefing', 'in_depth_analysis',
            'study', 'blog_post', 'other',
            name='eprs_publication_type_enum',
            create_type=False
        ),
        nullable=False
    )

    # URLs
    html_url = Column(String)   # epthinktank.eu page
    pdf_url = Column(String)    # europarl.europa.eu/RegData PDF

    # Publication metadata
    authors = Column(ARRAY(String), default=[])
    publication_date = Column(DateTime)

    # Content
    summary = Column(Text)      # Abstract / short summary
    full_text = Column(Text)    # Complete extracted text from PDF
    word_count = Column(Integer)
    page_count = Column(Integer)

    # Legislative context (critical for chatbot matching)
    policy_areas = Column(ARRAY(String), default=[])
    committees = Column(ARRAY(String), default=[])   # EP committee codes
    related_celex_numbers = Column(ARRAY(String), default=[])  # e.g. ["32024R1689"]
    related_procedures = Column(ARRAY(String), default=[])     # e.g. ["2021/0106(COD)"]

    # Categorization
    categories = Column(ARRAY(String), default=[])   # RSS tags

    # Quality metrics
    extraction_quality = Column(String)  # "high", "medium", "low"
    has_full_text = Column(Boolean, default=False)

    # Source discriminator (migration 041) — eprs | stoa | jrc | art | eca
    source = Column(String(10), nullable=False, default="eprs")
    # Reference numbers used by some sources
    doi = Column(Text, nullable=True)               # JRC + ECA papers carry a DOI
    eur_number = Column(String(50), nullable=True)  # JRC technical reports use EUR XXXXX

    # Temporal tracking
    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Indexes for chatbot queries
    __table_args__ = (
        Index('ix_eprs_publications_publication_id', 'publication_id'),
        Index('ix_eprs_publications_publication_type', 'publication_type'),
        Index('ix_eprs_publications_publication_date', 'publication_date'),
        Index('ix_eprs_publications_celex', 'related_celex_numbers', postgresql_using='gin'),
        Index('ix_eprs_publications_procedures', 'related_procedures', postgresql_using='gin'),
        Index('ix_eprs_publications_policy_areas', 'policy_areas', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<EPRSPublication {self.publication_id}: {self.title[:50]}>"
