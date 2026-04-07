"""
EU Law Search Service

Full-text search service for EU laws using PostgreSQL.
Provides fast, ranked search across 28K+ EU legal documents.

Usage:
    from services.eu_law_search import EULawSearchService

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

from models.eu_law import EULaw

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

    Uses PostgreSQL full-text search (TSVECTOR with GIN index) for fast,
    ranked search across 28K+ documents. Falls back to ILIKE for
    CELEX/short queries that TSVECTOR handles poorly.
    """

    # Valid document types for filtering (normalized)
    DOC_TYPES = [
        "Regulation",
        "Directive",
        "Decision",
        "Recommendation",
        "Opinion",
    ]

    def __init__(self, db: Session):
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
        Search EU laws using full-text search (TSVECTOR) with ILIKE fallback.

        TSVECTOR is used for multi-word natural language queries (near-instant via GIN index).
        ILIKE is used for CELEX lookups and single short terms where TSVECTOR may miss.
        """
        filters_applied = {}

        # Build base query
        db_query = self.db.query(EULaw)
        use_relevance_ordering = False

        # Text search
        if query:
            query_stripped = query.strip()
            filters_applied["query"] = query_stripped

            # CELEX direct lookup (starts with 3 + 4 digits)
            if len(query_stripped) >= 5 and query_stripped[0] == '3' and query_stripped[1:5].isdigit():
                db_query = db_query.filter(EULaw.celex == query_stripped)
            else:
                # Try TSVECTOR full-text search for multi-word queries
                ts_query = func.plainto_tsquery('english', query_stripped)
                ts_filter = EULaw.search_vector.op('@@')(ts_query)

                # Check if TSVECTOR would return results (for short/unusual terms it may not)
                ts_count = self.db.query(func.count(EULaw.id)).filter(ts_filter).scalar()

                if ts_count and ts_count > 0:
                    db_query = db_query.filter(ts_filter)
                    use_relevance_ordering = True
                else:
                    # Fallback to ILIKE for terms TSVECTOR misses
                    words = query_stripped.split()
                    if len(words) == 1:
                        db_query = db_query.filter(EULaw.title.ilike(f"%{query_stripped}%"))
                    else:
                        conditions = [EULaw.title.ilike(f"%{word}%") for word in words]
                        db_query = db_query.filter(and_(*conditions))

        # Policy area filter
        if policy_area:
            db_query = db_query.filter(EULaw.policy_area == policy_area)
            filters_applied["policy_area"] = policy_area

        # Document type filter (use normalized column if available, fall back to raw)
        if doc_type:
            db_query = db_query.filter(
                or_(
                    EULaw.doc_type_normalized == doc_type,
                    EULaw.doc_type.ilike(f"%{doc_type}%")
                )
            )
            filters_applied["doc_type"] = doc_type

        # Year range filter (use celex_year if available, fall back to date extract)
        if year_from:
            db_query = db_query.filter(
                or_(
                    EULaw.celex_year >= year_from,
                    func.extract('year', EULaw.date) >= year_from
                )
            )
            filters_applied["year_from"] = year_from

        if year_to:
            db_query = db_query.filter(
                or_(
                    EULaw.celex_year <= year_to,
                    func.extract('year', EULaw.date) <= year_to
                )
            )
            filters_applied["year_to"] = year_to

        # Primary legislation only
        if is_primary_only:
            db_query = db_query.filter(EULaw.is_primary_legislation == True)
            filters_applied["is_primary_only"] = True

        # Get total count before limit/offset
        total_count = db_query.count()

        # Order by relevance (TSVECTOR rank) or date
        if use_relevance_ordering and query:
            ts_query = func.plainto_tsquery('english', query.strip())
            db_query = db_query.order_by(
                func.ts_rank(EULaw.search_vector, ts_query).desc(),
                desc(EULaw.date)
            )
        else:
            db_query = db_query.order_by(desc(EULaw.date))

        results = db_query.offset(offset).limit(limit).all()

        # Convert to SearchResult objects
        search_results = [
            SearchResult(
                celex=law.celex or "",
                title=law.title or "",
                doc_type=law.doc_type_normalized or law.doc_type or "",
                date=law.date,
                policy_area=law.policy_area or "",
                oj_reference=law.oj_reference or "",
                relevance_score=1.0 if use_relevance_ordering else 0.0,
            )
            for law in results
        ]

        return SearchResponse(
            results=search_results,
            total_count=total_count,
            query=query,
            filters_applied=filters_applied,
        )

    def search_tsvector(
        self,
        query: str,
        policy_area: Optional[str] = None,
        primary_only: bool = True,
        doc_types: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Fast TSVECTOR-only search for internal use (chatbot context, document generator).

        Returns lightweight dicts instead of SearchResult objects.
        """
        ts_query = func.plainto_tsquery('english', query.strip())

        db_query = self.db.query(
            EULaw.celex,
            EULaw.title,
            EULaw.doc_type_normalized,
            EULaw.date,
            EULaw.policy_area,
            EULaw.citations,
            func.ts_rank(EULaw.search_vector, ts_query).label('rank')
        ).filter(
            EULaw.search_vector.op('@@')(ts_query)
        )

        if policy_area:
            db_query = db_query.filter(EULaw.policy_area == policy_area)

        if primary_only:
            db_query = db_query.filter(EULaw.is_primary_legislation == True)

        if doc_types:
            db_query = db_query.filter(EULaw.doc_type_normalized.in_(doc_types))

        db_query = db_query.order_by(desc('rank')).limit(limit)

        return [
            {
                'celex': row.celex,
                'title': row.title,
                'doc_type': row.doc_type_normalized,
                'date': row.date.isoformat() if row.date else None,
                'policy_area': row.policy_area,
                'citations': row.citations,
                'relevance': float(row.rank),
            }
            for row in db_query.all()
        ]

    def get_legal_framework(
        self,
        policy_area: str,
        keywords: str = "",
        limit: int = 5,
    ) -> list[dict]:
        """
        Get the most relevant laws for a policy area/topic.

        Used by Document Generator to inject a "Legal Framework" section
        into position papers and MEP briefings.
        """
        if keywords:
            results = self.search_tsvector(
                query=keywords,
                policy_area=policy_area,
                primary_only=True,
                doc_types=["Regulation", "Directive", "Decision"],
                limit=limit,
            )
            if results:
                return results

        # Fallback: newest primary legislation in this policy area
        laws = self.db.query(EULaw).filter(
            and_(
                EULaw.policy_area == policy_area,
                EULaw.is_primary_legislation == True,
                EULaw.doc_type_normalized.in_(["Regulation", "Directive", "Decision"]),
            )
        ).order_by(desc(EULaw.date)).limit(limit).all()

        return [
            {
                'celex': law.celex,
                'title': law.title,
                'doc_type': law.doc_type_normalized or law.doc_type,
                'date': law.date.isoformat() if law.date else None,
                'policy_area': law.policy_area,
            }
            for law in laws
        ]

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
        Get statistics by normalized document type.

        Returns:
            Dict with doc type counts
        """
        results = self.db.query(
            EULaw.doc_type_normalized,
            func.count(EULaw.id)
        ).group_by(EULaw.doc_type_normalized).all()

        return {
            doc_type or "Unknown": count
            for doc_type, count in results
        }

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
