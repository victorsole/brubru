"""
Base SPARQL Client for EU Institutional SPARQL Endpoints

Provides functionality for:
- SPARQL query building and execution
- Support for SELECT, CONSTRUCT, ASK, DESCRIBE queries
- Result parsing (JSON, XML, CSV, Turtle, N-Triples)
- Query validation
- Rate limiting and result set size limits
- Triple store interaction
"""

import logging
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import httpx
from urllib.parse import urlencode
import json
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class SPARQLResultFormat(Enum):
    """Supported SPARQL result formats"""
    JSON = "application/sparql-results+json"
    XML = "application/sparql-results+xml"
    CSV = "text/csv"
    TSV = "text/tab-separated-values"
    TURTLE = "text/turtle"
    RDF_XML = "application/rdf+xml"
    N_TRIPLES = "application/n-triples"
    JSON_LD = "application/ld+json"


class SPARQLQueryType(Enum):
    """SPARQL query types"""
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    ASK = "ASK"
    DESCRIBE = "DESCRIBE"


class SPARQLQuery:
    """
    SPARQL query builder with validation

    Example:
        query = SPARQLQuery(SPARQLQueryType.SELECT)
        query.add_prefix("cdm", "http://publications.europa.eu/ontology/cdm#")
        query.select(["?doc", "?title", "?date"])
        query.where([
            "?doc cdm:resource_legal_title ?title .",
            "?doc cdm:work_date_document ?date ."
        ])
        query.filter("?date > '2024-01-01'^^xsd:date")
        query.order_by("DESC(?date)")
        query.limit(100)
    """

    def __init__(self, query_type: SPARQLQueryType = SPARQLQueryType.SELECT):
        """
        Initialize SPARQL query builder

        Args:
            query_type: Type of SPARQL query
        """
        self.query_type = query_type
        self._prefixes: Dict[str, str] = {}
        self._select_vars: List[str] = []
        self._where_clauses: List[str] = []
        self._filter_clauses: List[str] = []
        self._optional_clauses: List[str] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._distinct: bool = False

    def add_prefix(self, prefix: str, namespace: str) -> 'SPARQLQuery':
        """Add namespace prefix"""
        self._prefixes[prefix] = namespace
        return self

    def select(self, variables: List[str]) -> 'SPARQLQuery':
        """Add SELECT variables"""
        if self.query_type != SPARQLQueryType.SELECT:
            raise ValueError("SELECT only valid for SELECT queries")
        self._select_vars = variables
        return self

    def where(self, clauses: List[str]) -> 'SPARQLQuery':
        """Add WHERE clauses (triple patterns)"""
        self._where_clauses.extend(clauses)
        return self

    def filter(self, condition: str) -> 'SPARQLQuery':
        """Add FILTER condition"""
        self._filter_clauses.append(condition)
        return self

    def optional(self, clauses: List[str]) -> 'SPARQLQuery':
        """Add OPTIONAL clause"""
        self._optional_clauses.extend(clauses)
        return self

    def order_by(self, expression: str) -> 'SPARQLQuery':
        """Add ORDER BY clause"""
        self._order_by = expression
        return self

    def limit(self, limit: int) -> 'SPARQLQuery':
        """Set LIMIT"""
        if limit <= 0:
            raise ValueError("LIMIT must be positive")
        self._limit = limit
        return self

    def offset(self, offset: int) -> 'SPARQLQuery':
        """Set OFFSET"""
        if offset < 0:
            raise ValueError("OFFSET must be non-negative")
        self._offset = offset
        return self

    def distinct(self, distinct: bool = True) -> 'SPARQLQuery':
        """Enable DISTINCT"""
        self._distinct = distinct
        return self

    def build(self) -> str:
        """
        Build final SPARQL query string

        Returns:
            Complete SPARQL query
        """
        parts = []

        # Prefixes
        for prefix, namespace in self._prefixes.items():
            parts.append(f"PREFIX {prefix}: <{namespace}>")

        if parts:
            parts.append("")  # Empty line after prefixes

        # Query type and modifiers
        query_start = self.query_type.value
        if self._distinct and self.query_type == SPARQLQueryType.SELECT:
            query_start = f"SELECT DISTINCT"

        # SELECT variables
        if self.query_type == SPARQLQueryType.SELECT:
            vars_str = " ".join(self._select_vars) if self._select_vars else "*"
            parts.append(f"{query_start} {vars_str}")
        else:
            parts.append(query_start)

        # WHERE clause
        if self._where_clauses or self._filter_clauses or self._optional_clauses:
            parts.append("WHERE {")

            # Main patterns
            for clause in self._where_clauses:
                parts.append(f"  {clause}")

            # OPTIONAL patterns
            if self._optional_clauses:
                parts.append("  OPTIONAL {")
                for clause in self._optional_clauses:
                    parts.append(f"    {clause}")
                parts.append("  }")

            # FILTER conditions
            for filter_clause in self._filter_clauses:
                parts.append(f"  FILTER ({filter_clause})")

            parts.append("}")

        # Solution modifiers
        if self._order_by:
            parts.append(f"ORDER BY {self._order_by}")

        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")

        return "\n".join(parts)


