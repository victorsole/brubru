"""
Pydantic schemas for EP Texts Adopted scraper.

These schemas define the structure of scraped data before
it's stored in the database.

Created: February 2026
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TextType(str, Enum):
    """Types of adopted texts."""
    RESOLUTION = "resolution"
    LEGISLATIVE_RESOLUTION = "legislative_resolution"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


# Parliamentary term mapping
PARLIAMENTARY_TERMS = {
    10: {"years": "2024-2029", "prefix": "TA-10"},
    9: {"years": "2019-2024", "prefix": "TA-9"},
    8: {"years": "2014-2019", "prefix": "TA-8"},
    7: {"years": "2009-2014", "prefix": "TA-7"},
    6: {"years": "2004-2009", "prefix": "TA-6"},
    5: {"years": "1999-2004", "prefix": "TA-5"},
    4: {"years": "1994-1999", "prefix": "TA-4"},
}


class ScrapedTextAdopted(BaseModel):
    """
    A single adopted text scraped from RSS or TOC page.

    This represents the basic data extracted from the RSS feed
    or the plenary session TOC page.
    """
    # Identifiers
    ta_reference: str = Field(
        ...,
        description="TA reference (e.g., P10_TA(2025)0042)"
    )
    title: str = Field(..., description="Text title")
    description: Optional[str] = Field(None, description="Short description")

    # Classification
    text_type: TextType = Field(
        TextType.OTHER,
        description="Type of adopted text"
    )
    procedure_ref: Optional[str] = Field(
        None,
        description="OEIL procedure reference (e.g., 2024/0176(COD))"
    )

    # Temporal
    adoption_date: datetime = Field(
        ...,
        description="Plenary session date when text was adopted"
    )
    scraped_at: datetime = Field(
        default_factory=datetime.now,
        description="When this item was scraped"
    )

    # URLs
    source_url: str = Field(
        ...,
        description="RSS item link or TOC page URL"
    )
    full_text_url: Optional[str] = Field(
        None,
        description="Link to the individual text page"
    )
    pdf_url: Optional[str] = Field(
        None,
        description="PDF download URL"
    )

    # Parliamentary term
    parliamentary_term: int = Field(
        10,
        description="Parliamentary term number (4-10)"
    )

    class Config:
        use_enum_values = True


class ScrapedTextAdoptedDetail(ScrapedTextAdopted):
    """
    Extended adopted text with additional data from the detail page.

    Inherits all fields from ScrapedTextAdopted and adds:
    - Full text content
    - Committee information
    - Rapporteur details
    - Vote results
    - Related documents
    """
    # Content
    full_text: Optional[str] = Field(
        None,
        description="Full text content"
    )

    # Committee info
    committees: List[str] = Field(
        default_factory=list,
        description="Committee codes (e.g., ['LIBE', 'AFET'])"
    )

    # Rapporteur
    rapporteur_name: Optional[str] = Field(
        None,
        description="Rapporteur name"
    )
    rapporteur_mep_id: Optional[str] = Field(
        None,
        description="MEP ID for linking"
    )

    # Related documents
    related_documents: List[dict] = Field(
        default_factory=list,
        description="Related documents [{title, url, type}]"
    )

    # EU identifiers
    celex_number: Optional[str] = Field(
        None,
        description="CELEX number if available"
    )

    # Vote results
    vote_results: Optional[dict] = Field(
        None,
        description="Vote results {for, against, abstentions}"
    )


class ScrapeResult(BaseModel):
    """Result of a scraping operation for a single plenary date."""
    plenary_date: str
    parliamentary_term: int
    items_found: int
    errors: List[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0


class ScrapeAllResult(BaseModel):
    """Result of scraping an entire parliamentary term or all terms."""
    total_items: int
    terms_scraped: int
    plenary_dates_scraped: int
    plenary_dates_failed: List[str] = Field(default_factory=list)
    results_by_date: List[ScrapeResult] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
