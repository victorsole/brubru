"""
User Document Schemas

Pydantic schemas for user document operations.
Part of My EU Bubble - Phase 2: User Content Repository
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


# ============================================================================
# Base Document Schemas
# ============================================================================

class UserDocumentBase(BaseModel):
    """Base schema for user documents"""
    document_type: str = Field(..., description="Type: amendment, analysis, strategy, note")
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content: Optional[str] = Field(None, description="Main content")

    # Links to EU legislation
    celex_number: Optional[str] = Field(None, max_length=100, description="CELEX number of related legislation")
    procedure_reference: Optional[str] = Field(None, max_length=100, description="Legislative procedure reference")

    # Categorization
    policy_areas: Optional[List[str]] = Field(None, max_length=20, description="Policy areas")
    tags: Optional[List[str]] = Field(None, max_length=50, description="User-defined tags")

    # Privacy
    is_private: bool = Field(default=True, description="Whether document is private")

    @field_validator('document_type')
    @classmethod
    def validate_document_type(cls, v):
        allowed_types = ['amendment', 'analysis', 'strategy', 'note', 'uploaded']
        if v not in allowed_types:
            raise ValueError(f'document_type must be one of: {allowed_types}')
        return v


# ============================================================================
# Amendment Schemas
# ============================================================================

class AmendmentCreate(UserDocumentBase):
    """Schema for creating an amendment"""
    document_type: Literal["amendment"] = Field(default="amendment")
    amendment_target: Optional[str] = Field(None, description="Original text being amended")
    amendment_justification: Optional[str] = Field(None, description="Justification for amendment")
    amendment_status: Optional[str] = Field(default="draft", description="Status: draft, submitted, adopted, rejected")

    @field_validator('amendment_status')
    @classmethod
    def validate_status(cls, v):
        if v and v not in ['draft', 'submitted', 'adopted', 'rejected']:
            raise ValueError('amendment_status must be: draft, submitted, adopted, or rejected')
        return v


class AmendmentResponse(AmendmentCreate):
    """Schema for amendment response"""
    id: UUID
    user_id: UUID
    amendment_target: Optional[str] = None
    amendment_justification: Optional[str] = None
    version: int = 1
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Analysis Schemas
# ============================================================================

class AnalysisCreate(UserDocumentBase):
    """Schema for creating a policy analysis"""
    document_type: Literal["analysis"] = Field(default="analysis")
    executive_summary: Optional[str] = Field(None, description="Executive summary")
    methodology: Optional[str] = Field(None, description="Research methodology")
    conclusions: Optional[str] = Field(None, description="Analysis conclusions")
    recommendations: Optional[str] = Field(None, description="Policy recommendations")


class AnalysisResponse(AnalysisCreate):
    """Schema for analysis response"""
    id: UUID
    user_id: UUID
    executive_summary: Optional[str] = None
    methodology: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None
    version: int = 1
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Strategy Schemas
# ============================================================================

class StrategyCreate(UserDocumentBase):
    """Schema for creating a strategy document"""
    document_type: Literal["strategy"] = Field(default="strategy")
    objectives: Optional[str] = Field(None, description="Strategic objectives")
    action_plan: Optional[str] = Field(None, description="Action plan")
    timeline: Optional[str] = Field(None, max_length=500, description="Timeline")
    stakeholders: Optional[List[str]] = Field(None, max_length=50, description="Key stakeholders")


class StrategyResponse(StrategyCreate):
    """Schema for strategy response"""
    id: UUID
    user_id: UUID
    objectives: Optional[str] = None
    action_plan: Optional[str] = None
    timeline: Optional[str] = None
    stakeholders: Optional[List[str]] = None
    version: int = 1
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Note Schemas
# ============================================================================

class NoteCreate(UserDocumentBase):
    """Schema for creating a note"""
    document_type: Literal["note"] = Field(default="note")
    doc_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class NoteResponse(NoteCreate):
    """Schema for note response"""
    id: UUID
    user_id: UUID
    doc_metadata: Optional[Dict[str, Any]] = None
    version: int = 1
    view_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Generic Document Schemas
# ============================================================================

class UserDocumentCreate(UserDocumentBase):
    """Generic schema for creating any document type"""
    # Amendment fields
    amendment_target: Optional[str] = None
    amendment_justification: Optional[str] = None
    amendment_status: Optional[str] = None

    # Analysis fields
    executive_summary: Optional[str] = None
    methodology: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None

    # Strategy fields
    objectives: Optional[str] = None
    action_plan: Optional[str] = None
    timeline: Optional[str] = None
    stakeholders: Optional[List[str]] = None

    # Metadata
    doc_metadata: Optional[Dict[str, Any]] = None


class UserDocumentUpdate(BaseModel):
    """Schema for updating a document"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = None
    policy_areas: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_private: Optional[bool] = None

    # Type-specific fields
    amendment_target: Optional[str] = None
    amendment_justification: Optional[str] = None
    amendment_status: Optional[str] = None
    executive_summary: Optional[str] = None
    methodology: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None
    objectives: Optional[str] = None
    action_plan: Optional[str] = None
    timeline: Optional[str] = None
    stakeholders: Optional[List[str]] = None
    doc_metadata: Optional[Dict[str, Any]] = None

    # AI context control (for uploaded docs)
    include_in_ai_context: Optional[bool] = None


