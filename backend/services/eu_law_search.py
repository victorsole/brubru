"""
EU Law Search Service

Full-text search service for EU laws using PostgreSQL.
Provides fast, ranked search across 28K+ EU legal documents.

Usage:
    from backend.services.eu_law_search import EULawSearchService

    search = EULawSearchService(db)

    # Simple search
    results = search.search("artificial intelligence", limit=20)

    # Filtered search
    results = search.search(
        query="data protection",
        policy_area="Digital Policy and Digital Economy",
        doc_type="Regulation",
        year_from=2020
    )
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import and_, or_, func, desc, text
from sqlalchemy.orm import Session

from backend.models.eu_law import EULaw

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Individual search result."""
    celex: str
    title: str
    doc_type: str
    date: Optional[date]
    policy_area: str
    oj_reference: str
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "celex": self.celex,
            "title": self.title,
            "doc_type": self.doc_type,
            "date": self.date.isoformat() if self.date else None,
            "policy_area": self.policy_area,
            "oj_reference": self.oj_reference,
            "relevance_score": self.relevance_score,
        }


@dataclass
class SearchResponse:
    """Search response with results and metadata."""
    results: list[SearchResult]
    total_count: int
    query: str
    filters_applied: dict

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "query": self.query,
            "filters_applied": self.filters_applied,
        }


