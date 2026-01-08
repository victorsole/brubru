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
    country: Optional[str] = Field(None, description="Member state (ISO 3166-1 alpha-2)")
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


# ============================================================================
# PHASE 4-7 ADDITIONS: API Integration Schemas
# ============================================================================

# ----------------------------------------------------------------------------
# Open Data Portal Schemas
# ----------------------------------------------------------------------------

class OpenDataPortalDataset(ScrapedData):
    """
    Dataset from EU Open Data Portal.
    Source: data.europa.eu
    """
    dataset_id: str = Field(..., description="Unique dataset identifier")
    title: str
    description: Optional[str] = None
    publisher: str = Field(..., description="Publishing organization")
    theme: List[str] = Field(default_factory=list, description="Dataset themes")
    keywords: List[str] = Field(default_factory=list)
    issued: Optional[datetime] = Field(None, description="Date published")
    modified: Optional[datetime] = Field(None, description="Date last modified")
    temporal_coverage: Optional[Dict[str, datetime]] = Field(None, description="Time period covered")
    spatial_coverage: List[str] = Field(default_factory=list, description="Geographic coverage")
    distributions: List[Dict[str, Any]] = Field(default_factory=list, description="Download formats")
    access_url: Optional[HttpUrl] = None
    download_url: Optional[HttpUrl] = None
    format: Optional[str] = Field(None, description="Data format (CSV, XML, JSON, etc.)")
    license: Optional[str] = None
    contact_point: Optional[Dict[str, str]] = None


class RegistryAPIResponse(BaseModel):
    """
    Generic response from EU Registry APIs.
    Used for various institutional registries.
    """
    status: str = Field(..., description="Response status")
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total_results: int
    page: int = 1
    page_size: int = 100
    has_more: bool = False
    metadata: Optional[Dict[str, Any]] = None


# ----------------------------------------------------------------------------
# RSS Feed Schemas
# ----------------------------------------------------------------------------

class RSSFeedEntry(ScrapedData):
    """
    Single RSS/Atom feed entry.
    Used across all EU institutional RSS feeds.
    """
    entry_id: str = Field(..., description="Unique entry ID (guid)")
    title: str
    link: HttpUrl
    published: Optional[datetime] = None
    updated: Optional[datetime] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    feed_source: str = Field(..., description="Source feed URL")
    feed_title: Optional[str] = None


class EURLexRSSEntry(RSSFeedEntry):
    """
    EUR-Lex specific RSS entry with additional metadata.
    Source: EUR-Lex RSS feeds
    """
    celex_number: Optional[str] = None
    document_type: Optional[DocumentType] = None
    eli_uri: Optional[str] = Field(None, description="European Legislation Identifier")
    subject_matter: List[str] = Field(default_factory=list)
    directory_code: Optional[str] = Field(None, description="EUR-Lex directory classification")


# ----------------------------------------------------------------------------
# EPRS Think Tank Publication Schemas (Phase 1: Full Content Extraction)
# ----------------------------------------------------------------------------

class EPRSPublicationType(str, Enum):
    """EPRS publication types"""
    AT_A_GLANCE = "at_a_glance"
    BRIEFING = "briefing"
    IN_DEPTH_ANALYSIS = "in_depth_analysis"
    STUDY = "study"
    BLOG_POST = "blog_post"
    OTHER = "other"


class EPRSPublication(ScrapedData):
    """
    European Parliament Research Service (Think Tank) publication.

    Phase 1: Full Content Extraction
    - Metadata from RSS feeds
    - Full text from PDFs
    - Extracted entities and references
    - Document structure

    Sources:
    - RSS: https://epthinktank.eu/feed
    - Publications Office: Cellar API

    This schema serves as a blueprint for other EU institutional research
    publications (JRC, Commission studies, etc.)
    """
    # Basic identification
    publication_id: str = Field(..., description="Unique publication identifier")
    title: str
    publication_type: EPRSPublicationType

    # URLs and files
    html_url: Optional[HttpUrl] = Field(None, description="Web page URL")
    pdf_url: Optional[HttpUrl] = Field(None, description="PDF download URL")
    pdf_local_path: Optional[str] = Field(None, description="Local PDF file path")

    # Publication metadata
    authors: List[str] = Field(default_factory=list)
    publication_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    # Content (Phase 1: extracted from PDF)
    summary: Optional[str] = Field(None, description="Short summary/abstract")
    full_text: Optional[str] = Field(None, description="Complete extracted text")
    word_count: Optional[int] = None
    page_count: Optional[int] = None

    # Document structure (Phase 1)
    sections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Document sections with headings and content"
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Key findings/conclusions"
    )

    # Legislative context
    policy_areas: List[str] = Field(default_factory=list, description="Policy domains")
    committees: List[str] = Field(default_factory=list, description="EP committees")
    related_celex_numbers: List[str] = Field(
        default_factory=list,
        description="Related EU legislation CELEX numbers"
    )
    related_procedures: List[str] = Field(
        default_factory=list,
        description="Related legislative procedures"
    )
    related_meps: List[str] = Field(
        default_factory=list,
        description="MEPs mentioned in publication"
    )

    # References and citations
    references: List[str] = Field(
        default_factory=list,
        description="Citations, URLs, and references found in document"
    )
    bibliography: List[str] = Field(default_factory=list)

    # Categorization
    categories: List[str] = Field(default_factory=list, description="RSS categories/tags")
    eurovoc_descriptors: List[str] = Field(default_factory=list)

    # Quality metrics (Phase 1)
    extraction_quality: Optional[str] = Field(
        None,
        description="PDF extraction quality: high, medium, low"
    )
    has_full_text: bool = Field(default=False, description="Full text successfully extracted")
    has_tables: bool = Field(default=False, description="Contains data tables")

    # Processing status
    is_processed: bool = Field(default=False, description="Fully processed and enriched")
    processed_at: Optional[datetime] = None

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional publication-specific metadata"
    )


