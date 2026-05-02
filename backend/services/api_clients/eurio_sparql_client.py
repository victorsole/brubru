"""
EURIO SPARQL client — Horizon Europe / FP7 / H2020 project tracking.

Phase 7 of docs/applications/euvoc.md.

Provenance honesty (May 2026):
  EURIO ("European Union Research Information Ontology") models the
  PROJECT side of EU research funding (consortia, deliverables,
  reporting periods, partner organisations) — the layer the
  eProcurement Ontology and CDM don't cover.

  The EURIO graph is **not exposed via the public Cellar SPARQL
  endpoint**. Live probes against `publications.europa.eu/webapi/rdf/sparql`
  for predicates under `http://data.europa.eu/s66/eurio` returned 0 rows
  + silent timeouts (verified 2026-05-02). EURIO data is hosted
  separately — likely at a dedicated EURIO portal or via CORDIS bulk
  Excel exports on `data.europa.eu/cordis*`.

  Until the right endpoint is identified, this client:
    - exposes the full EURIO method surface (find_projects_by_topic,
      get_project_consortium, etc.) so callers can wire against a
      stable signature
    - defaults to a placeholder endpoint and returns empty results
      gracefully (with `note='endpoint_unconfigured'`) instead of
      raising
    - takes an `endpoint_url` constructor arg so flipping to the real
      endpoint is a single config change

Public API (mirrors CellarSPARQLClient method shape):
    find_projects_by_topic(keyword, *, framework=None, limit=50)
    get_project_consortium(project_uri)
    get_project_deliverables(project_uri)
    get_project_funding_breakdown(project_uri)
    find_projects_by_organisation(org_name, *, limit=50)

Reference URIs (manifest):
    namespace = http://data.europa.eu/s66/eurio
    documentation = https://op.europa.eu/en/web/eu-vocabularies/eurio
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_sparql_client import BaseSPARQLClient

logger = logging.getLogger(__name__)

# Default placeholder — flip when the real endpoint is identified.
DEFAULT_EURIO_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
EURIO_NS = "http://data.europa.eu/s66/eurio#"


class EURIOClient(BaseSPARQLClient):
    """SPARQL client for EURIO research-information project data."""

    def __init__(self, endpoint_url: str = DEFAULT_EURIO_ENDPOINT, timeout: int = 60):
        super().__init__(endpoint_url=endpoint_url, timeout=timeout)
        self._endpoint_configured = endpoint_url != DEFAULT_EURIO_ENDPOINT

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # ------------------------------------------------------------------
    # Lookup methods — EURIO-shaped queries
    # ------------------------------------------------------------------

    async def find_projects_by_topic(
        self,
        keyword: str,
        *,
        framework: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Match projects by topic keyword (EuroSciVoc concept or free text).

        Args:
            keyword: free text or EuroSciVoc concept URI.
            framework: optional 'Horizon Europe' / 'H2020' / 'FP7' / 'Erasmus+'.
        """
        framework_filter = ""
        if framework:
            framework_filter = (
                f'?project <{EURIO_NS}underFrameworkProgramme> ?fp .\n'
                f'?fp rdfs:label ?fpLabel .\n'
                f'FILTER(LCASE(STR(?fpLabel)) = LCASE("{framework}"))\n'
            )

        kw_lower = keyword.lower()
        query = f"""
        PREFIX eurio: <{EURIO_NS}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?project ?title ?startDate ?endDate
        WHERE {{
            ?project a eurio:Project .
            ?project eurio:title ?title .
            OPTIONAL {{ ?project eurio:startDate ?startDate . }}
            OPTIONAL {{ ?project eurio:endDate ?endDate . }}
            FILTER(CONTAINS(LCASE(STR(?title)), "{kw_lower}"))
            {framework_filter}
        }}
        LIMIT {limit}
        """
        return await self._safe_query(query, label=f"find_projects_by_topic({keyword!r})")

    async def get_project_consortium(self, project_uri: str) -> Dict[str, Any]:
        """Return the partner organisations + roles for a project."""
        query = f"""
        PREFIX eurio: <{EURIO_NS}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?role ?org ?orgName ?country WHERE {{
            <{project_uri}> eurio:hasParticipant ?role .
            ?role eurio:participatingOrganisation ?org .
            OPTIONAL {{ ?org rdfs:label ?orgName . }}
            OPTIONAL {{ ?org eurio:country ?country . }}
        }}
        """
        return await self._safe_query(query, label=f"get_project_consortium({project_uri})")

    async def get_project_deliverables(self, project_uri: str) -> Dict[str, Any]:
        query = f"""
        PREFIX eurio: <{EURIO_NS}>

        SELECT ?deliverable ?title ?dueDate WHERE {{
            <{project_uri}> eurio:hasDeliverable ?deliverable .
            OPTIONAL {{ ?deliverable eurio:title ?title . }}
            OPTIONAL {{ ?deliverable eurio:dueDate ?dueDate . }}
        }}
        """
        return await self._safe_query(query, label=f"get_project_deliverables({project_uri})")

    async def get_project_funding_breakdown(self, project_uri: str) -> Dict[str, Any]:
        query = f"""
        PREFIX eurio: <{EURIO_NS}>

        SELECT ?totalCost ?euContribution ?currency WHERE {{
            <{project_uri}> eurio:totalCost ?totalCost .
            OPTIONAL {{ <{project_uri}> eurio:euContribution ?euContribution . }}
            OPTIONAL {{ <{project_uri}> eurio:currency ?currency . }}
        }}
        """
        return await self._safe_query(query, label=f"get_project_funding_breakdown({project_uri})")

    async def find_projects_by_organisation(
        self,
        org_name: str,
        *,
        limit: int = 50,
    ) -> Dict[str, Any]:
        org_lower = org_name.lower()
        query = f"""
        PREFIX eurio: <{EURIO_NS}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT DISTINCT ?project ?projectTitle ?role
        WHERE {{
            ?project a eurio:Project .
            ?project eurio:title ?projectTitle .
            ?project eurio:hasParticipant ?role .
            ?role eurio:participatingOrganisation ?org .
            ?org rdfs:label ?orgLabel .
            FILTER(CONTAINS(LCASE(STR(?orgLabel)), "{org_lower}"))
        }}
        LIMIT {limit}
        """
        return await self._safe_query(query, label=f"find_projects_by_organisation({org_name!r})")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _safe_query(self, query: str, *, label: str) -> Dict[str, Any]:
        """Run the query, swallow errors, return a JSON-shaped result.

        When the endpoint isn't configured, return an honest 'note' so
        callers can present the gap to users without raising.
        """
        out: Dict[str, Any] = {
            "results": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "label": label,
        }
        if not self._endpoint_configured:
            out["note"] = (
                "EURIO live endpoint not yet configured — see "
                "services/api_clients/eurio_sparql_client.py docstring. "
                "Pass endpoint_url to EURIOClient() to flip on live data."
            )
            return out
        try:
            rows = await self.select(query)
            out["results"] = rows
            out["count"] = len(rows)
            return out
        except Exception as e:  # noqa: BLE001
            logger.warning("EURIOClient: query failed (%s): %s", label, e)
            out["error"] = str(e)[:200]
            return out
