"""
Amendment Schemas

Pydantic schemas for amendment validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class AmendmentBase(BaseModel):
    """Base amendment schema with common fields"""
    document_id: str = Field(..., description="ID of the source document")
    document_filename: Optional[str] = Field(None, description="Filename of the source document")
    element_index: int = Field(..., description="Index of the element in the legislative structure")
    element_type: str = Field(..., description="Type of legislative element (recital, article, etc.)")
    element_number: Optional[str] = Field(None, description="Number or letter of the element")
    position_text: str = Field(..., description="Human-readable position (e.g., 'Recital 15')")
    amendment_type: str = Field(..., description="Type of amendment (suppression, addition, modification)")
    original_text: str = Field(..., description="Original text of the element")
    proposed_text: str = Field(..., description="Proposed text for the amendment")
    insert_after: Optional[int] = Field(None, description="For additions: element index to insert after")
    justification: Optional[str] = Field(None, description="Justification for the amendment")
    group_label: Optional[str] = Field(None, description="Political group or committee label")
    author: Optional[str] = Field(None, description="Author of the amendment")
    amendment_number: Optional[str] = Field(None, description="Amendment number (e.g., 'AM 1')")
    status: str = Field(default="draft", description="Status of the amendment")


class AmendmentCreate(AmendmentBase):
    """Schema for creating a new amendment"""
    pass


class AmendmentUpdate(BaseModel):
    """Schema for updating an existing amendment"""
    element_index: Optional[int] = None
    element_type: Optional[str] = None
    element_number: Optional[str] = None
    position_text: Optional[str] = None
    amendment_type: Optional[str] = None
    original_text: Optional[str] = None
    proposed_text: Optional[str] = None
    insert_after: Optional[int] = None
    justification: Optional[str] = None
    group_label: Optional[str] = None
    author: Optional[str] = None
    amendment_number: Optional[str] = None
    status: Optional[str] = None


class AmendmentResponse(AmendmentBase):
    """Schema for amendment API responses"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AmendmentBatchCreate(BaseModel):
    """Schema for creating multiple amendments at once"""
    document_id: str = Field(..., description="ID of the source document")
    document_filename: Optional[str] = Field(None, description="Filename of the source document")
    amendments: list[AmendmentCreate] = Field(..., description="List of amendments to create")


class AmendmentListResponse(BaseModel):
    """Schema for listing amendments with pagination"""
    amendments: list[AmendmentResponse]
    total: int
    page: int
    page_size: int


class AmendmentStats(BaseModel):
    """Statistics about user's amendments"""
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_document: dict[str, int]


# --- AI Batch Suggestion Schemas ---

class ElementSummary(BaseModel):
    """Summary of a legislative element for AI analysis"""
    position: str = Field(..., description="Human-readable position, e.g. 'Article 5', 'Recital 3'")
    element_type: str = Field(..., description="Type: recital, article, point, paragraph, etc.")
    text: str = Field(..., description="Legislative text content (may be truncated)")
    element_index: Optional[int] = Field(None, description="Index of this element in the full loaded document (for reliable placement)")


class BatchSuggestionRequest(BaseModel):
    """Request for document-wide AI amendment suggestions"""
    policy_position: str = Field(..., description="User's policy goals or position")
    supporting_context: Optional[str] = Field(None, description="Extracted text from uploaded supporting documents")
    elements: List[ElementSummary] = Field(..., description="Key legislative elements to analyse")
    max_suggestions: Optional[int] = Field(default=None, ge=1, description="Maximum suggestions (determined by subscription tier if not set)")
    celex: Optional[str] = Field(None, description="CELEX of the loaded law, used to inject drafting context")
    known_article_numbers: Optional[List[str]] = Field(None, description="All article numbers in the loaded document, for phantom-reference detection")


class SuggestionValidation(BaseModel):
    """Deterministic fidelity check results for one suggestion"""
    original_verified: bool = Field(True, description="Did the model faithfully echo the source element text?")
    scope_ratio: float = Field(0.0, description="Word-change fraction, 0.0 (minimal) to 1.0 (rewritten)")
    phantom_references: List[str] = Field(default_factory=list, description="Internal article references not present in the loaded document")
    flags: List[str] = Field(default_factory=list, description="Human-readable warning labels")


class BatchSuggestionItem(BaseModel):
    """A single AI-generated amendment suggestion"""
    element_position: str = Field(..., description="Which element this applies to, e.g. 'Article 5'")
    amendment_type: str = Field(..., description="modification, suppression, or addition")
    original_text: str = Field(..., description="Original text of the element")
    proposed_text: str = Field(..., description="AI-proposed amended text")
    justification: str = Field(..., description="Why this amendment serves the policy goal")
    element_index: Optional[int] = Field(None, description="Index of the target element in the full loaded document")
    validation: Optional[SuggestionValidation] = Field(None, description="Deterministic fidelity check results")


class BatchSuggestionResponse(BaseModel):
    """Response containing multiple AI amendment suggestions"""
    suggestions: List[BatchSuggestionItem]
    ai_provider: str
    ai_model: str


class ImproveTextRequest(BaseModel):
    """Request to improve user-drafted amendment text with AI"""
    drafted_text: str = Field(..., min_length=1, description="The user's current drafted amendment text")
    original_text: str = Field("", description="The original legislative text being amended")
    element_type: str = Field(..., description="Type: recital, article, point, paragraph, etc.")
    element_position: str = Field(..., description="Position reference, e.g. 'Article 5'")
    amendment_type: str = Field(..., description="modification or addition")
    document_title: Optional[str] = Field(None, description="Title of the legislative document")


class ImproveTextResponse(BaseModel):
    """Response containing AI-improved amendment text"""
    improved_text: str
    changes_summary: str
    ai_provider: str
    ai_model: str


class JustifyRequest(BaseModel):
    """Request to generate a justification for an amendment"""
    original_text: str = Field("", description="Original legislative text")
    proposed_text: str = Field("", description="Proposed amended text")
    amendment_type: str = Field("modification", description="modification, suppression, or addition")
    policy_rationale: Optional[str] = Field(None, description="The user's policy reason for the amendment")
    element_position: Optional[str] = Field(None, description="Position reference, e.g. 'Article 5'")


class JustifyResponse(BaseModel):
    """Response containing an AI-drafted justification"""
    justification: str
    ai_provider: str
    ai_model: str


class AnalyseArticleRequest(BaseModel):
    """Request to analyse an article for amendment opportunities"""
    article_text: str = Field(..., min_length=1, description="Text of the article to analyse")
    article_position: str = Field(..., description="Position reference, e.g. 'Article 5'")
    celex: Optional[str] = Field(None, description="CELEX of the loaded law, for drafting context")


class AnalyseArticleResponse(BaseModel):
    """Response containing an AI analysis of an article"""
    analysis: str
    ai_provider: str
    ai_model: str
