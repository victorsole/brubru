"""
Real-time Data Enrichment

Detects entity mentions in chat and enriches responses with live API data.
Part of Phase 13: AI Context Injection - Task 13.6

Features:
- Entity detection in conversation (CELEX, procedures, MEPs)
- Live API calls to fetch current data
- Automatic updates when new entities mentioned
- Caching to avoid redundant API calls
- Enrichment metadata tracking
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from services.indexing.metadata_extractor import MetadataExtractor, get_metadata_extractor
from api_clients.eurlex_client import EURLexClient
from api_clients.oeil_client import OEILClient
from api_clients.european_parliament_client import EuropeanParliamentClient

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of enrichment operation"""
    entity_type: str
    entity_id: str
    data: Dict[str, Any]
    source: str  # 'cache' or 'api'
    fetch_time_ms: float


class RealTimeEnricher:
    """
    Real-time data enrichment during chat conversations.

    Workflow:
    1. Detect entity mentions in messages (CELEX, procedures, MEPs)
    2. Check cache for recent data
    3. Fetch live data via APIs if not cached
    4. Return enriched data for AI context
    """

    def __init__(
        self,
        metadata_extractor: MetadataExtractor,
        eurlex_client: Optional[EURLexClient] = None,
        oeil_client: Optional[OEILClient] = None,
        parliament_client: Optional[EuropeanParliamentClient] = None,
        cache_ttl_minutes: int = 60
    ):
        """
        Initialize real-time enricher.

        Args:
            metadata_extractor: Entity extraction service
            eurlex_client: EUR-Lex API client
            oeil_client: OEIL API client
            parliament_client: Parliament API client
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.metadata_extractor = metadata_extractor
        self.eurlex_client = eurlex_client
        self.oeil_client = oeil_client
        self.parliament_client = parliament_client
        self.cache_ttl_minutes = cache_ttl_minutes

        # In-memory cache (in production, use Redis)
        self._cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"Initialized RealTimeEnricher (cache_ttl={cache_ttl_minutes}m)")

    async def enrich_message(
        self,
        message: str,
        max_entities_per_type: int = 3
    ) -> List[EnrichmentResult]:
        """
        Enrich message by detecting entities and fetching live data.

        Args:
            message: Message text to analyze
            max_entities_per_type: Max entities to fetch per type

        Returns:
            List of EnrichmentResult with fetched data

        Example:
            >>> enrichments = await enricher.enrich_message(
            ...     "What's the latest on the AI Act (2021/0106(COD))?"
            ... )
            >>> for e in enrichments:
            ...     print(f"{e.entity_type}: {e.entity_id}")
        """
        start_time = datetime.now()

        # Extract entities
        entities = self.metadata_extractor.extract_all(message)

        enrichments = []

        # Enrich CELEX numbers
        for celex in entities['celex_numbers'][:max_entities_per_type]:
            result = await self._enrich_legislation(celex)
            if result:
                enrichments.append(result)

        # Enrich procedure references
        for proc_ref in entities['procedure_references'][:max_entities_per_type]:
            result = await self._enrich_procedure(proc_ref)
            if result:
                enrichments.append(result)

        # Enrich MEP mentions
        for mep_name in entities['mep_mentions'][:max_entities_per_type]:
            result = await self._enrich_mep(mep_name)
            if result:
                enrichments.append(result)

        total_time = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Enriched message: {len(enrichments)} entities "
            f"({len(entities['celex_numbers'])} CELEX, "
            f"{len(entities['procedure_references'])} procedures, "
            f"{len(entities['mep_mentions'])} MEPs) in {total_time:.2f}ms"
        )

        return enrichments

    async def _enrich_legislation(self, celex: str) -> Optional[EnrichmentResult]:
        """Enrich legislation by CELEX number"""
        if not self.eurlex_client:
            return None

        start_time = datetime.now()

        # Check cache
        cache_key = f"legislation:{celex}"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.debug(f"Cache hit for {celex}")
            return EnrichmentResult(
                entity_type='legislation',
                entity_id=celex,
                data=cached,
                source='cache',
                fetch_time_ms=0.0
            )

        # Fetch from API
        try:
            metadata = await self.eurlex_client.get_document_metadata(celex)

            # Get document text excerpt
            try:
                text = await self.eurlex_client.get_document_text(celex, format='txt')
                text_excerpt = text[:1000] if text else ""
            except:
                text_excerpt = ""

            data = {
                'celex': celex,
                'title': metadata.get('title', ''),
                'date': metadata.get('date', ''),
                'type': metadata.get('type', ''),
                'status': metadata.get('in_force', True),
                'subjects': metadata.get('subjects', []),
                'text_excerpt': text_excerpt,
                'url': f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
            }

            # Cache result
            self._add_to_cache(cache_key, data)

            fetch_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.debug(f"Fetched legislation {celex} in {fetch_time:.2f}ms")

            return EnrichmentResult(
                entity_type='legislation',
                entity_id=celex,
                data=data,
                source='api',
                fetch_time_ms=fetch_time
            )

        except Exception as e:
            logger.error(f"Failed to enrich legislation {celex}: {str(e)}")
            return None

    async def _enrich_procedure(self, proc_ref: str) -> Optional[EnrichmentResult]:
        """Enrich legislative procedure"""
        if not self.oeil_client:
            return None

        start_time = datetime.now()

        # Check cache
        cache_key = f"procedure:{proc_ref}"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.debug(f"Cache hit for {proc_ref}")
            return EnrichmentResult(
                entity_type='procedure',
                entity_id=proc_ref,
                data=cached,
                source='cache',
                fetch_time_ms=0.0
            )

        # Fetch from API
        try:
            procedure = await self.oeil_client.get_procedure(proc_ref)

            data = {
                'reference': proc_ref,
                'title': procedure.get('title', ''),
                'type': procedure.get('type', ''),
                'status': procedure.get('current_stage', ''),
                'date_created': procedure.get('date', ''),
                'committees': procedure.get('committees', []),
                'rapporteur': procedure.get('rapporteur', ''),
                'shadow_rapporteurs': procedure.get('shadow_rapporteurs', []),
                'timeline': procedure.get('events', [])[:5],  # Last 5 events
                'url': f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={proc_ref}"
            }

            # Cache result
            self._add_to_cache(cache_key, data)

            fetch_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.debug(f"Fetched procedure {proc_ref} in {fetch_time:.2f}ms")

            return EnrichmentResult(
                entity_type='procedure',
                entity_id=proc_ref,
                data=data,
                source='api',
                fetch_time_ms=fetch_time
            )

        except Exception as e:
            logger.error(f"Failed to enrich procedure {proc_ref}: {str(e)}")
            return None

    async def _enrich_mep(self, mep_name: str) -> Optional[EnrichmentResult]:
        """Enrich MEP by name"""
        if not self.parliament_client:
            return None

        start_time = datetime.now()

        # Check cache
        cache_key = f"mep:{mep_name.lower()}"
        cached = self._get_from_cache(cache_key)

        if cached:
            logger.debug(f"Cache hit for {mep_name}")
            return EnrichmentResult(
                entity_type='mep',
                entity_id=mep_name,
                data=cached,
                source='cache',
                fetch_time_ms=0.0
            )

        # Fetch from API
        try:
            # Search for MEP
            search_results = await self.parliament_client.search_meps(name=mep_name)

            if not search_results:
                logger.warning(f"MEP not found: {mep_name}")
                return None

            # Take first match
            mep = search_results[0]
            mep_id = mep.get('id', '')

            # Get detailed profile
            if mep_id:
                details = await self.parliament_client.get_mep_details(mep_id)

                data = {
                    'id': mep_id,
                    'name': details.get('fullName', mep_name),
                    'country': details.get('country', ''),
                    'party': details.get('nationalPoliticalGroup', ''),
                    'group': details.get('politicalGroup', ''),
                    'committees': details.get('committees', []),
                    'bio': details.get('biography', '')[:500],  # Excerpt
                    'email': details.get('email', ''),
                    'active': details.get('active', True),
                    'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}"
                }

                # Cache result
                self._add_to_cache(cache_key, data)

                fetch_time = (datetime.now() - start_time).total_seconds() * 1000

                logger.debug(f"Fetched MEP {mep_name} in {fetch_time:.2f}ms")

                return EnrichmentResult(
                    entity_type='mep',
                    entity_id=mep_name,
                    data=data,
                    source='api',
                    fetch_time_ms=fetch_time
                )

        except Exception as e:
            logger.error(f"Failed to enrich MEP {mep_name}: {str(e)}")
            return None

    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if not expired"""
        if key not in self._cache:
            return None

        cached_data = self._cache[key]
        cached_time = cached_data.get('_cached_at')

        if not cached_time:
            return None

        # Check expiration
        age_minutes = (datetime.now() - cached_time).total_seconds() / 60

        if age_minutes > self.cache_ttl_minutes:
            # Expired
            del self._cache[key]
            return None

        # Return cached data (without metadata)
        data = {k: v for k, v in cached_data.items() if not k.startswith('_')}
        return data

    def _add_to_cache(self, key: str, data: Dict[str, Any]):
        """Add data to cache with timestamp"""
        self._cache[key] = {
            **data,
            '_cached_at': datetime.now()
        }

    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size': len(self._cache),
            'ttl_minutes': self.cache_ttl_minutes,
            'keys': list(self._cache.keys())
        }

    async def batch_enrich(
        self,
        entities: Dict[str, List[str]]
    ) -> Dict[str, List[EnrichmentResult]]:
        """
        Batch enrich multiple entities.

        Args:
            entities: Dict with entity types as keys, entity IDs as values:
            {
                'celex': ['32016R0679', '32018R1807'],
                'procedures': ['2021/0106(COD)'],
                'meps': ['Brando Benifei']
            }

        Returns:
            Dict with enrichment results per type
        """
        results = {
            'legislation': [],
            'procedures': [],
            'meps': []
        }

        # Enrich all in parallel
        tasks = []

        for celex in entities.get('celex', []):
            tasks.append(self._enrich_legislation(celex))

        for proc_ref in entities.get('procedures', []):
            tasks.append(self._enrich_procedure(proc_ref))

        for mep_name in entities.get('meps', []):
            tasks.append(self._enrich_mep(mep_name))

        # Wait for all
        enrichments = await asyncio.gather(*tasks, return_exceptions=True)

        # Group by type
        for enrichment in enrichments:
            if isinstance(enrichment, EnrichmentResult):
                if enrichment.entity_type == 'legislation':
                    results['legislation'].append(enrichment)
                elif enrichment.entity_type == 'procedure':
                    results['procedures'].append(enrichment)
                elif enrichment.entity_type == 'mep':
                    results['meps'].append(enrichment)

        logger.info(
            f"Batch enriched {len(enrichments)} entities: "
            f"{len(results['legislation'])} legislation, "
            f"{len(results['procedures'])} procedures, "
            f"{len(results['meps'])} MEPs"
        )

        return results


# Global singleton
_real_time_enricher: Optional[RealTimeEnricher] = None


def get_real_time_enricher(
    metadata_extractor: Optional[MetadataExtractor] = None,
    eurlex_client: Optional[EURLexClient] = None,
    oeil_client: Optional[OEILClient] = None,
    parliament_client: Optional[EuropeanParliamentClient] = None,
    cache_ttl_minutes: int = 60
) -> RealTimeEnricher:
    """
    Get global real-time enricher instance.

    Args:
        metadata_extractor: Entity extractor
        eurlex_client: EUR-Lex client
        oeil_client: OEIL client
        parliament_client: Parliament client
        cache_ttl_minutes: Cache TTL

    Returns:
        RealTimeEnricher instance
    """
    global _real_time_enricher

    if _real_time_enricher is None:
        _real_time_enricher = RealTimeEnricher(
            metadata_extractor=metadata_extractor or get_metadata_extractor(),
            eurlex_client=eurlex_client,
            oeil_client=oeil_client,
            parliament_client=parliament_client,
            cache_ttl_minutes=cache_ttl_minutes
        )

    return _real_time_enricher
