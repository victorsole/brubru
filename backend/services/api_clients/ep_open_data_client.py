"""
EP Open Data API Client

Client for the European Parliament Open Data Portal API (data.europarl.europa.eu).
Used for bulk discovery of amendment documents (AM), draft reports (PR),
and draft opinions (PA) across all committees and procedures.

API: https://data.europarl.europa.eu/api/v2
Format: JSON-LD (Accept: application/ld+json)
Rate limit: 500 requests per 5 minutes (~0.6s per request).

Key findings from API exploration (Feb 2026):
- The /documents endpoint contains both plenary (A-10-...) and committee (COMM-AM-...)
  amendment lists, but does NOT support server-side work-type filtering.
- The /committee-documents endpoint has PR and PA docs with COMMITTEE-TYPE-PENUMBER IDs.
- Committee AM docs (e.g. JURI-AM-753448) are discoverable via /documents.
- Doceo URL pattern: https://www.europarl.europa.eu/doceo/document/{identifier}_EN.docx
- Detail response uses JSON-LD with nested is_realized_by -> is_embodied_by structure.
- Procedure references are embedded in title_alternative fields.

Created: February 2026
"""

import asyncio
import logging
import re
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# EP Open Data work-type URIs (as returned by the API)
WORK_TYPE_AMENDMENT_LIST = "def/ep-document-types/AMENDMENT_LIST"
WORK_TYPE_REPORT_DRAFT = "def/ep-document-types/REPORT_PARLIAMENTARY_COMMITTEE_DRAFT"
WORK_TYPE_OPINION_DRAFT = "def/ep-document-types/OPINION_PARLIAMENTARY_COMMITTEE_DRAFT"

# Shortcodes used in the plan / CLI
WORK_TYPE_AMENDMENTS = "AMENDMENTS"
WORK_TYPE_DRAFT_REPORTS = "REPORT_DRAFT"
WORK_TYPE_DRAFT_OPINIONS = "OPINION_DRAFT"

# Map shortcodes to our document_type codes
WORK_TYPE_TO_DOC_TYPE = {
    WORK_TYPE_AMENDMENTS: "AM",
    WORK_TYPE_DRAFT_REPORTS: "PR",
    WORK_TYPE_DRAFT_OPINIONS: "PA",
}

# Map API work-type URIs to shortcodes
API_WORK_TYPE_MAP = {
    WORK_TYPE_AMENDMENT_LIST: WORK_TYPE_AMENDMENTS,
    WORK_TYPE_REPORT_DRAFT: WORK_TYPE_DRAFT_REPORTS,
    WORK_TYPE_OPINION_DRAFT: WORK_TYPE_DRAFT_OPINIONS,
}

# Regex patterns
RE_PROCEDURE_REF = re.compile(r'(\d{4}/\d{4}\([A-Z]{3}\))')
RE_PE_NUMBER = re.compile(r'PE[\s_-]?(\d{3})[.\s_-]?(\d{3})')
RE_COMMITTEE_CODE = re.compile(r'^([A-Z]{4})-')
# Committee AM docs: COMM-AM-NNNNNN (6-digit PE-like number)
RE_COMMITTEE_AM = re.compile(r'^[A-Z]{4}-AM-\d{6}')
# Committee PR/PA docs: COMM-PR-NNNNNN or COMM-PA-NNNNNN
RE_COMMITTEE_DOC = re.compile(r'^[A-Z]{4}-(PR|PA|AD|AM|RR)-\d{6}')

DOCEO_BASE = "https://www.europarl.europa.eu/doceo/document"


