"""
Tender Schemas

Pydantic schemas for Tenderator API operations.
Part of Tenderator - EU public procurement tender monitoring for Blue-tier users.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class TenderStatus(str, Enum):
    """Tender status values"""
    OPEN = "open"
    CLOSED = "closed"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class ProcedureType(str, Enum):
    """EU procurement procedure types"""
    OPEN = "open"
    RESTRICTED = "restricted"
    NEGOTIATED = "neg-w-call"
    COMPETITIVE_DIALOGUE = "comp-dial"
    INNOVATION_PARTNERSHIP = "innovation"
    NEGOTIATED_WITHOUT_CALL = "neg-wo-call"


class ContractNature(str, Enum):
    """Contract nature types"""
    WORKS = "works"
    SUPPLIES = "supplies"
    SERVICES = "services"


class CompanySize(str, Enum):
    """SME company size categories"""
    MICRO = "micro"  # < 10 employees, < €2M turnover
    SMALL = "small"  # < 50 employees, < €10M turnover
    MEDIUM = "medium"  # < 250 employees, < €50M turnover


class NotificationFrequency(str, Enum):
    """Notification frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BI_WEEKLY = "bi-weekly"


# ============================================================================
# Tender Schemas
# ============================================================================

class TenderBase(BaseModel):
    """Base schema for Tender"""
    publication_number: str = Field(..., max_length=50, description="TED publication number (e.g., '1776-2025')")
    title: str = Field(..., description="Tender title")
    description: Optional[str] = Field(None, description="Tender description")
    official_name: Optional[str] = Field(None, max_length=500, description="Contracting authority name")
    buyer_country: Optional[str] = Field(None, max_length=2, description="ISO 3166-1 alpha-2 country code")


class TenderCreate(TenderBase):
    """Schema for creating a tender (internal use)"""
    notice_id: Optional[str] = None
    form_type: Optional[str] = None
    procedure_type: Optional[str] = None
    cpv_codes: Optional[List[str]] = None
    cpv_main: Optional[str] = None
    nuts_codes: Optional[List[str]] = None
    contract_nature: Optional[str] = None
    estimated_value: Optional[float] = None
    estimated_value_currency: str = "EUR"
    submission_deadline: Optional[datetime] = None
    contract_duration_months: Optional[int] = None
    has_lots: bool = False
    lot_count: int = 0
    ted_url: Optional[str] = None
    xml_content: Optional[str] = None


class TenderSummary(BaseModel):
    """Compact tender summary for list views"""
    id: int
    publication_number: str
    title: str
    official_name: Optional[str] = None
    buyer_country: Optional[str] = None
    cpv_main: Optional[str] = None
    estimated_value: Optional[float] = None
    estimated_value_currency: str = "EUR"
    submission_deadline: Optional[datetime] = None
    status: TenderStatus = TenderStatus.OPEN
    sme_suitability_score: Optional[float] = None

    class Config:
        from_attributes = True


class TenderDetail(TenderBase):
    """Full tender details for detail view"""
    id: int
    notice_id: Optional[str] = None
    form_type: Optional[str] = None
    notice_subtype: Optional[str] = None
    procedure_type: Optional[str] = None
    legal_basis: Optional[str] = None
    cpv_codes: Optional[List[str]] = None
    cpv_main: Optional[str] = None
    nuts_codes: Optional[List[str]] = None
    contract_nature: Optional[str] = None
    estimated_value: Optional[float] = None
    estimated_value_currency: str = "EUR"
    value_range_low: Optional[float] = None
    value_range_high: Optional[float] = None
    publication_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None
    contract_start_date: Optional[datetime] = None
    contract_duration_months: Optional[int] = None
    award_criteria_type: Optional[str] = None
    award_criteria: Optional[Dict[str, Any]] = None
    selection_criteria: Optional[Dict[str, Any]] = None
    minimum_requirements: Optional[Dict[str, Any]] = None
    has_lots: bool = False
    lot_count: Optional[int] = 0
    lots: Optional[List[Dict[str, Any]]] = None
    ted_url: Optional[str] = None
    documents_url: Optional[str] = None
    submission_url: Optional[str] = None
    status: TenderStatus = TenderStatus.OPEN
    is_framework: bool = False
    is_joint_procurement: bool = False
    sme_suitability_score: Optional[float] = None
    sme_analysis: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LotSummary(BaseModel):
    """Lot information within a tender"""
    lot_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    cpv_code: Optional[str] = None
    estimated_value: Optional[float] = None
    currency: str = "EUR"


