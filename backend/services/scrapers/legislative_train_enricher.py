"""
Legislative Train Enricher

Enriches scraped Legislative Train data with cross-referenced institutional sources:
- OEIL: Full procedure details, timeline, key events
- EUR-Lex: Legal texts via CELEX numbers (NOW USING FULL CELLAR API)
- EPRS: Explainer briefings (reuses EPRSMatcher!)
- MEP data: Rapporteur profiles

ENHANCED (January 2025):
- Works with new ScrapedFile and ScrapedFileDetail schemas
- Timeline data enrichment
- Package-level statistics
- Full EUR-Lex CELLAR API integration (SPARQL + REST)

Similar to EPRSContentEnricher but for legislative tracking.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from schemas.scrapers.legislative_train_schemas import (
    LegislativeCarriage,
    EnrichedCarriage,
    EPRSBriefingReference,
    ScrapedFile,
    ScrapedFileDetail,
    CarriageStatus,
    TimelineEntry
)
from .oeil_scraper import OEILScraper
# get_eprs_matcher is imported lazily where constructed (below): it pulls the EPRS
# ChromaDB indexer (chromadb + onnxruntime, ~200 MB). This enricher is imported at
# boot by api/legislative_train.py, so a module-level import would pay that cost on
# every process start even though the production vector store is empty.
from services.api_clients.eurlex_client import EURLexClient
from services.search.hybrid_search import semantic_store_available

logger = logging.getLogger(__name__)


class LegislativeTrainEnricher:
    """
    Enriches Legislative Train carriages with institutional data.

    Key Innovation: Reuses existing infrastructure!
    - OEILScraper for procedure details
    - EPRSMatcher for explainer briefings
    - EUR-Lex integration for legal texts

    ENHANCED (January 2025):
    - Works with new scraped data structures
    - Timeline enrichment from OEIL
    - Policy area extraction

    Usage:
        enricher = LegislativeTrainEnricher()

        # Enrich single carriage
        enriched = await enricher.enrich_carriage(carriage)

        # Enrich from scraped file
        enriched = await enricher.enrich_scraped_file(scraped_file)

        # Batch enrich
        enriched_list = await enricher.enrich_multiple(carriages)
    """

    def __init__(
        self,
        oeil_scraper: Optional[OEILScraper] = None,
        eurlex_client: Optional[EURLexClient] = None,
        use_eprs_matcher: bool = True,
        use_eurlex_api: bool = True
    ):
        """
        Initialize enricher.

        Args:
            oeil_scraper: OEIL scraper instance (creates if None)
            eurlex_client: EUR-Lex client instance (creates if None)
            use_eprs_matcher: Whether to match EPRS briefings
            use_eurlex_api: Whether to use EUR-Lex CELLAR API for real metadata
        """
        self.oeil_scraper = oeil_scraper or OEILScraper()
        self.use_eprs_matcher = use_eprs_matcher
        self.use_eurlex_api = use_eurlex_api

        # Initialize EUR-Lex CELLAR API client
        if use_eurlex_api:
            self.eurlex_client = eurlex_client or EURLexClient()
        else:
            self.eurlex_client = None

        # EPRS matching runs on the ChromaDB vector store. Build the matcher only when
        # a populated store exists; on the empty production store it stays None and the
        # enrich-EPRS branch is skipped (already guarded below), so chromadb never loads.
        if use_eprs_matcher and semantic_store_available():
            from services.matching.eprs_matcher import get_eprs_matcher
            self.eprs_matcher = get_eprs_matcher()
        else:
            self.eprs_matcher = None

        logger.info(f"Initialized LegislativeTrainEnricher (EUR-Lex API: {use_eurlex_api})")

    async def enrich_scraped_file(
        self,
        scraped_file: ScrapedFileDetail,
        enrich_oeil: bool = True,
        enrich_eprs: bool = True,
        enrich_eurlex: bool = True
    ) -> EnrichedCarriage:
        """
        Enrich a scraped file detail into a full EnrichedCarriage.

        NEW method for the enhanced scraper.

        Args:
            scraped_file: ScrapedFileDetail from scraper
            enrich_oeil: Fetch OEIL procedure data
            enrich_eprs: Match EPRS briefings
            enrich_eurlex: Fetch EUR-Lex documents

        Returns:
            EnrichedCarriage with all cross-references
        """
        logger.info(f"Enriching scraped file: {scraped_file.title}")

        # Convert ScrapedFileDetail to LegislativeCarriage
        carriage = LegislativeCarriage(
            file_id=scraped_file.file_id,
            title=scraped_file.title,
            description=scraped_file.description,
            current_status=scraped_file.status,
            url=scraped_file.url,
            committees=scraped_file.committees,
            lead_committee=scraped_file.lead_committee,
            oeil_procedure_ref=scraped_file.oeil_procedure_ref,
            celex_numbers=scraped_file.celex_numbers,
            eprs_briefings=scraped_file.eprs_briefings,
            timeline=scraped_file.timeline,
            text_type=scraped_file.text_type,
            spotlight_tags=scraped_file.spotlight_tags,
            is_recently_updated=scraped_file.is_recently_updated,
            ec_priority_ids=scraped_file.ec_priority_ids,
            related_themes=scraped_file.related_themes,
            scraped_at=scraped_file.scraped_at
        )

        return await self.enrich_carriage(
            carriage,
            enrich_oeil=enrich_oeil,
            enrich_eprs=enrich_eprs,
            enrich_eurlex=enrich_eurlex
        )

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

            # Phase 3: EUR-Lex Enrichment (ENHANCED with CELLAR API)
            if enrich_eurlex and carriage.celex_numbers:
                logger.debug(f"Fetching EUR-Lex documents for {len(carriage.celex_numbers)} CELEX numbers")

                try:
                    eurlex_docs = []

                    for celex in carriage.celex_numbers[:3]:  # Limit to 3
                        eurlex_url = f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}"

                        doc_data = {
                            'celex': celex,
                            'url': eurlex_url,
                            'type': 'legal_text'
                        }

                        # Use EUR-Lex CELLAR API for real metadata
                        if self.eurlex_client and self.use_eurlex_api:
                            try:
                                # Fetch document metadata via SPARQL
                                doc_metadata = await self.eurlex_client.get_document_by_celex(celex)

                                if doc_metadata:
                                    doc_data['title'] = doc_metadata.get('title')
                                    doc_data['date'] = doc_metadata.get('date')
                                    doc_data['document_type'] = doc_metadata.get('type')
                                    doc_data['subject'] = doc_metadata.get('subject')
                                    doc_data['author'] = doc_metadata.get('author')
                                    doc_data['uri'] = doc_metadata.get('uri')

                                    logger.debug(f"EUR-Lex metadata fetched for {celex}: {doc_data.get('title', 'No title')[:50]}")

                                # Fetch document relationships (amendments, repeals)
                                relationships = await self.eurlex_client.get_document_relationships(celex)

                                if relationships:
                                    doc_data['amended_by'] = relationships.get('amended_by', [])
                                    doc_data['amends'] = relationships.get('amends', [])
                                    doc_data['repealed_by'] = relationships.get('repealed_by', [])
                                    doc_data['repeals'] = relationships.get('repeals', [])
                                    doc_data['implemented_by'] = relationships.get('implemented_by', [])

                                    total_relations = sum(len(v) for v in relationships.values() if isinstance(v, list))
                                    if total_relations > 0:
                                        logger.debug(f"EUR-Lex relationships fetched for {celex}: {total_relations} relations")

                            except Exception as api_error:
                                logger.warning(f"EUR-Lex API call failed for {celex}: {str(api_error)}")
                                # Continue with basic data even if API fails

                        eurlex_docs.append(doc_data)

                    enriched.eurlex_documents = eurlex_docs

                    if eurlex_docs:
                        enriched.legal_text_url = eurlex_docs[0]['url']

                    # Log enrichment summary
                    docs_with_metadata = sum(1 for d in eurlex_docs if d.get('title'))
                    logger.info(f"EUR-Lex documents enriched: {len(eurlex_docs)} documents ({docs_with_metadata} with full metadata)")

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

    async def enrich_scraped_files(
        self,
        scraped_files: List[ScrapedFileDetail],
        max_concurrent: int = 5
    ) -> List[EnrichedCarriage]:
        """
        Enrich multiple scraped files with concurrency control.

        NEW method for the enhanced scraper.

        Args:
            scraped_files: List of ScrapedFileDetail objects
            max_concurrent: Maximum concurrent enrichments

        Returns:
            List of enriched carriages
        """
        import asyncio

        logger.info(f"Batch enriching {len(scraped_files)} scraped files")

        enriched_carriages = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(file):
            async with semaphore:
                return await self.enrich_scraped_file(file)

        # Create tasks
        tasks = [enrich_with_semaphore(f) for f in scraped_files]

        # Execute with progress logging
        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            enriched = await task
            enriched_carriages.append(enriched)

            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(scraped_files)} files enriched")

        logger.info(f"Batch enrichment complete: {len(enriched_carriages)} files")
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
        - Same package (NEW)
        - Similar timeline patterns (NEW)

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
            if candidate.file_id == carriage.file_id:
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

            # Same package (NEW)
            if carriage.package_slug and candidate.package_slug:
                if carriage.package_slug == candidate.package_slug:
                    score += 5

            # Same train
            if carriage.train_id and candidate.train_id and carriage.train_id == candidate.train_id:
                score += 1

            # Similar status (NEW)
            if carriage.current_status == candidate.current_status:
                score += 1

            # EC Priority overlap (NEW)
            if carriage.ec_priority_ids and candidate.ec_priority_ids:
                common_priorities = set(carriage.ec_priority_ids) & set(candidate.ec_priority_ids)
                score += len(common_priorities) * 2

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

    def analyze_timeline_velocity(self, timeline: List[TimelineEntry]) -> Dict[str, Any]:
        """
        Analyze legislative velocity from timeline.

        NEW method for timeline analytics.

        Args:
            timeline: List of TimelineEntry objects

        Returns:
            Dict with velocity metrics
        """
        if not timeline or len(timeline) < 2:
            return {
                'has_progression': False,
                'months_tracked': len(timeline),
                'status_changes': 0
            }

        # Sort timeline
        sorted_timeline = sorted(timeline, key=lambda x: (x.year, x.month))

        # Count status changes
        status_changes = 0
        prev_status = None
        for entry in sorted_timeline:
            if prev_status and entry.status != prev_status:
                status_changes += 1
            prev_status = entry.status

        # Calculate months from first to last
        first = sorted_timeline[0]
        last = sorted_timeline[-1]
        months_tracked = (last.year - first.year) * 12 + (last.month - first.month)

        # Determine velocity
        if months_tracked == 0:
            velocity = "unknown"
        elif status_changes == 0:
            velocity = "stalled"
        elif status_changes / months_tracked > 0.3:
            velocity = "fast"
        elif status_changes / months_tracked > 0.1:
            velocity = "normal"
        else:
            velocity = "slow"

        return {
            'has_progression': status_changes > 0,
            'months_tracked': months_tracked,
            'status_changes': status_changes,
            'velocity': velocity,
            'first_status': sorted_timeline[0].status.value,
            'current_status': sorted_timeline[-1].status.value
        }

    async def close(self):
        """Close scraper and API client connections"""
        if hasattr(self.oeil_scraper, 'close'):
            await self.oeil_scraper.close()

        if self.eurlex_client and hasattr(self.eurlex_client, 'close'):
            await self.eurlex_client.close()

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


async def enrich_scraped_file(
    scraped_file: ScrapedFileDetail,
    **kwargs
) -> EnrichedCarriage:
    """
    Convenience function to enrich a scraped file in one step.

    NEW convenience function for enhanced scraper.

    Args:
        scraped_file: ScrapedFileDetail to enrich
        **kwargs: Additional enrichment options

    Returns:
        Enriched carriage
    """
    enricher = LegislativeTrainEnricher()

    enriched = await enricher.enrich_scraped_file(scraped_file, **kwargs)

    await enricher.close()

    return enriched
