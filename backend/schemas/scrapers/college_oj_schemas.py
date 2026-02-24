"""
College OJ (Ordre du Jour) Scraper Schemas.

Pydantic models for scraped Commission College meeting agendas
from the EC Register of Commission Documents.

Reference format: OJ(YYYY)NNNN
API endpoint: GET /api/search/OJ(YYYY)NNNN?lang=en

Created: February 2026
"""

from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime


class ScrapedCollegeAgenda(BaseModel):
    """A scraped Commission College meeting agenda (Ordre du Jour)."""
    oj_reference: str                  # e.g. "OJ(2026)2555"
    meeting_number: int                # e.g. 2555
    meeting_date: date                 # Parsed from title (actual meeting date)
    publication_date: Optional[date] = None  # API 'date' field (when published)
    location: Optional[str] = None     # "Brussels" or "Strasbourg"
    title: str                         # Full title from attachment
    ers_id: Optional[str] = None       # ERS document ID for PDF retrieval
    attachment_number: Optional[str] = None  # e.g. "OJ(2026)2555/4660057"
    languages: List[str] = ["EN", "FR"]
    detail_url: str                    # Link to Document Register detail page
    scraped_at: datetime