# ============================================================================
# Tender Profile Schemas
# ============================================================================

class TenderProfileBase(BaseModel):
    """Base schema for user tender preferences"""
    company_name: Optional[str] = Field(None, max_length=300, description="Company name")
    company_size: Optional[CompanySize] = Field(None, description="SME category")
    annual_turnover: Optional[float] = Field(None, ge=0, description="Annual turnover in EUR")
    employee_count: Optional[int] = Field(None, ge=0, description="Number of employees")
    years_in_business: Optional[int] = Field(None, ge=0, description="Years in business")


class TenderProfileCreate(TenderProfileBase):
    """Schema for creating a tender profile"""
    cpv_categories: Optional[List[str]] = Field(None, description="CPV code categories (e.g., ['72', '48'])")
    cpv_codes: Optional[List[str]] = Field(None, description="Specific CPV codes of interest")
    sectors_description: Optional[str] = Field(None, description="Free-text business sector description")
    countries_of_interest: Optional[List[str]] = Field(None, description="ISO country codes")
    nuts_regions: Optional[List[str]] = Field(None, description="NUTS region codes")
    eu_wide: bool = Field(True, description="Open to all EU tenders")
    min_tender_value: Optional[float] = Field(None, ge=0, description="Minimum tender value")
    max_tender_value: Optional[float] = Field(None, ge=0, description="Maximum tender value")
    preferred_procedures: Optional[List[str]] = Field(None, description="Preferred procedure types")
    exclude_frameworks: bool = Field(False, description="Exclude framework agreements")
    keywords: Optional[List[str]] = Field(None, description="Keywords to look for")
    excluded_keywords: Optional[List[str]] = Field(None, description="Keywords to exclude")
    min_deadline_days: int = Field(30, ge=7, le=180, description="Minimum days until deadline")
    certifications: Optional[List[str]] = Field(None, description="Company certifications")
    notification_frequency: NotificationFrequency = Field(
        NotificationFrequency.WEEKLY,
        description="How often to receive notifications"
    )
    notification_email: bool = Field(True, description="Receive email notifications")
    notification_in_app: bool = Field(True, description="Receive in-app notifications")

    @field_validator('countries_of_interest')
    @classmethod
    def validate_countries(cls, v):
        if v:
            for code in v:
                if len(code) != 2:
                    raise ValueError(f"Country code must be 2 characters: {code}")
        return v

    @field_validator('cpv_codes', 'cpv_categories')
    @classmethod
    def validate_cpv_codes(cls, v):
        if v:
            for code in v:
                if not code.isdigit():
                    raise ValueError(f"CPV code must be numeric: {code}")
        return v


class TenderProfileUpdate(BaseModel):
    """Schema for updating a tender profile"""
    company_name: Optional[str] = None
    company_size: Optional[CompanySize] = None
    annual_turnover: Optional[float] = None
    employee_count: Optional[int] = None
    cpv_categories: Optional[List[str]] = None
    cpv_codes: Optional[List[str]] = None
    countries_of_interest: Optional[List[str]] = None
    eu_wide: Optional[bool] = None
    min_tender_value: Optional[float] = None
    max_tender_value: Optional[float] = None
    preferred_procedures: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    min_deadline_days: Optional[int] = None
    certifications: Optional[List[str]] = None
    notification_frequency: Optional[NotificationFrequency] = None
    notification_email: Optional[bool] = None
    notification_in_app: Optional[bool] = None
    is_active: Optional[bool] = None


class TenderProfileResponse(TenderProfileBase):
    """Schema for tender profile response"""
    id: int
    user_id: UUID
    cpv_categories: Optional[List[str]] = None
    cpv_codes: Optional[List[str]] = None
    sectors_description: Optional[str] = None
    countries_of_interest: Optional[List[str]] = None
    nuts_regions: Optional[List[str]] = None
    eu_wide: bool = True
    min_tender_value: Optional[float] = None
    max_tender_value: Optional[float] = None
    preferred_procedures: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    min_deadline_days: int = 30
    certifications: Optional[List[str]] = None
    notification_frequency: NotificationFrequency = NotificationFrequency.WEEKLY
    notification_email: bool = True
    notification_in_app: bool = True
    is_active: bool = True
    last_matched_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Tender Match Schemas
# ============================================================================

