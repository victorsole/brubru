"""
Commission Document Register API Client.

HTTP client for the European Commission Register of Commission Documents at
https://ec.europa.eu/transparency/documents-register/

The register contains all Commission documents produced since 1 January 2001:
COM (legislative proposals), SWD (impact assessments), SEC (internal),
C (delegated/implementing acts), JOIN (CFSP joint texts), OJ, PV (minutes).

API Status (February 2026):
- Portal is a JavaScript SPA backed by a REST API
- API base: /transparency/documents-register/api/
- API requires browser-like headers (User-Agent + Referer)
- Working endpoints:
    /api/search/{reference}?lang=en  (individual document lookup)
    /api/search/{reference}/related  (related documents)
    /api/search/{reference}/correctedBy (corrections)
    /api/topDocuments/{category}     (homepage widget, 3 items)
    /api/maintenance                 (health check, returns null when OK)
- Still 503:
    /api/search?category=COM&...     (paginated search)
- Title is inside attachments[0].linguisticVersions.{lang}.title

Architecture:
- Discovery: EUR-Lex RSS (COM, OJ) + CELLAR SPARQL (SWD) for bulk document finding
- Enrichment: RegDoc API /search/{ref} for filling in titles, DGs, languages
- When paginated search returns, it can optionally replace discovery too

Future Integration Points:
  - PV (Commission minutes) -> Predictions tab (early signal of College agenda)
  - PV (Commission minutes) -> EU Calendar feature (future, all institutions)
  - COM/SWD/C trackable -> My EU Bubble > My Files tab
  - COM proposals -> Context builder (Tier 1 source, legislative pipeline)

Created: February 2026
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from schemas.scrapers.commission_doc_register_schemas import (
    CommissionDocType,
    CommissionDocItem,
    CommissionDocDetail,
    CommissionDocSearchParams,
    COMMISSION_DOC_TYPE_LABELS,
)

logger = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    """Raised when the RegDoc API is unavailable (503)."""
    pass


class CommissionDocRegisterClient:
    """
    HTTP client for the EC Register of Commission Documents API.

    Features:
    - Async HTTP requests with aiohttp
    - Rate limiting (3-second delay between requests)
    - In-memory response caching (6-hour TTL)
    - Health check for API availability
    - Stub methods ready for implementation when API is live

    Usage:
        client = get_commission_doc_register_client()

        # Check if API is available
        available = await client.check_api_availability()

        # Get known document types (always works)
        types = await client.get_document_types()

        # Search documents (stub - raises until API is live)
        results = await client.search_documents(CommissionDocSearchParams(doc_type="COM"))
    """

    BASE_URL = "https://ec.europa.eu/transparency/documents-register"
    API_BASE = "https://ec.europa.eu/transparency/documents-register/api"

    # Known endpoint patterns (discovered during Feb 2026 investigation)
    ENDPOINTS = {
        'search_v1': '/v1/search',
        'search_v2': '/v2/search',
        'search': '/search',
        'document': '/v1/document',
        'types': '/v1/types',
        'services': '/v1/services',
    }

    # Rate limiting (EC sites need conservative rate)
    RATE_LIMIT_DELAY = 3.0
    TIMEOUT = 30

    # Browser-like headers (required by EC server)
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    )
    REFERER = "https://ec.europa.eu/transparency/documents-register/"

    def __init__(self):
        self._last_request_time: Optional[float] = None
        self._request_lock = asyncio.Lock()
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._cache_ttl = 21600  # 6 hours

        # Track availability to avoid hammering a down service
        self._last_availability_check: Optional[datetime] = None
        self._last_availability_result: Optional[bool] = None
        self._availability_cache_ttl = 300  # Re-check every 5 minutes

        logger.info("[START] CommissionDocRegisterClient initialized (stub mode)")

    # =========================================================================
    # Infrastructure (rate limiting, caching, HTTP)
    # =========================================================================

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._request_lock:
            if self._last_request_time is not None:
                elapsed = asyncio.get_event_loop().time() - self._last_request_time
                if elapsed < self.RATE_LIMIT_DELAY:
                    wait_time = self.RATE_LIMIT_DELAY - elapsed
                    logger.debug(f"Rate limiting, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key in self._cache:
            cached_at, data = self._cache[cache_key]
            if (datetime.now() - cached_at).total_seconds() < self._cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return data
            else:
                del self._cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, data: Any):
        """Save data to cache."""
        self._cache[cache_key] = (datetime.now(), data)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._last_availability_check = None
        self._last_availability_result = None
        logger.info("[OK] Cache cleared")

    async def _fetch_json(
        self,
        url: str,
        params: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch URL and parse JSON response.

        Args:
            url: URL to fetch
            params: Query parameters
            use_cache: Whether to use cached response

        Returns:
            Parsed JSON as dict

        Raises:
            ServiceUnavailableError: If API returns 503
            aiohttp.ClientError: For other HTTP errors
        """
        cache_key = f"{url}:{str(params)}"
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached:
                return cached

        await self._rate_limit()

        headers = {
            'User-Agent': self.USER_AGENT,
            'Referer': self.REFERER,
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        timeout = ClientTimeout(total=self.TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"Fetching {url}")
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 503:
                        body = await response.text()
                        raise ServiceUnavailableError(
                            f"EC RegDoc API returned 503 Service Unavailable. "
                            f"URL: {url} | Response: {body[:200]}"
                        )

                    response.raise_for_status()
                    data = await response.json()

                    if use_cache:
                        self._save_to_cache(cache_key, data)

                    logger.info(f"[OK] Fetched {url}")
                    return data

        except ServiceUnavailableError:
            raise
        except aiohttp.ClientError as e:
            logger.error(f"[ERROR] Failed to fetch {url}: {e}")
            raise

    # =========================================================================
    # Live methods (work immediately)
    # =========================================================================

    async def check_api_availability(self) -> bool:
        """
        Check whether the RegDoc API is currently available.

        Uses the /maintenance endpoint as a health check (returns null when OK).
        Caches result for 5 minutes to avoid hammering.

        Returns:
            True if the API responds with a non-error status, False otherwise.
        """
        # Return cached result if recent
        if (
            self._last_availability_check is not None
            and self._last_availability_result is not None
        ):
            elapsed = (datetime.now() - self._last_availability_check).total_seconds()
            if elapsed < self._availability_cache_ttl:
                return self._last_availability_result

        headers = {
            'User-Agent': self.USER_AGENT,
            'Referer': self.REFERER,
            'Accept': 'application/json',
        }
        timeout = ClientTimeout(total=10)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.API_BASE}/maintenance",
                    headers=headers
                ) as response:
                    available = response.status == 200
                    self._last_availability_check = datetime.now()
                    self._last_availability_result = available
                    if available:
                        logger.info("[OK] RegDoc API is available")
                    else:
                        logger.info(f"[INFO] RegDoc API returned {response.status}")
                    return available

        except Exception as e:
            logger.debug(f"[INFO] RegDoc API unavailable: {e}")
            self._last_availability_check = datetime.now()
            self._last_availability_result = False
            return False

    async def get_document_types(self) -> List[Dict[str, str]]:
        """
        Return the known Commission document types.

        This method works immediately (no API call needed) and returns
        the static list of document types from the schema enum.

        Returns:
            List of dicts with 'code', 'label' keys.
        """
        return [
            {"code": doc_type.value, "label": COMMISSION_DOC_TYPE_LABELS[doc_type]}
            for doc_type in CommissionDocType
        ]

    # =========================================================================
    # Live API methods (individual document lookup)
    # =========================================================================

    async def fetch_document_by_reference(
        self,
        reference: str,
        lang: str = "en"
    ) -> Optional[CommissionDocItem]:
        """
        Fetch a single document from the RegDoc API by reference.

        Uses the working endpoint: GET /search/{reference}?lang={lang}

        Args:
            reference: Document reference (e.g. "SWD(2025)420", "COM(2025)87")
            lang: Language code for response (default: "en")

        Returns:
            CommissionDocItem with full metadata, or None if not found.
        """
        from urllib.parse import quote
        encoded_ref = quote(reference, safe='')
        url = f"{self.API_BASE}/search/{encoded_ref}"

        try:
            data = await self._fetch_json(url, params={'lang': lang})
            if not data:
                return None
            return self._parse_api_document(data, lang=lang)
        except ServiceUnavailableError:
            logger.info(f"[INFO] RegDoc API 503 for {reference}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch {reference}: {e}")
            return None

    async def fetch_related_documents(
        self,
        reference: str,
        lang: str = "en"
    ) -> List[CommissionDocItem]:
        """
        Fetch documents related to a given reference.

        Uses: GET /search/{reference}/related?lang={lang}

        Args:
            reference: Document reference.
            lang: Language code.

        Returns:
            List of related CommissionDocItems.
        """
        from urllib.parse import quote
        encoded_ref = quote(reference, safe='')
        url = f"{self.API_BASE}/search/{encoded_ref}/related"

        try:
            data = await self._fetch_json(url, params={'lang': lang})
            if not data or not isinstance(data, list):
                return []
            return [
                doc for doc in
                (self._parse_api_document(item, lang=lang) for item in data)
                if doc is not None
            ]
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch related docs for {reference}: {e}")
            return []

    def _parse_api_document(
        self,
        raw: Dict[str, Any],
        lang: str = "en"
    ) -> Optional[CommissionDocItem]:
        """
        Parse a RegDoc API response into a CommissionDocItem.

        Title is extracted from attachments[0].linguisticVersions.{lang}.title
        (the top-level 'title' field is always null in the API).
        """
        try:
            reference = raw.get('reference', '')
            if not reference:
                return None

            # Extract title from attachments
            title = ''
            languages = []
            attachments = raw.get('attachments', [])
            for att in attachments:
                if att.get('main'):
                    ling_versions = att.get('linguisticVersions', {})
                    languages = [code.upper() for code in ling_versions.keys()]
                    # Prefer requested language, fall back to first available
                    if lang in ling_versions:
                        title = ling_versions[lang].get('title', '')
                    elif ling_versions:
                        first_lang = next(iter(ling_versions))
                        title = ling_versions[first_lang].get('title', '')
                    break

            if not title:
                title = reference

            # Map category to doc_type
            category = raw.get('category', '')
            doc_type_map = {
                'COM': CommissionDocType.COM,
                'SWD': CommissionDocType.SWD,
                'SEC': CommissionDocType.SEC,
                'C': CommissionDocType.C,
                'JOIN': CommissionDocType.JOIN,
                'OJ': CommissionDocType.OJ,
                'PV': CommissionDocType.PV,
            }
            doc_type = doc_type_map.get(category, CommissionDocType.COM)

            # Parse date
            pub_date = None
            date_str = raw.get('date')
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass

            return CommissionDocItem(
                reference=reference,
                title=title,
                doc_type=doc_type,
                publication_date=pub_date,
                dg_responsible=raw.get('responsibleDepartment'),
                languages=languages if languages else ['EN'],
                portal_url=f"{self.BASE_URL}/detail/{reference}",
            )

        except Exception as e:
            logger.error(f"[ERROR] Failed to parse API document: {e}")
            return None

    # =========================================================================
    # Stub methods (ready for implementation when API is live)
    # =========================================================================

    async def _ensure_available(self):
        """
        Check API availability and raise if unavailable.

        Raises:
            ServiceUnavailableError: If the API is not responding.
        """
        available = await self.check_api_availability()
        if not available:
            raise ServiceUnavailableError(
                "EC Register of Commission Documents API is currently unavailable (503). "
                "This stub client will work when the API returns to service. "
                "Monitor status at: https://ec.europa.eu/transparency/documents-register/"
            )

    async def search_documents(
        self,
        params: CommissionDocSearchParams
    ) -> List[CommissionDocItem]:
        """
        Search the Register of Commission Documents.

        Args:
            params: Search parameters (doc_type, DG, date range, text, etc.)

        Returns:
            List of matching documents.

        Raises:
            ServiceUnavailableError: If the API is not available.
            NotImplementedError: If the API is available but parsing is not yet implemented.

        Implementation notes (for when API is live):
            - Try endpoints in order: /v2/search, /v1/search, /search
            - Map CommissionDocSearchParams fields to API query params
            - Parse JSON response into CommissionDocItem list
            - Expected params: documentType, serviceCode, year, dateFrom, dateTo,
              searchText, language, page, size, sortBy, orderBy
        """
        await self._ensure_available()

        # --- Actual implementation goes here when API is live ---
        # Suggested approach:
        #
        # api_params = {
        #     'page': params.page,
        #     'size': params.limit,
        #     'sortBy': 'dateDocument',
        #     'orderBy': 'DESC',
        #     'language': params.language,
        # }
        # if params.doc_type:
        #     api_params['documentType'] = params.doc_type
        # if params.dg:
        #     api_params['serviceCode'] = params.dg
        # if params.year:
        #     api_params['year'] = params.year
        # if params.search_text:
        #     api_params['searchText'] = params.search_text
        # if params.date_from:
        #     api_params['dateFrom'] = params.date_from.isoformat()
        # if params.date_to:
        #     api_params['dateTo'] = params.date_to.isoformat()
        #
        # data = await self._fetch_json(f"{self.API_BASE}/v2/search", params=api_params)
        # return [self._parse_doc_item(item) for item in data.get('results', [])]

        raise NotImplementedError(
            "RegDoc API is available but search_documents() parsing is not yet implemented. "
            "Inspect the API response structure and implement _parse_doc_item()."
        )

    async def get_document_detail(
        self,
        reference: str
    ) -> Optional[CommissionDocDetail]:
        """
        Fetch full details for a specific Commission document.

        Args:
            reference: Document reference (e.g. "COM(2021) 206 final")

        Returns:
            Full document detail, or None if not found.

        Raises:
            ServiceUnavailableError: If the API is not available.
            NotImplementedError: If the API is available but parsing is not yet implemented.

        Implementation notes (for when API is live):
            - Endpoint: /v1/document?reference={ref}
            - URL-encode the reference (parentheses, spaces)
            - Parse JSON into CommissionDocDetail
        """
        await self._ensure_available()

        # --- Actual implementation goes here when API is live ---
        # from urllib.parse import quote
        #
        # encoded_ref = quote(reference)
        # data = await self._fetch_json(
        #     f"{self.API_BASE}/v1/document",
        #     params={'reference': reference}
        # )
        # if not data:
        #     return None
        # return self._parse_doc_detail(data)

        raise NotImplementedError(
            "RegDoc API is available but get_document_detail() parsing is not yet implemented. "
            "Inspect the API response for a single document and implement _parse_doc_detail()."
        )

    async def get_latest_documents(
        self,
        doc_type: Optional[CommissionDocType] = None,
        days: int = 7
    ) -> List[CommissionDocItem]:
        """
        Fetch the most recent Commission documents.

        Convenience method that wraps search_documents with a date range filter.

        Args:
            doc_type: Filter by document type (None for all types)
            days: How many days back to search

        Returns:
            List of recent documents, sorted by date descending.

        Raises:
            ServiceUnavailableError: If the API is not available.
            NotImplementedError: If the API is available but parsing is not yet implemented.
        """
        params = CommissionDocSearchParams(
            doc_type=doc_type,
            date_from=date.today() - timedelta(days=days),
            date_to=date.today(),
            limit=50,
        )
        return await self.search_documents(params)

    async def get_services_list(self) -> List[Dict[str, str]]:
        """
        Fetch the list of DGs/services from the register.

        Falls back to the known DG list from ec_consultations if
        the API is unavailable.

        Returns:
            List of dicts with 'code' and 'name' keys.
        """
        available = await self.check_api_availability()

        if not available:
            # Fallback: return known DGs from the consultations knowledge base
            logger.info("[INFO] RegDoc API unavailable, using DG fallback list")
            try:
                from knowledge_base.ec_consultations import DG_BY_CODE
                return [
                    {"code": code, "name": dg.name}
                    for code, dg in DG_BY_CODE.items()
                ]
            except ImportError:
                logger.warning("[WARN] Could not import DG fallback data")
                return []

        # --- Actual implementation goes here when API is live ---
        # data = await self._fetch_json(f"{self.API_BASE}/v1/services")
        # return [
        #     {"code": svc.get("code", ""), "name": svc.get("name", "")}
        #     for svc in data.get("services", [])
        # ]

        raise NotImplementedError(
            "RegDoc API is available but get_services_list() parsing is not yet implemented."
        )

    # =========================================================================
    # Parser stubs (to be implemented when API response structure is known)
    # =========================================================================

    def _parse_doc_item(self, raw: Dict[str, Any]) -> CommissionDocItem:
        """
        Parse a raw API response item into a CommissionDocItem.

        To implement: inspect the actual JSON structure returned by the
        /v2/search endpoint and map fields accordingly.

        Expected fields (guessed from SPA URL params):
            - reference, title, dateDocument, documentType
            - serviceCode (DG), languages[], procedureReference
        """
        raise NotImplementedError("Implement after inspecting live API response")

    def _parse_doc_detail(self, raw: Dict[str, Any]) -> CommissionDocDetail:
        """
        Parse a raw API response into a CommissionDocDetail.

        To implement: inspect the actual JSON structure returned by the
        /v1/document endpoint.
        """
        raise NotImplementedError("Implement after inspecting live API response")

    # =========================================================================
    # EUR-Lex fallback (works even while RegDoc API is down)
    # =========================================================================

    async def get_latest_com_proposals_via_eurlex(
        self,
        days: int = 7
    ) -> List[CommissionDocItem]:
        """
        Fetch latest COM proposals via the EUR-Lex RSS feed (rssId=161).

        This is the primary fallback when the RegDoc API is unavailable.
        Uses the existing EURLexClient which has a working RSS feed for
        Commission proposals.

        Args:
            days: How many days back to search.

        Returns:
            List of CommissionDocItem from EUR-Lex RSS data.
        """
        import re
        from .eurlex_client import EURLexClient

        client = EURLexClient()
        try:
            items = await client.get_latest_commission_proposals(days=days)
            results = []
            for item in items:
                # Extract COM reference from title or CELEX
                reference = item.get('celex', '')
                title = item.get('title', '')

                # Try to extract COM(YYYY) NNN from title
                com_match = re.search(r'COM\(\d{4}\)\s*\d+', title)
                if com_match:
                    reference = com_match.group(0)

                results.append(CommissionDocItem(
                    reference=reference,
                    title=title,
                    doc_type=CommissionDocType.COM,
                    publication_date=item.get('date'),
                    dg_responsible=None,
                    languages=['EN'],
                    portal_url=item.get('url'),
                ))
            logger.info(f"[OK] EUR-Lex fallback returned {len(results)} COM proposals")
            return results
        except Exception as e:
            logger.error(f"[ERROR] EUR-Lex fallback failed: {e}")
            return []
        finally:
            await client.close()

    async def get_latest_legislation_via_eurlex(
        self,
        days: int = 7
    ) -> List[CommissionDocItem]:
        """
        Fetch latest adopted legislation via EUR-Lex RSS feed (rssId=162).

        Fallback for OJ-type documents (adopted regulations, directives,
        decisions from Parliament and Council).

        Args:
            days: How many days back to search.

        Returns:
            List of CommissionDocItem from EUR-Lex RSS data.
        """
        from .eurlex_client import EURLexClient

        client = EURLexClient()
        try:
            items = await client.get_latest_legislation(days=days)
            results = []
            for item in items:
                results.append(CommissionDocItem(
                    reference=item.get('celex', ''),
                    title=item.get('title', ''),
                    doc_type=CommissionDocType.OJ,
                    publication_date=item.get('date'),
                    dg_responsible=None,
                    languages=['EN'],
                    portal_url=item.get('url'),
                ))
            logger.info(f"[OK] EUR-Lex fallback returned {len(results)} legislation items")
            return results
        except Exception as e:
            logger.error(f"[ERROR] EUR-Lex legislation fallback failed: {e}")
            return []
        finally:
            await client.close()

    async def get_latest_swd_via_sparql(
        self,
        days: int = 30,
        limit: int = 100
    ) -> List[CommissionDocItem]:
        """
        Fetch latest SWD (Staff Working Documents) via CELLAR SPARQL.

        SWD documents have CELEX numbers starting with '5' (preparatory acts)
        and type code 'SC' (e.g. 52024SC0305 = SWD(2024) 305).

        Uses the EUR-Lex SPARQL endpoint at publications.europa.eu.

        Args:
            days: How many days back to search.
            limit: Maximum number of results.

        Returns:
            List of CommissionDocItem for SWD documents.
        """
        import re
        from datetime import timedelta
        from .eurlex_client import EURLexClient

        client = EURLexClient()
        try:
            date_from = datetime.now() - timedelta(days=days)

            # SPARQL query for SWD documents
            # SWD CELEX pattern: 5YYYYSCNNNN (sector 5, type SC)
            sparql_query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT DISTINCT ?celex ?title ?date
