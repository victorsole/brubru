"""
data.europa.eu Open Data Portal Scraper

PHASE 4 UPGRADE: Integrated with API clients
- Registry API (hub/repo) - Primary
- Search API (hub/search) - Secondary
- SPARQL endpoint - Advanced queries
- Web scraping as fallback

Scrapes EU open datasets from data.europa.eu
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_scraper import BaseScraper
from ..api_clients.data_europa_client import DataEuropaClient
from ...schemas.scrapers.scraper_schemas import OpenDataPortalDataset

logger = logging.getLogger(__name__)


class DataEuropaScraper(BaseScraper):
    """
    Scraper for data.europa.eu Open Data Portal.

    PHASE 4 UPGRADE:
    - Primary: Registry API (hub/repo)
    - Secondary: Search API (hub/search)
    - SPARQL endpoint for advanced queries
    - Fallback: Web scraping

    Key Features:
    - EU institution datasets (Parliament, Eurostat, Council, Agencies)
    - Dataset search and discovery
    - Catalogue browsing
    - Metadata quality metrics
    """

    def __init__(self, **kwargs):
        super().__init__(
            base_url="https://data.europa.eu",
            name="data.europa.eu",
            rate_limit_delay=1.0,
            **kwargs
        )

        # PHASE 4: Initialize API client
        self.api_client = DataEuropaClient()
        self.use_api = True

        logger.info("data.europa.eu Scraper initialized with API client")

    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search open datasets.

        PHASE 4: API first

        Args:
            query: Search query
            **kwargs: Additional parameters (publisher, format, country, theme, limit)

        Returns:
            List of datasets
        """
        if self.use_api:
            try:
                logger.info(f"Searching datasets via API: {query}")

                datasets = await self.api_client.search_datasets(
                    query=query,
                    publisher=kwargs.get('publisher'),
                    format=kwargs.get('format'),
                    country=kwargs.get('country'),
                    theme=kwargs.get('theme'),
                    limit=kwargs.get('limit', 50)
                )

                return datasets

            except Exception as e:
                logger.error(f"Dataset search failed: {str(e)}")

        return []

    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get dataset by ID.

        Args:
            document_id: Dataset identifier

        Returns:
            Dataset metadata
        """
        if self.use_api:
            try:
                logger.info(f"Fetching dataset: {document_id}")
                dataset = await self.api_client.get_dataset_by_id(document_id)
                return dataset or {}
            except Exception as e:
                logger.error(f"Failed to fetch dataset {document_id}: {str(e)}")

        return {}

    async def get_latest_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest dataset updates.

        Args:
            limit: Maximum results

        Returns:
            Latest datasets
        """
        if self.use_api:
            try:
                logger.info("Fetching latest dataset updates")
                # Could use trending or search with recent dates
                datasets = await self.api_client.search_datasets(limit=limit)
                return datasets
            except Exception as e:
                logger.error(f"Failed to fetch latest updates: {str(e)}")

        return []

    async def get_eu_institution_datasets(
        self,
        institution: str = "ep",
        limit: int = 50
    ) -> List[OpenDataPortalDataset]:
        """
        Get datasets from specific EU institution.

        Args:
            institution: Institution catalogue ID
                - ep: European Parliament
                - estat: Eurostat
                - consil: Council
                - eea-sdi: European Environment Agency
                - eeas: European External Action Service
                - europol: Europol
                - frontex: Frontex
            limit: Maximum results

        Returns:
            List of OpenDataPortalDataset objects
        """
        if not self.use_api:
            raise NotImplementedError("Requires API client")

        try:
            logger.info(f"Fetching datasets from {institution}")

            datasets = await self.api_client.get_eu_institution_datasets(
                institution=institution,
                limit=limit
            )

            # Convert to schema objects
            dataset_objects = []
            for ds in datasets:
                try:
                    dataset_obj = OpenDataPortalDataset(
                        source=self.name,
                        source_url=ds.get('landing_page') or ds.get('access_url') or f"https://data.europa.eu/data/datasets/{ds['id']}",
                        dataset_id=ds['id'],
                        title=ds['title'],
                        description=ds.get('description'),
                        publisher=ds.get('publisher', institution),
                        theme=ds.get('theme', []),
                        keywords=ds.get('keywords', []),
                        issued=datetime.fromisoformat(ds['issued']) if ds.get('issued') else None,
                        modified=datetime.fromisoformat(ds['modified']) if ds.get('modified') else None,
                        temporal_coverage=ds.get('temporal'),
                        spatial_coverage=ds.get('spatial', []),
                        distributions=ds.get('distributions', []),
                        access_url=ds.get('access_url'),
                        download_url=ds.get('download_url'),
                        format=ds.get('format'),
                        license=ds.get('license'),
                        contact_point=ds.get('contact_point')
                    )
                    dataset_objects.append(dataset_obj)
                except Exception as e:
                    logger.warning(f"Failed to convert dataset {ds.get('id')}: {str(e)}")
                    continue

            logger.info(f"Retrieved {len(dataset_objects)} datasets from {institution}")
            return dataset_objects

        except Exception as e:
            logger.error(f"Failed to fetch institution datasets: {str(e)}")
            return []

    async def get_parliament_datasets(self, limit: int = 20) -> List[OpenDataPortalDataset]:
        """Get European Parliament datasets"""
        return await self.get_eu_institution_datasets("ep", limit=limit)

    async def get_eurostat_datasets(self, limit: int = 50) -> List[OpenDataPortalDataset]:
        """Get Eurostat datasets"""
        return await self.get_eu_institution_datasets("estat", limit=limit)

    async def get_council_datasets(self, limit: int = 20) -> List[OpenDataPortalDataset]:
        """Get Council of the EU datasets"""
        return await self.get_eu_institution_datasets("consil", limit=limit)

    async def list_eu_catalogues(self) -> List[str]:
        """
        List all EU institution catalogues.

        Returns:
            List of catalogue IDs
        """
        if not self.use_api:
            raise NotImplementedError("Requires API client")

        try:
            logger.info("Listing EU institution catalogues")
            catalogues = await self.api_client.list_eu_institution_catalogues()
            return catalogues
        except Exception as e:
            logger.error(f"Failed to list catalogues: {str(e)}")
            return []

    async def search_by_theme(
        self,
        theme: str,
        limit: int = 50
    ) -> List[OpenDataPortalDataset]:
        """
        Search datasets by theme.

        Common themes:
        - agriculture
        - economy
        - education
        - energy
        - environment
        - government
        - health
        - transport

        Args:
            theme: Theme name
            limit: Maximum results

        Returns:
            List of datasets
        """
        if not self.use_api:
            raise NotImplementedError("Requires API client")

        try:
            logger.info(f"Searching datasets by theme: {theme}")

            datasets = await self.api_client.get_datasets_by_theme(
                theme=theme,
                limit=limit
            )

            # Convert to schema objects
            dataset_objects = []
            for ds in datasets:
                try:
                    dataset_obj = OpenDataPortalDataset(
                        source=self.name,
                        source_url=ds.get('landing_page') or ds.get('access_url') or f"https://data.europa.eu/data/datasets/{ds['id']}",
                        dataset_id=ds['id'],
                        title=ds['title'],
                        description=ds.get('description'),
                        publisher=ds.get('publisher', 'Unknown'),
                        theme=ds.get('theme', []),
                        keywords=ds.get('keywords', []),
                        issued=datetime.fromisoformat(ds['issued']) if ds.get('issued') else None,
                        modified=datetime.fromisoformat(ds['modified']) if ds.get('modified') else None,
                        temporal_coverage=ds.get('temporal'),
                        spatial_coverage=ds.get('spatial', []),
                        distributions=ds.get('distributions', []),
                        access_url=ds.get('access_url'),
                        download_url=ds.get('download_url'),
                        format=ds.get('format'),
                        license=ds.get('license'),
                        contact_point=ds.get('contact_point')
                    )
                    dataset_objects.append(dataset_obj)
                except Exception as e:
                    logger.warning(f"Failed to convert dataset: {str(e)}")
                    continue

            logger.info(f"Found {len(dataset_objects)} datasets for theme '{theme}'")
            return dataset_objects

        except Exception as e:
            logger.error(f"Theme search failed: {str(e)}")
            return []

    async def close(self):
        """Close API client connections"""
        if hasattr(self, 'api_client'):
            await self.api_client.close()
            logger.info("Closed data.europa.eu API client")
