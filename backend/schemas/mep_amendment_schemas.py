"""
MEP Amendment API Schemas

Pydantic models for MEP Amendment API endpoints.

Created: February 2026
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


# ===== Response Schemas =====

class AmendmentDocumentResponse(BaseModel):
    """Metadata about a parsed EP amendment document."""
    id: UUID
    procedure_reference: str
    committee_code: str
    pe_reference: str
    document_type: str
    document_date: Optional[date] = None
    doceo_url: str
    rapporteur_name: Optional[str] = None
    total_amendments: int = 0
    status: str
    error_message: Optional[str] = None
    scraped_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MEPAmendmentResponse(BaseModel):
    """A single scraped amendment."""
    id: UUID
    procedure_reference: str
    committee_code: str
    pe_reference: str
    amendment_number: int
    author_names: List[str]
    political_group: Optional[str] = None
    on_behalf_of_group: bool = False
    element_type: str
    element_number: Optional[str] = None
    element_reference: str
    amendment_type: str
    original_text: str
    proposed_text: str
    justification: Optional[str] = None
    original_language: str = "en"
    source_url: str
    parsing_confidence: float = 1.0
    document_date: Optional[date] = None

    class Config:
        from_attributes = True


class MEPAmendmentListResponse(BaseModel):
    """Paginated list of amendments with filters."""
    items: List[MEPAmendmentResponse]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[Dict[str, Any]] = None


class AmendmentDocumentListResponse(BaseModel):
    """List of amendment documents for a procedure."""
    items: List[AmendmentDocumentResponse]
    total: int


# ===== Statistics Schemas =====

class GroupAmendmentCount(BaseModel):
    """Amendment count for a political group."""
    political_group: str
    count: int
    percentage: float = 0.0


class ElementAmendmentCount(BaseModel):
    """Amendment count for a legislative element."""
    element_reference: str
    element_type: str
    count: int


class TypeAmendmentCount(BaseModel):
    """Amendment count by type (modification, suppression, addition)."""
    amendment_type: str
    count: int
    percentage: float = 0.0


class RapporteurInfo(BaseModel):
    """Rapporteur details for a procedure."""
    name: str
    political_group: Optional[str] = None
    photo_url: Optional[str] = None
    mep_id: Optional[str] = None


class AmendmentStatsResponse(BaseModel):
    """Aggregated statistics for amendments on a procedure."""
    procedure_reference: str
    total_amendments: int
    total_documents: int
    committees: List[str]
    rapporteur: Optional[RapporteurInfo] = None
    by_group: List[GroupAmendmentCount]
    by_element: List[ElementAmendmentCount]
    by_type: List[TypeAmendmentCount]
    top_authors: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top MEPs by amendment count: [{name, group, count}]"
    )


# ===== Request Schemas =====

class AmendmentFetchRequest(BaseModel):
    """Request to trigger amendment fetching for a procedure."""
    force_refetch: bool = Field(
        False,
        description="Re-fetch and re-parse even if documents already exist"
    )


class AmendmentFetchResponse(BaseModel):
    """Response after triggering amendment fetch."""
    procedure_reference: str
    documents_found: int
    documents_parsed: int
    amendments_stored: int
    errors: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


# ===== Bulk Sync Schemas =====

class BulkSyncRequest(BaseModel):
    """Request to trigger bulk amendment sync from EP Open Data API."""
    years: List[int] = Field(
        default_factory=lambda: [2025],
        description="Years to fetch documents for"
    )
    work_types: List[str] = Field(
        default_factory=lambda: ["AMENDMENTS", "REPORT_DRAFT"],
        description="EP Open Data work types to fetch"
    )
    force_refetch: bool = Field(
        False,
        description="Re-parse documents even if already parsed"
    )


class BulkSyncResponse(BaseModel):
    """Response from bulk amendment sync."""
    documents_discovered: int
    documents_skipped: int
    documents_parsed: int
    documents_failed: int
    amendments_stored: int
    errors: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class SyncStatusResponse(BaseModel):
    """Aggregate sync status for amendment documents."""
    total_documents: int
    parsed: int
    failed: int
    pending: int
    total_amendments: int
    last_sync: Optional[datetime] = None
    by_year: Dict[str, int] = Field(default_factory=dict)
    by_committee: Dict[str, int] = Field(default_factory=dict)


class MEPAmendmentCrossRefResponse(BaseModel):
    """Cross-procedure amendment results for a specific MEP."""
    author_name: str
    total_amendments: int
    procedures: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="[{procedure_ref, count, committees}]"
    )
    items: List[MEPAmendmentResponse]
    limit: int
    offset: int


# ===== Alignment Scoring Schemas (Phase 4) =====

class AlignmentScoreRequest(BaseModel):
    """Request to score MEP amendments against a policy position."""
    policy_position: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Natural language description of the user's policy position"
    )


class AlignmentScoreItem(BaseModel):
    """A single alignment score with amendment metadata."""
    mep_amendment_id: UUID
    score: int = Field(..., ge=-2, le=2)
    explanation: Optional[str] = None
    author_names: List[str] = Field(default_factory=list)
    political_group: Optional[str] = None
    element_reference: str
    amendment_type: str


class AlignmentScoreResponse(BaseModel):
    """Full alignment scoring result."""
    procedure_reference: str
    policy_position_hash: str
    total_scored: int
    score_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Score counts: {'-2': 5, '-1': 10, '0': 50, '1': 30, '2': 15}"
    )
    scores: List[AlignmentScoreItem]


class ComparisonAllyItem(BaseModel):
    """A ranked MEP ally."""
    name: str
    group: str
    avg_score: float
    count: int


class ComparisonResponse(BaseModel):
    """Comparative analysis results."""
    best_allies: List[ComparisonAllyItem] = Field(default_factory=list)
    coverage_gaps: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="{user_unique: [...], blind_spots: [...]}"
    )
    political_landscape: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="{supportive: [...], mixed: [...], opposed: [...]}"
    )