class UserDocumentResponse(UserDocumentBase):
    """Schema for document response"""
    id: UUID
    user_id: UUID

    # Amendment fields
    amendment_target: Optional[str] = None
    amendment_justification: Optional[str] = None
    amendment_status: Optional[str] = None

    # Analysis fields
    executive_summary: Optional[str] = None
    methodology: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None

    # Strategy fields
    objectives: Optional[str] = None
    action_plan: Optional[str] = None
    timeline: Optional[str] = None
    stakeholders: Optional[List[str]] = None

    # Metadata
    doc_metadata: Optional[Dict[str, Any]] = None
    version: int
    parent_document_id: Optional[UUID] = None
    view_count: int
    word_count: int = 0

    # Uploaded document fields
    storage_document_id: Optional[str] = None
    original_filename: Optional[str] = None
    file_content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    include_in_ai_context: bool = False

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserDocumentListResponse(BaseModel):
    """Schema for paginated document list"""
    documents: List[UserDocumentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================================
# Document Filter Schemas
# ============================================================================

class DocumentFilterParams(BaseModel):
    """Schema for filtering documents"""
    document_type: Optional[str] = Field(None, description="Filter by type")
    policy_areas: Optional[List[str]] = Field(None, description="Filter by policy areas")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    search: Optional[str] = Field(None, max_length=200, description="Search in title and content")
    celex_number: Optional[str] = Field(None, description="Filter by CELEX number")
    procedure_reference: Optional[str] = Field(None, description="Filter by procedure")
    is_private: Optional[bool] = Field(None, description="Filter by privacy status")
    from_date: Optional[datetime] = Field(None, description="Created after this date")
    to_date: Optional[datetime] = Field(None, description="Created before this date")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# ============================================================================
# Document Statistics Schemas
# ============================================================================

class DocumentStatsResponse(BaseModel):
    """Schema for document statistics"""
    total_documents: int
    by_type: Dict[str, int]
    by_policy_area: Dict[str, int]
    total_amendments: int
    total_analyses: int
    total_strategies: int
    total_notes: int
    total_uploaded: int = 0
    total_word_count: int
    most_viewed_documents: List[UserDocumentResponse]


# ============================================================================
# Document Version Schema
# ============================================================================

class DocumentVersionResponse(BaseModel):
    """Schema for document version info"""
    id: UUID
    version: int
    title: str
    updated_at: datetime
    parent_document_id: Optional[UUID] = None

    class Config:
        from_attributes = True
