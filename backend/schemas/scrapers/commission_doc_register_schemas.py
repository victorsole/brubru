"""
Pydantic schemas for the EC Register of Commission Documents.

Defines the data models for documents from the Commission's transparency
register at https://ec.europa.eu/transparency/documents-register/

Document types: COM, SWD, SEC, C, JOIN, OJ, PV
Available since 1 January 2001.

Note: The API backend is currently returning 503. These schemas are
ready for when the service comes back online.

Created: February 2026
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date
from enum import Enum


class CommissionDocType(str, Enum):
    """Types of documents in the Register of Commission Documents."""
    COM = "COM"       # Legislative proposals, communications, reports, white/green papers
    SWD = "SWD"       # Staff Working Documents (impact assessments, background analysis)
    SEC = "SEC"       # Secretariat-General documents (pre-2012 label, still used for some)
    C = "C"           # Delegated/implementing acts, preliminary COM versions, guidelines
    JOIN = "JOIN"     # Joint documents (Commission + High Representative, CFSP/CSDP)
    OJ = "OJ"         # Official Journal references
    PV = "PV"         # Proces-Verbal (Commission meeting minutes)


# Human-readable labels for document types
COMMISSION_DOC_TYPE_LABELS: Dict[str, str] = {
    CommissionDocType.COM: "Commission Document (legislative proposals, communications, reports)",
    CommissionDocType.SWD: "Staff Working Document (impact assessments, background analysis)",
    CommissionDocType.SEC: "Secretariat-General Document (internal Commission documents)",
    CommissionDocType.C: "C Document (delegated/implementing acts, guidelines)",
    CommissionDocType.JOIN: "Joint Document (Commission + High Representative)",
    CommissionDocType.OJ: "Official Journal",
    CommissionDocType.PV: "Proces-Verbal (Commission meeting minutes)",
}


class CommissionDocSearchParams(BaseModel):
    """Parameters for searching the Register of Commission Documents."""
    doc_type: Optional[CommissionDocType] = Field(None, description="Filter by document type")
    dg: Optional[str] = Field(None, description="Filter by DG code (e.g. CNECT, GROW)")
    year: Optional[int] = Field(None, description="Filter by year")
    search_text: Optional[str] = Field(None, description="Free text search in title/content")
    date_from: Optional[date] = Field(None, description="Start date for date range filter")
    date_to: Optional[date] = Field(None, description="End date for date range filter")
    language: str = Field("EN", description="Document language code")
    page: int = Field(0, ge=0, description="Page number (0-indexed)")
    limit: int = Field(20, ge=1, le=100, description="Results per page")

    class Config:
        use_enum_values = True


class CommissionDocItem(BaseModel):
    """
    A document from the Register of Commission Documents (list view).

    Represents the basic metadata returned from a search query.
    Reference format examples: COM(2021) 206 final, SWD(2024) 1, C(2025) 100
    """
    reference: str = Field(..., description="Document reference (e.g. 'COM(2021) 206 final')")
    title: str = Field(..., description="Document title")
    doc_type: CommissionDocType = Field(..., description="Document type")
    publication_date: Optional[date] = Field(None, description="Publication date")
    dg_responsible: Optional[str] = Field(None, description="Responsible DG code (e.g. CNECT)")
    author: Optional[str] = Field(None, description="Author or responsible service")
    procedure_ref: Optional[str] = Field(
        None,
        description="Related OEIL procedure reference (e.g. 2021/0106(COD))"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Available language codes (e.g. ['EN', 'FR', 'DE'])"
    )
    portal_url: Optional[str] = Field(None, description="Link to RegDoc portal page")
    scraped_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this data was fetched"
    )

    class Config:
        use_enum_values = True


class CommissionDocDetail(CommissionDocItem):
    """
    Full document detail from the Register of Commission Documents.

    Extends CommissionDocItem with additional fields available on the
    document detail page.
    """
    summary: Optional[str] = Field(None, description="Document summary or description")
    related_docs: List[str] = Field(
        default_factory=list,
        description="References of related documents"
    )
    pdf_urls: Dict[str, str] = Field(
        default_factory=dict,
        description="PDF download URLs by language code (e.g. {'EN': 'https://...'})"
    )
    celex: Optional[str] = Field(
        None,
        description="CELEX number if the document has been adopted into law"
    )
    legal_basis: Optional[str] = Field(None, description="Legal basis (Treaty article)")

    class Config:
        use_enum_values = True
