"""
API Pydantic schemas for EC Public Consultations.

These schemas define request/response models for the API endpoints.

Created: January 2026
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from uuid import UUID


# ============================================================================
# Enums
# ============================================================================

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


class SubmissionStatus(str, Enum):
    """User's submission status."""
    NOT_STARTED = "not_started"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    NOT_PARTICIPATING = "not_participating"


# ============================================================================
# Response Models - Documents
# ============================================================================

class ConsultationDocumentResponse(BaseModel):
    """Response model for a consultation document."""
    id: UUID
    title: str
    document_type: DocumentType
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None
    language: str = "en"

    class Config:
        from_attributes = True


# ============================================================================
# Response Models - Consultations
# ============================================================================

class ConsultationListItem(BaseModel):
    """Summary model for consultation list views."""
    id: UUID
    initiative_id: str
    title: str
    short_title: Optional[str] = None
    consultation_type: ConsultationType
    status: ConsultationStatus
    dg_responsible: Optional[str] = None
    dg_name: Optional[str] = None
    policy_areas: List[str] = []
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_closing_soon: bool = False
    feedback_count: int = 0
    relevance_score: int = 50
    is_tracked: bool = False
    portal_url: Optional[str] = None
    # All-EU hub (migration 142): 'commission' | 'agency'; body_name is the
    # responsible body's display name (DG name or agency name).
    source: str = "commission"
    source_body: Optional[str] = None
    body_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConsultationDetailResponse(BaseModel):
    """Full details model for a consultation."""
    id: UUID
    initiative_id: str
    publication_id: Optional[str] = None
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    full_description: Optional[str] = None
    objectives: Optional[str] = None
    target_group: Optional[str] = None

    consultation_type: ConsultationType
    status: ConsultationStatus

    dg_responsible: Optional[str] = None
    dg_name: Optional[str] = None
    policy_areas: List[str] = []

    # All-EU hub: 'commission' | 'agency'; body_name is the responsible body name.
    source: str = "commission"
    source_body: Optional[str] = None
    body_name: Optional[str] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_closing_soon: bool = False

    feedback_count: int = 0
    views_count: Optional[int] = None

    portal_url: Optional[str] = None
    feedback_url: Optional[str] = None

    com_references: List[str] = []
    celex_numbers: List[str] = []

    outcome_summary: Optional[str] = None
    outcome_published_date: Optional[date] = None
    outcome_document_url: Optional[str] = None

    relevance_score: int = 50
    documents: List[ConsultationDocumentResponse] = []

    # User-specific fields
    is_tracked: bool = False
    user_notes: Optional[str] = None
    tracked_since: Optional[datetime] = None
    submission_status: Optional[SubmissionStatus] = None

    created_at: datetime
    last_updated: datetime

    class Config:
        from_attributes = True


class ConsultationListResponse(BaseModel):
    """Paginated list response for consultations."""
    items: List[ConsultationListItem]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[Dict[str, Any]] = None


# ============================================================================
# Response Models - Tracking
# ============================================================================

class TrackedConsultationResponse(BaseModel):
    """Response for a tracked consultation."""
    track_id: Optional[str] = None        # UserConsultationTrack.id — for archive/restore
    archived_at: Optional[datetime] = None
    consultation: ConsultationListItem
    tracked_since: datetime
    notify_on_deadline: bool = True
    notify_on_outcome: bool = True
    notify_days_before: int = 7
    submission_status: SubmissionStatus = SubmissionStatus.NOT_STARTED
    notes: Optional[str] = None
    priority: int = 0
    last_notified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrackedConsultationsListResponse(BaseModel):
    """List of tracked consultations."""
    items: List[TrackedConsultationResponse]
    total: int


# ============================================================================
# Request Models - Tracking
# ============================================================================

class TrackConsultationRequest(BaseModel):
    """Request to track a consultation."""
    notify_on_deadline: bool = True
    notify_on_outcome: bool = True
    notify_days_before: int = Field(default=7, ge=1, le=30)
    notes: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=2)


class UpdateTrackingRequest(BaseModel):
    """Request to update tracking preferences."""
    notify_on_deadline: Optional[bool] = None
    notify_on_outcome: Optional[bool] = None
    notify_days_before: Optional[int] = Field(default=None, ge=1, le=30)
    submission_status: Optional[SubmissionStatus] = None
    notes: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=2)


# ============================================================================
# Response Models - AI Analysis (Blue Tier)
# ============================================================================

class ConsultationAnalysisResponse(BaseModel):
    """AI analysis of a consultation."""
    consultation_id: UUID
    executive_summary: str
    key_questions: List[str]
    stakeholder_categories: List[str]
    legislation_context: Optional[str] = None
    submission_requirements: Optional[str] = None
    generated_at: datetime


class ConsultationProposalItem(BaseModel):
    """Single AI-generated proposal."""
    id: str
    question_addressed: str
    proposed_response: str
    supporting_arguments: List[str]
    source_documents: List[str]
    confidence_score: float = Field(ge=0, le=1)
    tone_recommendation: Optional[str] = None


class ConsultationProposalsResponse(BaseModel):
    """AI-generated proposals for a consultation."""
    consultation_id: UUID
    proposals: List[ConsultationProposalItem]
    user_documents_used: List[str]
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    generated_at: datetime


class GenerateProposalsRequest(BaseModel):
    """Request to generate AI proposals."""
    document_ids: List[UUID] = Field(
        default=[],
        description="User document IDs to use as context"
    )
    focus_areas: List[str] = Field(
        default=[],
        description="Optional focus areas or keywords"
    )


class RefineProposalRequest(BaseModel):
    """Request to refine a proposal."""
    proposal_id: str
    user_feedback: str = Field(..., min_length=1)


# ============================================================================
# Response Models - Alignment (Blue Tier)
# ============================================================================

class AlignmentDetailItem(BaseModel):
    """Detail of alignment analysis."""
    category: str
    user_position: str
    ec_outcome: str
    alignment_level: str  # "aligned", "partially_aligned", "divergent"
    notes: Optional[str] = None


class AlignmentAssessmentResponse(BaseModel):
    """Alignment assessment between user input and outcome."""
    consultation_id: UUID
    alignment_score: float = Field(ge=0, le=100)
    summary: str
    aligned_points: List[str]
    divergent_points: List[str]
    details: List[AlignmentDetailItem]
    recommended_actions: List[str]
    assessed_at: datetime


# ============================================================================
# Response Models - Sync Status
# ============================================================================

class SyncStatusResponse(BaseModel):
    """Status of consultation sync."""
    last_sync: Optional[datetime] = None
    total_consultations: int
    open_count: int
    closed_count: int
    outcome_count: int
    consultations_by_dg: Dict[str, int] = {}
    consultations_by_policy_area: Dict[str, int] = {}


class SyncResultResponse(BaseModel):
    """Result of a sync operation."""
    added: int
    updated: int
    skipped: int
    errors: int
    status_changes: int = 0
    duration_seconds: float


# ============================================================================
# Response Models - DG and Policy Areas
# ============================================================================

class DGInfo(BaseModel):
    """Directorate-General information."""
    code: str
    name: str
    full_name: str


class PolicyAreaInfo(BaseModel):
    """Policy area information."""
    code: str
    name: str


class DGListResponse(BaseModel):
    """List of Directorate-Generals."""
    dgs: List[DGInfo]
    total: int


class PolicyAreasListResponse(BaseModel):
    """List of policy areas."""
    policy_areas: List[PolicyAreaInfo]
    total: int
