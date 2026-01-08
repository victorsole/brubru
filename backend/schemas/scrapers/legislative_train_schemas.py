"""
Legislative Train Schemas

Pydantic models for Legislative Train Schedule data structures.
"""

from datetime import datetime
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
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class StatusChange(BaseModel):
    """Status change event"""
    status: CarriageStatus
    changed_at: datetime
    duration_days: Optional[int] = None


class EPRSBriefingReference(BaseModel):
    """Reference to EPRS briefing"""
    url: str
    title: str
    publication_id: Optional[str] = None


class LegislativeTrain(BaseModel):
    """EC Priority 'train' with grouped legislative files"""
    id: UUID = Field(..., description="Train ID (UUID)")
    priority_number: int = Field(..., ge=1, le=7, description="Priority number (1-7)")
    name: str = Field(..., description="Priority name")
    description: Optional[str] = None
    commission_term: str = Field(default="2024-2029", description="Commission term")

    # Statistics
    total_files: Optional[int] = Field(default=0, description="Total legislative files")
    files_by_status: Dict[str, int] = Field(default_factory=dict, description="Files count by status")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True


class LegislativeCarriage(BaseModel):
    """Individual legislative file within a train"""
    id: UUID = Field(..., description="Carriage ID (UUID)")
    train_id: Optional[UUID] = Field(None, description="Parent train ID (UUID)")

    # Basic info
    title: str = Field(..., description="File title")
    description: Optional[str] = Field(None, description="File description")

    # Status tracking
    current_status: CarriageStatus = Field(..., description="Current status")
    status_history: List[StatusChange] = Field(default_factory=list, description="Status change history")
    days_in_current_status: Optional[int] = Field(None, description="Days in current status")
    is_blocked: bool = Field(default=False, description="True if blocked 9+ months")

    # Cross-references
    oeil_procedure_ref: Optional[str] = Field(None, description="OEIL procedure reference")
    celex_numbers: List[str] = Field(default_factory=list, description="Related CELEX numbers")
    eprs_briefings: List[EPRSBriefingReference] = Field(default_factory=list, description="EPRS briefings")

    # Stakeholders
    lead_committee: Optional[str] = Field(None, description="Lead committee code")
    opinion_committees: List[str] = Field(default_factory=list, description="Opinion committees")
    committees: List[str] = Field(default_factory=list, description="All involved committees")
    rapporteur_mep_id: Optional[str] = Field(None, description="Rapporteur MEP ID")

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
    train_id: UUID
    train_name: str
    total_files: int
    files_by_status: Dict[CarriageStatus, int]
    average_days_per_status: Dict[CarriageStatus, float]
    blocked_files_count: int
    completion_rate: float = Field(..., ge=0, le=1, description="Proportion of completed files")


class CommitteeWorkload(BaseModel):
    """Committee workload analysis"""
    committee_code: str
    committee_name: Optional[str] = None
    active_files: int
    files_by_status: Dict[CarriageStatus, int]
    average_processing_time_days: Optional[float] = None
    blocked_files: int
    lead_files: int = Field(default=0, description="Files where committee is lead")
    opinion_files: int = Field(default=0, description="Files where committee gives opinion")


class BlockedFileAlert(BaseModel):
    """Alert for blocked legislative file"""
    carriage_id: UUID
    title: str
    train_name: str
    status: CarriageStatus
    days_blocked: int
    last_activity: Optional[datetime] = None
    blocking_reason: Optional[str] = None
    alert_severity: str = Field(..., description="low, medium, high")


class TimelinePrediction(BaseModel):
    """Predicted timeline for legislative file"""
    carriage_id: UUID
    current_status: CarriageStatus
    estimated_completion_date: Optional[datetime] = None
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    remaining_steps: List[CarriageStatus] = Field(default_factory=list)
    estimated_days_per_step: Dict[CarriageStatus, int] = Field(default_factory=dict)
    based_on_historical_avg: bool = Field(default=True)


class CarriageSearchFilters(BaseModel):
    """Filters for carriage search"""
    query: Optional[str] = None
    train_id: Optional[UUID] = None
    status: Optional[CarriageStatus] = None
    committee: Optional[str] = None
    is_blocked: Optional[bool] = None
    has_eprs_briefings: Optional[bool] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class CarriageListResponse(BaseModel):
    """Response for carriage list endpoint"""
    carriages: List[LegislativeCarriage]
    total: int
    limit: int
    offset: int
    filters_applied: CarriageSearchFilters


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
