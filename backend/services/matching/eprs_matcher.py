"""
EPRS Matcher Service

Phase 3: Intelligent Matching
Automatically finds EPRS "explainer" briefings for EU legislation.

This is the KEY service that makes EPRS briefings act as "jargon translators":
- When EUR-Lex document is fetched → find matching EPRS briefing
- When OEIL procedure is accessed → find "At a Glance" summary
- When CELEX number is mentioned → find explanatory research

Result: Every complex EU law comes with a built-in plain-language explanation.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import re

from services.indexing.eprs_indexer import EPRSIndexer, get_eprs_indexer
from schemas.scrapers.scraper_schemas import EPRSPublication

logger = logging.getLogger(__name__)


class EPRSMatcher:
    """
    Intelligent matcher for finding EPRS briefings that explain EU legislation.

    Matching strategies:
    1. **CELEX Exact Match**: Briefing explicitly mentions CELEX number
    2. **Procedure Match**: Briefing covers a specific legislative procedure
    3. **Semantic Match**: Briefing is semantically similar to legislation
    4. **Title Match**: Briefing title matches legislation title
    5. **Hybrid**: Combination of above strategies

    Usage:
        matcher = EPRSMatcher()

        # Find briefings for specific legislation
        briefings = await matcher.find_explainers_for_celex("32024R1689")
        # Returns: ["AI Act - At a Glance", "AI Act: In-depth analysis"]

        # Find briefings for procedure
        briefings = await matcher.find_explainers_for_procedure("2021/0106(COD)")

        # Automatic matching when fetching legislation
        result = await matcher.auto_match_legislation(
            celex="32024R1689",
            title="Artificial Intelligence Act",
            text="Regulation (EU) 2024/1689..."
        )
    """

    def __init__(
        self,
        eprs_indexer: Optional[EPRSIndexer] = None,
        cache_ttl_seconds: int = 3600
    ):
        """
        Initialize EPRS matcher.

        Args:
            eprs_indexer: EPRS indexer instance (creates if None)
            cache_ttl_seconds: How long to cache match results (default 1 hour)
        """
        self.eprs_indexer = eprs_indexer or get_eprs_indexer()
        self.cache_ttl = cache_ttl_seconds

        # Cache for match results: {celex: (results, timestamp)}
        self._celex_cache: Dict[str, tuple] = {}
        self._procedure_cache: Dict[str, tuple] = {}

        logger.info("Initialized EPRSMatcher with intelligent matching")

    async def find_explainers_for_celex(
        self,
        celex: str,
        max_results: int = 3,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find EPRS briefings that explain a specific EUR-Lex document.

        Phase 3: Core method for CELEX-to-EPRS matching.

        Args:
            celex: CELEX number (e.g., "32024R1689")
            max_results: Maximum briefings to return
            use_cache: Use cached results if available

        Returns:
            List of matching EPRS briefings with metadata

        Example:
            briefings = await matcher.find_explainers_for_celex("32016R0679")
            # Returns briefings about GDPR
        """
        logger.info(f"Finding EPRS explainers for CELEX: {celex}")

        # Check cache
        if use_cache and celex in self._celex_cache:
            cached_results, timestamp = self._celex_cache[celex]
            age = (datetime.now() - timestamp).total_seconds()

            if age < self.cache_ttl:
                logger.debug(f"Using cached results for {celex} (age: {age:.0f}s)")
                return cached_results

        matches = []

        # Strategy 1: Exact CELEX match in metadata
        logger.debug(f"Strategy 1: Searching for exact CELEX match in metadata")
        exact_matches = await self._search_by_celex_metadata(celex, max_results)

        if exact_matches:
            matches.extend(exact_matches)
            logger.info(f"Found {len(exact_matches)} exact CELEX matches")

        # Strategy 2: Semantic search with CELEX in query
        if len(matches) < max_results:
            logger.debug(f"Strategy 2: Semantic search with CELEX {celex}")
            semantic_matches = await self._search_by_celex_semantic(
                celex,
                max_results - len(matches)
            )

            # Add semantic matches that aren't already in results
            existing_ids = {m.get('publication_id') for m in matches}
            for match in semantic_matches:
                if match.get('publication_id') not in existing_ids:
                    matches.append(match)

            logger.info(f"Added {len(semantic_matches)} semantic matches")

        # Deduplicate and rank
        matches = self._rank_and_deduplicate(matches, celex, max_results)

        # Cache results
        if use_cache:
            self._celex_cache[celex] = (matches, datetime.now())

        logger.info(f"Total: {len(matches)} EPRS explainers found for {celex}")
        return matches

    async def find_explainers_for_procedure(
        self,
        procedure_ref: str,
        max_results: int = 3,
        prefer_at_a_glance: bool = True,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find EPRS briefings for a legislative procedure.

        Args:
            procedure_ref: Procedure reference (e.g., "2021/0106(COD)")
            max_results: Maximum briefings to return
            prefer_at_a_glance: Prioritize "At a Glance" summaries
            use_cache: Use cached results if available

        Returns:
            List of matching EPRS briefings

        Example:
            briefings = await matcher.find_explainers_for_procedure("2021/0106(COD)")
            # Returns "AI Act - At a Glance" and related briefings
        """
        logger.info(f"Finding EPRS explainers for procedure: {procedure_ref}")

        # Check cache
        if use_cache and procedure_ref in self._procedure_cache:
            cached_results, timestamp = self._procedure_cache[procedure_ref]
            age = (datetime.now() - timestamp).total_seconds()

            if age < self.cache_ttl:
                logger.debug(f"Using cached results for {procedure_ref}")
                return cached_results

        matches = []

        # Strategy 1: Exact procedure match in metadata
        exact_matches = await self._search_by_procedure_metadata(
            procedure_ref,
            max_results
        )

        if exact_matches:
            matches.extend(exact_matches)
            logger.info(f"Found {len(exact_matches)} exact procedure matches")

        # Strategy 2: Semantic search
        if len(matches) < max_results:
            semantic_matches = await self._search_by_procedure_semantic(
                procedure_ref,
                max_results - len(matches)
            )

            existing_ids = {m.get('publication_id') for m in matches}
            for match in semantic_matches:
                if match.get('publication_id') not in existing_ids:
                    matches.append(match)

        # Prioritize "At a Glance" if requested
        if prefer_at_a_glance:
            matches = self._prioritize_at_a_glance(matches)

        # Rank and deduplicate
        matches = self._rank_and_deduplicate(matches, procedure_ref, max_results)

        # Cache results
        if use_cache:
            self._procedure_cache[procedure_ref] = (matches, datetime.now())

        logger.info(f"Total: {len(matches)} EPRS explainers found for {procedure_ref}")
        return matches

    async def auto_match_legislation(
        self,
        celex: Optional[str] = None,
        procedure_ref: Optional[str] = None,
        title: Optional[str] = None,
        text: Optional[str] = None,
        max_results: int = 2
    ) -> Dict[str, Any]:
        """
        Automatically find EPRS explainers for legislation.

        Phase 3: This is called when EUR-Lex document is fetched.
        It intelligently finds the best EPRS briefings to include.

        Args:
            celex: CELEX number
            procedure_ref: Procedure reference
            title: Document title
            text: Document text excerpt
            max_results: Maximum briefings to return

        Returns:
            Dict with:
                - explainers: List[Dict] - Matching EPRS briefings
                - match_strategy: str - How matches were found
                - confidence: float - Matching confidence (0-1)

        Example:
            # When fetching EUR-Lex document
            result = await matcher.auto_match_legislation(
                celex="32024R1689",
                title="Artificial Intelligence Act",
                text="Regulation (EU) 2024/1689..."
            )

            # result['explainers'] contains EPRS briefings
            # AI gets both legal text + plain-language explanation
        """
        logger.info("Auto-matching legislation to EPRS explainers")

        explainers = []
        strategies_used = []
        confidence = 0.0

        # Strategy 1: CELEX exact match (highest confidence)
        if celex:
            celex_matches = await self.find_explainers_for_celex(
                celex,
                max_results=max_results
            )

            if celex_matches:
                explainers.extend(celex_matches)
                strategies_used.append("celex_exact")
                confidence = max(confidence, 0.9)

                logger.info(f"Found {len(celex_matches)} via CELEX match")

        # Strategy 2: Procedure match (high confidence)
        if procedure_ref and len(explainers) < max_results:
            proc_matches = await self.find_explainers_for_procedure(
                procedure_ref,
                max_results=max_results - len(explainers),
                prefer_at_a_glance=True
            )

            if proc_matches:
                # Add non-duplicates
                existing_ids = {e.get('publication_id') for e in explainers}
                for match in proc_matches:
                    if match.get('publication_id') not in existing_ids:
                        explainers.append(match)

                strategies_used.append("procedure_exact")
                confidence = max(confidence, 0.85)

                logger.info(f"Found {len(proc_matches)} via procedure match")

        # Strategy 3: Title + text semantic search (medium confidence)
        if title and len(explainers) < max_results:
            query = title
            if text:
                query = f"{title} {text[:500]}"

            semantic_matches = await self.eprs_indexer.search(
                query=query,
                limit=max_results - len(explainers)
            )

            if semantic_matches:
                existing_ids = {e.get('publication_id') for e in explainers}

                for result in semantic_matches:
                    metadata = result.get('metadata', {})

                    if metadata.get('publication_id') not in existing_ids:
                        explainers.append({
                            'publication_id': metadata.get('publication_id'),
                            'title': metadata.get('title'),
                            'publication_type': metadata.get('publication_type'),
                            'text': result.get('text', '')[:500],
                            'url': metadata.get('html_url'),
                            'match_type': 'semantic',
                            'confidence': 1 - result.get('distance', 1)
                        })

                strategies_used.append("semantic")
                confidence = max(confidence, 0.7)

                logger.info(f"Found {len(semantic_matches)} via semantic search")

        # Determine overall confidence
        if not explainers:
            confidence = 0.0
        elif "celex_exact" in strategies_used:
            confidence = 0.9
        elif "procedure_exact" in strategies_used:
            confidence = 0.85
        else:
            confidence = 0.7

        result = {
            'explainers': explainers[:max_results],
            'match_strategy': '+'.join(strategies_used) if strategies_used else 'none',
            'confidence': confidence,
            'total_found': len(explainers)
        }

        logger.info(
            f"Auto-match complete: {len(result['explainers'])} explainers "
            f"(strategy: {result['match_strategy']}, confidence: {confidence:.0%})"
        )

        return result

    async def _search_by_celex_metadata(
        self,
        celex: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search for EPRS briefings with CELEX in metadata"""
        try:
            # Search with CELEX filter
            results = await self.eprs_indexer.search(
                query=celex,
                limit=limit,
                filters={'related_celex_numbers': celex}
            )

            return self._format_search_results(results, match_type='celex_metadata')

        except Exception as e:
            logger.error(f"CELEX metadata search failed: {str(e)}")
            return []

    async def _search_by_celex_semantic(
        self,
        celex: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Semantic search using CELEX number in query"""
        try:
            # Convert CELEX to more readable format for search
            # 32024R1689 → "Regulation 2024/1689"
            readable = self._celex_to_readable(celex)

            query = f"CELEX {celex} {readable}"

            results = await self.eprs_indexer.search(
                query=query,
                limit=limit
            )

            return self._format_search_results(results, match_type='celex_semantic')

        except Exception as e:
            logger.error(f"CELEX semantic search failed: {str(e)}")
            return []

    async def _search_by_procedure_metadata(
        self,
        procedure_ref: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search for EPRS briefings with procedure in metadata"""
        try:
            results = await self.eprs_indexer.search(
                query=procedure_ref,
                limit=limit,
                filters={'related_procedures': procedure_ref}
            )

            return self._format_search_results(results, match_type='procedure_metadata')

        except Exception as e:
            logger.error(f"Procedure metadata search failed: {str(e)}")
            return []

    async def _search_by_procedure_semantic(
        self,
        procedure_ref: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Semantic search using procedure reference"""
        try:
            query = f"procedure {procedure_ref} legislative"

            results = await self.eprs_indexer.search(
                query=query,
                limit=limit
            )

            return self._format_search_results(results, match_type='procedure_semantic')

        except Exception as e:
            logger.error(f"Procedure semantic search failed: {str(e)}")
            return []

    def _format_search_results(
        self,
        results: List[Dict[str, Any]],
        match_type: str
    ) -> List[Dict[str, Any]]:
        """Format search results into standardized structure"""
        formatted = []

        for result in results:
            metadata = result.get('metadata', {})

            formatted.append({
                'publication_id': metadata.get('publication_id'),
                'title': metadata.get('title'),
                'publication_type': metadata.get('publication_type'),
                'text': result.get('text', '')[:500],
                'url': metadata.get('html_url'),
                'pdf_url': metadata.get('pdf_url'),
                'related_celex': metadata.get('related_celex_numbers', '').split(',') if metadata.get('related_celex_numbers') else [],
                'related_procedures': metadata.get('related_procedures', '').split(',') if metadata.get('related_procedures') else [],
                'match_type': match_type,
                'confidence': 1 - result.get('distance', 1) if 'distance' in result else 0.5
            })

        return formatted

    def _rank_and_deduplicate(
        self,
        matches: List[Dict[str, Any]],
        reference: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Rank matches by quality and remove duplicates"""
        # Deduplicate by publication_id
        seen = set()
        unique = []

        for match in matches:
            pub_id = match.get('publication_id')
            if pub_id and pub_id not in seen:
                seen.add(pub_id)
                unique.append(match)

        # Rank by match type and confidence
        rank_order = {
            'celex_metadata': 4,
            'procedure_metadata': 3,
            'celex_semantic': 2,
            'procedure_semantic': 1,
            'semantic': 0
        }

        unique.sort(
            key=lambda x: (
                rank_order.get(x.get('match_type', 'semantic'), 0),
                x.get('confidence', 0)
            ),
            reverse=True
        )

        return unique[:max_results]

    def _prioritize_at_a_glance(
        self,
        matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Move 'At a Glance' briefings to front of results"""
        at_a_glance = []
        other = []

        for match in matches:
            pub_type = match.get('publication_type', '')
            if 'at_a_glance' in pub_type.lower():
                at_a_glance.append(match)
            else:
                other.append(match)

        return at_a_glance + other

    def _celex_to_readable(self, celex: str) -> str:
        """Convert CELEX to readable format for search"""
        # Pattern: 32024R1689 → year=2024, type=R, number=1689
        match = re.match(r'[0-9]?([0-9]{4})([A-Z])([0-9]+)', celex)

        if match:
            year, doc_type, number = match.groups()

            type_map = {
                'R': 'Regulation',
                'L': 'Directive',
                'D': 'Decision',
                'C': 'Communication'
            }

            type_name = type_map.get(doc_type, doc_type)
            return f"{type_name} {year}/{number}"

        return celex

    def clear_cache(self):
        """Clear all cached match results"""
        self._celex_cache.clear()
        self._procedure_cache.clear()
        logger.info("Cleared EPRS matcher cache")


# Global singleton
_eprs_matcher: Optional[EPRSMatcher] = None


def get_eprs_matcher() -> EPRSMatcher:
    """Get global EPRS matcher instance"""
    global _eprs_matcher

    if _eprs_matcher is None:
        _eprs_matcher = EPRSMatcher()

    return _eprs_matcher
