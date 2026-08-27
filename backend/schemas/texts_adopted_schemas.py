"""
Texts Adopted API Schemas

Pydantic models for EP Texts Adopted API endpoints.

Created: February 2026
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class TextType(str, Enum):
    """Types of adopted texts."""
    RESOLUTION = "resolution"
    LEGISLATIVE_RESOLUTION = "legislative_resolution"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


# ===== Response Schemas =====

class TextAdoptedSummary(BaseModel):
    """Summary schema for list views."""
    id: UUID
    ta_reference: str
    title: str
    text_type: TextType
    # Optional: some texts are listed before an adoption_date is populated
    # (draft / working items). Without this, the full /items endpoint 500s
    # because a subset of rows have NULL here.
    adoption_date: Optional[datetime] = None
    procedure_ref: Optional[str] = None
    parliamentary_term: int
    committees: List[str] = Field(default_factory=list)
    rapporteur_name: Optional[str] = None
    source_url: Optional[str] = None
    full_text_url: Optional[str] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class TextAdoptedDetailResponse(BaseModel):
    """Full detail response with content and tracking info."""
    id: UUID
    ta_reference: str
    title: str
    description: Optional[str] = None
    text_type: TextType
    adoption_date: Optional[datetime] = None
    procedure_ref: Optional[str] = None
    parliamentary_term: int

    # Content
    full_text: Optional[str] = None

    # Metadata
    committees: List[str] = Field(default_factory=list)
    rapporteur_name: Optional[str] = None
    rapporteur_mep_id: Optional[str] = None
    celex_number: Optional[str] = None
    vote_results: Optional[Dict[str, Any]] = None
    related_documents: List[Dict[str, Any]] = Field(default_factory=list)

    # URLs
    source_url: Optional[str] = None
    full_text_url: Optional[str] = None
    pdf_url: Optional[str] = None

    # Cross-references
    legislative_carriage_id: Optional[UUID] = None

    # Temporal
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    scraped_at: Optional[datetime] = None

    # Tracking info (populated per-user)
    is_tracked: bool = False
    user_notes: Optional[str] = None
    tracked_since: Optional[datetime] = None

    class Config:
        from_attributes = True


class TextAdoptedListResponse(BaseModel):
    """Paginated list response."""
    items: List[TextAdoptedSummary]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[Dict[str, Any]] = None
    # What the CORPUS holds, as distinct from what this QUERY matched (D2).
    # The corpus opened on 20 Jan 2026 and never said so, so the EP's 26 Nov 2025
    # resolution on protecting minors online was invisible and a search for it
    # returned a confident zero.
    coverage_from: Optional[date] = None
    coverage_to: Optional[date] = None
    coverage_note: Optional[str] = None


# ===== Tracking Schemas =====

class TrackTextRequest(BaseModel):
    """Request to track an adopted text."""
    notes: Optional[str] = Field(None, description="User notes")


class TrackedTextAdoptedResponse(BaseModel):
    """Response for a tracked adopted text."""
    track_id: Optional[str] = None
    archived_at: Optional[datetime] = None
    text: TextAdoptedSummary
    tracked_since: datetime
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class TrackedTextsListResponse(BaseModel):
    """Response for list of tracked texts."""
    items: List[TrackedTextAdoptedResponse]
    total: int


# ===== Term Info =====

class ParliamentaryTermInfo(BaseModel):
    """Information about a parliamentary term."""
    term: int
    years: str
    prefix: str
    text_count: int = 0


class TermsListResponse(BaseModel):
    """Response for list of available terms."""
    terms: List[ParliamentaryTermInfo]


# ===== Sync Schemas =====

class SyncStatusResponse(BaseModel):
    """Sync status and statistics."""
    last_sync: Optional[datetime] = None
    total_items: int = 0
    items_by_term: Dict[int, int] = Field(default_factory=dict)
    items_by_type: Dict[str, int] = Field(default_factory=dict)


class SyncResultResponse(BaseModel):
    """Response after running sync."""
    added: int
    updated: int
    skipped: int
    errors: int
    duration_seconds: float = 0.0