class EPOpenDataClient:
    """
    Client for the EP Open Data API v2.

    Discovers amendment documents (AM, PR, PA) with metadata including
    committee, rapporteur, procedure reference, and DOCX download URLs.
    """

    BASE_URL = "https://data.europarl.europa.eu/api/v2"
    RATE_LIMIT_DELAY = 0.7  # seconds between requests (500 req / 5 min safe margin)

    def __init__(self, timeout: int = 60):
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "Accept": "application/ld+json",
                    "User-Agent": "Brubru/1.0 (EU Policy Intelligence)",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _list_endpoint(
        self,
        endpoint: str,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch a page from a list endpoint.

        The EP Open Data API does NOT support server-side filtering by
        work-type or year. We paginate and filter client-side.
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/{endpoint}"
        params = {"offset": offset, "limit": min(limit, 100)}

        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("data", [])

    async def get_document_detail(
        self,
        identifier: str,
        endpoint: str = "documents",
    ) -> Dict[str, Any]:
        """
        Get detailed metadata for a single document.

        Args:
            identifier: EP document identifier (e.g. 'JURI-AM-753448')
            endpoint: API endpoint ('documents' or 'committee-documents')

        Returns:
            Normalised document dict
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/{endpoint}/{identifier}"

        response = await client.get(url)
        response.raise_for_status()

        raw = response.json()
        return self._parse_document_detail(raw, identifier)

    def _parse_document_detail(
        self,
        raw: Dict[str, Any],
        identifier: str,
    ) -> Dict[str, Any]:
        """
        Parse JSON-LD document detail into a normalised dict.

        The API returns nested is_realized_by (Expression) ->
        is_embodied_by (Manifestation) with language-specific titles
        and download paths.
        """
        result: Dict[str, Any] = {
            "identifier": identifier,
            "title": "",
            "pe_reference": "",
            "committee_code": "",
            "procedure_reference": "",
            "rapporteur_name": "",
            "document_type": "",
            "doceo_url": "",
            "date": "",
        }

        # Unwrap data array
        data = raw.get("data", raw)
        if isinstance(data, list) and data:
            data = data[0]

        # Date
        result["date"] = data.get("document_date", "")

        # Committee code from identifier prefix
        committee_match = RE_COMMITTEE_CODE.match(identifier)
        if committee_match:
            result["committee_code"] = committee_match.group(1)

        # Document type from identifier
        if "-AM-" in identifier:
            result["document_type"] = "AM"
        elif "-PR-" in identifier or "-RR-" in identifier:
            result["document_type"] = "PR"
        elif "-PA-" in identifier or "-AD-" in identifier:
            result["document_type"] = "PA"

        # PE reference: the numeric suffix IS the PE number
        # e.g. JURI-AM-753448 -> PE753.448
        pe_match = re.search(r'-(\d{3})(\d{3})$', identifier)
        if pe_match:
            result["pe_reference"] = f"PE{pe_match.group(1)}.{pe_match.group(2)}"

        # Extract title, procedure_reference, and rapporteur from expressions
        # Prefer EN, fallback to any language
        expressions = data.get("is_realized_by", [])
        if isinstance(expressions, dict):
            expressions = [expressions]

        en_expr = None
        any_expr = None
        for expr in expressions:
            lang = expr.get("language", "")
            if "ENG" in lang:
                en_expr = expr
                break
            if any_expr is None:
                any_expr = expr

        expr = en_expr or any_expr
        if expr:
            # Title
            title_dict = expr.get("title_alternative", expr.get("title", {}))
            if isinstance(title_dict, dict):
                # Get EN key or first available
                result["title"] = (
                    title_dict.get("en", "")
                    or next(iter(title_dict.values()), "")
                )
            elif isinstance(title_dict, str):
                result["title"] = title_dict

        # Extract procedure reference from title
        if result["title"]:
            proc_match = RE_PROCEDURE_REF.search(result["title"])
            if proc_match:
                result["procedure_reference"] = proc_match.group(1)

        # Also check foresees_change_of for parent doc link
        foresees = data.get("foresees_change_of", "")
        if isinstance(foresees, str) and not result["procedure_reference"]:
            proc_match = RE_PROCEDURE_REF.search(foresees)
            if proc_match:
                result["procedure_reference"] = proc_match.group(1)

        # Construct doceo URL
        # Pattern: https://www.europarl.europa.eu/doceo/document/{identifier}_EN.docx
        result["doceo_url"] = f"{DOCEO_BASE}/{identifier}_EN.docx"

        return result

    async def enumerate_all_documents(
        self,
        work_types: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Discover amendment-related documents from the EP Open Data API.

        Fast discovery: extracts metadata from identifiers and labels only
        (no individual detail fetches during enumeration). Detail is fetched
        later by BulkAmendmentSyncService only for docs that need parsing.

        Strategy:
        - /committee-documents: paginate for PR and PA docs (~2500 items, ~20s)
        - For AM docs: probe COMM-AM-{pe_number} doceo URLs derived from PRs

        Args:
            work_types: Shortcodes to fetch (defaults to AM + PR)
            years: Filter by year (from label/identifier heuristics)
            progress_callback: Optional callback(current, total, message)

        Returns:
            List of document dicts with identifiers and doceo URLs
        """
        if work_types is None:
            work_types = [WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS]

        # Phase 1: Discover PR and PA docs from /committee-documents (fast pagination)
        pr_pa_types = set()
        if WORK_TYPE_DRAFT_REPORTS in work_types:
            pr_pa_types.add(WORK_TYPE_REPORT_DRAFT)
        if WORK_TYPE_DRAFT_OPINIONS in work_types:
            pr_pa_types.add(WORK_TYPE_OPINION_DRAFT)

        all_docs: List[Dict[str, Any]] = []

        if pr_pa_types:
            stubs = await self._paginate_endpoint(
                "committee-documents",
                filter_work_types=pr_pa_types,
                progress_callback=progress_callback,
            )
            logger.info(f"[INFO] Found {len(stubs)} PR/PA stubs from /committee-documents")

            # Convert stubs to doc dicts (fast, no API calls)
            for stub in stubs:
                identifier = stub["identifier"]
                doc = self._stub_to_doc(identifier)
                all_docs.append(doc)

        if progress_callback:
            progress_callback(0, len(all_docs), f"Discovered {len(all_docs)} PR/PA documents")

        # Phase 2: Probe for AM docs derived from PR identifiers
        if WORK_TYPE_AMENDMENTS in work_types:
            am_docs = await self._probe_am_documents(all_docs, progress_callback)
            all_docs.extend(am_docs)
            logger.info(f"[INFO] Probed {len(am_docs)} AM docs")

        logger.info(f"[OK] Total discovered: {len(all_docs)} documents")

        if progress_callback:
            progress_callback(len(all_docs), len(all_docs), f"Done: {len(all_docs)} documents")

        return all_docs

    def _stub_to_doc(self, identifier: str) -> Dict[str, Any]:
        """Convert a list-endpoint identifier into a doc dict without API calls."""
        doc: Dict[str, Any] = {
            "identifier": identifier,
            "title": "",
            "pe_reference": "",
            "committee_code": "",
            "procedure_reference": "",
            "rapporteur_name": "",
            "document_type": "",
            "doceo_url": f"{DOCEO_BASE}/{identifier}_EN.docx",
            "date": "",
        }

        # Committee code from identifier prefix
        committee_match = RE_COMMITTEE_CODE.match(identifier)
        if committee_match:
            doc["committee_code"] = committee_match.group(1)

        # Document type from identifier
        if "-AM-" in identifier:
            doc["document_type"] = "AM"
        elif "-PR-" in identifier or "-RR-" in identifier:
            doc["document_type"] = "PR"
        elif "-PA-" in identifier or "-AD-" in identifier:
            doc["document_type"] = "PA"

        # PE reference from numeric suffix
        pe_match = re.search(r'-(\d{3})(\d{3})$', identifier)
        if pe_match:
            doc["pe_reference"] = f"PE{pe_match.group(1)}.{pe_match.group(2)}"

        return doc

    async def _probe_am_documents(
        self,
        pr_docs: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Probe for AM documents based on discovered PR documents.

        For each PR doc like JURI-PR-751881, check if JURI-AM-{nearby PE numbers}
        exists on doceo. Committee AMs typically have PE numbers close to
        (but slightly higher than) the parent PR's PE number.
        """
        am_docs: List[Dict[str, Any]] = []
        probed: set = set()
        client = await self._get_client()

        pr_list = [d for d in pr_docs if d.get("document_type") == "PR"]
        logger.info(f"[INFO] Probing AM docs for {len(pr_list)} PR documents...")

        for pr in pr_list:
            committee = pr.get("committee_code", "")
            pe_ref = pr.get("pe_reference", "")
            if not committee or not pe_ref:
                continue

            pe_match = re.match(r'PE(\d{3})\.(\d{3})', pe_ref)
            if not pe_match:
                continue

            pe_num = int(pe_match.group(1) + pe_match.group(2))

            # Probe PE numbers slightly higher than the PR
            for delta in range(1, 6):
                am_pe = pe_num + delta
                am_id = f"{committee}-AM-{am_pe}"

                if am_id in probed:
                    continue
                probed.add(am_id)

                # HEAD request to check if doceo URL exists (fast, no download)
                am_url = f"{DOCEO_BASE}/{am_id}_EN.docx"
                try:
                    await asyncio.sleep(0.2)  # Lighter rate limit for HEAD
                    resp = await client.head(am_url)
                    if resp.status_code == 200:
                        doc = self._stub_to_doc(am_id)
                        doc["procedure_reference"] = pr.get("procedure_reference", "")
                        am_docs.append(doc)
                        logger.info(f"[OK] Found AM doc: {am_id}")
                    else:
                        break  # No AM at this PE, stop probing range
                except Exception:
                    break

        return am_docs

    async def _paginate_endpoint(
        self,
        endpoint: str,
        filter_work_types: Optional[set] = None,
        filter_identifier_pattern: Optional[re.Pattern] = None,
        max_pages: int = 200,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Paginate through an endpoint, filtering items client-side.

        Returns list of stubs: {identifier, work_type, endpoint, label}
        """
        stubs: List[Dict[str, Any]] = []
        offset = 0
        page_size = 100
        page = 0

        while page < max_pages:
            try:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
                items = await self._list_endpoint(endpoint, offset=offset, limit=page_size)

                if not items:
                    break

                for item in items:
                    work_type = item.get("work_type", "")
                    identifier = item.get("identifier", "")

                    # Filter by work type
                    if filter_work_types and work_type not in filter_work_types:
                        continue

                    # Filter by identifier pattern (e.g. committee AM only)
                    if filter_identifier_pattern and not filter_identifier_pattern.match(identifier):
                        continue

                    stubs.append({
                        "identifier": identifier,
                        "work_type": work_type,
                        "endpoint": endpoint,
                        "label": item.get("label", ""),
                    })

                logger.debug(
                    f"[INFO] {endpoint} offset={offset}: "
                    f"{len(items)} items, {len(stubs)} matching so far"
                )

                if len(items) < page_size:
                    break
                offset += page_size
                page += 1

            except httpx.HTTPStatusError as e:
                logger.warning(f"[WARN] HTTP {e.response.status_code} on {endpoint} offset={offset}")
                break
            except Exception as e:
                logger.error(f"[ERROR] Failed paginating {endpoint}: {e}")
                break

        return stubs


def get_ep_open_data_client() -> EPOpenDataClient:
    """Factory function for EPOpenDataClient."""
    return EPOpenDataClient()
