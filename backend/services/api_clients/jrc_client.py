"""
JRC API Client

Joint Research Centre (JRC) - European Commission's science and knowledge service:
- Data Catalogue - Research data and publications
- PVGIS (Photovoltaic Geographical Information System) - Solar energy data
- Research publications and reports

Documentation:
- JRC: https://joint-research-centre.ec.europa.eu/
- PVGIS: https://re.jrc.ec.europa.eu/pvg_tools/en/
- PVGIS API: https://joint-research-centre.ec.europa.eu/pvgis-photovoltaic-geographical-information-system/getting-started-pvgis/api-non-interactive-service_en
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat

logger = logging.getLogger(__name__)


class PVGISDatabase(Enum):
    """PVGIS radiation databases"""
    PVGIS_SARAH2 = "PVGIS-SARAH2"  # Europe, Africa, Asia (2005-2020)
    PVGIS_NSRDB = "PVGIS-NSRDB"  # Americas (1998-2020)
    PVGIS_ERA5 = "PVGIS-ERA5"  # Global (2005-2020)
    PVGIS_COSMO = "PVGIS-COSMO"  # Europe (2007-2020)


class JRCClient(BaseAPIClient):
    """
    Client for JRC APIs

    Features:
    - PVGIS solar radiation and PV performance data
    - Research data catalog
    - Publications search

    IMPORTANT: PVGIS has a strict 30 calls/second rate limit!
    """

    BASE_URL = "https://joint-research-centre.ec.europa.eu/api"
    PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2"

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        pvgis_endpoint: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize JRC client

        Args:
            endpoint_url: Override base URL
            pvgis_endpoint: Override PVGIS endpoint
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL

        # CRITICAL: PVGIS has 30 calls/second limit!
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.NONE,
            rate_limit_calls=30,
            rate_limit_period=1,  # 30 calls per 1 second!
            timeout=timeout
        )

        self.pvgis_endpoint = pvgis_endpoint or self.PVGIS_URL

        logger.info("Initialized JRC client (PVGIS rate limit: 30 calls/sec)")

    async def get_pvgis_hourly_radiation(
        self,
        latitude: float,
        longitude: float,
        year: Optional[int] = None,
        database: PVGISDatabase = PVGISDatabase.PVGIS_SARAH2
    ) -> Optional[Dict[str, Any]]:
        """
        Get hourly solar radiation data for a location

        Args:
            latitude: Latitude (-90 to 90)
            longitude: Longitude (-180 to 180)
            year: Specific year (None for typical year)
            database: Radiation database to use

        Returns:
            Hourly radiation data
        """
        logger.info(f"Fetching PVGIS hourly radiation for ({latitude}, {longitude})")

        params = {
            "lat": latitude,
            "lon": longitude,
            "raddatabase": database.value,
            "outputformat": "json"
        }

        if year:
            params["year"] = year

        try:
            response = await self.client.get(
                f"{self.pvgis_endpoint}/seriescalc",
                params=params
            )
            response.raise_for_status()

            data = response.json()

            return {
                "location": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "inputs": data.get("inputs"),
                "outputs": data.get("outputs"),
                "meta": data.get("meta")
            }

        except Exception as e:
            logger.error(f"PVGIS hourly radiation fetch failed: {str(e)}")
            return None

    async def get_pvgis_monthly_radiation(
        self,
        latitude: float,
        longitude: float,
        database: PVGISDatabase = PVGISDatabase.PVGIS_SARAH2
    ) -> Optional[Dict[str, Any]]:
        """
        Get monthly solar radiation averages for a location

        Args:
            latitude: Latitude
            longitude: Longitude
            database: Radiation database

        Returns:
            Monthly radiation data
        """
        logger.info(f"Fetching PVGIS monthly radiation for ({latitude}, {longitude})")

        params = {
            "lat": latitude,
            "lon": longitude,
            "raddatabase": database.value,
            "outputformat": "json"
        }

        try:
            response = await self.client.get(
                f"{self.pvgis_endpoint}/MRcalc",
                params=params
            )
            response.raise_for_status()

            data = response.json()

            return {
                "location": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "monthly_data": data.get("outputs", {}).get("monthly"),
                "yearly_average": data.get("outputs", {}).get("totals"),
                "meta": data.get("meta")
            }

        except Exception as e:
            logger.error(f"PVGIS monthly radiation fetch failed: {str(e)}")
            return None

    async def get_pvgis_pv_performance(
        self,
        latitude: float,
        longitude: float,
        pv_capacity_kw: float = 1.0,
        system_loss: float = 14.0,
        slope: int = 35,
        azimuth: int = 0,
        database: PVGISDatabase = PVGISDatabase.PVGIS_SARAH2
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate PV system performance

        Args:
            latitude: Latitude
            longitude: Longitude
            pv_capacity_kw: PV peak power in kW
            system_loss: System losses in %
            slope: Tilt angle (0-90 degrees)
            azimuth: Orientation (0=south, 90=west, -90=east)
            database: Radiation database

        Returns:
            PV performance data
        """
        logger.info(f"Calculating PV performance for ({latitude}, {longitude})")

        params = {
            "lat": latitude,
            "lon": longitude,
            "peakpower": pv_capacity_kw,
            "loss": system_loss,
            "angle": slope,
            "aspect": azimuth,
            "raddatabase": database.value,
            "outputformat": "json"
        }

        try:
            response = await self.client.get(
                f"{self.pvgis_endpoint}/PVcalc",
                params=params
            )
            response.raise_for_status()

            data = response.json()

            return {
                "location": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "inputs": data.get("inputs"),
                "monthly_production": data.get("outputs", {}).get("monthly"),
                "yearly_production": data.get("outputs", {}).get("totals"),
                "meta": data.get("meta")
            }

        except Exception as e:
            logger.error(f"PVGIS PV performance calculation failed: {str(e)}")
            return None

    async def health_check(self) -> bool:
        """
        Check if JRC APIs are accessible

        Returns:
            True if healthy
        """
        try:
            # Test PVGIS with Brussels coordinates
            result = await self.get_pvgis_monthly_radiation(50.85, 4.35)
            return result is not None
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
