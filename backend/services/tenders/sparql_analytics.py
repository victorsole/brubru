"""
SPARQL Analytics Service

Pre-built analytics queries for the Tenderator dashboard.
Uses TED SPARQL endpoint to gather aggregated statistics.

Queries:
- Tenders by buyer (buyer history)
- Award success rates by sector/CPV
- Average tender values by country/sector
- Most active contracting authorities
- Sector trends over time
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from dataclasses import dataclass

from .ted_sparql_client import TEDSPARQLClient, QueryCache

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsResult:
    """Container for analytics query results."""
    query_name: str
    data: List[Dict[str, Any]]
    total_count: int
    query_time_ms: float
    cached: bool = False
    error: Optional[str] = None


class SPARQLAnalytics:
    """
    Analytics service using SPARQL queries against TED Open Data.

    Provides pre-built analytics for:
    - Buyer analysis (history, success rates)
    - Sector analysis (CPV trends, values)
    - Geographic analysis (country breakdown)
    - Time-based trends
    """

    def __init__(self, cache_ttl: int = 3600):
        """
        Initialize analytics service.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.cache = QueryCache(default_ttl=cache_ttl)

    async def get_buyer_history(
        self,
        buyer_name: str,
        limit: int = 50
    ) -> AnalyticsResult:
        """
        Get all tenders published by a specific buyer.

        Useful for understanding a contracting authority's procurement patterns.

        Args:
            buyer_name: Name of the contracting authority
            limit: Maximum results

        Returns:
            AnalyticsResult with tender history
        """
        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?publicationNumber ?title ?publicationDate ?estimatedValue ?procedureType
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?publicationDate ;
                    epo:hasNoticePublicationNumber ?publicationNumber ;
                    epo:announcesRole [
                      a epo:Buyer ;
                      epo:playedBy [
                        epo:hasLegalName ?legalName
                      ]
                    ] ;
                    epo:refersToProcedure ?procedure .

            ?procedure dcterms:title ?title .

            OPTIONAL {{ ?procedure epo:hasEstimatedValue [ epo:hasAmountValue ?estimatedValue ] }}
            OPTIONAL {{ ?procedure epo:hasProcedureType [ skos:prefLabel ?procedureType ] }}

            FILTER(CONTAINS(LCASE(?legalName), LCASE("{buyer_name}")))
          }}
        }}
        ORDER BY DESC(?publicationDate)
        LIMIT {limit}
        """

        return await self._execute_analytics_query("buyer_history", query)

    async def get_award_success_by_cpv(
        self,
        cpv_prefix: str = "",
        months_back: int = 12
    ) -> AnalyticsResult:
        """
        Get award success rates by CPV sector.

        Args:
            cpv_prefix: CPV code prefix to filter (e.g., "72" for IT)
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with success rates by CPV
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        cpv_filter = ""
        if cpv_prefix:
            cpv_filter = f'FILTER(STRSTARTS(?cpvCode, "{cpv_prefix}"))'

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?cpvCode (COUNT(DISTINCT ?notice) as ?totalTenders)
               (COUNT(DISTINCT ?awardedNotice) as ?awardedTenders)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:refersToProcedure ?procedure .

            ?procedure epo:hasMainCPVCode ?cpvUri .
            ?cpvUri skos:notation ?cpvCode .

            OPTIONAL {{
              ?awardedNotice a epo:Notice ;
                            epo:refersToProcedure ?procedure ;
                            epo:hasNoticeType ?noticeType .
              ?noticeType skos:prefLabel "Contract award notice"@en .
            }}

            FILTER(?pubDate >= "{date_from}"^^xsd:date)
            {cpv_filter}
          }}
        }}
        GROUP BY ?cpvCode
        ORDER BY DESC(?totalTenders)
        LIMIT 50
        """

        return await self._execute_analytics_query("award_success_by_cpv", query)

    async def get_average_values_by_country(
        self,
        months_back: int = 12
    ) -> AnalyticsResult:
        """
        Get average tender values by country.

        Args:
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with average values per country
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX cccev: <http://data.europa.eu/m8g/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?country (AVG(?value) as ?avgValue) (COUNT(?notice) as ?tenderCount) (SUM(?value) as ?totalValue)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:announcesRole [
                      a epo:Buyer ;
                      epo:playedBy [
                        cccev:registeredAddress [
                          epo:hasCountryCode ?countryUri
                        ]
                      ]
                    ] ;
                    epo:refersToProcedure [
                      epo:hasEstimatedValue [
                        epo:hasAmountValue ?value
                      ]
                    ] .

            ?countryUri skos:prefLabel ?country .
            FILTER(LANG(?country) = "en")
            FILTER(?pubDate >= "{date_from}"^^xsd:date)
            FILTER(?value > 0)
          }}
        }}
        GROUP BY ?country
        ORDER BY DESC(?tenderCount)
        LIMIT 30
        """

        return await self._execute_analytics_query("average_values_by_country", query)

    async def get_average_values_by_sector(
        self,
        country: Optional[str] = None,
        months_back: int = 12
    ) -> AnalyticsResult:
        """
        Get average tender values by CPV sector.

        Args:
            country: Optional country filter
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with average values per sector
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        country_filter = ""
        if country:
            country_filter = f'?countryUri skos:prefLabel "{country}"@en .'

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX cccev: <http://data.europa.eu/m8g/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?cpvDivision ?cpvLabel (AVG(?value) as ?avgValue) (COUNT(?notice) as ?tenderCount)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:refersToProcedure ?procedure .

            ?procedure epo:hasMainCPVCode ?cpvUri ;
                      epo:hasEstimatedValue [ epo:hasAmountValue ?value ] .

            ?cpvUri skos:notation ?cpvCode ;
                   skos:prefLabel ?cpvLabel .
            FILTER(LANG(?cpvLabel) = "en")

            BIND(SUBSTR(?cpvCode, 1, 2) AS ?cpvDivision)

            {country_filter}

            FILTER(?pubDate >= "{date_from}"^^xsd:date)
            FILTER(?value > 0)
          }}
        }}
        GROUP BY ?cpvDivision ?cpvLabel
        ORDER BY DESC(?tenderCount)
        LIMIT 30
        """

        return await self._execute_analytics_query("average_values_by_sector", query)

    async def get_most_active_buyers(
        self,
        country: Optional[str] = None,
        months_back: int = 12,
        limit: int = 20
    ) -> AnalyticsResult:
        """
        Get most active contracting authorities.

        Args:
            country: Optional country filter
            months_back: Number of months to analyze
            limit: Maximum results

        Returns:
            AnalyticsResult with buyer activity ranking
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        country_filter = ""
        if country:
            country_filter = f'?countryUri skos:prefLabel "{country}"@en .'

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX cccev: <http://data.europa.eu/m8g/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?buyerName ?country (COUNT(DISTINCT ?notice) as ?tenderCount)
               (SUM(?value) as ?totalValue) (AVG(?value) as ?avgValue)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:announcesRole [
                      a epo:Buyer ;
                      epo:playedBy ?org
                    ] ;
                    epo:refersToProcedure ?procedure .

            ?org epo:hasLegalName ?buyerName .

            OPTIONAL {{
              ?org cccev:registeredAddress [ epo:hasCountryCode ?countryUri ] .
              ?countryUri skos:prefLabel ?country .
              FILTER(LANG(?country) = "en")
            }}

            OPTIONAL {{
              ?procedure epo:hasEstimatedValue [ epo:hasAmountValue ?value ] .
            }}

            {country_filter}

            FILTER(?pubDate >= "{date_from}"^^xsd:date)
          }}
        }}
        GROUP BY ?buyerName ?country
        ORDER BY DESC(?tenderCount)
        LIMIT {limit}
        """

        return await self._execute_analytics_query("most_active_buyers", query)

    async def get_sector_trends(
        self,
        cpv_prefix: str,
        months_back: int = 24
    ) -> AnalyticsResult:
        """
        Get tender volume trends for a CPV sector over time.

        Args:
            cpv_prefix: CPV code prefix (e.g., "72" for IT)
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with monthly trends
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?yearMonth (COUNT(DISTINCT ?notice) as ?tenderCount) (SUM(?value) as ?totalValue)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:refersToProcedure ?procedure .

            ?procedure epo:hasMainCPVCode ?cpvUri .
            ?cpvUri skos:notation ?cpvCode .

            OPTIONAL {{
              ?procedure epo:hasEstimatedValue [ epo:hasAmountValue ?value ] .
            }}

            BIND(CONCAT(STR(YEAR(?pubDate)), "-", STR(MONTH(?pubDate))) AS ?yearMonth)

            FILTER(STRSTARTS(?cpvCode, "{cpv_prefix}"))
            FILTER(?pubDate >= "{date_from}"^^xsd:date)
          }}
        }}
        GROUP BY ?yearMonth
        ORDER BY ?yearMonth
        """

        return await self._execute_analytics_query("sector_trends", query)

    async def get_procedure_type_distribution(
        self,
        country: Optional[str] = None,
        months_back: int = 12
    ) -> AnalyticsResult:
        """
        Get distribution of tenders by procedure type.

        Args:
            country: Optional country filter
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with procedure type distribution
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        country_filter = ""
        if country:
            country_filter = f'?countryUri skos:prefLabel "{country}"@en .'

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX cccev: <http://data.europa.eu/m8g/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?procedureType (COUNT(DISTINCT ?notice) as ?tenderCount) (AVG(?value) as ?avgValue)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:refersToProcedure ?procedure .

            ?procedure epo:hasProcedureType ?procTypeUri .
            ?procTypeUri skos:prefLabel ?procedureType .
            FILTER(LANG(?procedureType) = "en")

            OPTIONAL {{
              ?procedure epo:hasEstimatedValue [ epo:hasAmountValue ?value ] .
            }}

            {country_filter}

            FILTER(?pubDate >= "{date_from}"^^xsd:date)
          }}
        }}
        GROUP BY ?procedureType
        ORDER BY DESC(?tenderCount)
        """

        return await self._execute_analytics_query("procedure_type_distribution", query)

    async def get_sme_friendly_stats(
        self,
        max_value: float = 5_000_000,
        months_back: int = 12
    ) -> AnalyticsResult:
        """
        Get statistics on SME-friendly tenders (below value threshold).

        Args:
            max_value: Maximum tender value for SME filter
            months_back: Number of months to analyze

        Returns:
            AnalyticsResult with SME-friendly stats
        """
        date_from = (date.today() - timedelta(days=months_back * 30)).isoformat()

        query = f"""
        PREFIX epo: <http://data.europa.eu/a4g/ontology#>
        PREFIX cccev: <http://data.europa.eu/m8g/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        SELECT ?country (COUNT(DISTINCT ?notice) as ?smeFriendlyCount)
               (SUM(?value) as ?totalValue) (AVG(?value) as ?avgValue)
        WHERE {{
          GRAPH ?g {{
            ?notice a epo:Notice ;
                    epo:hasPublicationDate ?pubDate ;
                    epo:announcesRole [
                      a epo:Buyer ;
                      epo:playedBy [
                        cccev:registeredAddress [
                          epo:hasCountryCode ?countryUri
                        ]
                      ]
                    ] ;
                    epo:refersToProcedure [
                      epo:hasEstimatedValue [
                        epo:hasAmountValue ?value
                      ]
                    ] .

            ?countryUri skos:prefLabel ?country .
            FILTER(LANG(?country) = "en")
            FILTER(?pubDate >= "{date_from}"^^xsd:date)
            FILTER(?value > 0 && ?value <= {max_value})
          }}
        }}
        GROUP BY ?country
        ORDER BY DESC(?smeFriendlyCount)
        LIMIT 30
        """

        return await self._execute_analytics_query("sme_friendly_stats", query)

    async def _execute_analytics_query(
        self,
        query_name: str,
        query: str
    ) -> AnalyticsResult:
        """Execute analytics query with caching and error handling."""
        start_time = datetime.utcnow()

        # Check cache
        cached_result = self.cache.get(query)
        if cached_result is not None:
            return AnalyticsResult(
                query_name=query_name,
                data=cached_result.get("data", []),
                total_count=cached_result.get("total_count", 0),
                query_time_ms=0,
                cached=True
            )

        try:
            async with TEDSPARQLClient() as client:
                result = await client.query(query)

                bindings = result.get("results", {}).get("bindings", [])

                # Convert bindings to simple dicts
                data = []
                for binding in bindings:
                    row = {}
                    for key, val in binding.items():
                        row[key] = val.get("value")
                    data.append(row)

                query_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Cache the result
                self.cache.set(query, {
                    "data": data,
                    "total_count": len(data)
                })

                return AnalyticsResult(
                    query_name=query_name,
                    data=data,
                    total_count=len(data),
                    query_time_ms=query_time,
                    cached=False
                )

        except Exception as e:
            logger.error(f"Analytics query '{query_name}' failed: {e}")
            query_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return AnalyticsResult(
                query_name=query_name,
                data=[],
                total_count=0,
                query_time_ms=query_time,
                cached=False,
                error=str(e)
            )


# Convenience functions
async def get_buyer_tender_history(buyer_name: str, limit: int = 50) -> List[Dict]:
    """Get tender history for a specific buyer."""
    analytics = SPARQLAnalytics()
    result = await analytics.get_buyer_history(buyer_name, limit)
    return result.data


async def get_sector_statistics(cpv_prefix: str, months: int = 12) -> Dict[str, Any]:
    """Get statistics for a CPV sector."""
    analytics = SPARQLAnalytics()

    success_result = await analytics.get_award_success_by_cpv(cpv_prefix, months)
    trend_result = await analytics.get_sector_trends(cpv_prefix, months * 2)

    return {
        "award_rates": success_result.data,
        "trends": trend_result.data,
        "errors": [r.error for r in [success_result, trend_result] if r.error]
    }


async def get_dashboard_stats(months: int = 12) -> Dict[str, Any]:
    """Get aggregated stats for the Tenderator dashboard."""
    analytics = SPARQLAnalytics()

    country_result = await analytics.get_average_values_by_country(months)
    buyer_result = await analytics.get_most_active_buyers(months_back=months, limit=10)
    procedure_result = await analytics.get_procedure_type_distribution(months_back=months)
    sme_result = await analytics.get_sme_friendly_stats(months_back=months)

    return {
        "by_country": country_result.data,
        "top_buyers": buyer_result.data,
        "by_procedure": procedure_result.data,
        "sme_friendly": sme_result.data,
        "query_times": {
            "country": country_result.query_time_ms,
            "buyers": buyer_result.query_time_ms,
            "procedure": procedure_result.query_time_ms,
            "sme": sme_result.query_time_ms
        }
    }
