"""
Base Scraper Schemas

Standardized Pydantic models for all scraper outputs.
Ensures consistency across all EU institutional scrapers.

All scrapers should output data conforming to these base schemas
or their domain-specific extensions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class DataSource(str, Enum):
    """Source institution for scraped data"""
    EUROPEAN_PARLIAMENT = "european_parliament"
    EUROPEAN_COMMISSION = "european_commission"
    COUNCIL = "council"
    EUR_LEX = "eur_lex"
    OEIL = "oeil"
    EPRS = "eprs"
    JRC = "jrc"
    DATA_EUROPA = "data_europa"
    WHO_IS_WHO = "who_is_who"
    LEGISLATIVE_TRAIN = "legislative_train"
    OTHER = "other"


class DocumentType(str, Enum):
    """Type of document"""
    LEGISLATION = "legislation"
    PROPOSAL = "proposal"
    AMENDMENT = "amendment"
    RESOLUTION = "resolution"
    REPORT = "report"
    BRIEFING = "briefing"
    PRESS_RELEASE = "press_release"
    OPINION = "opinion"
    SPEECH = "speech"
    NEWS = "news"
    PERSON = "person"
    ORGANISATION = "organisation"
    OTHER = "other"


class ScrapedItemBase(BaseModel):
    """
    Base model for all scraped items.

    All scraper outputs should extend this class to ensure
    consistent metadata and traceability.
    """
    # Unique identifier
    id: UUID = Field(default_factory=uuid4, description="Unique item ID")

    # Source tracking
    source: DataSource = Field(..., description="Source institution")
    source_url: Optional[str] = Field(None, description="Original URL")
    source_id: Optional[str] = Field(None, description="ID from source system")

    # Content
    title: str = Field(..., description="Item title")
    description: Optional[str] = Field(None, description="Item description or summary")

    # Temporal data
    scraped_at: datetime = Field(default_factory=datetime.now, description="When this was scraped")
    published_at: Optional[datetime] = Field(None, description="When originally published")
    updated_at: Optional[datetime] = Field(None, description="When last updated at source")

    # Classification
    document_type: DocumentType = Field(default=DocumentType.OTHER, description="Type of document")
    language: str = Field(default="en", description="Language code (ISO 639-1)")
    tags: List[str] = Field(default_factory=list, description="Classification tags")

    # Quality metadata
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Extraction confidence (0-1)")
    is_complete: bool = Field(default=True, description="Whether all expected data was extracted")
    extraction_notes: Optional[str] = Field(None, description="Notes about extraction quality")

    class Config:
        from_attributes = True


class ScrapedDocument(ScrapedItemBase):
    """
    Scraped document with full content.

    For documents like legislation, reports, briefings.
    """
    # Content
    content_text: Optional[str] = Field(None, description="Full text content")
    content_html: Optional[str] = Field(None, description="HTML content if available")
    pdf_url: Optional[str] = Field(None, description="PDF download URL")

    # EU-specific identifiers
    celex_number: Optional[str] = Field(None, description="CELEX identifier")
    procedure_ref: Optional[str] = Field(None, description="Procedure reference (e.g., 2021/0106(COD))")
    document_ref: Optional[str] = Field(None, description="Document reference")

    # Related entities
    committees: List[str] = Field(default_factory=list, description="Related committee codes")
    authors: List[str] = Field(default_factory=list, description="Author names or IDs")
    related_documents: List[str] = Field(default_factory=list, description="Related document IDs")


class ScrapedPerson(ScrapedItemBase):
    """
    Scraped person profile.

    For MEPs, Commissioners, officials.
    """
    document_type: DocumentType = Field(default=DocumentType.PERSON)

    # Personal info
    full_name: str = Field(..., description="Full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")

    # Role and affiliation
    role: Optional[str] = Field(None, description="Current role/position")
    institution: Optional[str] = Field(None, description="Institution name")
    department: Optional[str] = Field(None, description="Department or DG")
    political_group: Optional[str] = Field(None, description="Political group (for MEPs)")
    country: Optional[str] = Field(None, description="Country code")

    # Contact
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    office_address: Optional[str] = Field(None, description="Office address")

    # Media
    photo_url: Optional[str] = Field(None, description="Photo URL")

    # IDs
    mep_id: Optional[str] = Field(None, description="MEP ID")
    person_id: Optional[str] = Field(None, description="Who's Who ID")


class ScrapedOrganisation(ScrapedItemBase):
    """
    Scraped organisation profile.

    For DGs, agencies, committees.
    """
    document_type: DocumentType = Field(default=DocumentType.ORGANISATION)

    # Organisation info
    full_name: str = Field(..., description="Full organisation name")
    short_name: Optional[str] = Field(None, description="Acronym or short name")
    org_type: Optional[str] = Field(None, description="Organisation type")

    # Hierarchy
    parent_org: Optional[str] = Field(None, description="Parent organisation ID or name")
    child_orgs: List[str] = Field(default_factory=list, description="Child organisation IDs")

    # Contact
    website: Optional[str] = Field(None, description="Website URL")
    email: Optional[str] = Field(None, description="Contact email")
    address: Optional[str] = Field(None, description="Address")

    # Leadership
    head_name: Optional[str] = Field(None, description="Head of organisation name")
    head_role: Optional[str] = Field(None, description="Head's role title")


class ScrapedNewsItem(ScrapedItemBase):
    """
    Scraped news or press release.
    """
    document_type: DocumentType = Field(default=DocumentType.NEWS)

    # Content
    summary: Optional[str] = Field(None, description="News summary")
    body_text: Optional[str] = Field(None, description="Full article text")

    # Media
    image_url: Optional[str] = Field(None, description="Featured image URL")
    video_url: Optional[str] = Field(None, description="Video URL if available")

    # Categories
    categories: List[str] = Field(default_factory=list, description="News categories")
    related_topics: List[str] = Field(default_factory=list, description="Related topics")


class ScrapedSearchResult(BaseModel):
    """
    Generic search result from any scraper.
    """
    # Core fields
    id: str = Field(..., description="Result ID")
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: Optional[str] = Field(None, description="Result snippet/excerpt")

    # Source
    source: DataSource = Field(..., description="Source institution")

    # Relevance
    score: Optional[float] = Field(None, description="Relevance score")
    rank: Optional[int] = Field(None, description="Result rank")

    # Metadata
    document_type: Optional[DocumentType] = Field(None, description="Document type")
    date: Optional[datetime] = Field(None, description="Document date")
    language: str = Field(default="en", description="Language")


class ScrapeBatchResult(BaseModel):
    """
    Result of a batch scraping operation.
    """
    # Summary
    total_items: int = Field(default=0, description="Total items scraped")
    successful: int = Field(default=0, description="Successfully scraped items")
    failed: int = Field(default=0, description="Failed items")
    skipped: int = Field(default=0, description="Skipped items (e.g., already exists)")

    # Timing
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(None)
    duration_seconds: Optional[float] = Field(None)

    # Items
    items: List[ScrapedItemBase] = Field(default_factory=list, description="Scraped items")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")

    # Source
    source: DataSource = Field(..., description="Source institution")
    scraper_name: str = Field(..., description="Scraper name")

    def complete(self) -> None:
        """Mark the batch as complete and calculate duration"""
        self.completed_at = datetime.now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
