"""
EPRS Archive Downloader

Phase 4: Historical Archive Building
Systematically downloads and indexes ALL historical EPRS publications from
the EU Publications Office (Cellar).

This orchestrator:
1. Queries Cellar for EPRS publications by year
2. Downloads metadata from SPARQL endpoint
3. Enriches with full PDF content (using Phase 1 infrastructure)
4. Indexes into ChromaDB (using Phase 2 infrastructure)
5. Tracks progress and handles deduplication
6. Provides statistics and monitoring

Result: Complete 15-year EPRS archive indexed and searchable

Usage:
    downloader = EPRSArchiveDownloader()

    # Download and index entire archive
    result = await downloader.download_full_archive(
        year_from=2009,
        year_to=2024
    )

    # Download specific year
    result = await downloader.download_year(2023)

    # Get progress statistics
    stats = downloader.get_progress_stats()
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from services.api_clients.eprs_archive_client import EPRSArchiveClient, get_eprs_archive_client, EPRSPublicationType
from services.document_processing.eprs_enricher import EPRSContentEnricher
from services.indexing.eprs_indexer import EPRSIndexer, get_eprs_indexer
from schemas.scrapers.scraper_schemas import (
    EPRSPublication,
    EPRSExtractionResult,
    EPRSPublicationType as SchemaPublicationType
)

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """Track download progress"""
    total_found: int = 0
    total_downloaded: int = 0
    total_enriched: int = 0
    total_indexed: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    current_year: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_found == 0:
            return 0.0
        return (self.total_indexed / self.total_found) * 100

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class EPRSArchiveDownloader:
    """
    Orchestrates systematic download and indexing of historical EPRS publications

    This is the Phase 4 core component that builds the complete historical archive.

    Process:
    1. Query Cellar SPARQL endpoint for EPRS publications (by year)
    2. Download metadata (title, date, URL, CELEX, etc.)
    3. Enrich with full PDF content extraction (Phase 1)
    4. Index into ChromaDB vector database (Phase 2)
    5. Track progress and handle errors

    Example:
        downloader = EPRSArchiveDownloader()

        # Download entire archive
        result = await downloader.download_full_archive(
            year_from=2009,
            year_to=2024,
            enable_enrichment=True
        )

        print(f"Indexed {result.total_indexed} publications")
        print(f"Success rate: {result.success_rate:.1f}%")
    """

    def __init__(
        self,
        archive_client: Optional[EPRSArchiveClient] = None,
        enricher: Optional[EPRSContentEnricher] = None,
        indexer: Optional[EPRSIndexer] = None,
        progress_file: Optional[str] = None,
        batch_size: int = 50,
        enable_enrichment: bool = True
    ):
        """
        Initialize EPRS Archive Downloader

        Args:
            archive_client: EPRSArchiveClient instance (creates if None)
            enricher: EPRSContentEnricher instance (creates if None)
            indexer: EPRSIndexer instance (creates if None)
            progress_file: Path to save progress JSON (optional)
            batch_size: Publications to process per batch
            enable_enrichment: If True, extract full PDF content
        """
        self.archive_client = archive_client or get_eprs_archive_client()
        self.enricher = enricher or EPRSContentEnricher()
        self.indexer = indexer or get_eprs_indexer()

        self.progress_file = progress_file
        self.batch_size = batch_size
        self.enable_enrichment = enable_enrichment

        self.progress = DownloadProgress()

        logger.info(
            f"Initialized EPRS Archive Downloader "
            f"(enrichment: {enable_enrichment}, batch_size: {batch_size})"
        )

    def _map_cellar_type_to_schema(self, cellar_type: str) -> SchemaPublicationType:
        """
        Map Cellar resource type to schema PublicationType

        Args:
            cellar_type: Type string from Cellar

        Returns:
            SchemaPublicationType enum
        """
        cellar_type_lower = cellar_type.lower() if cellar_type else ""

        if "at a glance" in cellar_type_lower or "at-a-glance" in cellar_type_lower:
            return SchemaPublicationType.AT_A_GLANCE
        elif "briefing" in cellar_type_lower:
            return SchemaPublicationType.BRIEFING
        elif "in-depth" in cellar_type_lower or "in depth" in cellar_type_lower:
            return SchemaPublicationType.IN_DEPTH_ANALYSIS
        elif "study" in cellar_type_lower:
            return SchemaPublicationType.STUDY
        elif "blog" in cellar_type_lower:
            return SchemaPublicationType.BLOG_POST
        else:
            return SchemaPublicationType.OTHER

    def _convert_cellar_to_publication(
        self,
        cellar_data: Dict[str, Any]
    ) -> Optional[EPRSPublication]:
        """
        Convert Cellar metadata to EPRSPublication (minimal version)

        Args:
            cellar_data: Metadata from Cellar SPARQL query

        Returns:
            EPRSPublication with basic metadata (no full content yet)
        """
        try:
            # Generate publication ID from URI
            uri = cellar_data.get("uri", "")
            pub_id = uri.split("/")[-1] if uri else f"cellar_{hash(str(cellar_data))}"

            # Parse date
            date_str = cellar_data.get("date")
            pub_date = None
            if date_str:
                try:
                    pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Map type
            pub_type = self._map_cellar_type_to_schema(cellar_data.get("type", ""))

            # Create minimal EPRSPublication
            publication = EPRSPublication(
                publication_id=pub_id,
                title=cellar_data.get("title", "Untitled"),
                publication_type=pub_type,
                summary=cellar_data.get("abstract") or cellar_data.get("subject") or "",
                publication_date=pub_date,
                html_url=cellar_data.get("url"),
                pdf_url=cellar_data.get("url") if cellar_data.get("url", "").endswith(".pdf") else None,
                authors=[cellar_data.get("author")] if cellar_data.get("author") else [],
                related_celex_numbers=[cellar_data.get("celex")] if cellar_data.get("celex") else [],
                metadata={
                    "cellar_uri": uri,
                    "cellar_isbn": cellar_data.get("isbn"),
                    "cellar_subject": cellar_data.get("subject"),
                    "source": "cellar_archive"
                }
            )

            return publication

        except Exception as e:
            logger.error(f"Failed to convert Cellar data: {str(e)}")
            return None

    async def download_year(
        self,
        year: int,
        force_reindex: bool = False
    ) -> DownloadProgress:
        """
        Download and index all EPRS publications from a specific year

        Args:
            year: Year to download (e.g., 2023)
            force_reindex: If True, reindex existing publications

        Returns:
            DownloadProgress with results
        """
        logger.info(f"{'='*80}")
        logger.info(f"DOWNLOADING EPRS ARCHIVE: Year {year}")
        logger.info(f"{'='*80}")

        self.progress = DownloadProgress(
            current_year=year,
            start_time=datetime.now()
        )

        try:
            # Step 1: Query Cellar for publications
            logger.info(f"\nStep 1: Querying Cellar for {year} publications...")

            cellar_publications = await self.archive_client.get_eprs_publications(
                year_from=year,
                year_to=year,
                limit=10000  # High limit for complete year
            )

            self.progress.total_found = len(cellar_publications)
            logger.info(f"✓ Found {self.progress.total_found} publications in {year}\n")

            if self.progress.total_found == 0:
                logger.warning(f"No publications found for {year}")
                self.progress.end_time = datetime.now()
                return self.progress

            # Step 2: Process in batches
            logger.info(f"Step 2: Processing publications in batches of {self.batch_size}...")

            for i in range(0, len(cellar_publications), self.batch_size):
                batch = cellar_publications[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(cellar_publications) + self.batch_size - 1) // self.batch_size

                logger.info(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} publications)")

                await self._process_batch(batch, force_reindex)

                # Save progress after each batch
                if self.progress_file:
                    self._save_progress()

            # Final summary
            self.progress.end_time = datetime.now()

            logger.info(f"\n{'='*80}")
            logger.info(f"YEAR {year} COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"Total found:    {self.progress.total_found}")
            logger.info(f"Downloaded:     {self.progress.total_downloaded}")
            logger.info(f"Enriched:       {self.progress.total_enriched}")
            logger.info(f"Indexed:        {self.progress.total_indexed}")
            logger.info(f"Skipped:        {self.progress.total_skipped}")
            logger.info(f"Failed:         {self.progress.total_failed}")
            logger.info(f"Success rate:   {self.progress.success_rate:.1f}%")
            logger.info(f"Duration:       {self.progress.duration_seconds:.0f}s")
            logger.info(f"{'='*80}\n")

            return self.progress

        except Exception as e:
            error_msg = f"Failed to download year {year}: {str(e)}"
            logger.error(error_msg)
            self.progress.errors.append(error_msg)
            self.progress.end_time = datetime.now()
            return self.progress

    async def _process_batch(
        self,
        cellar_publications: List[Dict[str, Any]],
        force_reindex: bool
    ):
        """
        Process a batch of Cellar publications

        Args:
            cellar_publications: List of Cellar metadata dicts
            force_reindex: Force reindexing
        """
        for cellar_data in cellar_publications:
            try:
                # Convert Cellar data to EPRSPublication (minimal)
                publication = self._convert_cellar_to_publication(cellar_data)

                if not publication:
                    self.progress.total_failed += 1
                    continue

                self.progress.total_downloaded += 1

                # Enrich with full content (Phase 1)
                if self.enable_enrichment and publication.pdf_url:
                    logger.debug(f"Enriching: {publication.title[:60]}...")

                    enrichment_result = await self.enricher.enrich_publication(
                        publication_id=publication.publication_id,
                        title=publication.title,
                        summary=publication.summary,
                        pdf_url=str(publication.pdf_url) if publication.pdf_url else None,
                        html_url=str(publication.html_url) if publication.html_url else None,
                        publication_type=publication.publication_type,
                        publication_date=publication.publication_date,
                        authors=publication.authors,
                        committees=publication.committees,
                        policy_areas=publication.policy_areas
                    )

                    if enrichment_result.success and enrichment_result.publication:
                        publication = enrichment_result.publication
                        self.progress.total_enriched += 1
                        logger.debug(f"  ✓ Enriched ({publication.word_count} words)")
                    else:
                        logger.debug(f"  ⚠ Enrichment failed, using basic metadata")

                # Index into ChromaDB (Phase 2)
                index_result = await self.indexer.index_publication(
                    publication=publication,
                    force_reindex=force_reindex
                )

                if index_result['success']:
                    if index_result.get('skipped'):
                        self.progress.total_skipped += 1
                        logger.debug(f"  ⊘ Skipped (already indexed)")
                    else:
                        self.progress.total_indexed += 1
                        logger.debug(f"  ✓ Indexed ({index_result['chunks_indexed']} chunks)")
                else:
                    self.progress.total_failed += 1
                    error_msg = f"Indexing failed for {publication.publication_id}: {index_result['errors']}"
                    logger.warning(f"  ✗ {error_msg}")
                    self.progress.errors.append(error_msg)

            except Exception as e:
                self.progress.total_failed += 1
                error_msg = f"Failed to process publication: {str(e)}"
                logger.error(error_msg)
                self.progress.errors.append(error_msg)

    async def download_full_archive(
        self,
        year_from: int = 2009,
        year_to: Optional[int] = None,
        force_reindex: bool = False
    ) -> DownloadProgress:
        """
        Download and index COMPLETE EPRS archive

        This is the main Phase 4 operation - systematically builds
        the entire historical archive.

        Args:
            year_from: Start year (default: 2009, when EPRS started)
            year_to: End year (default: current year)
            force_reindex: Force reindexing of existing publications

        Returns:
            Combined DownloadProgress for all years

        Example:
            downloader = EPRSArchiveDownloader()
            result = await downloader.download_full_archive()
            print(f"Indexed {result.total_indexed} publications")
        """
        if year_to is None:
            year_to = datetime.now().year

        logger.info(f"\n{'='*80}")
        logger.info(f"EPRS HISTORICAL ARCHIVE DOWNLOAD: {year_from}-{year_to}")
        logger.info(f"{'='*80}\n")

        # Initialize combined progress
        combined_progress = DownloadProgress(start_time=datetime.now())

        # Download year by year
        for year in range(year_from, year_to + 1):
            year_progress = await self.download_year(year, force_reindex)

            # Combine results
            combined_progress.total_found += year_progress.total_found
            combined_progress.total_downloaded += year_progress.total_downloaded
            combined_progress.total_enriched += year_progress.total_enriched
            combined_progress.total_indexed += year_progress.total_indexed
            combined_progress.total_skipped += year_progress.total_skipped
            combined_progress.total_failed += year_progress.total_failed
            combined_progress.errors.extend(year_progress.errors)

        combined_progress.end_time = datetime.now()

        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPLETE ARCHIVE DOWNLOAD FINISHED")
        logger.info(f"{'='*80}")
        logger.info(f"Years processed:  {year_from}-{year_to} ({year_to - year_from + 1} years)")
        logger.info(f"Total found:      {combined_progress.total_found}")
        logger.info(f"Total indexed:    {combined_progress.total_indexed}")
        logger.info(f"Total skipped:    {combined_progress.total_skipped}")
        logger.info(f"Total failed:     {combined_progress.total_failed}")
        logger.info(f"Success rate:     {combined_progress.success_rate:.1f}%")
        logger.info(f"Total duration:   {combined_progress.duration_seconds:.0f}s")
        logger.info(f"{'='*80}\n")

        if self.progress_file:
            self._save_progress(combined_progress)

        return combined_progress

    def _save_progress(self, progress: Optional[DownloadProgress] = None):
        """
        Save progress to JSON file

        Args:
            progress: Progress to save (uses self.progress if None)
        """
        if not self.progress_file:
            return

        progress_to_save = progress or self.progress

        try:
            progress_path = Path(self.progress_file)
            progress_path.parent.mkdir(parents=True, exist_ok=True)

            with open(progress_path, 'w') as f:
                json.dump(progress_to_save.to_dict(), f, indent=2)

            logger.debug(f"Saved progress to {self.progress_file}")

        except Exception as e:
            logger.warning(f"Failed to save progress: {str(e)}")

    def get_progress_stats(self) -> Dict[str, Any]:
        """
        Get current progress statistics

        Returns:
            Progress statistics dictionary
        """
        return self.progress.to_dict()

    async def download_by_topic(
        self,
        topic: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: int = 100,
        force_reindex: bool = False
    ) -> DownloadProgress:
        """
        Download publications about a specific topic

        Args:
            topic: Topic keyword (e.g., "artificial intelligence")
            year_from: Start year
            year_to: End year
            limit: Maximum publications
            force_reindex: Force reindexing

        Returns:
            DownloadProgress with results
        """
        logger.info(f"Downloading publications about '{topic}'")

        self.progress = DownloadProgress(start_time=datetime.now())

        try:
            # Query Cellar for topic
            cellar_publications = await self.archive_client.get_eprs_publications_by_topic(
                topic=topic,
                year_from=year_from,
                year_to=year_to,
                limit=limit
            )

            self.progress.total_found = len(cellar_publications)
            logger.info(f"Found {self.progress.total_found} publications about '{topic}'")

            # Process batch
            await self._process_batch(cellar_publications, force_reindex)

            self.progress.end_time = datetime.now()

            logger.info(f"\nTopic download complete:")
            logger.info(f"  Indexed: {self.progress.total_indexed}")
            logger.info(f"  Success rate: {self.progress.success_rate:.1f}%")

            return self.progress

        except Exception as e:
            error_msg = f"Topic download failed: {str(e)}"
            logger.error(error_msg)
            self.progress.errors.append(error_msg)
            self.progress.end_time = datetime.now()
            return self.progress

    async def close(self):
        """Close HTTP clients"""
        await self.archive_client.close()
        await self.enricher.close()
        logger.info("Closed EPRS Archive Downloader")


# Global singleton
_eprs_archive_downloader: Optional[EPRSArchiveDownloader] = None


def get_eprs_archive_downloader(
    enable_enrichment: bool = True,
    batch_size: int = 50
) -> EPRSArchiveDownloader:
    """
    Get global EPRS Archive Downloader instance

    Args:
        enable_enrichment: Enable full PDF content extraction
        batch_size: Publications per batch

    Returns:
        EPRSArchiveDownloader instance
    """
    global _eprs_archive_downloader

    if _eprs_archive_downloader is None:
        _eprs_archive_downloader = EPRSArchiveDownloader(
            enable_enrichment=enable_enrichment,
            batch_size=batch_size
        )

    return _eprs_archive_downloader