class TenderMatchBase(BaseModel):
    """Base schema for tender matches"""
    match_score: float = Field(..., ge=0, le=100, description="Match score (0-100)")
    match_reasons: Optional[Dict[str, float]] = Field(None, description="Score breakdown by criteria")
    match_details: Optional[str] = Field(None, description="Human-readable match explanation")


class TenderMatchResponse(TenderMatchBase):
    """Schema for tender match response"""
    id: int
    tender_id: int
    user_id: UUID
    is_viewed: bool = False
    is_saved: bool = False
    is_dismissed: bool = False
    is_applied: bool = False
    user_notes: Optional[str] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    notified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenderMatchWithTender(TenderMatchResponse):
    """Match response including tender summary"""
    tender: TenderSummary


class TenderMatchUpdate(BaseModel):
    """Schema for updating a tender match"""
    is_saved: Optional[bool] = None
    is_dismissed: Optional[bool] = None
    is_applied: Optional[bool] = None
    user_notes: Optional[str] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)


# ============================================================================
# Search & Filter Schemas
# ============================================================================

class TenderSearchParams(BaseModel):
    """Parameters for tender search"""
    query: Optional[str] = Field(None, description="Text search query")
    countries: Optional[List[str]] = Field(None, description="Filter by countries")
    cpv_codes: Optional[List[str]] = Field(None, description="Filter by CPV codes")
    procedure_types: Optional[List[str]] = Field(None, description="Filter by procedure types")
    contract_nature: Optional[ContractNature] = Field(None, description="Filter by contract nature")
    min_value: Optional[float] = Field(None, ge=0, description="Minimum estimated value")
    max_value: Optional[float] = Field(None, ge=0, description="Maximum estimated value")
    deadline_from: Optional[datetime] = Field(None, description="Minimum submission deadline")
    deadline_to: Optional[datetime] = Field(None, description="Maximum submission deadline")
    status: Optional[TenderStatus] = Field(TenderStatus.OPEN, description="Tender status")
    sme_friendly: bool = Field(False, description="Only show SME-friendly tenders")
    exclude_frameworks: bool = Field(False, description="Exclude framework agreements")
    sort_by: str = Field("publication_date", description="Sort field")
    sort_order: str = Field("desc", description="Sort order (asc/desc)")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Results per page")


class TenderSearchResponse(BaseModel):
    """Response for tender search"""
    tenders: List[TenderSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class TenderMatchListParams(BaseModel):
    """Parameters for listing user matches"""
    include_dismissed: bool = Field(False, description="Include dismissed matches")
    saved_only: bool = Field(False, description="Only show saved matches")
    min_score: Optional[float] = Field(None, ge=0, le=100, description="Minimum match score")
    sort_by: str = Field("match_score", description="Sort field")
    sort_order: str = Field("desc", description="Sort order")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class TenderMatchListResponse(BaseModel):
    """Response for match listing"""
    matches: List[TenderMatchWithTender]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Fetch Job Schemas
# ============================================================================

class TenderFetchJobResponse(BaseModel):
    """Schema for fetch job status"""
    id: int
    job_id: str
    job_type: Optional[str] = None
    source: Optional[str] = None
    status: str
    tenders_found: int = 0
    tenders_new: int = 0
    tenders_updated: int = 0
    errors: Optional[List[str]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class TenderFetchRequest(BaseModel):
    """Request to trigger a tender fetch"""
    days_back: int = Field(7, ge=1, le=90, description="Days to look back")
    countries: Optional[List[str]] = Field(None, description="Countries to fetch")
    cpv_codes: Optional[List[str]] = Field(None, description="CPV codes to filter")
    max_value: float = Field(5_000_000, ge=0, description="Maximum tender value")
    source: str = Field("ted_api", description="Data source (ted_api or ted_sparql)")


# ============================================================================
# Statistics Schemas
# ============================================================================

class TenderStatistics(BaseModel):
    """Tender statistics for dashboard"""
    total_tenders: int = 0
    open_tenders: int = 0
    tenders_this_week: int = 0
    average_value: Optional[float] = None
    by_country: Dict[str, int] = {}
    by_cpv_category: Dict[str, int] = {}
    by_procedure_type: Dict[str, int] = {}


class UserTenderStatistics(BaseModel):
    """User-specific tender statistics"""
    total_matches: int = 0
    saved_tenders: int = 0
    dismissed_tenders: int = 0
    applied_tenders: int = 0
    average_match_score: Optional[float] = None
    matches_this_week: int = 0
