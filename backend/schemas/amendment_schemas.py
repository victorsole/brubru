"""
Amendment Schemas

Pydantic schemas for amendment validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional
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