class EPRSSection(BaseModel):
    """
    Section within EPRS publication.
    Extracted during Phase 1 content processing.
    """
    heading: str
    content: str
    page_number: int
    level: int = Field(default=1, description="Heading level (1=main, 2=sub, etc.)")
    word_count: int = 0


class EPRSExtractionResult(BaseModel):
    """
    Result of EPRS PDF extraction process.
    Used to pass data between PDF processor and enricher.
    """
    publication: EPRSPublication
    extraction_quality: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_seconds: float = 0.0


# ----------------------------------------------------------------------------
# EUR-Lex / Cellar API Schemas
# ----------------------------------------------------------------------------

class CellarDocument(ScrapedData):
    """
    Document from Cellar REST API (EUR-Lex backend).
    Source: Cellar API
    """
    cellar_id: str = Field(..., description="Cellar URI")
    celex_number: Optional[str] = None
    eli_uri: Optional[str] = Field(None, description="European Legislation Identifier")
    title: str
    document_type: Optional[DocumentType] = None
    work_date: Optional[datetime] = Field(None, description="Work date")
    published_in_official_journal: Optional[bool] = None
    oj_series: Optional[str] = Field(None, description="Official Journal series")
    oj_number: Optional[str] = None
    oj_date: Optional[datetime] = None
    author: List[str] = Field(default_factory=list)
    subject_matter: List[str] = Field(default_factory=list)
    eurovoc: List[str] = Field(default_factory=list)
    text_formats: List[str] = Field(default_factory=list, description="Available formats")
    manifestation_uris: Dict[str, str] = Field(default_factory=dict, description="Format URIs")


class SOAPSearchResult(BaseModel):
    """
    Result from EUR-Lex SOAP search service.
    Source: EUR-Lex SOAP API
    """
    uri: HttpUrl
    title: str
    document_type: Optional[str] = None
    date: Optional[datetime] = None
    author: List[str] = Field(default_factory=list)
    eurovoc_descriptors: List[str] = Field(default_factory=list)
    relevance_score: Optional[float] = None


class SPARQLQueryResult(BaseModel):
    """
    Result from SPARQL endpoint queries.
    Source: EUR-Lex, European Parliament, Publications Office SPARQL
    """
    bindings: List[Dict[str, Any]] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)
    total_results: int
    query: Optional[str] = Field(None, description="Original SPARQL query")


# ----------------------------------------------------------------------------
# Search API Schemas
# ----------------------------------------------------------------------------

