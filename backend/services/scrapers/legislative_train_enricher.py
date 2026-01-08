"""
Legislative Train Enricher

Enriches scraped Legislative Train data with cross-referenced institutional sources:
- OEIL: Full procedure details, timeline, key events
- EUR-Lex: Legal texts via CELEX numbers
- EPRS: Explainer briefings (reuses EPRSMatcher!)
- MEP data: Rapporteur profiles

Similar to EPRSContentEnricher but for legislative tracking.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from ...schemas.scrapers.legislative_train_schemas import (
    LegislativeCarriage,
    EnrichedCarriage,
    EPRSBriefingReference
)
from .oeil_scraper import OEILScraper
from ..matching.eprs_matcher import get_eprs_matcher

logger = logging.getLogger(__name__)


class LegislativeTrainEnricher:
    """
    Enriches Legislative Train carriages with institutional data.

    Key Innovation: Reuses existing infrastructure!
    - OEILScraper for procedure details
    - EPRSMatcher for explainer briefings
    - EUR-Lex integration for legal texts

    Usage:
        enricher = LegislativeTrainEnricher()

        # Enrich single carriage
        enriched = await enricher.enrich_carriage(carriage)

        # Batch enrich
        enriched_list = await enricher.enrich_multiple(carriages)
    """

    def __init__(
        self,
        oeil_scraper: Optional[OEILScraper] = None,
        use_eprs_matcher: bool = True
    ):
        """
        Initialize enricher.

        Args:
            oeil_scraper: OEIL scraper instance (creates if None)
            use_eprs_matcher: Whether to match EPRS briefings
        """
        self.oeil_scraper = oeil_scraper or OEILScraper()
        self.use_eprs_matcher = use_eprs_matcher

        if use_eprs_matcher:
            self.eprs_matcher = get_eprs_matcher()
        else:
            self.eprs_matcher = None

        logger.info("Initialized LegislativeTrainEnricher")

    async def enrich_carriage(
        self,
        carriage: LegislativeCarriage,
        enrich_oeil: bool = True,
        enrich_eprs: bool = True,
        enrich_eurlex: bool = True
    ) -> EnrichedCarriage:
        """
        Fully enrich a legislative carriage.

        Args:
            carriage: Base carriage from scraper
            enrich_oeil: Fetch OEIL procedure data
            enrich_eprs: Match EPRS briefings
            enrich_eurlex: Fetch EUR-Lex documents

        Returns:
            EnrichedCarriage with all cross-references
        """
        logger.info(f"Enriching carriage: {carriage.title}")

        # Convert to EnrichedCarriage
        enriched = EnrichedCarriage(**carriage.model_dump())
        enrichment_quality = "high"

        try:
            # Phase 1: OEIL Enrichment
            if enrich_oeil and carriage.oeil_procedure_ref:
                logger.debug(f"Fetching OEIL data for {carriage.oeil_procedure_ref}")

                try:
                    oeil_data = await self.oeil_scraper.get_procedure(
                        carriage.oeil_procedure_ref
                    )

                    if oeil_data:
                        enriched.oeil_procedure_data = oeil_data

                        # Extract timeline
                        if 'timeline' in oeil_data:
                            enriched.oeil_timeline = oeil_data['timeline']

                        # Extract key events
                        if 'key_events' in oeil_data:
                            enriched.oeil_key_events = oeil_data['key_events']

                        logger.info(f"OEIL data enriched for {carriage.oeil_procedure_ref}")
                    else:
                        enrichment_quality = "medium"
                        logger.warning(f"No OEIL data found for {carriage.oeil_procedure_ref}")

                except Exception as e:
                    enrichment_quality = "medium"
                    logger.error(f"OEIL enrichment failed: {str(e)}")

            # Phase 2: EPRS Briefing Matching
            if enrich_eprs and self.eprs_matcher:
                logger.debug("Matching EPRS briefings")

                try:
                    # Use auto_match_legislation for intelligent matching
                    match_result = await self.eprs_matcher.auto_match_legislation(
                        celex=carriage.celex_numbers[0] if carriage.celex_numbers else None,
                        procedure_ref=carriage.oeil_procedure_ref,
                        title=carriage.title,
                        text=carriage.description,
                        max_results=3
                    )

                    if match_result['explainers']:
                        enriched.eprs_matched_briefings = match_result['explainers']
                        enriched.eprs_match_confidence = match_result['confidence']

                        logger.info(
                            f"Matched {len(match_result['explainers'])} EPRS briefings "
                            f"(confidence: {match_result['confidence']:.0%})"
                        )
                    else:
                        logger.debug("No EPRS briefings matched")

                except Exception as e:
                    logger.error(f"EPRS matching failed: {str(e)}")

            # Phase 3: EUR-Lex Enrichment
            if enrich_eurlex and carriage.celex_numbers:
                logger.debug(f"Fetching EUR-Lex documents for {len(carriage.celex_numbers)} CELEX numbers")

                try:
                    eurlex_docs = []

                    for celex in carriage.celex_numbers[:3]:  # Limit to 3
                        # Construct EUR-Lex URL
                        eurlex_url = f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}"

                        eurlex_docs.append({
                            'celex': celex,
                            'url': eurlex_url,
                            'type': 'legal_text'
                        })

                    enriched.eurlex_documents = eurlex_docs

                    if eurlex_docs:
                        enriched.legal_text_url = eurlex_docs[0]['url']

                    logger.info(f"EUR-Lex documents enriched: {len(eurlex_docs)} documents")

                except Exception as e:
                    logger.error(f"EUR-Lex enrichment failed: {str(e)}")

            # Mark as enriched
            enriched.enriched_at = datetime.now()
            enriched.enrichment_quality = enrichment_quality

            logger.info(
                f"Carriage enriched: {carriage.title} "
                f"(quality: {enrichment_quality})"
            )

            return enriched

        except Exception as e:
            logger.error(f"Enrichment failed: {str(e)}")

            # Return basic enriched carriage even on failure
            enriched.enriched_at = datetime.now()
            enriched.enrichment_quality = "low"
            return enriched

    async def enrich_multiple(
        self,
        carriages: List[LegislativeCarriage],
        max_concurrent: int = 5
    ) -> List[EnrichedCarriage]:
        """
        Enrich multiple carriages with concurrency control.

        Args:
            carriages: List of carriages to enrich
            max_concurrent: Maximum concurrent enrichments

        Returns:
            List of enriched carriages
        """
        import asyncio

        logger.info(f"Batch enriching {len(carriages)} carriages")

        enriched_carriages = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(carriage):
            async with semaphore:
                return await self.enrich_carriage(carriage)

        # Create tasks
        tasks = [enrich_with_semaphore(c) for c in carriages]

        # Execute with progress logging
        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            enriched = await task
            enriched_carriages.append(enriched)

            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(carriages)} carriages enriched")

        logger.info(f"Batch enrichment complete: {len(enriched_carriages)} carriages")
        return enriched_carriages

    async def find_related_carriages(
        self,
        carriage: LegislativeCarriage,
        all_carriages: List[LegislativeCarriage],
        max_results: int = 5
    ) -> List[LegislativeCarriage]:
        """
        Find related legislative files.

        Criteria:
        - Same CELEX numbers
        - Same OEIL procedure
        - Same committees
        - Same policy area (based on EPRS briefings)

        Args:
            carriage: Target carriage
            all_carriages: All available carriages
            max_results: Maximum results

        Returns:
            List of related carriages
        """
        logger.debug(f"Finding related carriages for: {carriage.title}")

        related = []
        scores = []

        for candidate in all_carriages:
            # Skip self
            if candidate.id == carriage.id:
                continue

            score = 0

            # CELEX match (highest weight)
            if carriage.celex_numbers and candidate.celex_numbers:
                common_celex = set(carriage.celex_numbers) & set(candidate.celex_numbers)
                if common_celex:
                    score += 10

            # OEIL procedure match
            if (carriage.oeil_procedure_ref and candidate.oeil_procedure_ref
                    and carriage.oeil_procedure_ref == candidate.oeil_procedure_ref):
                score += 8

            # Committee overlap
            if carriage.committees and candidate.committees:
                common_committees = set(carriage.committees) & set(candidate.committees)
                score += len(common_committees) * 2

            # Same train
            if carriage.train_id and candidate.train_id and carriage.train_id == candidate.train_id:
                score += 1

            if score > 0:
                related.append(candidate)
                scores.append(score)

        # Sort by score
        sorted_pairs = sorted(zip(related, scores), key=lambda x: x[1], reverse=True)
        related_sorted = [carriage for carriage, score in sorted_pairs]

        logger.debug(f"Found {len(related_sorted)} related carriages")
        return related_sorted[:max_results]

    def extract_policy_areas(self, carriage: LegislativeCarriage) -> List[str]:
        """
        Extract policy areas from carriage data.

        Uses:
        - Committee codes (map to policy areas)
        - Title keywords
        - EPRS briefing categories

        Args:
            carriage: Carriage to analyze

        Returns:
            List of policy area tags
        """
        policy_areas = set()

        # Committee to policy area mapping
        committee_policy_map = {
            'AFET': 'foreign_affairs',
            'DEVE': 'development',
            'INTA': 'trade',
            'BUDG': 'budget',
            'ECON': 'economy',
            'EMPL': 'employment',
            'ENVI': 'environment',
            'ITRE': 'industry',
            'IMCO': 'internal_market',
            'TRAN': 'transport',
            'REGI': 'regional',
            'AGRI': 'agriculture',
            'CULT': 'culture',
            'JURI': 'justice',
            'LIBE': 'civil_liberties',
        }

        # Map committees to policy areas
        for committee in carriage.committees:
            if committee in committee_policy_map:
                policy_areas.add(committee_policy_map[committee])

        # Keyword detection in title
        title_lower = carriage.title.lower()

        policy_keywords = {
            'climate': ['climate', 'green deal', 'carbon'],
            'digital': ['digital', 'ai', 'technology', 'data'],
            'energy': ['energy', 'renewable'],
            'health': ['health', 'medical', 'pharmaceutical'],
            'migration': ['migration', 'asylum', 'border'],
            'security': ['security', 'defense', 'defence'],
        }

        for area, keywords in policy_keywords.items():
            if any(kw in title_lower for kw in keywords):
                policy_areas.add(area)

        return sorted(list(policy_areas))

    async def close(self):
        """Close scraper connections"""
        if hasattr(self.oeil_scraper, 'close'):
            await self.oeil_scraper.close()

        logger.info("Closed LegislativeTrainEnricher")


# Convenience function
async def enrich_legislative_carriage(
    carriage: LegislativeCarriage,
    **kwargs
) -> EnrichedCarriage:
    """
    Convenience function to enrich a carriage in one step.

    Args:
        carriage: Carriage to enrich
        **kwargs: Additional enrichment options

    Returns:
        Enriched carriage
    """
    enricher = LegislativeTrainEnricher()

    enriched = await enricher.enrich_carriage(carriage, **kwargs)

    await enricher.close()

    return enriched
