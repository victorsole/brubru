"""
data.europa.eu API Client

The official portal for European data:
- Dataset search and discovery
- Metadata registry
- SPARQL endpoint for linked data
- Data quality assessments (MQA)
- Organization and catalog information

Documentation:
- Portal: https://data.europa.eu/
- API: https://data.europa.eu/api/
- SPARQL: https://data.europa.eu/sparql
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat
from .base_sparql_client import BaseSPARQLClient, SPARQLQuery, SPARQLQueryType

logger = logging.getLogger(__name__)


class DatasetFormat(Enum):
    """Common dataset formats"""
    CSV = "CSV"
    JSON = "JSON"
    XML = "XML"
    RDF = "RDF"
    PDF = "PDF"
    XLS = "XLS"
    XLSX = "XLSX"
    API = "API"


class DataEuropaClient(BaseAPIClient):
    """
    Client for data.europa.eu open data portal

    Features:
    - Dataset search and discovery
    - Metadata retrieval
    - Organization catalogs
    - SPARQL queries
    - Data quality metrics (MQA)
    """

    BASE_URL = "https://data.europa.eu/api"
    SPARQL_ENDPOINT = "https://data.europa.eu/sparql"
    SEARCH_ENDPOINT = "/hub/search/datasets"
    REPO_BASE = "/hub/repo"  # Registry API base
    CATALOGUES_ENDPOINT = "/hub/repo/catalogues"
    DATASETS_ENDPOINT = "/hub/repo/datasets"

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        party_token: Optional[str] = None,
        sparql_endpoint: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize data.europa.eu client

        Args:
            endpoint_url: Override base URL
            party_token: Optional party token for higher limits
            sparql_endpoint: Override SPARQL endpoint
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL

        auth_type = AuthType.API_KEY if party_token else AuthType.NONE

        super().__init__(
            base_url=base_url,
            auth_type=auth_type,
            api_key=party_token,
            timeout=timeout
        )

        self.party_token = party_token

        # SPARQL client
        self.sparql = BaseSPARQLClient(
            endpoint_url=sparql_endpoint or self.SPARQL_ENDPOINT,
            max_results=10000,
            timeout=timeout
        )

        logger.info(f"Initialized data.europa.eu client (party token: {bool(party_token)})")

    async def search_datasets(
        self,
        query: Optional[str] = None,
        publisher: Optional[str] = None,
        format: Optional[DatasetFormat] = None,
        country: Optional[str] = None,
        theme: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search datasets

        Args:
            query: Search query text
            publisher: Filter by publisher
            format: Filter by format
            country: Filter by country code
            theme: Filter by theme/category
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of datasets
        """
        logger.info(f"Searching datasets: {query or 'all'}")

        params = {
            "limit": limit,
            "offset": offset,
            "filter": {}
        }

        if query:
            params["query"] = query

        if publisher:
            params["filter"]["publisher"] = publisher

        if format:
            params["filter"]["format"] = format.value

        if country:
            params["filter"]["country"] = country

        if theme:
            params["filter"]["theme"] = theme

        # Add party token if available
        headers = {}
        if self.party_token:
            headers["Authorization"] = f"Bearer {self.party_token}"

        try:
            response = await self.get(
                self.SEARCH_ENDPOINT,
                params=params,
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            data = response.json()
            datasets = []

            if "results" in data:
                for item in data["results"]:
                    datasets.append({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "publisher": item.get("publisher"),
                        "issued": item.get("issued"),
                        "modified": item.get("modified"),
                        "theme": item.get("theme", []),
                        "format": item.get("format", []),
                        "country": item.get("country"),
                        "access_url": item.get("access_url"),
                        "download_url": item.get("download_url")
                    })

            logger.info(f"Found {len(datasets)} datasets")
            return datasets

        except Exception as e:
            logger.error(f"Dataset search failed: {str(e)}")
            return []

    async def get_dataset_by_id(
        self,
        dataset_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get dataset metadata by ID

        Args:
            dataset_id: Dataset identifier

        Returns:
            Dataset metadata
        """
        logger.info(f"Fetching dataset: {dataset_id}")

        headers = {}
        if self.party_token:
            headers["Authorization"] = f"Bearer {self.party_token}"

        try:
            response = await self.get(
                f"{self.DATASET_ENDPOINT}/{dataset_id}",
                headers=headers,
                response_format=ResponseFormat.JSON
            )

            dataset = response.json()

            return {
                "id": dataset.get("id"),
                "title": dataset.get("title"),
                "description": dataset.get("description"),
                "publisher": dataset.get("publisher"),
                "issued": dataset.get("issued"),
                "modified": dataset.get("modified"),
                "theme": dataset.get("theme", []),
                "keywords": dataset.get("keywords", []),
                "language": dataset.get("language", []),
                "spatial": dataset.get("spatial"),
                "temporal": dataset.get("temporal"),
                "distributions": dataset.get("distributions", []),
                "contact_point": dataset.get("contact_point"),
                "landing_page": dataset.get("landing_page"),
                "license": dataset.get("license")
            }

        except Exception as e:
            logger.error(f"Failed to fetch dataset {dataset_id}: {str(e)}")
            return None

    async def get_datasets_by_publisher(
        self,
        publisher: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all datasets from a specific publisher

        Args:
            publisher: Publisher name or ID
            limit: Maximum results

        Returns:
            List of datasets
        """
        logger.info(f"Fetching datasets from publisher: {publisher}")

        return await self.search_datasets(
            publisher=publisher,
            limit=limit
        )

    async def get_datasets_by_theme(
        self,
        theme: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get datasets by theme/category

        Common themes: agriculture, economy, education, energy, environment,
                      government, health, transport

        Args:
            theme: Theme name
            limit: Maximum results

        Returns:
            List of datasets
        """
        logger.info(f"Fetching datasets for theme: {theme}")

        return await self.search_datasets(
            theme=theme,
            limit=limit
        )

    async def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get list of data providers/organizations

        Returns:
            List of organizations
        """
        logger.info("Fetching organizations")

        try:
            response = await self.get(
                "/hub/search/publishers",
                response_format=ResponseFormat.JSON
            )

            data = response.json()
            organizations = []

            if "results" in data:
                for org in data["results"]:
                    organizations.append({
                        "id": org.get("id"),
                        "name": org.get("name"),
                        "country": org.get("country"),
                        "type": org.get("type"),
                        "dataset_count": org.get("dataset_count"),
                        "homepage": org.get("homepage")
                    })

            logger.info(f"Found {len(organizations)} organizations")
            return organizations

        except Exception as e:
            logger.error(f"Failed to fetch organizations: {str(e)}")
            return []

    async def sparql_query_datasets(
        self,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Execute SPARQL query on data catalog

        Args:
            query: SPARQL query string

        Returns:
            Query results
        """
        logger.info("Executing SPARQL query on data catalog")

        try:
            results = await self.sparql.select(query)
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed: {str(e)}")
            return []

    async def get_eu_datasets_by_keyword(
        self,
        keyword: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search EU datasets by keyword

        Args:
            keyword: Search keyword
            limit: Maximum results

        Returns:
            List of datasets
        """
        logger.info(f"Searching EU datasets by keyword: {keyword}")

        return await self.search_datasets(
            query=keyword,
            limit=limit
        )

    async def get_high_value_datasets(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get High-Value Datasets (HVDs)

        HVDs are datasets with high potential for economic and social benefit.

        Args:
            category: HVD category (geospatial, earth_observation, environment,
                     meteorological, statistics, companies_and_company_ownership)

        Returns:
            List of HVDs
        """
        logger.info(f"Fetching High-Value Datasets (category: {category or 'all'})")

        # HVDs are tagged with specific theme
        return await self.search_datasets(
            theme=f"high_value_dataset_{category}" if category else "high_value_dataset",
            limit=200
        )

    async def get_dataset_quality_metrics(
        self,
        dataset_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get MQA (Metadata Quality Assessment) for a dataset

        Args:
            dataset_id: Dataset identifier

        Returns:
            Quality metrics
        """
        logger.info(f"Fetching quality metrics for dataset: {dataset_id}")

        try:
            response = await self.get(
                f"/mqa/datasets/{dataset_id}",
                response_format=ResponseFormat.JSON
            )

            metrics = response.json()

            return {
                "dataset_id": dataset_id,
                "overall_score": metrics.get("overall_score"),
                "findability": metrics.get("findability"),
                "accessibility": metrics.get("accessibility"),
                "interoperability": metrics.get("interoperability"),
                "reusability": metrics.get("reusability"),
                "contextuality": metrics.get("contextuality"),
                "last_assessed": metrics.get("last_assessed")
            }

        except Exception as e:
            logger.error(f"Failed to fetch quality metrics: {str(e)}")
            return None

    async def get_trending_datasets(
        self,
        period: str = "week",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get trending/popular datasets

        Args:
            period: Time period (day, week, month, year)
            limit: Maximum results

        Returns:
            List of trending datasets
        """
        logger.info(f"Fetching trending datasets ({period})")

        try:
            response = await self.get(
                f"/hub/trending/{period}",
                params={"limit": limit},
                response_format=ResponseFormat.JSON
            )

            data = response.json()
            return data.get("results", [])

        except Exception as e:
            logger.error(f"Failed to fetch trending datasets: {str(e)}")
            return []

    # =========================================================================
    # Registry API Methods (hub/repo)
    # =========================================================================

    async def list_catalogues(
        self,
        limit: int = 100,
        offset: int = 0,
        value_type: str = "identifiers"
    ) -> List[str]:
        """
        List available catalogues (data providers)

        Args:
            limit: Maximum results (1-5000)
            offset: Pagination offset
            value_type: Return type (identifiers, uriRefs, metadata)

        Returns:
            List of catalogue identifiers
        """
        logger.info(f"Fetching catalogues (limit={limit})")

        try:
            response = await self.get(
                self.CATALOGUES_ENDPOINT,
                params={
                    "limit": min(limit, 5000),
                    "offset": offset,
                    "valueType": value_type
                },
                response_format=ResponseFormat.JSON
            )

            catalogues = response.json()
            logger.info(f"Found {len(catalogues)} catalogues")
            return catalogues

        except Exception as e:
            logger.error(f"Failed to list catalogues: {str(e)}")
            return []

    async def get_catalogue_datasets(
        self,
        catalogue_id: str,
        limit: int = 100,
        offset: int = 0,
        value_type: str = "identifiers"
    ) -> List[str]:
        """
        Get datasets from a specific catalogue

        Args:
            catalogue_id: Catalogue ID (e.g., 'ep', 'estat', 'eurostat')
            limit: Maximum results
            offset: Pagination offset
            value_type: Return type (identifiers, uriRefs, metadata)

        Returns:
            List of dataset identifiers
        """
        logger.info(f"Fetching datasets from catalogue: {catalogue_id}")

        try:
            response = await self.get(
                f"{self.CATALOGUES_ENDPOINT}/{catalogue_id}/datasets",
                params={
                    "limit": min(limit, 5000),
                    "offset": offset,
                    "valueType": value_type
                },
                response_format=ResponseFormat.JSON
            )

            datasets = response.json()
            logger.info(f"Found {len(datasets)} datasets in {catalogue_id}")
            return datasets

        except Exception as e:
            logger.error(f"Failed to fetch datasets from {catalogue_id}: {str(e)}")
            return []

    async def get_eu_institution_datasets(
        self,
        institution: str = "ep",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get datasets from EU institutions

        Common institutions:
        - ep: European Parliament
        - estat: Eurostat
        - consil: Council
        - eeas: European External Action Service
        - europol: Europol
        - frontex: Frontex
        - eea-sdi: European Environment Agency

        Args:
            institution: Institution catalogue ID
            limit: Maximum results

        Returns:
            List of dataset metadata
        """
        logger.info(f"Fetching datasets from {institution}")

        dataset_ids = await self.get_catalogue_datasets(
            catalogue_id=institution,
            limit=limit,
            value_type="identifiers"
        )

        datasets = []
        for dataset_id in dataset_ids[:limit]:
            dataset = await self.get_dataset_by_id(dataset_id)
            if dataset:
                datasets.append(dataset)

        return datasets

    async def list_eu_institution_catalogues(self) -> List[str]:
        """
        List EU institution catalogues

        Returns:
            List of EU institution catalogue IDs
        """
        logger.info("Fetching EU institution catalogues")

        all_catalogues = await self.list_catalogues(limit=200)

        # Filter for EU institutions (common patterns)
        eu_patterns = [
            'ep', 'estat', 'consil', 'ec-', 'eu-', 'eeas', 'europol',
            'frontex', 'eea', 'efsa', 'ema', 'echa', 'cedefop', 'eurofound'
        ]

        eu_catalogues = [
            cat for cat in all_catalogues
            if any(pattern in cat.lower() for pattern in eu_patterns)
        ]

        logger.info(f"Found {len(eu_catalogues)} EU institution catalogues")
        return eu_catalogues

    async def get_parliament_datasets(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get datasets from European Parliament

        Returns:
            Parliament datasets
        """
        return await self.get_eu_institution_datasets("ep", limit=limit)

    async def get_eurostat_datasets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get datasets from Eurostat

        Returns:
            Eurostat datasets
        """
        return await self.get_eu_institution_datasets("estat", limit=limit)

    async def get_council_datasets(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get datasets from Council of the EU

        Returns:
            Council datasets
        """
        return await self.get_eu_institution_datasets("consil", limit=limit)

    # =========================================================================
    # Health & Utilities
    # =========================================================================

    async def health_check(self) -> bool:
        """
        Check if data.europa.eu API is accessible

        Returns:
            True if healthy
        """
        try:
            # Try listing catalogues
            catalogues = await self.list_catalogues(limit=1)
            return len(catalogues) > 0
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def close(self):
        """Close HTTP clients"""
        await super().close()
        await self.sparql.close()
        logger.info("Closed data.europa.eu client")
