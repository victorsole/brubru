"""
Committee Agenda Scraper Schemas.

Pydantic models for scraped EP committee draft agenda metadata.

Created: February 2026
"""

from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime


class ScrapedCommitteeAgenda(BaseModel):
    """A scraped draft agenda from EP committee latest-documents page."""
    committee_code: str
    meeting_date: date
    title: str
    document_id: Optional[str] = None
    pe_number: Optional[str] = None
    pdf_url: Optional[str] = None
    doc_url: Optional[str] = None
    source_url: str
    scraped_at: datetime