class EULawSearchService:
    """
    Search service for EU laws.

    Uses PostgreSQL ILIKE for simple pattern matching.
    Supports filtering by policy area, document type, and date range.
    """

    # Valid document types for filtering
    DOC_TYPES = [
        "Regulation",
        "Directive",
        "Decision",
        "Recommendation",
        "Opinion",
    ]

    # Policy areas from the database
    POLICY_AREAS = [
        "Digital Policy and Digital Economy",
        "Environment and Climate Action",
        "Economic and Financial Affairs",
        "Agriculture",
        "Health and Food Safety",
        "Transport",
        "Migration and Home Affairs",
        "Competition and State Aid",
        "Employment and Social Affairs",
        "Energy",
        "Trade",
    ]

    def __init__(self, db: Session):
        """
        Initialize search service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def search(
        self,
        query: str,
        policy_area: Optional[str] = None,
        doc_type: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        is_primary_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """
        Search EU laws.

        Args:
            query: Search query (searches title)
            policy_area: Filter by policy area
            doc_type: Filter by document type (Regulation, Directive, etc.)
            year_from: Filter by year (from)
            year_to: Filter by year (to)
            is_primary_only: Only return primary legislation
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            SearchResponse with results and metadata
        """
        filters_applied = {}

        # Build query
        db_query = self.db.query(EULaw)

        # Text search (title)
        if query:
            # Split query into words and search each
            words = query.strip().split()
            if len(words) == 1:
                db_query = db_query.filter(EULaw.title.ilike(f"%{query}%"))
            else:
                # All words must match
                conditions = [EULaw.title.ilike(f"%{word}%") for word in words]
                db_query = db_query.filter(and_(*conditions))
            filters_applied["query"] = query

        # Policy area filter
        if policy_area:
            db_query = db_query.filter(EULaw.policy_area == policy_area)
            filters_applied["policy_area"] = policy_area

        # Document type filter
        if doc_type:
            db_query = db_query.filter(EULaw.doc_type.ilike(f"%{doc_type}%"))
            filters_applied["doc_type"] = doc_type

        # Year range filter
        if year_from:
            db_query = db_query.filter(
                func.extract('year', EULaw.date) >= year_from
            )
            filters_applied["year_from"] = year_from

        if year_to:
            db_query = db_query.filter(
                func.extract('year', EULaw.date) <= year_to
            )
            filters_applied["year_to"] = year_to

        # Primary legislation only
        if is_primary_only:
            db_query = db_query.filter(EULaw.is_primary_legislation == True)
            filters_applied["is_primary_only"] = True

        # Get total count before limit/offset
        total_count = db_query.count()

        # Order by date (newest first) and apply pagination
        db_query = db_query.order_by(desc(EULaw.date))
        results = db_query.offset(offset).limit(limit).all()

        # Convert to SearchResult objects
        search_results = [
            SearchResult(
                celex=law.celex or "",
                title=law.title or "",
                doc_type=law.doc_type or "",
                date=law.date,
                policy_area=law.policy_area or "",
                oj_reference=law.oj_reference or "",
                relevance_score=1.0,  # Simple relevance for now
            )
            for law in results
        ]

        return SearchResponse(
            results=search_results,
            total_count=total_count,
            query=query,
            filters_applied=filters_applied,
        )

    def get_by_celex(self, celex: str) -> Optional[SearchResult]:
        """
        Get a single law by CELEX number.

        Args:
            celex: CELEX number (e.g., "32024R1689")

        Returns:
            SearchResult or None if not found
        """
        law = self.db.query(EULaw).filter(EULaw.celex == celex).first()
        if not law:
            return None

        return SearchResult(
            celex=law.celex or "",
            title=law.title or "",
            doc_type=law.doc_type or "",
            date=law.date,
            policy_area=law.policy_area or "",
            oj_reference=law.oj_reference or "",
        )

    def get_related_laws(
        self,
        celex: str,
        limit: int = 10
    ) -> list[SearchResult]:
        """
        Get laws related to a given law (same policy area, similar date).

        Args:
            celex: CELEX number of the reference law
            limit: Maximum results

        Returns:
            List of related laws
        """
        # Get the reference law
        reference = self.db.query(EULaw).filter(EULaw.celex == celex).first()
        if not reference:
            return []

        # Find related by policy area
        query = self.db.query(EULaw).filter(
            and_(
                EULaw.celex != celex,
                EULaw.policy_area == reference.policy_area
            )
        )

        # Order by date proximity (date difference returns integer days in PostgreSQL)
        if reference.date:
            query = query.order_by(
                func.abs(EULaw.date - reference.date)
            )
        else:
            query = query.order_by(desc(EULaw.date))

        results = query.limit(limit).all()

        return [
            SearchResult(
                celex=law.celex or "",
                title=law.title or "",
                doc_type=law.doc_type or "",
                date=law.date,
                policy_area=law.policy_area or "",
                oj_reference=law.oj_reference or "",
            )
            for law in results
        ]

    def get_policy_area_stats(self) -> dict:
        """
        Get statistics by policy area.

        Returns:
            Dict with policy area counts
        """
        results = self.db.query(
            EULaw.policy_area,
            func.count(EULaw.id)
        ).group_by(EULaw.policy_area).all()

        return {
            area or "Unknown": count
            for area, count in results
        }

    def get_doc_type_stats(self) -> dict:
        """
        Get statistics by document type.

        Returns:
            Dict with doc type counts
        """
        stats = {}
        for doc_type in self.DOC_TYPES:
            count = self.db.query(func.count(EULaw.id)).filter(
                EULaw.doc_type.ilike(f"%{doc_type}%")
            ).scalar()
            stats[doc_type] = count

        return stats

    def get_year_stats(self, year_from: int = 2000) -> dict:
        """
        Get statistics by year.

        Args:
            year_from: Starting year

        Returns:
            Dict with year counts
        """
        results = self.db.query(
            func.extract('year', EULaw.date).label('year'),
            func.count(EULaw.id)
        ).filter(
            func.extract('year', EULaw.date) >= year_from
        ).group_by('year').order_by('year').all()

        return {
            int(year) if year else 0: count
            for year, count in results
        }


# Convenience function
def search_eu_laws(
    db: Session,
    query: str,
    **kwargs
) -> SearchResponse:
    """
    Quick search function.

    Args:
        db: Database session
        query: Search query
        **kwargs: Additional filters

    Returns:
        SearchResponse
    """
    service = EULawSearchService(db)
    return service.search(query, **kwargs)
