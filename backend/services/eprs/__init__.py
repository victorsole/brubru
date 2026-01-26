"""
EPRS (European Parliament Research Service) Unified Service Module

This module coordinates all EPRS-related functionality:
- ThinkTankScraper: RSS feeds and PDF extraction
- EPRSArchiveClient: Historical CELLAR/SPARQL queries
- EPRSIndexer: Vector database indexing
- EPRSMatcher: Finding explainer briefings for legislation
- LegislationInProgressScraper: Curated procedure list from epthinktank.eu

Usage:
    from services.eprs import EPRSService, get_eprs_service

    # Get unified service
    service = get_eprs_service()

    # Find EPRS explainers for legislation
    explainers = await service.find_explainers_for_procedure("2021/0106(COD)")

    # Get curated "EU Legislation in Progress" procedures
    procedures = await service.get_legislation_in_progress()

    # Index new publications
    await service.index_recent_publications(days=7)
"""

from .eprs_service import EPRSService, get_eprs_service
from .legislation_in_progress_scraper import LegislationInProgressScraper

__all__ = [
    "EPRSService",
    "get_eprs_service",
    "LegislationInProgressScraper",
]
