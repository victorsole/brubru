"""
Pydantic schemas for EP Committee Work scraper.

These schemas define the structure of scraped data before
it's stored in the database.

Created: January 2026
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ProcedureType(str, Enum):
    """
    Procedure types with relevance hierarchy.

    COD (100): Ordinary legislative procedure - laws
    APP (80): Consent procedure
    CNS (70): Consultation procedure
    NLE (50): Non-legislative procedure
    INI (40): Own-initiative reports
    """
    COD = "COD"
    APP = "APP"
    CNS = "CNS"
    NLE = "NLE"
    INI = "INI"


class CommitteeRole(str, Enum):
    """Committee's role in the procedure."""
    LEAD = "lead"
    ASSOCIATED = "associated"
    OPINION = "opinion"


class ScrapedCommitteeWorkItem(BaseModel):
    """
    A single work item scraped from a committee's work-in-progress page.

    This represents the basic data extracted from the list view.
    """
    # Identifiers
    procedure_ref: str = Field(
        ...,
        description="OEIL procedure reference (e.g., 2025/0580(CNS))"
    )
    committee_code: str = Field(
        ...,
        description="Committee code (e.g., ECON, LIBE)"
    )

    # Content
    title: str = Field(..., description="Procedure title")
    description: Optional[str] = Field(None, description="Short description if available")

    # Procedure metadata
    procedure_type: ProcedureType = Field(
        ProcedureType.INI,
        description="Procedure type extracted from reference"
    )
    committee_role: CommitteeRole = Field(
        CommitteeRole.LEAD,
        description="Committee's role in this procedure"
    )

    # Rapporteur
    rapporteur_name: Optional[str] = Field(None, description="Rapporteur name if assigned")
    rapporteur_mep_id: Optional[str] = Field(None, description="MEP ID for linking")

    # Status
    status: Optional[str] = Field(None, description="Current status text")
    stage: Optional[str] = Field(None, description="Committee stage")

    # URLs
    oeil_url: Optional[str] = Field(None, description="Link to OEIL procedure page")
    eurlex_url: Optional[str] = Field(None, description="Link to EUR-Lex if available")
    ep_page_url: Optional[str] = Field(None, description="Direct link to EP page")
    source_url: Optional[str] = Field(None, description="URL this was scraped from")

    # Scraping metadata
    scraped_at: datetime = Field(
        default_factory=datetime.now,
        description="When this item was scraped"
    )

    class Config:
        use_enum_values = True


class ScrapedCommitteeWorkDetail(ScrapedCommitteeWorkItem):
    """
    Extended work item with additional detail from the item's detail page.

    Inherits all fields from ScrapedCommitteeWorkItem and adds:
    - Full description
    - Timeline information
    - Related documents
    - Shadow rapporteurs
    """
    # Extended content
    full_description: Optional[str] = Field(None, description="Full procedure description")

    # Timeline
    timeline_events: List[dict] = Field(
        default_factory=list,
        description="List of timeline events [{date, event, status}]"
    )

    # Related documents
    related_documents: List[dict] = Field(
        default_factory=list,
        description="List of related documents [{title, url, type}]"
    )

    # Shadow rapporteurs
    shadow_rapporteurs: List[dict] = Field(
        default_factory=list,
        description="List of shadow rapporteurs [{name, group, mep_id}]"
    )

    # CELEX numbers if available
    celex_numbers: List[str] = Field(
        default_factory=list,
        description="Related CELEX numbers"
    )

    # Votes
    vote_date: Optional[datetime] = Field(None, description="Scheduled vote date")
    vote_result: Optional[str] = Field(None, description="Vote result if voted")


class ScrapeResult(BaseModel):
    """Result of a scraping operation."""
    committee_code: str
    items_found: int
    pages_scraped: int
    errors: List[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0


class ScrapeAllResult(BaseModel):
    """Result of scraping all committees."""
    total_items: int
    committees_scraped: int
    committees_failed: List[str] = Field(default_factory=list)
    results_by_committee: List[ScrapeResult] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
