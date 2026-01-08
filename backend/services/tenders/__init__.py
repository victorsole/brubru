"""
Tenders Services Package

Services for the Tenderator feature - EU public procurement tender monitoring.

Components:
- ted_client: TED REST API client for real-time searches
- ted_sparql_client: TED SPARQL client for bulk/historical queries
- eforms_parser: eForms XML parser for notice data extraction
- tender_service: Main orchestrator for tender operations
- sme_scorer: SME suitability scoring
- sparql_analytics: SPARQL-based analytics queries
- tender_vector_db: ChromaDB vector database for semantic search

AI Services (Phase 3):
- hf_tender_classifier: Zero-shot sector classification
- hf_tender_summarizer: Tender summary generation
- hf_tender_search: Semantic search service
- hf_sme_analyzer: SME suitability analysis
- hf_tender_requirements: ESPD requirements extraction
- hf_award_explainer: Award criteria explanation
"""

from .ted_client import TEDClient, NoticeType, ProcedureType
from .ted_sparql_client import TEDSPARQLClient
from .eforms_parser import EFormsParser
from .tender_service import TenderService
from .sme_scorer import SMEScorer, SMEProfile, SMECategory

# Analytics and Vector DB
from .sparql_analytics import SPARQLAnalytics, get_dashboard_stats
from .tender_vector_db import TenderVectorDB, get_tender_vector_db

# HuggingFace AI Services
from .hf_tender_classifier import (
    TenderClassifier,
    get_tender_classifier,
    classify_tender_sector,
    get_sector_from_cpv
)
from .hf_tender_summarizer import (
    TenderSummarizer,
    get_tender_summarizer,
    summarize_tender
)
from .hf_tender_search import (
    TenderSemanticSearch,
    get_tender_search_service,
    semantic_tender_search,
    find_similar,
    search_sme_opportunities
)
from .hf_sme_analyzer import (
    SMEAnalyzer,
    get_sme_analyzer,
    analyze_sme_suitability
)
from .hf_tender_requirements import (
    TenderRequirementsExtractor,
    get_requirements_extractor,
    extract_tender_requirements,
    get_espd_categories
)
from .hf_award_explainer import (
    AwardCriteriaExplainer,
    get_award_explainer,
    explain_award_criteria,
    get_strategy_for_weights
)

# Matching & Notifications
from .matcher import (
    TenderMatcher,
    MatchResult,
    MatchWeight,
    run_tender_matching
)
from .tender_notifications import (
    TenderNotificationService,
    send_tender_match_notifications,
    send_tender_weekly_digests,
    send_tender_deadline_reminders
)

__all__ = [
    # Core Services
    "TEDClient",
    "TEDSPARQLClient",
    "EFormsParser",
    "TenderService",
    "NoticeType",
    "ProcedureType",

    # SME Scoring
    "SMEScorer",
    "SMEProfile",
    "SMECategory",

    # Analytics
    "SPARQLAnalytics",
    "get_dashboard_stats",

    # Vector DB
    "TenderVectorDB",
    "get_tender_vector_db",

    # HF Classifier
    "TenderClassifier",
    "get_tender_classifier",
    "classify_tender_sector",
    "get_sector_from_cpv",

    # HF Summarizer
    "TenderSummarizer",
    "get_tender_summarizer",
    "summarize_tender",

    # HF Search
    "TenderSemanticSearch",
    "get_tender_search_service",
    "semantic_tender_search",
    "find_similar",
    "search_sme_opportunities",

    # HF SME Analyzer
    "SMEAnalyzer",
    "get_sme_analyzer",
    "analyze_sme_suitability",

    # HF Requirements Extractor
    "TenderRequirementsExtractor",
    "get_requirements_extractor",
    "extract_tender_requirements",
    "get_espd_categories",

    # HF Award Explainer
    "AwardCriteriaExplainer",
    "get_award_explainer",
    "explain_award_criteria",
    "get_strategy_for_weights",

    # Matching
    "TenderMatcher",
    "MatchResult",
    "MatchWeight",
    "run_tender_matching",

    # Notifications
    "TenderNotificationService",
    "send_tender_match_notifications",
    "send_tender_weekly_digests",
    "send_tender_deadline_reminders",
]
