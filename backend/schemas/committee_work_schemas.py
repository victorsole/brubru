"""
Committee Work API Schemas

Pydantic models for EP Committee Work In Progress API endpoints.

Created: January 2026
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class ProcedureType(str, Enum):
    """OEIL procedure types (used to validate the ?procedure_type filter).

    OEIL's vocabulary is open-ended; this is the comprehensive set we currently
    store. The stored column is a free varchar, so unseen types never crash.
    """
    COD = "COD"  # Ordinary legislative procedure
    CNS = "CNS"  # Consultation procedure
    APP = "APP"  # Consent procedure
    NLE = "NLE"  # Non-legislative (international agreements / appointments)
    INI = "INI"  # Own-initiative report
    INL = "INL"  # Legislative own-initiative
    RSP = "RSP"  # Resolution on a topical subject
    RSO = "RSO"  # Internal organisation resolution
    REG = "REG"  # Rules of Procedure
    RPS = "RPS"  # Implementing acts (regulatory scrutiny)
    DEA = "DEA"  # Delegated acts (scrutiny)
    IMM = "IMM"  # MEP immunity
    BUD = "BUD"  # Budgetary procedure
    BUI = "BUI"  # Budgetary initiative
    DEC = "DEC"  # Discharge
    GBD = "GBD"  # General budget
    ACI = "ACI"  # Interinstitutional agreement
    COS = "COS"  # Strategy paper
    DCE = "DCE"  # Written declaration


class CommitteeRole(str, Enum):
    """Committee's role in the procedure."""
    LEAD = "lead"
    ASSOCIATED = "associated"
    OPINION = "opinion"


class CommitteeWorkStatus(str, Enum):
    """Status of the work item."""
    IN_COMMITTEE = "in_committee"
    AWAITING_VOTE = "awaiting_vote"
    TABLED = "tabled"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


# ===== Response Schemas =====

class CommitteeWorkItemBase(BaseModel):
    """Base schema for committee work item."""
    procedure_ref: str = Field(..., description="OEIL procedure reference (e.g., 2025/0580(CNS))")
    committee_code: str = Field(..., description="Committee code (e.g., AFET, LIBE)")
    title: str = Field(..., description="Procedure title")
    description: Optional[str] = Field(None, description="Short description")

    procedure_type: str = Field("INI", description="OEIL procedure type code (free text; e.g. COD, DEA, RSP)")
    committee_role: CommitteeRole = Field(CommitteeRole.LEAD, description="Committee role")
    relevance_score: int = Field(40, ge=0, le=100, description="Relevance score (40-100)")

    rapporteur_name: Optional[str] = Field(None, description="Rapporteur name")
    rapporteur_mep_id: Optional[str] = Field(None, description="MEP ID for linking")

    status: CommitteeWorkStatus = Field(CommitteeWorkStatus.UNKNOWN, description="Current status")
    status_text: Optional[str] = Field(None, description="Original status text")

    oeil_url: Optional[str] = Field(None, description="OEIL procedure page URL")
    ep_page_url: Optional[str] = Field(None, description="EP committee page URL")


class CommitteeWorkItemResponse(CommitteeWorkItemBase):
    """Full response schema for committee work item."""
    id: UUID = Field(..., description="Work item ID")

    full_description: Optional[str] = Field(None, description="Full description")
    stage: Optional[str] = Field(None, description="Committee stage")

    shadow_rapporteurs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Shadow rapporteurs [{name, group, mep_id}]"
    )

    timeline_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Timeline events [{date, event, status}]"
    )
    vote_date: Optional[datetime] = Field(None, description="Scheduled vote date")
    vote_result: Optional[str] = Field(None, description="Vote result if voted")

    related_documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Related documents [{title, url, type}]"
    )
    celex_numbers: List[str] = Field(default_factory=list, description="Related CELEX numbers")

    legislative_carriage_id: Optional[UUID] = Field(
        None,
        description="Linked LegislativeCarriage ID if available"
    )

    eurlex_url: Optional[str] = Field(None, description="EUR-Lex URL")
    source_url: Optional[str] = Field(None, description="Source URL where scraped from")

    first_seen: datetime = Field(..., description="When first seen")
    last_updated: datetime = Field(..., description="Last update time")
    scraped_at: Optional[datetime] = Field(None, description="When scraped")

    class Config:
        from_attributes = True


class CommitteeWorkItemSummary(BaseModel):
    """Summary schema for list views."""
    id: UUID
    procedure_ref: str
    committee_code: str
    title: str
    procedure_type: str
    committee_role: CommitteeRole
    relevance_score: int
    rapporteur_name: Optional[str] = None
    status: CommitteeWorkStatus
    last_updated: datetime
    # first_seen is the reliable chronological signal (when the procedure first
    # appeared in our scrape); last_updated is touched by backfills so it is not.
    first_seen: Optional[datetime] = None
    # Lets the In-committee tab open the in-app file-detail modal for items that
    # are linked to a legislative carriage; null items fall back to OEIL.
    legislative_carriage_id: Optional[UUID] = None
    oeil_url: Optional[str] = None

    class Config:
        from_attributes = True


class CommitteeWorkListResponse(BaseModel):
    """Response for paginated list of committee work items."""
    items: List[CommitteeWorkItemSummary]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[Dict[str, Any]] = None


class CommitteeWorkDetailResponse(CommitteeWorkItemResponse):
    """Detailed response with tracking info."""
    is_tracked: bool = Field(False, description="Whether user is tracking this item")
    user_notes: Optional[str] = Field(None, description="User's notes on this item")
    tracked_since: Optional[datetime] = Field(None, description="When user started tracking")


# ===== Request Schemas =====

class TrackWorkItemRequest(BaseModel):
    """Request to track a work item."""
    notify_on_status_change: bool = Field(True, description="Notify on status changes")
    notify_on_rapporteur_change: bool = Field(True, description="Notify on rapporteur changes")
    notify_on_new_documents: bool = Field(True, description="Notify on new documents")
    notes: Optional[str] = Field(None, description="User notes")


class UpdateTrackingRequest(BaseModel):
    """Request to update tracking preferences."""
    notify_on_status_change: Optional[bool] = None
    notify_on_rapporteur_change: Optional[bool] = None
    notify_on_new_documents: Optional[bool] = None
    notes: Optional[str] = None


# ===== Tracking Response =====

class TrackedWorkItemResponse(BaseModel):
    """Response for a tracked work item."""
    work_item: CommitteeWorkItemSummary
    tracked_since: datetime
    notify_on_status_change: bool
    notify_on_rapporteur_change: bool
    notify_on_new_documents: bool
    notes: Optional[str] = None
    last_notified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrackedWorkItemsListResponse(BaseModel):
    """Response for list of tracked work items."""
    items: List[TrackedWorkItemResponse]
    total: int


# ===== Committee Info =====

class CommitteeInfo(BaseModel):
    """Committee information."""
    code: str
    name: str
    full_name: str
    policy_area: str


class CommitteesListResponse(BaseModel):
    """Response for list of committees."""
    committees: List[CommitteeInfo]
    total: int


# ===== Sync Status =====

class SyncStatusResponse(BaseModel):
    """Response for sync status."""
    last_sync: Optional[datetime] = None
    total_items: int = 0
    items_by_committee: Dict[str, int] = Field(default_factory=dict)
    items_by_type: Dict[str, int] = Field(default_factory=dict)


class SyncResultResponse(BaseModel):
    """Response after running sync."""
    added: int
    updated: int
    skipped: int
    errors: int
    status_changes: int = 0
    duration_seconds: float = 0.0
