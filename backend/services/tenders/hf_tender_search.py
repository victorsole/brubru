"""
Hugging Face Tender Semantic Search

Semantic search over EU tenders using BGE-M3 embeddings.
Supports all 24 EU languages for multilingual queries.

Usage:
    from services.tenders.hf_tender_search import semantic_tender_search

    results = await semantic_tender_search(
        "services de cybersécurité pour institutions européennes",
        country="BE",
        max_value=5000000
    )
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .tender_vector_db import get_tender_vector_db, TenderVectorDB

logger = logging.getLogger(__name__)


class TenderSemanticSearch:
    """
    Semantic search service for EU tenders.

    Uses BGE-M3 embeddings for multilingual search across
    all 24 EU languages. Combines semantic similarity with
    metadata filtering for precise results.
    """

    def __init__(self):
        self._vector_db: Optional[TenderVectorDB] = None

    @property
    def vector_db(self) -> TenderVectorDB:
        """Lazy load vector database."""
        if self._vector_db is None:
            self._vector_db = get_tender_vector_db()
        return self._vector_db

    async def search(
        self,
        query: str,
        n_results: int = 20,
        country: Optional[str] = None,
        cpv_prefix: Optional[str] = None,
        sector: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        status: str = "open",
        min_sme_score: Optional[float] = None,
        days_until_deadline: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over tenders.

        Supports multilingual queries - search in any EU language
        and find results regardless of the tender's original language.

        Args:
            query: Search query (any EU language)
            n_results: Maximum results
            country: Filter by country code (e.g., "BE")
            cpv_prefix: Filter by CPV code prefix (e.g., "72")
            sector: Filter by sector name
            min_value: Minimum estimated value
            max_value: Maximum estimated value (SME filter)
            status: Tender status filter
            min_sme_score: Minimum SME suitability score
            days_until_deadline: Minimum days until deadline

        Returns:
            List of matching tenders with similarity scores
        """
        logger.info(f"Semantic search: '{query[:50]}...' with filters")

        # Perform vector search with metadata filters
        results = self.vector_db.search(
            query=query,
            n_results=n_results * 2,  # Over-fetch for post-filtering
            country=country,
            cpv_prefix=cpv_prefix,
            min_value=min_value,
            max_value=max_value,
            status=status,
            min_sme_score=min_sme_score
        )

        # Post-process results
        processed = []
        for result in results:
            tender_data = self._process_result(result)

            # Apply additional filters
            if days_until_deadline:
                deadline = tender_data.get("deadline")
                if deadline:
                    try:
                        deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                        days_left = (deadline_dt - datetime.utcnow()).days
                        if days_left < days_until_deadline:
                            continue
                    except (ValueError, TypeError):
                        pass

            if sector:
                # Check if sector matches (if we have sector info)
                tender_sector = tender_data.get("sector", "")
                if sector.lower() not in tender_sector.lower():
                    continue

            processed.append(tender_data)

            if len(processed) >= n_results:
                break

        logger.info(f"Found {len(processed)} matching tenders")
        return processed

    async def find_similar_tenders(
        self,
        tender_id: str,
        n_results: int = 10,
        same_country: bool = False,
        same_sector: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find tenders similar to a given tender.

        Useful for:
        - Finding comparable opportunities
        - Understanding the competitive landscape
        - Identifying patterns in buyer behavior

        Args:
            tender_id: Publication number of reference tender
            n_results: Number of similar tenders
            same_country: Restrict to same country
            same_sector: Restrict to same sector/CPV

        Returns:
            List of similar tenders with similarity scores
        """
        results = self.vector_db.find_similar(tender_id, n_results * 2)

        processed = []
        reference_country = None
        reference_cpv = None

        # Get reference tender info for filtering
        if same_country or same_sector:
            ref = self.vector_db.collection.get(
                ids=[tender_id],
                include=["metadatas"]
            )
            if ref and ref["metadatas"]:
                reference_country = ref["metadatas"][0].get("country")
                reference_cpv = ref["metadatas"][0].get("cpv_main", "")[:2]

        for result in results:
            tender_data = self._process_result(result)

            # Apply filters
            if same_country and reference_country:
                if tender_data.get("country") != reference_country:
                    continue

            if same_sector and reference_cpv:
                tender_cpv = tender_data.get("cpv_main", "")[:2]
                if tender_cpv != reference_cpv:
                    continue

            processed.append(tender_data)

            if len(processed) >= n_results:
                break

        return processed

    async def search_by_buyer(
        self,
        buyer_name: str,
        n_results: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search tenders by contracting authority name.

        Args:
            buyer_name: Contracting authority name (partial match)
            n_results: Maximum results
            status: Optional status filter

        Returns:
            List of tenders from the buyer
        """
        # Use semantic search with buyer name as query
        # This works because tender embeddings include buyer info
        query = f"tender by {buyer_name}"

        results = await self.search(
            query=query,
            n_results=n_results,
            status=status
        )

        # Re-rank by buyer name match
        for result in results:
            buyer = result.get("buyer", "").lower()
            if buyer_name.lower() in buyer:
                result["score"] = min(1.0, result["score"] * 1.5)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    async def search_sme_opportunities(
        self,
        query: str,
        n_results: int = 20,
        countries: Optional[List[str]] = None,
        max_value: float = 5_000_000,
        min_deadline_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search for SME-friendly tender opportunities.

        Pre-filtered for SME accessibility:
        - Lower contract values
        - Sufficient time to deadline
        - Higher SME suitability scores

        Args:
            query: Search query
            n_results: Maximum results
            countries: List of country codes to include
            max_value: Maximum tender value
            min_deadline_days: Minimum days until deadline

        Returns:
            List of SME-friendly tenders
        """
        results = []

        if countries:
            # Search each country separately
            per_country = max(5, n_results // len(countries))
            for country in countries:
                country_results = await self.search(
                    query=query,
                    n_results=per_country,
                    country=country,
                    max_value=max_value,
                    status="open",
                    min_sme_score=50,
                    days_until_deadline=min_deadline_days
                )
                results.extend(country_results)
        else:
            results = await self.search(
                query=query,
                n_results=n_results,
                max_value=max_value,
                status="open",
                min_sme_score=50,
                days_until_deadline=min_deadline_days
            )

        # Sort by SME score
        results.sort(key=lambda x: x.get("sme_score", 0), reverse=True)
        return results[:n_results]

    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process a vector search result into tender data."""
        metadata = result.get("metadata", {})

        return {
            "id": result.get("id"),
            "title": metadata.get("title") or result.get("title", ""),
            "score": result.get("score", 0),
            "country": metadata.get("country"),
            "cpv_main": metadata.get("cpv_main"),
            "status": metadata.get("status"),
            "procedure_type": metadata.get("procedure_type"),
            "estimated_value": metadata.get("estimated_value"),
            "sme_score": metadata.get("sme_score"),
            "deadline": metadata.get("deadline"),
            "publication_date": metadata.get("publication_date"),
            "indexed_at": metadata.get("indexed_at"),
            "buyer": metadata.get("buyer", ""),
            "sector": metadata.get("sector", "")
        }


# Global instance
_search_service: Optional[TenderSemanticSearch] = None


def get_tender_search_service() -> TenderSemanticSearch:
    """Get or create the global TenderSemanticSearch instance."""
    global _search_service
    if _search_service is None:
        _search_service = TenderSemanticSearch()
    return _search_service


# Convenience functions
async def semantic_tender_search(
    query: str,
    n_results: int = 20,
    country: Optional[str] = None,
    cpv_prefix: Optional[str] = None,
    max_value: Optional[float] = None,
    status: str = "open"
) -> List[Dict[str, Any]]:
    """
    Search tenders using semantic similarity.

    Works across all 24 EU languages!

    Example:
        >>> results = await semantic_tender_search(
        ...     "services de cybersécurité pour institutions européennes"
        ... )
        # Returns relevant tenders even if titles are in other languages

    Args:
        query: Search query in any EU language
        n_results: Maximum results
        country: Country code filter
        cpv_prefix: CPV prefix filter
        max_value: Maximum value filter
        status: Status filter

    Returns:
        List of matching tenders with scores
    """
    service = get_tender_search_service()
    return await service.search(
        query=query,
        n_results=n_results,
        country=country,
        cpv_prefix=cpv_prefix,
        max_value=max_value,
        status=status
    )


async def find_similar(
    tender_id: str,
    n_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Find tenders similar to a given tender.

    Args:
        tender_id: Publication number
        n_results: Number of results

    Returns:
        List of similar tenders
    """
    service = get_tender_search_service()
    return await service.find_similar_tenders(tender_id, n_results)


async def search_sme_opportunities(
    query: str,
    countries: Optional[List[str]] = None,
    max_value: float = 5_000_000
) -> List[Dict[str, Any]]:
    """
    Search for SME-friendly opportunities.

    Args:
        query: Search query
        countries: Country filter list
        max_value: Maximum tender value

    Returns:
        List of SME-friendly tenders
    """
    service = get_tender_search_service()
    return await service.search_sme_opportunities(
        query=query,
        countries=countries,
        max_value=max_value
    )
