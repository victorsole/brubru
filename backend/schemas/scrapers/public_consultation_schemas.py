"""
Pydantic schemas for EC Public Consultations scraper.

These schemas define the structure of scraped data from the
EC "Have Your Say" portal before storage in the database.

Created: January 2026
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class ConsultationType(str, Enum):
    """Types of EC public consultations."""
    PUBLIC_CONSULTATION = "public_consultation"
    CALL_FOR_EVIDENCE = "call_for_evidence"
    FEEDBACK = "feedback"
    ROADMAP = "roadmap"
    INITIATIVE = "initiative"


class ConsultationStatus(str, Enum):
    """Status of a consultation."""
    OPEN = "open"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    OUTCOME_PUBLISHED = "outcome_published"
    WITHDRAWN = "withdrawn"


class DocumentType(str, Enum):
    """Types of consultation documents."""
    QUESTIONNAIRE = "questionnaire"
    IMPACT_ASSESSMENT = "impact_assessment"
    DRAFT_ACT = "draft_act"
    EXPLANATORY_MEMO = "explanatory_memo"
    ANNEX = "annex"
    FACTSHEET = "factsheet"
    SUMMARY = "summary"
    INCEPTION_IMPACT_ASSESSMENT = "inception_impact_assessment"
    ROADMAP = "roadmap"
    OUTCOME_REPORT = "outcome_report"
    STATISTICS = "statistics"
    OTHER = "other"


class ScrapedConsultationDocument(BaseModel):
    """A document attached to a consultation."""
    title: str = Field(..., description="Document title")
    document_type: DocumentType = Field(DocumentType.OTHER, description="Type of document")
    file_url: Optional[str] = Field(None, description="Download URL")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    language: str = Field("en", description="Document language")
    format: Optional[str] = Field(None, description="File format (PDF, DOCX, etc.)")

    class Config:
        use_enum_values = True


class ScrapedRelatedLegislation(BaseModel):
    """Related legislation referenced by a consultation."""
    title: str = Field(..., description="Legislation title")
    celex: Optional[str] = Field(None, description="CELEX number")
    com_ref: Optional[str] = Field(None, description="COM document reference")
    url: Optional[str] = Field(None, description="Link to legislation")
    type: Optional[str] = Field(None, description="Legislation type")


class ScrapedConsultationItem(BaseModel):
    """
    A single consultation scraped from the Have Your Say portal.

    This represents the basic data extracted from the list view.
    """
    # Identifiers
    initiative_id: str = Field(
        ...,
        description="EC initiative ID (unique identifier)"
    )
    publication_id: Optional[str] = Field(
        None,
        description="Publication ID for feedback submissions"
    )

    # Content
    title: str = Field(..., description="Consultation title")
    short_title: Optional[str] = Field(None, description="Short title if available")
    description: Optional[str] = Field(None, description="Short description")

    # Type and status
    consultation_type: ConsultationType = Field(
        ConsultationType.INITIATIVE,
        description="Type of consultation"
    )
    status: ConsultationStatus = Field(
        ConsultationStatus.OPEN,
        description="Current status"
    )

    # Responsible entities
    dg_responsible: Optional[str] = Field(
        None,
        description="Lead Directorate-General code (e.g., GROW, CNECT)"
    )
    policy_areas: List[str] = Field(
        default_factory=list,
        description="Policy area codes"
    )

    # Timeline
    start_date: Optional[date] = Field(None, description="Consultation opening date")
    end_date: Optional[date] = Field(None, description="Consultation deadline")

    # Statistics
    feedback_count: int = Field(0, description="Number of feedback submissions")
    views_count: Optional[int] = Field(None, description="Number of page views")

    # URLs
    portal_url: Optional[str] = Field(None, description="Link to Have Your Say page")
    feedback_url: Optional[str] = Field(None, description="Link to submit feedback")

    # Scraping metadata
    scraped_at: datetime = Field(
        default_factory=datetime.now,
        description="When this item was scraped"
    )

    class Config:
        use_enum_values = True


class ScrapedConsultationDetail(ScrapedConsultationItem):
    """
    Extended consultation with additional detail from the detail page.

    Inherits all fields from ScrapedConsultationItem and adds:
    - Full description
    - Documents
    - Related legislation
    - Outcome information
    """
    # Extended content
    full_description: Optional[str] = Field(None, description="Full consultation description")
    objectives: Optional[str] = Field(None, description="Consultation objectives")
    target_group: Optional[str] = Field(None, description="Target stakeholder groups")

    # Documents
    documents: List[ScrapedConsultationDocument] = Field(
        default_factory=list,
        description="Attached documents"
    )

    # Related legislation
    related_legislation: List[ScrapedRelatedLegislation] = Field(
        default_factory=list,
        description="Related EU legislation"
    )

    # Related COM references
    com_references: List[str] = Field(
        default_factory=list,
        description="COM document references"
    )

    # Related CELEX numbers
    celex_numbers: List[str] = Field(
        default_factory=list,
        description="Related CELEX numbers"
    )

    # Outcome (populated after deadline)
    outcome_summary: Optional[str] = Field(None, description="Summary of consultation outcome")
    outcome_published_date: Optional[date] = Field(None, description="When outcome was published")
    outcome_document_url: Optional[str] = Field(None, description="Link to outcome report")

    # Feedback statistics
    feedback_by_country: Optional[Dict[str, int]] = Field(
        None,
        description="Feedback count by country code"
    )
    feedback_by_category: Optional[Dict[str, int]] = Field(
        None,
        description="Feedback count by stakeholder category"
    )


class ScrapeConsultationsResult(BaseModel):
    """Result of a consultation scraping operation."""
    status: ConsultationStatus
    items_found: int
    pages_scraped: int
    new_items: int = 0
    updated_items: int = 0
    errors: List[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0


class ScrapeAllConsultationsResult(BaseModel):
    """Result of scraping all consultation statuses."""
    total_items: int
    open_count: int = 0
    closed_count: int = 0
    outcome_count: int = 0
    results_by_status: Dict[str, ScrapeConsultationsResult] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0


class FeedbackSubmission(BaseModel):
    """A feedback submission to a consultation (optional, for future use)."""
    submission_id: str
    consultation_id: str
    organization_name: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    feedback_text: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)
    submitted_at: Optional[datetime] = None
