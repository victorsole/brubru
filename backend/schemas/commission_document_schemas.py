"""
Commission Document API Schemas

Pydantic models for Commission Documents API endpoints.

Created: February 2026
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class CommissionDocType(str, Enum):
    """Document types for filtering."""
    COM = "COM"
    SWD = "SWD"
    # SEC = "SEC"       # Secretariat — not exposed in UI
    # C = "C"           # Delegated Acts — not exposed in UI
    JOIN = "JOIN"
    OJ = "OJ"
    # PV = "PV"         # Minutes — will be used in EU Calendar


# ===== Response Schemas =====

class CommissionDocumentSummary(BaseModel):
    """Summary schema for list views."""
    id: UUID
    reference: str
    title: str
    common_name: Optional[str] = None
    doc_type: str
    publication_date: Optional[datetime] = None
    dg_responsible: Optional[str] = None
    procedure_ref: Optional[str] = None
    portal_url: Optional[str] = None
    celex: Optional[str] = None
    last_updated: datetime

    # eMeeting enrichment (the COM as referred to an EP committee). Populated at
    # query time by canon-ref join to ep_emeeting_documents - gives the feed the
    # committee + dossier + referral-PDF anchors the EC scrape lacks.
    committee_code: Optional[str] = None
    committee_name: Optional[str] = None
    referral_pdf_url: Optional[str] = None
    matches_interests: bool = False
    matches_tracked: bool = False

    class Config:
        from_attributes = True


class CommissionDocDetailResponse(BaseModel):
    """Full detail response."""
    id: UUID
    reference: str
    title: str
    common_name: Optional[str] = None
    doc_type: str
    publication_date: Optional[datetime] = None
    dg_responsible: Optional[str] = None
    procedure_ref: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    portal_url: Optional[str] = None
    celex: Optional[str] = None
    legislative_carriage_id: Optional[UUID] = None
    first_seen: datetime
    last_updated: datetime
    scraped_at: Optional[datetime] = None

    # Tracking info (populated per-user)
    is_tracked: bool = False
    user_notes: Optional[str] = None
    tracked_since: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommissionDocListResponse(BaseModel):
    """Paginated list response."""
    items: List[CommissionDocumentSummary]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[Dict[str, Any]] = None
    # PI / tracked lens meta (powered by the eMeeting enrichment).
    my_committees: List[str] = Field(default_factory=list)
    pi_active: bool = False
    files_active: bool = False
    has_tracked_files: bool = False


# ===== Tracking Schemas =====

class TrackCommissionDocRequest(BaseModel):
    """Request to track a Commission document."""
    notes: Optional[str] = Field(None, description="User notes")
    notify_on_new_documents: bool = Field(True, description="Notify on updates")


class TrackedCommissionDocResponse(BaseModel):
    """Response for a tracked Commission document."""
    track_id: Optional[str] = None
    archived_at: Optional[datetime] = None
    document: CommissionDocumentSummary
    tracked_since: datetime
    notes: Optional[str] = None
    notify_on_new_documents: bool = True

    class Config:
        from_attributes = True


class TrackedCommissionDocsListResponse(BaseModel):
    """Response for list of tracked Commission documents."""
    items: List[TrackedCommissionDocResponse]
    total: int


# ===== Sync Schemas =====

class SyncResultResponse(BaseModel):
    """Response after running sync."""
    added: int
    updated: int
    skipped: int
    errors: int
    duration_seconds: float = 0.0
