"""
Data Schemas for EU Institutional Scrapers

Pydantic models for validated, structured data from all EU sources.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, HttpUrl, Field


# ============================================================================
# Enums
# ============================================================================

class DocumentType(str, Enum):
    """EU document types"""
    REGULATION = "regulation"
    DIRECTIVE = "directive"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    OPINION = "opinion"
    RESOLUTION = "resolution"
    REPORT = "report"
    AMENDMENT = "amendment"
    COMMUNICATION = "communication"
    OTHER = "other"


class LegislativeStage(str, Enum):
    """Stages of EU legislative procedure"""
    PLANNING = "planning"
    CONSULTATION = "consultation"
    PROPOSAL = "proposal"
    FIRST_READING_EP = "first_reading_ep"
    FIRST_READING_COUNCIL = "first_reading_council"
    SECOND_READING_EP = "second_reading_ep"
    SECOND_READING_COUNCIL = "second_reading_council"
    CONCILIATION = "conciliation"
    THIRD_READING = "third_reading"
    ADOPTION = "adoption"
    IMPLEMENTATION = "implementation"
    COMPLETED = "completed"


class InstitutionType(str, Enum):
    """EU institutions"""
    EUROPEAN_PARLIAMENT = "european_parliament"
    EUROPEAN_COMMISSION = "european_commission"
    COUNCIL = "council"
    COURT_OF_JUSTICE = "court_of_justice"
    EUROPEAN_COUNCIL = "european_council"
    ECB = "ecb"
    COURT_OF_AUDITORS = "court_of_auditors"


# ============================================================================
# Base Models
# ============================================================================

class ScrapedData(BaseModel):
    """Base model for all scraped data"""
    source: str = Field(..., description="Source scraper name")
    source_url: HttpUrl = Field(..., description="URL where data was scraped from")
    scraped_at: datetime = Field(default_factory=datetime.now, description="Timestamp of scraping")
    language: str = Field(default="en", description="Content language")


# ============================================================================
# MEP (Member of European Parliament) Models
# ============================================================================

class PoliticalGroup(BaseModel):
    """Political group in European Parliament"""
    code: str = Field(..., description="Group code (e.g., 'EPP', 'S&D')")
    name: str = Field(..., description="Full group name")


class MEP(ScrapedData):
    """Member of European Parliament"""
    mep_id: str = Field(..., description="Unique MEP identifier")
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    country: str = Field(..., description="Member state (ISO 3166-1 alpha-2)")
    political_group: Optional[PoliticalGroup] = None
    national_party: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    profile_url: HttpUrl
    committees: List[str] = Field(default_factory=list, description="Committee memberships")
    delegations: List[str] = Field(default_factory=list, description="Delegation memberships")
    assistant_info: Optional[Dict[str, Any]] = None
    term_start: Optional[datetime] = None
    term_end: Optional[datetime] = None


# ============================================================================
# Legislative Document Models
# ============================================================================

class LegislativeDocument(ScrapedData):
    """EU legislative document"""
    celex_number: Optional[str] = Field(None, description="CELEX identifier")
    document_id: str = Field(..., description="Unique document identifier")
    title: str
    document_type: DocumentType
    procedure_reference: Optional[str] = None
    legal_basis: Optional[str] = None
    date_published: Optional[datetime] = None
    date_effect: Optional[datetime] = None
    authors: List[str] = Field(default_factory=list, description="Document authors/institutions")
    subjects: List[str] = Field(default_factory=list, description="Subject matter descriptors")
    eurovoc_descriptors: List[str] = Field(default_factory=list, description="EuroVoc thesaurus terms")
    text_content: Optional[str] = None
    html_url: Optional[HttpUrl] = None
    pdf_url: Optional[HttpUrl] = None
    xml_url: Optional[HttpUrl] = None
    related_documents: List[str] = Field(default_factory=list, description="Related CELEX numbers")


class LegislativeProcedure(ScrapedData):
    """Legislative procedure tracking"""
    procedure_reference: str = Field(..., description="Procedure identifier (e.g., '2021/0106(COD)')")
    title: str
    legal_basis: Optional[str] = None
    current_stage: LegislativeStage
    procedure_type: str = Field(..., description="E.g., 'Ordinary legislative procedure (COD)'")
    commission_proposal_date: Optional[datetime] = None
    ep_committee_responsible: Optional[str] = None
    ep_rapporteur: Optional[str] = None
    council_configuration: Optional[str] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological events")
    latest_event: Optional[str] = None
    latest_event_date: Optional[datetime] = None
    expected_adoption_date: Optional[datetime] = None
    documents: List[str] = Field(default_factory=list, description="Associated document IDs")


# ============================================================================
# Commission Models
# ============================================================================

class Commissioner(ScrapedData):
    """European Commissioner"""
    commissioner_id: str
    full_name: str
    portfolio: str = Field(..., description="Policy portfolio")
    country: str
    photo_url: Optional[HttpUrl] = None
    profile_url: HttpUrl
    biography: Optional[str] = None
    directorate_general: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None
    term_start: Optional[datetime] = None
    term_end: Optional[datetime] = None


class PolicyInitiative(ScrapedData):
    """European Commission policy initiative"""
    initiative_id: str
    title: str
    initiative_type: str = Field(..., description="E.g., 'Legislative', 'Non-legislative'")
    policy_area: str
    lead_dg: Optional[str] = Field(None, description="Lead Directorate-General")
    stage: str
    planned_adoption: Optional[datetime] = None
    consultation_period: Optional[Dict[str, datetime]] = None
    impact_assessment_url: Optional[HttpUrl] = None
    related_procedures: List[str] = Field(default_factory=list)


# ============================================================================
# Council Models
# ============================================================================

class CouncilConfiguration(ScrapedData):
    """Council of the EU configuration"""
    configuration_name: str = Field(..., description="E.g., 'General Affairs Council'")
    responsible_for: List[str] = Field(default_factory=list, description="Policy areas")
    meeting_frequency: Optional[str] = None
    presidency: Optional[str] = Field(None, description="Current presidency holder")
    next_meeting_date: Optional[datetime] = None


class CouncilDocument(ScrapedData):
    """Council document"""
    document_number: str = Field(..., description="Council document number")
    title: str
    document_type: str
    configuration: Optional[str] = None
    date_published: Optional[datetime] = None
    status: str = Field(..., description="E.g., 'Public', 'Limité'")
    pdf_url: Optional[HttpUrl] = None


# ============================================================================
# Think Tank / Research Models
# ============================================================================

class ResearchPublication(ScrapedData):
    """Research publication or policy brief"""
    publication_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    publication_type: str = Field(..., description="E.g., 'Briefing', 'In-depth analysis', 'Study'")
    policy_area: str
    date_published: Optional[datetime] = None
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    pdf_url: Optional[HttpUrl] = None
    html_url: Optional[HttpUrl] = None


# ============================================================================
# Terminology Models
# ============================================================================

class TerminologyEntry(ScrapedData):
    """IATE terminology entry"""
    entry_id: str
    term: str = Field(..., description="Term in specified language")
    definition: Optional[str] = None
    subject_field: str = Field(..., description="Domain/subject area")
    reliability_code: Optional[str] = None
    translations: Dict[str, str] = Field(default_factory=dict, description="Language code to translation")
    related_terms: List[str] = Field(default_factory=list)


# ============================================================================
# Contact / Who's Who Models
# ============================================================================

class InstitutionalContact(ScrapedData):
    """Institutional contact from Who's Who"""
    contact_id: str
    full_name: str
    title: Optional[str] = None
    institution: InstitutionType
    department: Optional[str] = None
    directorate_general: Optional[str] = None
    unit: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    org_chart_url: Optional[HttpUrl] = None


# ============================================================================
# Search Result Models
# ============================================================================

class SearchResult(ScrapedData):
    """Generic search result"""
    result_id: str
    title: str
    description: Optional[str] = None
    result_type: str
    url: HttpUrl
    date: Optional[datetime] = None
    relevance_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# Response Models (API responses)
# ============================================================================

class ScraperResponse(BaseModel):
    """Standard scraper response wrapper"""
    success: bool
    scraper_name: str
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    cache_hit: bool = False
    execution_time_ms: Optional[float] = None


class BulkScraperResponse(BaseModel):
    """Response for bulk/batch scraping operations"""
    total_requested: int
    successful: int
    failed: int
    results: List[ScraperResponse]
    total_execution_time_ms: float
