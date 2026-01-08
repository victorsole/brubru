"""
Pydantic Schemas for EU Data

Data validation schemas for all EU institutional data:
- European Parliament (MEPs, documents, committees)
- EUR-Lex (legal documents)
- TED (procurement notices)
- IATE (terminology)
- Datasets
- RSS feeds
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# European Parliament Schemas
# ============================================================================

class MEPSchema(BaseModel):
    """Member of European Parliament"""
    id: str
    name: str
    country: str
    group: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[datetime] = None
    photo: Optional[HttpUrl] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "http://data.europarl.europa.eu/person/12345",
                "name": "John Doe",
                "country": "Spain",
                "group": "EPP",
                "email": "john.doe@europarl.europa.eu"
            }
        }


class CommitteeSchema(BaseModel):
    """European Parliament Committee"""
    id: str
    code: str
    name: str
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "http://data.europarl.europa.eu/org/envi",
                "code": "ENVI",
                "name": "Committee on the Environment, Public Health and Food Safety"
            }
        }


class EPDocumentSchema(BaseModel):
    """European Parliament Document"""
    id: str
    title: str
    date: datetime
    type: str
    committee: Optional[str] = None
    language: str = "en"

    class Config:
        json_schema_extra = {
            "example": {
                "id": "http://data.europarl.europa.eu/doc/123456",
                "title": "Report on climate action",
                "date": "2025-01-15T10:00:00",
                "type": "report",
                "committee": "ENVI"
            }
        }


# ============================================================================
# EUR-Lex Schemas
# ============================================================================

class EURLexDocumentSchema(BaseModel):
    """EUR-Lex Legal Document"""
    uri: str
    celex: str
    title: str
    date: datetime
    type: str
    subject: Optional[str] = None
    author: Optional[str] = None
    language: str = "en"

    class Config:
        json_schema_extra = {
            "example": {
                "uri": "http://publications.europa.eu/resource/celex/32023R1234",
                "celex": "32023R1234",
                "title": "Regulation on digital services",
                "date": "2023-06-15T00:00:00",
                "type": "regulation"
            }
        }


class DocumentRelationshipsSchema(BaseModel):
    """EUR-Lex Document Relationships"""
    celex: str
    amended_by: List[str] = Field(default_factory=list)
    amends: List[str] = Field(default_factory=list)
    corrected_by: List[str] = Field(default_factory=list)
    corrects: List[str] = Field(default_factory=list)
    repealed_by: List[str] = Field(default_factory=list)
    repeals: List[str] = Field(default_factory=list)
    implemented_by: List[str] = Field(default_factory=list)


# ============================================================================
# TED Procurement Schemas
# ============================================================================

class TEDNoticeSchema(BaseModel):
    """TED Procurement Notice"""
    id: str
    title: str
    notice_type: str
    publication_date: datetime
    country: str
    cpv_codes: List[str] = Field(default_factory=list)
    contracting_authority: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    url: Optional[HttpUrl] = None
    deadline: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "2023-123456",
                "title": "Construction of public building",
                "notice_type": "contract_notice",
                "publication_date": "2023-05-15T00:00:00",
                "country": "ES",
                "cpv_codes": ["45000000"],
                "value": 5000000.0,
                "currency": "EUR"
            }
        }


# ============================================================================
# IATE Terminology Schemas
# ============================================================================

class IATETermSchema(BaseModel):
    """IATE Terminology Entry"""
    id: str
    term: str
    language: str
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    reliability: Optional[str] = None
    definition: Optional[str] = None
    context: Optional[str] = None
    translations: Dict[str, List[str]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "IATE-123456",
                "term": "biodiversity",
                "language": "en",
                "domain": "ENVIRONMENT",
                "reliability": "3",
                "definition": "The variety of life forms",
                "translations": {
                    "es": ["biodiversidad"],
                    "fr": ["biodiversité"]
                }
            }
        }


# ============================================================================
# Dataset Schemas
# ============================================================================

class DatasetSchema(BaseModel):
    """Open Dataset"""
    id: str
    title: str
    description: Optional[str] = None
    publisher: Optional[str] = None
    issued: Optional[datetime] = None
    modified: Optional[datetime] = None
    theme: List[str] = Field(default_factory=list)
    format: List[str] = Field(default_factory=list)
    country: Optional[str] = None
    access_url: Optional[HttpUrl] = None
    download_url: Optional[HttpUrl] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "dataset-123456",
                "title": "EU Emissions Data",
                "description": "Greenhouse gas emissions data",
                "publisher": "European Environment Agency",
                "issued": "2023-01-01T00:00:00",
                "format": ["CSV", "JSON"]
            }
        }


# ============================================================================
# RSS Feed Schemas
# ============================================================================

class RSSEntrySchema(BaseModel):
    """RSS Feed Entry"""
    id: str
    title: str
    link: HttpUrl
    published: datetime
    summary: str
    content: Optional[str] = None
    source: str
    feed_name: str
    categories: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    author: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rss-entry-123",
                "title": "Parliament adopts new regulation",
                "link": "https://europarl.europa.eu/news/123",
                "published": "2025-01-15T14:30:00",
                "summary": "The European Parliament has adopted...",
                "source": "european_parliament",
                "feed_name": "press_releases"
            }
        }


# ============================================================================
# Sync Task Schemas
# ============================================================================

class SyncTaskStatusSchema(BaseModel):
    """Sync Task Status"""
    name: str
    description: str
    priority: str
    status: str
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    total_runs: int = 0
    error_count: int = 0
    last_result: Optional[Dict[str, Any]] = None


class SyncStatisticsSchema(BaseModel):
    """Sync Statistics"""
    total_tasks: int
    total_runs: int
    total_errors: int
    successful_tasks: int
    running: bool
    tasks_by_status: Dict[str, int]


# ============================================================================
# Search and Query Schemas
# ============================================================================

class SearchQuerySchema(BaseModel):
    """Search Query Parameters"""
    query: str
    language: str = "en"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v


class SearchResultsSchema(BaseModel):
    """Search Results"""
    query: str
    total: int
    results: List[Dict[str, Any]]
    execution_time_ms: float


# ============================================================================
# Amendment Tracking Schemas (Amendator)
# ============================================================================

class AmendmentSchema(BaseModel):
    """Legislative Amendment"""
    id: str
    document_id: str
    article: str
    paragraph: Optional[str] = None
    original_text: str
    proposed_text: str
    justification: Optional[str] = None
    author: str
    status: str  # pending, accepted, rejected
    created_at: datetime
    updated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "amendment-123",
                "document_id": "32023R1234",
                "article": "Article 5",
                "original_text": "Member States shall...",
                "proposed_text": "Member States must...",
                "author": "John Doe MEP",
                "status": "pending",
                "created_at": "2025-01-15T10:00:00",
                "updated_at": "2025-01-15T10:00:00"
            }
        }


# ============================================================================
# Chat and AI Schemas
# ============================================================================

class ChatMessageSchema(BaseModel):
    """Chat Message"""
    id: Optional[str] = None
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    context_sources: List[str] = Field(default_factory=list)

    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError('Role must be user, assistant, or system')
        return v


class ChatRequestSchema(BaseModel):
    """Chat Request"""
    message: str
    conversation_id: Optional[str] = None
    language: str = "en"
    include_context: bool = True
    max_context_documents: int = Field(default=5, ge=1, le=20)

    @validator('message')
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v


class ChatResponseSchema(BaseModel):
    """Chat Response"""
    message: str
    conversation_id: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    model: str = "claude-3-5-sonnet"


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckSchema(BaseModel):
    """Health Check Response"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, bool]
    version: str = "1.0.0"


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponseSchema(BaseModel):
    """Error Response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    path: Optional[str] = None
