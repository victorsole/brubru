"""
Tenders Services Package

Services for the Tenderator feature - EU public procurement tender monitoring.

Components:
- ted_client: TED REST API client for real-time searches
- ted_sparql_client: TED SPARQL client for bulk/historical queries
- eforms_parser: eForms XML parser for notice data extraction
- tender_service: Main orchestrator for tender operations
- sme_scorer: SME suitability scoring
- country_codes: the one place that decides what a country code is
- sparql_analytics: SPARQL-based analytics queries
- tender_vector_db: ChromaDB vector database for semantic search

AI Services (Phase 3). NOTE: as of 10 Aug 2026 no API endpoint calls any of
these. They are reachable and tested, but nothing in the request path reaches
them; hf_tender_search in particular is the embedding path that was once
proposed as the fix for match quality and is still unused. Left in place rather
than deleted, but do not assume a change here affects production behaviour:
- hf_tender_classifier: Zero-shot sector classification
- hf_tender_summarizer: Tender summary generation
- hf_tender_search: Semantic search service
- hf_sme_analyzer: SME suitability analysis
- hf_tender_requirements: ESPD requirements extraction
- hf_award_explainer: Award criteria explanation

--------------------------------------------------------------------------
Imports here are LAZY (PEP 562). They used to be eager, and importing any
submodule runs this file first -- so `from services.tenders.tender_service
import TenderService`, which api/tenderator.py does at boot, pulled in
tender_vector_db, which does `import chromadb` at module level, which pulls
sentence_transformers. Measured on this machine: ~0.95s for chromadb and ~8.7s
cumulative for sentence_transformers, paid on every process start including
every cron subprocess, for machinery no endpoint calls.

`from services.tenders import TenderMatcher` still works and still returns the
same object. It is resolved on first attribute access instead of at import.
"""

from typing import TYPE_CHECKING

# attribute name -> submodule it lives in
_EXPORTS = {
    # Core
    "TEDClient": "ted_client",
    "NoticeType": "ted_client",
    "ProcedureType": "ted_client",
    "TEDSPARQLClient": "ted_sparql_client",
    "EFormsParser": "eforms_parser",
    "TenderService": "tender_service",
    # Country codes
    "normalise_country": "country_codes",
    "is_valid_country": "country_codes",
    # SME scoring
    "SMEScorer": "sme_scorer",
    "SMEProfile": "sme_scorer",
    "SMECategory": "sme_scorer",
    # Analytics
    "SPARQLAnalytics": "sparql_analytics",
    "get_dashboard_stats": "sparql_analytics",
    # Vector DB (imports chromadb -- do not touch unless you need it)
    "TenderVectorDB": "tender_vector_db",
    "get_tender_vector_db": "tender_vector_db",
    # HF classifier
    "TenderClassifier": "hf_tender_classifier",
    "get_tender_classifier": "hf_tender_classifier",
    "classify_tender_sector": "hf_tender_classifier",
    "get_sector_from_cpv": "hf_tender_classifier",
    # HF summarizer
    "TenderSummarizer": "hf_tender_summarizer",
    "get_tender_summarizer": "hf_tender_summarizer",
    "summarize_tender": "hf_tender_summarizer",
    # HF search
    "TenderSemanticSearch": "hf_tender_search",
    "get_tender_search_service": "hf_tender_search",
    "semantic_tender_search": "hf_tender_search",
    "find_similar": "hf_tender_search",
    "search_sme_opportunities": "hf_tender_search",
    # HF SME analyzer
    "SMEAnalyzer": "hf_sme_analyzer",
    "get_sme_analyzer": "hf_sme_analyzer",
    "analyze_sme_suitability": "hf_sme_analyzer",
    # HF requirements extractor
    "TenderRequirementsExtractor": "hf_tender_requirements",
    "get_requirements_extractor": "hf_tender_requirements",
    "extract_tender_requirements": "hf_tender_requirements",
    "get_espd_categories": "hf_tender_requirements",
    # HF award explainer
    "AwardCriteriaExplainer": "hf_award_explainer",
    "get_award_explainer": "hf_award_explainer",
    "explain_award_criteria": "hf_award_explainer",
    "get_strategy_for_weights": "hf_award_explainer",
    # Matching
    "TenderMatcher": "matcher",
    "MatchResult": "matcher",
    "MatchWeight": "matcher",
    "run_tender_matching": "matcher",
    # Notifications
    "TenderNotificationService": "tender_notifications",
    "send_tender_match_notifications": "tender_notifications",
    "send_tender_weekly_digests": "tender_notifications",
    "send_tender_deadline_reminders": "tender_notifications",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve an export on first access (PEP 562)."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value          # cache, so the next access is a plain lookup
    return value


def __dir__():
    return sorted(__all__)


# Type checkers cannot follow __getattr__, so give them the real thing. This
# block never runs at runtime.
if TYPE_CHECKING:  # pragma: no cover
    from .ted_client import TEDClient, NoticeType, ProcedureType
    from .ted_sparql_client import TEDSPARQLClient
    from .eforms_parser import EFormsParser
    from .tender_service import TenderService
    from .country_codes import normalise_country, is_valid_country
    from .sme_scorer import SMEScorer, SMEProfile, SMECategory
    from .matcher import TenderMatcher, MatchResult, MatchWeight, run_tender_matching