WHERE {{
  ?doc cdm:resource_legal_id_celex ?celex .
  ?doc cdm:work_date_document ?date .
  OPTIONAL {{
    ?doc cdm:resource_legal_title ?title .
    FILTER(LANG(?title) = 'en')
  }}
  FILTER(STRSTARTS(STR(?celex), "5"))
  FILTER(CONTAINS(STR(?celex), "SC"))
  FILTER(?date >= "{date_from.strftime('%Y-%m-%d')}"^^xsd:date)
}}
ORDER BY DESC(?date)
LIMIT {limit}
"""

            results = await client.sparql.select(sparql_query)

            items = []
            for row in results:
                celex = row.get('celex', '')
                title = row.get('title', '')
                date_str = row.get('date')

                # Skip entries without a title
                if not title:
                    title = f"SWD document {celex}"

                # Parse SWD reference from CELEX: 5YYYYSCNNNN -> SWD(YYYY) NNN
                swd_ref = celex
                swd_match = re.match(r'5(\d{4})SC(\d+)', celex)
                if swd_match:
                    year = swd_match.group(1)
                    number = swd_match.group(2).lstrip('0') or '0'
                    swd_ref = f"SWD({year}) {number}"

                # Parse date
                pub_date = None
                if date_str:
                    try:
                        pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        try:
                            pub_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                        except (ValueError, TypeError):
                            pass

                portal_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

                items.append(CommissionDocItem(
                    reference=swd_ref,
                    title=title,
                    doc_type=CommissionDocType.SWD,
                    publication_date=pub_date,
                    dg_responsible=None,
                    languages=['EN'],
                    portal_url=portal_url,
                ))

            logger.info(f"[OK] SPARQL fallback returned {len(items)} SWD documents")
            return items

        except Exception as e:
            logger.error(f"[ERROR] SPARQL SWD fallback failed: {e}")
            return []
        finally:
            await client.close()

    async def get_latest_join_via_sparql(
        self,
        days: int = 30,
        limit: int = 100
    ) -> List[CommissionDocItem]:
        """
        Fetch latest JOIN (Joint Commission + High Representative) documents
        via CELLAR SPARQL.

        JOIN documents have CELEX numbers starting with '5' (preparatory acts)
        and type code 'JC' (e.g. 52025JC0001 = JOIN(2025) 1).

        Args:
            days: How many days back to search.
            limit: Maximum number of results.

        Returns:
            List of CommissionDocItem for JOIN documents.
        """
        import re
        from datetime import timedelta
        from .eurlex_client import EURLexClient

        client = EURLexClient()
        try:
            date_from = datetime.now() - timedelta(days=days)

            sparql_query = f"""
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT DISTINCT ?celex ?title ?date
WHERE {{
  ?doc cdm:resource_legal_id_celex ?celex .
  ?doc cdm:work_date_document ?date .
  OPTIONAL {{
    ?doc cdm:resource_legal_title ?title .
    FILTER(LANG(?title) = 'en')
  }}
  FILTER(STRSTARTS(STR(?celex), "5"))
  FILTER(CONTAINS(STR(?celex), "JC"))
  FILTER(?date >= "{date_from.strftime('%Y-%m-%d')}"^^xsd:date)
}}
ORDER BY DESC(?date)
LIMIT {limit}
"""

            results = await client.sparql.select(sparql_query)

            items = []
            for row in results:
                celex = row.get('celex', '')
                title = row.get('title', '')
                date_str = row.get('date')

                if not title:
                    title = f"JOIN document {celex}"

                # Parse JOIN reference from CELEX: 5YYYYJCNNNN -> JOIN(YYYY) NNN
                join_ref = celex
                join_match = re.match(r'5(\d{4})JC(\d+)', celex)
                if join_match:
                    year = join_match.group(1)
                    number = join_match.group(2).lstrip('0') or '0'
                    join_ref = f"JOIN({year}) {number}"

                pub_date = None
                if date_str:
                    try:
                        pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        try:
                            pub_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                        except (ValueError, TypeError):
                            pass

                portal_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

                items.append(CommissionDocItem(
                    reference=join_ref,
                    title=title,
                    doc_type=CommissionDocType.JOIN,
                    publication_date=pub_date,
                    dg_responsible=None,
                    languages=['EN'],
                    portal_url=portal_url,
                ))

            logger.info(f"[OK] SPARQL fallback returned {len(items)} JOIN documents")
            return items

        except Exception as e:
            logger.error(f"[ERROR] SPARQL JOIN fallback failed: {e}")
            return []
        finally:
            await client.close()

    async def get_latest_with_fallback(
        self,
        doc_type: Optional[CommissionDocType] = None,
        days: int = 7
    ) -> List[CommissionDocItem]:
        """
        Fetch latest documents, automatically falling back to EUR-Lex
        if the RegDoc API is unavailable.

        This is the recommended entry point for consumers who need
        Commission documents regardless of API status.

        Args:
            doc_type: Filter by document type (None for COM proposals)
            days: How many days back to search.

        Returns:
            List of CommissionDocItem (from RegDoc API or EUR-Lex fallback).
        """
        available = await self.check_api_availability()

        if available:
            try:
                return await self.get_latest_documents(doc_type=doc_type, days=days)
            except NotImplementedError:
                logger.info("[INFO] RegDoc API live but not implemented, using EUR-Lex fallback")

        # Fallback to EUR-Lex
        if doc_type is None or doc_type == CommissionDocType.COM:
            return await self.get_latest_com_proposals_via_eurlex(days=days)
        elif doc_type == CommissionDocType.OJ:
            return await self.get_latest_legislation_via_eurlex(days=days)
        elif doc_type == CommissionDocType.SWD:
            return await self.get_latest_swd_via_sparql(days=days)
        elif doc_type == CommissionDocType.JOIN:
            return await self.get_latest_join_via_sparql(days=days)
        else:
            logger.info(
                f"[INFO] No EUR-Lex fallback for doc_type={doc_type}, "
                f"only COM, OJ, SWD, and JOIN are supported via fallback"
            )
            return []


# =============================================================================
# Singleton
# =============================================================================

_client: Optional[CommissionDocRegisterClient] = None


def get_commission_doc_register_client() -> CommissionDocRegisterClient:
    """
    Get the global CommissionDocRegisterClient singleton.

    Returns:
        CommissionDocRegisterClient instance.
    """
    global _client
    if _client is None:
        _client = CommissionDocRegisterClient()
    return _client
