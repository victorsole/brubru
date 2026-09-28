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
class EPOpenDataUpstreamError(RuntimeError):
    """EP Open Data answered HTTP 200 with an error in the body.

    The API forwards its own backend's failure as a 200 whose payload carries an
    `error` key instead of `data`, e.g.
      "500 Internal Server Error from POST https://admin.data.europarl.europa.eu/..."
    It is intermittent: the same offset can fail and then succeed seconds later.
    Reading that as an empty page made the amendment sync stop at the first blip and
    report "0 documents discovered" as success, which is why nothing has been stored
    since 3 May 2026.
    """


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

        last_error = None
        for attempt in range(1, 4):
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            # A 200 can carry the failure in its body. "data" absent plus "error"
            # present is an upstream fault, never an empty page.
            if "data" not in data and data.get("error"):
                last_error = str(data["error"])[:200]
                logger.warning(
                    f"[WARN] {endpoint} offset={offset}: EP answered 200 with an error "
                    f"body (attempt {attempt}/3): {last_error}"
                )
                await asyncio.sleep(2.0 * attempt)
                continue
            return data.get("data", [])
        raise EPOpenDataUpstreamError(
            f"{endpoint} offset={offset} returned an error body three times: {last_error}"
        )

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
        max_am_probe: int = 120,
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
            am_docs = await self._probe_am_documents(
                all_docs, progress_callback, max_am_probe=max_am_probe)
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
        max_am_probe: int = 120,
    ) -> List[Dict[str, Any]]:
        """
        Probe for AM documents based on discovered PR documents.

        For each PR doc like JURI-PR-751881, check if JURI-AM-{nearby PE numbers}
        exists on doceo. Committee AMs typically have PE numbers close to
        (but slightly higher than) the parent PR's PE number.
        """
        am_docs: List[Dict[str, Any]] = []
        probed: set = set()

        # Newest PE numbers first, and bounded. Every candidate costs a browser fetch
        # now that doceo can only be read past its WAF, so probing 5 deltas across all
        # 1,127 PRs would be ~5,600 fetches in a job that has to finish daily. The new
        # amendments are attached to the newest reports, and an older PR that gains an
        # AM later is picked up by a full run (max_am_probe=0).
        pr_list = [d for d in pr_docs if d.get("document_type") == "PR"]
        pr_list.sort(key=lambda d: d.get("pe_reference", ""), reverse=True)
        if max_am_probe:
            pr_list = pr_list[:max_am_probe]
        logger.info(f"[INFO] Probing AM docs for {len(pr_list)} PR documents...")

        # Build every candidate first, then ask the browser. doceo answers plain HTTP
        # with 202 and an empty body whether or not the document exists, so the old
        # HEAD probe saw 202 (never 200), treated it as "no AM at this PE" and broke
        # out of the range immediately: it discovered ZERO amendment documents on every
        # run. Only a browser that has cleared the host's challenge sees the true
        # status, which is what separates a real document from a 404.
        candidates: List[tuple] = []
        for pr in pr_list:
            committee = pr.get("committee_code", "")
            pe_ref = pr.get("pe_reference", "")
            if not committee or not pe_ref:
                continue
            pe_match = re.match(r'PE(\d{3})\.(\d{3})', pe_ref)
            if not pe_match:
                continue
            pe_num = int(pe_match.group(1) + pe_match.group(2))
            for delta in range(1, 6):
                am_id = f"{committee}-AM-{pe_num + delta}"
                if am_id in probed:
                    continue
                probed.add(am_id)
                candidates.append((am_id, f"{DOCEO_BASE}/{am_id}_EN.docx",
                                   pr.get("procedure_reference", "")))

        if not candidates:
            return am_docs

        try:
            import importlib.util
            import sys as _sys
            from pathlib import Path as _Path
            spec = importlib.util.spec_from_file_location(
                "waf_browser_fetcher",
                str(_Path(__file__).resolve().parents[1] / "scrapers" / "waf_browser_fetcher.py"))
            waf = importlib.util.module_from_spec(spec)
            _sys.modules["waf_browser_fetcher"] = waf
            spec.loader.exec_module(waf)
        except Exception as e:  # noqa: BLE001
            raise EPOpenDataUpstreamError(
                f"doceo is behind a WAF and the browser fetcher is unavailable ({e}), "
                f"so no amendment document can be discovered") from e

        by_url = {url: (am_id, proc) for am_id, url, proc in candidates}
        urls = list(by_url)
        logger.info(f"[INFO] Probing {len(urls)} candidate AM URLs through the browser")
        found = 0
        for start in range(0, len(urls), 25):
            batch = urls[start:start + 25]
            try:
                out = await asyncio.to_thread(
                    waf.fetch_bytes_isolated, batch,
                    warm_url="https://www.europarl.europa.eu/doceo/", timeout_s=600.0)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[WARN] AM probe batch {start}: {e}")
                continue
            for url, (status, body, err) in out.items():
                if status == 200 and body[:2] == b"PK":
                    am_id, proc = by_url[url]
                    doc = self._stub_to_doc(am_id)
                    doc["procedure_reference"] = proc
                    am_docs.append(doc)
                    found += 1
            if progress_callback:
                progress_callback(start + len(batch), len(urls),
                                  f"AM probe: {found} found")
        logger.info(f"[OK] AM probe: {found} real documents out of {len(urls)} candidates")

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

            except EPOpenDataUpstreamError:
                # Never return a short list as if it were the whole one: the caller
                # cannot tell truncation from "that is all there is", and a sync that
                # discovers nothing would record success.
                raise
            except httpx.HTTPStatusError as e:
                raise EPOpenDataUpstreamError(
                    f"HTTP {e.response.status_code} on {endpoint} offset={offset} after "
                    f"{len(stubs)} stub(s): the listing is incomplete"
                ) from e
            except Exception as e:
                raise EPOpenDataUpstreamError(
                    f"failed paginating {endpoint} at offset={offset} after "
                    f"{len(stubs)} stub(s): {type(e).__name__}: {e}"
                ) from e

        return stubs


def get_ep_open_data_client() -> EPOpenDataClient:
    """Factory function for EPOpenDataClient."""
    return EPOpenDataClient()
