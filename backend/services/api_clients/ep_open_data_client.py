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
  amendment lists. In Feb 2026 it had no server-side filter; since at least 11 Nov 2026
  it filters by `year` and `work-type` (1,528 AMENDMENT_LIST documents for 2026).
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
# Four characters: a committee (ECON) or a joint committee (CJ13).
RE_COMMITTEE_CODE = re.compile(r'^([A-Z][A-Z0-9]{3})-')
# A committee's amendment document, as EP Open Data lists it: ECON-AM-789865, CJ13-AM-797588.
# Plenary amendments (A-10-2026-0001-AM-001-243) are another corpus and are not read here.
RE_COMMITTEE_AM_ID = re.compile(r'^[A-Z][A-Z0-9]{3}-AM-\d{6}$')
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
    TRANSIENT_WAITS = (15, 60)  # seconds before the 2nd and 3rd try of a page that errored

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
        filters: Optional[Dict[str, Any]] = None,
        empty_ok: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch a page from a list endpoint.

        `filters` are extra query parameters. /documents filters on the server by `year`
        and `work-type` (read 11 Nov 2026; in February 2026 it did not);
        /committee-documents is still filtered client-side. `empty_ok` is for a filtered
        list that may truly hold nothing (a year with no document yet): its 204 at
        offset 0 is then an empty list, not a fault.
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/{endpoint}"
        params = {**(filters or {}), "offset": offset, "limit": min(limit, 100)}

        last_error = None
        for attempt in range(1, 4):
            # A transient upstream fault (HTTP 500/502/504, a dropped connection) on ONE of
            # the ~25 pages used to abort the whole listing at once: it raised on the first
            # try, and the nightly amendment sync died at a different offset on 3, 8 and
            # 12 Oct 2026 (300, 900, 1200). Wait and ask again, like a throttle.
            try:
                response = await client.get(url, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = type(exc).__name__
                logger.warning(f"[WARN] {endpoint} offset={offset}: {last_error} (attempt {attempt}/3)")
                if attempt < 3:
                    await asyncio.sleep(self.TRANSIENT_WAITS[attempt - 1])
                    continue
                raise EPOpenDataUpstreamError(
                    f"{endpoint} offset={offset}: {last_error}, still failing after 3 tries") from exc
            if response.status_code in (500, 502, 504):
                last_error = f"HTTP {response.status_code}"
                logger.warning(f"[WARN] {endpoint} offset={offset}: {last_error} (attempt {attempt}/3)")
                if attempt < 3:
                    await asyncio.sleep(self.TRANSIENT_WAITS[attempt - 1])
                    continue
                raise EPOpenDataUpstreamError(
                    f"{last_error} on {endpoint} offset={offset}, still failing after 3 tries")
            # EP answers 429 with `Retry-After: 60` and means it. Raising instead of
            # waiting turns a pause into a failed run, and swallowing it turns a pause
            # into "there is nothing here": neither is true.
            if response.status_code in (429, 503):
                try:
                    wait = int(response.headers.get("Retry-After") or 60)
                except (TypeError, ValueError):
                    wait = 60
                last_error = f"HTTP {response.status_code}, Retry-After {wait}s"
                logger.warning(f"[WARN] {endpoint} offset={offset}: EP is throttling "
                               f"(attempt {attempt}/3), waiting {wait}s")
                if attempt < 3:
                    await asyncio.sleep(min(max(wait, 5), 180))
                    continue
                raise EPOpenDataUpstreamError(
                    f"{endpoint} offset={offset}: {last_error}, still refused after 3 tries")
            # EP answers 204 with no body past the last page (30 Oct 2026: committee-documents held
            # exactly 3,200 items, so offset 3,200 was a 204 and its empty body failed as JSON on
            # 29 and 30 Oct). Past the first page that is the end of the list; at offset 0 it would
            # say the whole list is empty, which is never true, so there it stays an upstream fault.
            if response.status_code == 204:
                if offset > 0 or empty_ok:
                    return []
                raise EPOpenDataUpstreamError(f"{endpoint} offset=0: HTTP 204, no list at all")
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

        for attempt in range(1, 4):
            response = await client.get(url)
            if response.status_code in (429, 503) and attempt < 3:
                try:
                    wait = int(response.headers.get("Retry-After") or 60)
                except (TypeError, ValueError):
                    wait = 60
                await asyncio.sleep(min(max(wait, 5), 180))
                continue
            break
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

        # /documents keeps the title on the work itself, in every language.
        if not result["title"]:
            titles = data.get("title_dcterms")
            if isinstance(titles, dict):
                result["title"] = titles.get("en", "") or next(iter(titles.values()), "")

        # Extract procedure reference from title
        if result["title"]:
            proc_match = RE_PROCEDURE_REF.search(result["title"])
            if proc_match:
                result["procedure_reference"] = proc_match.group(1)

        # Also check foresees_change_of for parent doc link
        foresees = data.get("foresees_change_of", "")
        if isinstance(foresees, list):
            foresees = foresees[0] if foresees else ""
        # The document these amendments are tabled to: eli/dl/doc/TRAN-PA-796508.
        result["parent_identifier"] = foresees.rsplit("/", 1)[-1] if isinstance(foresees, str) else ""
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
        - AM docs: /documents?year=&work-type=AMENDMENT_LIST, committee identifiers only

        Args:
            work_types: Shortcodes to fetch (defaults to AM + PR)
            years: Years whose amendment documents are listed (default: this year)
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

        # Phase 2: the committees' amendment documents, from the list EP publishes.
        if WORK_TYPE_AMENDMENTS in work_types:
            am_docs = await self.list_amendment_documents(years, progress_callback)
            all_docs.extend(am_docs)
            logger.info(f"[INFO] Listed {len(am_docs)} AM docs")

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

    async def list_amendment_documents(
        self,
        years: Optional[List[int]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Every committee amendment document EP Open Data lists for `years` (default: this year).

        Until 11 Nov 2026 these were GUESSED: for the 120 newest draft reports, PE number
        +1 to +5 was tried at doceo. Committees number their amendment documents far from
        the report and table them weeks later, so the guess found 15 of the 839 documents
        of 2026, none dated after 6 July, and a run that found none recorded success.
        /documents?year=&work-type=AMENDMENT_LIST lists them all.

        A year that cannot be listed raises: a short list is never returned as the whole one.
        """
        from datetime import datetime as _dt
        docs: List[Dict[str, Any]] = []
        seen: set = set()
        for year in (years or [_dt.now().year]):
            stubs = await self._paginate_endpoint(
                "documents",
                filter_identifier_pattern=RE_COMMITTEE_AM_ID,
                filters={"year": year, "work-type": "AMENDMENT_LIST"},
                empty_ok=True,
                progress_callback=progress_callback,
            )
            for stub in stubs:
                identifier = stub["identifier"]
                if identifier in seen:
                    continue
                seen.add(identifier)
                docs.append(self._stub_to_doc(identifier))
            logger.info(f"[INFO] {year}: {len(stubs)} committee amendment documents listed")
        return docs

    async def _paginate_endpoint(
        self,
        endpoint: str,
        filter_work_types: Optional[set] = None,
        filter_identifier_pattern: Optional[re.Pattern] = None,
        max_pages: int = 200,
        progress_callback: Optional[Callable] = None,
        filters: Optional[Dict[str, Any]] = None,
        empty_ok: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Paginate through an endpoint, filtering items client-side (after any server
        `filters`).

        Returns list of stubs: {identifier, work_type, endpoint, label}
        """
        stubs: List[Dict[str, Any]] = []
        offset = 0
        page_size = 100
        page = 0

        while page < max_pages:
            try:
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
                items = await self._list_endpoint(
                    endpoint, offset=offset, limit=page_size, filters=filters, empty_ok=empty_ok)

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
