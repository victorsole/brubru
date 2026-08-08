"""
Legislative Train Schemas

Pydantic models for Legislative Train Schedule data structures.

ENHANCED (January 2025):
- Package hierarchy support (parent/sub-packages)
- Monthly timeline extraction
- Text type and spotlight tags
- EC Priority and EP Committee filters
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class CarriageStatus(str, Enum):
    """Legislative file status categories"""
    ANNOUNCED = "announced"
    LEGISLATIVE_INITIATIVE = "legislative_initiative"
    TABLED = "tabled"
    CLOSE_TO_ADOPTION = "close_to_adoption"
    COMPLETED = "completed"
    ADOPTED = "adopted"  # Alias for completed
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class TextType(str, Enum):
    """Legislative text type"""
    LEGISLATIVE = "legislative"
    NON_LEGISLATIVE = "non_legislative"
    UNKNOWN = "unknown"


class StatusChange(BaseModel):
    """Status change event"""
    status: CarriageStatus
    changed_at: datetime
    duration_days: Optional[int] = None


class TimelineEntry(BaseModel):
    """Monthly status snapshot for a file"""
    year: int = Field(..., description="Year (e.g., 2024)")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    status: CarriageStatus = Field(..., description="Status at this month")
    is_current: bool = Field(default=False, description="Is this the current month")


class EPRSBriefingReference(BaseModel):
    """Reference to EPRS briefing"""
    url: str
    title: str
    publication_id: Optional[str] = None


class PackageStatusCounts(BaseModel):
    """Status counts for a package"""
    announced: int = Field(default=0)
    tabled: int = Field(default=0)
    blocked: int = Field(default=0)
    close_to_adoption: int = Field(default=0)
    adopted: int = Field(default=0)
    withdrawn: int = Field(default=0)
    total: int = Field(default=0)


class LegislativePackage(BaseModel):
    """
    Package within the Legislative Train (NEW in 2025).

    Packages are thematic groupings that can have sub-packages.
    Example: "Vision for Agriculture and Food" contains sub-packages
    like "Sustainable food systems" and "Animal welfare".
    """
    id: Optional[UUID] = Field(None, description="Package ID (UUID)")
    slug: str = Field(..., description="URL slug (e.g., 'package-vision-for-agriculture-and-food')")
    name: str = Field(..., description="Package name")
    description: Optional[str] = None

    # Hierarchy
    parent_id: Optional[UUID] = Field(None, description="Parent package ID")
    parent_slug: Optional[str] = Field(None, description="Parent package slug")
    is_sub_package: bool = Field(default=False, description="True if this is a sub-package")

    # Status counts
    status_counts: PackageStatusCounts = Field(default_factory=PackageStatusCounts)

    # Filter metadata
    ec_priorities: List[str] = Field(default_factory=list, description="EC Priority codes")
    ep_committees: List[str] = Field(default_factory=list, description="EP Committee codes")

    # URLs
    url: Optional[str] = Field(None, description="Full URL to package page")

    # Metadata
    scraped_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class LegislativeTrain(BaseModel):
    """EC Priority 'train' with grouped legislative files"""
    id: Optional[UUID] = Field(None, description="Train ID (UUID)")
    priority_number: int = Field(..., ge=1, le=7, description="Priority number (1-7)")
    name: str = Field(..., description="Priority name")
    description: Optional[str] = None
    commission_term: str = Field(default="2024-2029", description="Commission term")
    theme_slug: Optional[str] = Field(None, description="URL slug for this priority theme")

    # Statistics
    total_files: Optional[int] = Field(default=0, description="Total legislative files")
    files_by_status: Dict[str, int] = Field(default_factory=dict, description="Files count by status")

    # Packages within this train
    packages: List[LegislativePackage] = Field(default_factory=list, description="Packages in this train")

    # Metadata
    url: Optional[str] = Field(None, description="Full URL to train page")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class LegislativeCarriage(BaseModel):
    """Individual legislative file within a train"""
    id: Optional[UUID] = Field(None, description="Carriage ID (UUID)")
    file_id: Optional[str] = Field(None, description="Legislative Train file ID/slug")
    train_id: Optional[UUID] = Field(None, description="Parent train ID (UUID)")
    package_id: Optional[UUID] = Field(None, description="Parent package ID (UUID)")
    package_slug: Optional[str] = Field(None, description="Parent package slug")

    # Basic info
    title: str = Field(..., description="File title")
    short_title: Optional[str] = Field(
        None,
        description=(
            "Human-readable short name (max ~60 chars) for headings and list "
            "rows: a curated alias, or a subject line synthesised from the "
            "official title and checked against it. Null means the caller "
            "should fall back to the instrument designation parsed from "
            "`title`. Never a substitute for `title` in legal contexts."
        ),
    )
    description: Optional[str] = Field(None, description="File description")

    # Status tracking
    current_status: CarriageStatus = Field(..., description="Current status")
    status_history: List[StatusChange] = Field(default_factory=list, description="Status change history")
    days_in_current_status: Optional[int] = Field(None, description="Days in current status")
    is_blocked: bool = Field(default=False, description="True if blocked 9+ months")

    # NEW: Timeline (monthly status snapshots)
    timeline: List[TimelineEntry] = Field(default_factory=list, description="Monthly status history")

    # NEW: Text type and spotlight
    text_type: TextType = Field(default=TextType.UNKNOWN, description="Legislative or non-legislative")
    spotlight_tags: List[str] = Field(default_factory=list, description="Spotlight tags (e.g., 'recently_updated')")
    is_recently_updated: bool = Field(default=False, description="Marked as recently updated")

    # Cross-references
    oeil_procedure_ref: Optional[str] = Field(None, description="OEIL procedure reference")
    celex_numbers: List[str] = Field(default_factory=list, description="Related CELEX numbers")
    eprs_briefings: List[EPRSBriefingReference] = Field(default_factory=list, description="EPRS briefings")

    # Stakeholders
    lead_committee: Optional[str] = Field(None, description="Lead committee code")
    opinion_committees: List[str] = Field(default_factory=list, description="Opinion committees")
    committees: List[str] = Field(default_factory=list, description="All involved committees")
    rapporteur_mep_id: Optional[str] = Field(None, description="Rapporteur MEP ID")

    # Filter metadata (NEW)
    ec_priority_ids: List[str] = Field(default_factory=list, description="EC Priority IDs")
    related_themes: List[str] = Field(default_factory=list, description="Related theme slugs")

    # URLs
    url: Optional[str] = Field(None, description="Full URL to file page")

    # Temporal data
    scraped_at: datetime = Field(default_factory=datetime.now)
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    expected_completion: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnrichedCarriage(LegislativeCarriage):
    """
    Carriage enriched with OEIL, EUR-Lex, and EPRS data.

    Extends LegislativeCarriage with additional enrichment data.
    """
    # OEIL enrichment
    oeil_procedure_data: Optional[Dict[str, Any]] = Field(None, description="Full OEIL procedure data")
    oeil_timeline: List[Dict[str, Any]] = Field(default_factory=list, description="OEIL timeline events")
    oeil_key_events: List[Dict[str, Any]] = Field(default_factory=list, description="Key events from OEIL")

    # EUR-Lex enrichment
    eurlex_documents: List[Dict[str, Any]] = Field(default_factory=list, description="EUR-Lex documents")
    legal_text_url: Optional[str] = Field(None, description="EUR-Lex legal text URL")

    # EPRS enrichment
    eprs_matched_briefings: List[Dict[str, Any]] = Field(default_factory=list, description="Matched EPRS briefings")
    eprs_match_confidence: Optional[float] = Field(None, description="EPRS match confidence (0-1)")

    # MEP enrichment
    rapporteur_data: Optional[Dict[str, Any]] = Field(None, description="Rapporteur details")
    shadow_rapporteurs: List[Dict[str, Any]] = Field(default_factory=list, description="Shadow rapporteurs")

    # Enrichment metadata
    enriched_at: Optional[datetime] = None
    enrichment_quality: Optional[str] = Field(None, description="Quality: high, medium, low")


class TrainStatistics(BaseModel):
    """Statistics for a legislative train"""
    train_id: str
    train_name: str
    total_files: int
    files_by_status: Dict[str, int]
    average_days_per_status: Dict[str, float]
    blocked_files_count: int
    completion_rate: float = Field(..., ge=0, le=1, description="Proportion of completed files")


class PackageStatistics(BaseModel):
    """Statistics for a legislative package"""
    package_id: Optional[UUID] = None
    package_slug: str
    package_name: str
    total_files: int
    status_counts: PackageStatusCounts
    sub_packages_count: int = 0
    average_days_in_status: Dict[str, float] = Field(default_factory=dict)


class CommitteeWorkload(BaseModel):
    """Committee workload analysis"""
    committee_code: str
    committee_name: Optional[str] = None
    active_files: int
    files_by_status: Dict[str, int]
    average_processing_time_days: Optional[float] = None
    blocked_files: int
    lead_files: int = Field(default=0, description="Files where committee is lead")
    opinion_files: int = Field(default=0, description="Files where committee gives opinion")


class BlockedFileAlert(BaseModel):
    """Alert for blocked legislative file"""
    carriage_id: str
    title: str
    train_name: str
    status: CarriageStatus
    days_blocked: int
    last_activity: Optional[datetime] = None
    blocking_reason: Optional[str] = None
    alert_severity: str = Field(..., description="low, medium, high")


class TimelinePrediction(BaseModel):
    """Predicted timeline for legislative file"""
    carriage_id: str
    current_status: CarriageStatus
    estimated_completion_date: Optional[datetime] = None
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    remaining_steps: List[CarriageStatus] = Field(default_factory=list)
    estimated_days_per_step: Dict[str, int] = Field(default_factory=dict)
    based_on_historical_avg: bool = Field(default=True)


class CarriageSearchFilters(BaseModel):
    """Filters for carriage search"""
    query: Optional[str] = None
    train_id: Optional[UUID] = None
    package_slug: Optional[str] = None
    status: Optional[CarriageStatus] = None
    committee: Optional[str] = None
    text_type: Optional[TextType] = None
    is_blocked: Optional[bool] = None
    is_recently_updated: Optional[bool] = None
    has_eprs_briefings: Optional[bool] = None
    ec_priority: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class CarriageListResponse(BaseModel):
    """Response for carriage list endpoint"""
    carriages: List[LegislativeCarriage]
    total: int
    limit: int
    offset: int
    filters_applied: CarriageSearchFilters


class PackageListResponse(BaseModel):
    """Response for package list endpoint"""
    packages: List[LegislativePackage]
    total: int
    include_sub_packages: bool = True


class EnrichedCarriageResponse(BaseModel):
    """Response for enriched carriage endpoint"""
    carriage: EnrichedCarriage
    related_carriages: List[LegislativeCarriage] = Field(default_factory=list)
    timeline_prediction: Optional[TimelinePrediction] = None


class TrainListResponse(BaseModel):
    """Response for train list endpoint"""
    trains: List[LegislativeTrain]
    total: int
    commission_term: str


# ===== Scraper-specific schemas =====

class ScrapedPackage(BaseModel):
    """Raw package data from scraping"""
    slug: str
    name: str
    url: str
    status_counts: PackageStatusCounts
    parent_slug: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.now)


class ScrapedFile(BaseModel):
    """Raw file data from scraping"""
    file_id: str
    title: str
    url: str
    status: CarriageStatus
    package_slug: Optional[str] = None
    committees: List[str] = Field(default_factory=list)
    text_type: TextType = TextType.UNKNOWN
    is_recently_updated: bool = False
    timeline: List[TimelineEntry] = Field(default_factory=list)
    oeil_procedure_ref: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.now)


class ScrapedFileDetail(ScrapedFile):
    """Detailed file data from scraping individual file page"""
    description: Optional[str] = None
    celex_numbers: List[str] = Field(default_factory=list)
    lead_committee: Optional[str] = None
    opinion_committees: List[str] = Field(default_factory=list)
    rapporteur_mep_id: Optional[str] = None
    eprs_briefings: List[EPRSBriefingReference] = Field(default_factory=list)
    ec_priority_ids: List[str] = Field(default_factory=list)
    related_themes: List[str] = Field(default_factory=list)
    spotlight_tags: List[str] = Field(default_factory=list)
    # Added for unified scraping (January 2025)
    train_priority: Optional[int] = Field(None, description="EC Priority number (1-7) from train-based scraping")