class SearchAPIResult(ScrapedData):
    """
    Result from EU Search API.
    Source: europa.eu search
    """
    result_id: str
    title: str
    url: HttpUrl
    description: Optional[str] = None
    content_type: str = Field(..., description="Page type")
    institution: Optional[str] = None
    language: str = "en"
    publication_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    relevance_score: float
    highlighted_fragments: List[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# TED (Tenders Electronic Daily) Schemas
# ----------------------------------------------------------------------------

class TEDNotice(ScrapedData):
    """
    Public procurement notice from TED.
    Source: ted.europa.eu
    """
    notice_id: str = Field(..., description="TED notice number")
    title: str
    contracting_authority: str
    authority_country: str = Field(..., description="ISO 3166-1 alpha-2")
    notice_type: str = Field(..., description="E.g., 'Contract notice', 'Contract award'")
    cpv_codes: List[str] = Field(default_factory=list, description="Common Procurement Vocabulary")
    publication_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None
    estimated_value: Optional[Dict[str, Any]] = Field(None, description="Value and currency")
    contract_type: Optional[str] = Field(None, description="Works, supplies, or services")
    procedure_type: Optional[str] = Field(None, description="Open, restricted, etc.")
    description: Optional[str] = None
    document_urls: List[HttpUrl] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# Publications Office Schemas
# ----------------------------------------------------------------------------

class PublicationMetadata(ScrapedData):
    """
    Metadata for EU publication.
    Source: Publications Office
    """
    publication_id: str = Field(..., description="Publication identifier")
    title: str
    subtitle: Optional[str] = None
    isbn: Optional[str] = None
    issn: Optional[str] = None
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    publisher: str
    publication_date: Optional[datetime] = None
    edition: Optional[str] = None
    series: Optional[str] = None
    volume: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    language: str = "en"
    subject_classification: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    pages: Optional[int] = None
    format: Optional[str] = Field(None, description="Physical/digital format")
    catalogue_url: Optional[HttpUrl] = None
    download_formats: Dict[str, HttpUrl] = Field(default_factory=dict)


# ----------------------------------------------------------------------------
# IATE Terminology Schemas (Enhanced)
# ----------------------------------------------------------------------------

class TermTranslation(BaseModel):
    """Translation of a terminology term"""
    language: str = Field(..., description="ISO 639-1 language code")
    term: str
    reliability: Optional[str] = Field(None, description="Reliability code 1-4")
    note: Optional[str] = None
    source: Optional[str] = None


class DomainClassification(BaseModel):
    """IATE domain classification"""
    domain_code: str
    domain_name: str
    subdomain: Optional[str] = None


class EnhancedTerminologyEntry(ScrapedData):
    """
    Enhanced IATE terminology entry with full translation data.
    Source: IATE (Inter-Active Terminology for Europe)
    """
    entry_id: str
    term: str = Field(..., description="Term in source language")
    definition: Optional[str] = None
    translations: List[TermTranslation] = Field(default_factory=list)
    domains: List[DomainClassification] = Field(default_factory=list)
    reliability_code: Optional[str] = Field(None, description="1=Reliable, 4=Unreliable")
    entry_type: Optional[str] = Field(None, description="Full form, abbreviation, etc.")
    grammatical_info: Optional[Dict[str, str]] = None
    context: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    related_concepts: List[str] = Field(default_factory=list)
    last_updated: Optional[datetime] = None


# ----------------------------------------------------------------------------
# JRC (Joint Research Centre) Schemas
# ----------------------------------------------------------------------------

class JRCDataset(ScrapedData):
    """
    Dataset from JRC Data Catalogue.
    Source: data.jrc.ec.europa.eu
    """
    dataset_id: str
    title: str
    description: Optional[str] = None
    theme: List[str] = Field(default_factory=list)
    research_area: Optional[str] = None
    jrc_directorate: Optional[str] = None
    publication_date: Optional[datetime] = None
    temporal_coverage: Optional[Dict[str, datetime]] = None
    spatial_coverage: Optional[str] = None
    data_format: List[str] = Field(default_factory=list)
    access_level: str = Field(..., description="Public, restricted, etc.")
    license: Optional[str] = None
    doi: Optional[str] = None
    related_publications: List[str] = Field(default_factory=list)
    download_url: Optional[HttpUrl] = None
    api_endpoint: Optional[HttpUrl] = None


class PVGISCalculation(BaseModel):
    """
    PVGIS solar radiation calculation result.
    Source: PVGIS API (JRC)

    CRITICAL: PVGIS has 30 calls/second rate limit!
    """
    latitude: float
    longitude: float
    calculation_type: str = Field(..., description="monthly, daily, hourly")
    pv_technology: Optional[str] = Field(None, description="PV panel technology")
    pv_capacity_kw: Optional[float] = None
    system_loss: Optional[float] = Field(None, description="System loss percentage")
    slope: Optional[float] = Field(None, description="Panel slope angle")
    azimuth: Optional[float] = Field(None, description="Panel azimuth angle")
    monthly_radiation: Optional[List[Dict[str, float]]] = Field(None, description="Monthly values")
    yearly_total: Optional[float] = Field(None, description="Annual total kWh/kWp")
    optimal_angle: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


class EMMNewsItem(ScrapedData):
    """
    News item from Europe Media Monitor.
    Source: EMM (JRC)
    """
    article_id: str
    title: str
    source: str = Field(..., description="News source/publication")
    url: HttpUrl
    publication_date: datetime
    language: str
    country: Optional[str] = None
    category: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted entities")
    topics: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = Field(None, description="Positive, negative, neutral")
    relevance_score: Optional[float] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None


class MedISysHealthAlert(ScrapedData):
    """
    Health alert from MedISys system.
    Source: MedISys (JRC)
    """
    alert_id: str
    title: str
    alert_type: str = Field(..., description="Disease outbreak, bioterrorism, etc.")
    disease: Optional[str] = None
    affected_countries: List[str] = Field(default_factory=list)
    date_reported: datetime
    date_updated: Optional[datetime] = None
    severity: Optional[str] = Field(None, description="Low, medium, high, critical")
    source_documents: List[str] = Field(default_factory=list)
    affected_population: Optional[str] = None
    geographical_spread: Optional[str] = None
    public_health_actions: Optional[str] = None
    related_alerts: List[str] = Field(default_factory=list)
    who_notification: Optional[bool] = None
    ecdc_assessment: Optional[str] = None