class BaseSPARQLClient:
    """
    Base client for querying SPARQL endpoints

    Supports:
    - SELECT, CONSTRUCT, ASK, DESCRIBE queries
    - Multiple result formats (JSON, XML, CSV, Turtle, etc.)
    - Query validation and optimization
    - Rate limiting and result size limits
    - Connection pooling
    """

    def __init__(
        self,
        endpoint_url: str,
        max_results: int = 10000,
        timeout: int = 60,
        user_agent: str = "Brubru/1.0 (EU Policy Intelligence; +https://brubru.beresol.eu)"
    ):
        """
        Initialize SPARQL client

        Args:
            endpoint_url: SPARQL endpoint URL
            max_results: Maximum results per query (safety limit)
            timeout: Query timeout in seconds
            user_agent: User agent string
        """
        self.endpoint_url = endpoint_url.rstrip('/')
        self.max_results = max_results
        self.timeout = timeout
        self.user_agent = user_agent

        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": user_agent}
        )

        logger.info(f"Initialized SPARQLClient for {endpoint_url}")

    def _validate_query(self, query: str) -> bool:
        """
        Validate SPARQL query syntax

        Args:
            query: SPARQL query string

        Returns:
            True if valid
        """
        # Basic validation
        query_upper = query.upper()

        # Check for query type
        valid_types = ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]
        has_valid_type = any(qt in query_upper for qt in valid_types)

        if not has_valid_type:
            logger.error("Query must contain SELECT, CONSTRUCT, ASK, or DESCRIBE")
            return False

        # Check for WHERE clause (required for most queries)
        if "SELECT" in query_upper or "CONSTRUCT" in query_upper:
            if "WHERE" not in query_upper:
                logger.warning("Query missing WHERE clause")

        return True

    def _get_accept_header(self, result_format: SPARQLResultFormat) -> str:
        """Get Accept header for result format"""
        return result_format.value

    async def query(
        self,
        query: Union[str, SPARQLQuery],
        result_format: SPARQLResultFormat = SPARQLResultFormat.JSON,
        default_graph_uri: Optional[str] = None,
        named_graph_uri: Optional[str] = None
    ) -> Union[Dict[str, Any], str]:
        """
        Execute SPARQL query

        Args:
            query: SPARQL query string or SPARQLQuery object
            result_format: Desired result format
            default_graph_uri: Default graph URI (optional)
            named_graph_uri: Named graph URI (optional)

        Returns:
            Query results (parsed if JSON/XML, raw string otherwise)
        """
        # Convert SPARQLQuery to string
        if isinstance(query, SPARQLQuery):
            query_str = query.build()
        else:
            query_str = query

        # Validate query
        if not self._validate_query(query_str):
            raise ValueError("Invalid SPARQL query")

        # Build query parameters
        params = {"query": query_str}

        if default_graph_uri:
            params["default-graph-uri"] = default_graph_uri

        if named_graph_uri:
            params["named-graph-uri"] = named_graph_uri

        # Set Accept header
        headers = {
            "Accept": self._get_accept_header(result_format)
        }

        logger.info(f"Executing SPARQL query on {self.endpoint_url}")
        logger.debug(f"Query: {query_str[:200]}...")

        try:
            # Use GET for short queries, POST for long ones
            if len(query_str) < 2000:
                response = await self.client.get(
                    self.endpoint_url,
                    params=params,
                    headers=headers
                )
            else:
                # POST with URL-encoded form data
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = await self.client.post(
                    self.endpoint_url,
                    data=urlencode(params),
                    headers=headers
                )

            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.error(f"SPARQL query failed: {str(e)}")
            raise

        # Parse response based on format
        if result_format == SPARQLResultFormat.JSON:
            return response.json()
        elif result_format == SPARQLResultFormat.XML:
            return ET.fromstring(response.text)
        else:
            return response.text

    async def select(
        self,
        query: Union[str, SPARQLQuery],
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results as list of dictionaries

        Args:
            query: SPARQL SELECT query
            limit: Override query limit (safety limit)

        Returns:
            List of result bindings
        """
        # Apply safety limit
        if isinstance(query, SPARQLQuery):
            if limit:
                query.limit(min(limit, self.max_results))
            elif not query._limit or query._limit > self.max_results:
                query.limit(self.max_results)

        result = await self.query(query, SPARQLResultFormat.JSON)

        # Parse JSON results
        if isinstance(result, dict) and "results" in result:
            bindings = result["results"].get("bindings", [])

            # Convert to simple dict format
            parsed_results = []
            for binding in bindings:
                row = {}
                for var, value_obj in binding.items():
                    row[var] = value_obj.get("value")
                parsed_results.append(row)

            logger.info(f"SPARQL SELECT returned {len(parsed_results)} results")
            return parsed_results

        return []

    async def ask(self, query: Union[str, SPARQLQuery]) -> bool:
        """
        Execute ASK query

        Args:
            query: SPARQL ASK query

        Returns:
            Boolean result
        """
        result = await self.query(query, SPARQLResultFormat.JSON)

        if isinstance(result, dict) and "boolean" in result:
            return result["boolean"]

        return False

    async def construct(
        self,
        query: Union[str, SPARQLQuery],
        result_format: SPARQLResultFormat = SPARQLResultFormat.TURTLE
    ) -> str:
        """
        Execute CONSTRUCT query

        Args:
            query: SPARQL CONSTRUCT query
            result_format: RDF serialization format

        Returns:
            RDF graph as string
        """
        return await self.query(query, result_format)

    async def describe(
        self,
        resource_uri: str,
        result_format: SPARQLResultFormat = SPARQLResultFormat.TURTLE
    ) -> str:
        """
        Execute DESCRIBE query for a resource

        Args:
            resource_uri: URI of resource to describe
            result_format: RDF serialization format

        Returns:
            RDF description as string
        """
        query = f"DESCRIBE <{resource_uri}>"
        return await self.query(query, result_format)

    async def count(self, query: Union[str, SPARQLQuery]) -> int:
        """
        Get count of results without fetching all data

        Args:
            query: SPARQL query to count

        Returns:
            Number of results
        """
        # Create count query
        if isinstance(query, SPARQLQuery):
            query_str = query.build()
        else:
            query_str = query

        # Wrap in COUNT query
        count_query = f"""
        SELECT (COUNT(*) as ?count)
        WHERE {{
            {query_str.split('WHERE')[1] if 'WHERE' in query_str.upper() else query_str}
        }}
        """

        result = await self.query(count_query, SPARQLResultFormat.JSON)

        if isinstance(result, dict) and "results" in result:
            bindings = result["results"].get("bindings", [])
            if bindings and "count" in bindings[0]:
                return int(bindings[0]["count"]["value"])

        return 0

    async def paginate(
        self,
        query: SPARQLQuery,
        page_size: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Execute query with pagination to handle large result sets

        Args:
            query: SPARQL query
            page_size: Results per page

        Returns:
            All results combined
        """
        all_results = []
        offset = 0

        while True:
            # Create paginated query
            page_query = SPARQLQuery(query.query_type)
            page_query._prefixes = query._prefixes
            page_query._select_vars = query._select_vars
            page_query._where_clauses = query._where_clauses
            page_query._filter_clauses = query._filter_clauses
            page_query._optional_clauses = query._optional_clauses
            page_query._order_by = query._order_by
            page_query.limit(page_size)
            page_query.offset(offset)

            # Fetch page
            results = await self.select(page_query)

            if not results:
                break

            all_results.extend(results)
            offset += page_size

            # Safety limit
            if len(all_results) >= self.max_results:
                logger.warning(f"Reached max results limit ({self.max_results})")
                break

            logger.debug(f"Fetched {len(results)} results (total: {len(all_results)})")

        return all_results

    async def health_check(self) -> bool:
        """
        Check if SPARQL endpoint is accessible

        Returns:
            True if endpoint is healthy
        """
        try:
            # Simple ASK query
            result = await self.ask("ASK { ?s ?p ?o }")
            return True
        except Exception as e:
            logger.error(f"SPARQL health check failed: {str(e)}")
            return False

    async def get_namespaces(self) -> Dict[str, str]:
        """
        Retrieve common namespace prefixes from endpoint

        Returns:
            Dictionary of prefix -> namespace URI
        """
        query = """
        SELECT DISTINCT ?prefix ?namespace
        WHERE {
            ?s ?p ?o .
            BIND(REPLACE(STR(?p), "^(.*[/#]).*$", "$1") AS ?namespace)
            BIND(REPLACE(STR(?p), "^.*[/#](.*)$", "$1") AS ?prefix)
        }
        LIMIT 100
        """

        try:
            results = await self.select(query, limit=100)
            namespaces = {r["prefix"]: r["namespace"] for r in results if r.get("prefix") and r.get("namespace")}
            return namespaces
        except Exception as e:
            logger.warning(f"Failed to retrieve namespaces: {str(e)}")
            return {}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("Closed SPARQL client")
