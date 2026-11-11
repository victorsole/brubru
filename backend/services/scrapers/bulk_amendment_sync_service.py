"""
Bulk Amendment Sync Service

Orchestrates bulk discovery and parsing of EP amendment documents
via the EP Open Data API. Unlike EPAmendmentSyncService (which fetches
per-procedure from OEIL), this service discovers ALL amendment documents
across all committees and procedures, then parses their DOCX files.

Workflow:
1. Enumerate documents via EP Open Data API (AM, PR, PA)
2. Skip already-parsed documents (check amendment_documents.ep_identifier)
3. Download DOCX from doceo for each new/pending document
4. Parse with EPAmendmentParser (reuse existing pipeline)
5. Upsert amendments + document records
6. Return aggregate stats

Created: February 2026
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.mep_amendment import AmendmentDocument, MEPAmendment
from services.api_clients.ep_open_data_client import (
    EPOpenDataClient,
    WORK_TYPE_AMENDMENTS,
    WORK_TYPE_DRAFT_REPORTS,
    WORK_TYPE_DRAFT_OPINIONS,
    WORK_TYPE_TO_DOC_TYPE,
)
from services.parsers.ep_amendment_parser import EPAmendmentParser
from services.scrapers.amendment_document_text import (
    MIN_CHARS, procedure_from_cover, text_from_docx, text_from_pdf,
)

logger = logging.getLogger(__name__)


@dataclass
class BulkSyncResult:
    """Summary of a bulk sync operation."""
    documents_discovered: int = 0
    documents_skipped: int = 0  # already parsed
    documents_parsed: int = 0
    documents_failed: int = 0
    documents_unsupported: int = 0  # legacy Word .doc: a format, not a failure
    documents_not_found: int = 0    # HTTP 404 at doceo
    # Listed and not yet read: left for the next run by the per-run limit. Never silent.
    documents_deferred: int = 0
    documents_listed_by_type: Dict[str, int] = field(default_factory=dict)
    amendments_stored: int = 0
    # Documents held without their own text that this run read (see fill_missing_text),
    # those it could not read, and those still waiting after it.
    texts_filled: int = 0
    texts_unread: int = 0
    texts_remaining: int = 0
    # `errors` is the RUN failing (the listing could not be read). A document that could
    # not be read goes to `document_errors`: 41 such documents made every nightly run
    # "failed" from 29 Sep to 12 Oct 2026 while the sync itself worked.
    errors: List[str] = field(default_factory=list)
    document_errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class UnsupportedDocumentFormat(ValueError):
    """The document exists but is not a DOCX (a legacy Word .doc): nothing to retry."""


class DocumentNotFound(ValueError):
    """doceo answered 404 for the document."""


# First bytes of an OLE2 compound file: Word 97-2003 `.doc`. doceo serves 38 documents of
# 2005-2016 in that format under a `.docx` address.
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# A document doceo answers 404 for is asked again after this many days, not every night.
NOT_FOUND_RETRY_DAYS = 7
# Documents the nightly run reads at most. Each is a browser fetch past doceo's WAF and a
# DOCX parse inside the API's own container; the rest wait for the next night, newest first.
NIGHTLY_DOCUMENT_LIMIT = 60
# Documents held without their text that the nightly run reads at most, newest first.
NIGHTLY_TEXT_LIMIT = 150
# Seconds between two files asked of the open data portal.
OPEN_DATA_PACE = 1.0
# A document that gave no text is asked again after this many days.
TEXT_RETRY_DAYS = 7
# The endpoint of EP Open Data that holds a document, by its type.
def _detail_endpoint(doc_type: str) -> str:
    return "documents" if doc_type == "AM" else "committee-documents"


# How the text of a PDF edition starts: the file stamp ("AM\\1297712EN.docx PE758.950").
_PDF_STAMPS = ("AM\\", "PR\\", "PA\\", "AD\\", "RD\\")


def _pdf_address(doceo_url: str) -> str:
    """The doceo address of a document's PDF edition, from its .docx address."""
    return doceo_url[:-len(".docx")] + ".pdf" if doceo_url.endswith(".docx") else doceo_url


class BulkAmendmentSyncService:
    """
    Bulk discovery + parse of EP amendment documents via EP Open Data API.

    Reuses EPAmendmentParser for DOCX parsing and the same upsert logic
    as EPAmendmentSyncService.
    """

    def __init__(self, db: Session):
        self.db = db
        self.client = EPOpenDataClient()
        self.parser = EPAmendmentParser()
        # doceo bytes fetched past the WAF by the browser, keyed by URL.
        self._docx_cache: Dict[str, bytes] = {}
        # What the browser got for a URL that is NOT a DOCX: (HTTP status, kind), kind being
        # 'legacy_doc', 'not_found' or 'other'. The browser's answer is the true one.
        self._fetch_facts: Dict[str, tuple] = {}
        # The open data record of each document read this run, keyed by EP identifier,
        # and the PDF address of a document that has no .docx, keyed by its doceo URL.
        self._details: Dict[str, Dict[str, Any]] = {}
        self._pdf_urls: Dict[str, str] = {}

    async def sync_all(
        self,
        years: Optional[List[int]] = None,
        work_types: Optional[List[str]] = None,
        force_refetch: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_documents: Optional[int] = None,
    ) -> BulkSyncResult:
        """
        Full bulk sync: enumerate documents from EP Open Data API,
        download and parse DOCX files, upsert amendments.

        Args:
            years: Years to fetch (defaults to current year)
            work_types: Document types (defaults to AM + PR)
            force_refetch: Re-parse even if already done
            progress_callback: Optional callback(current, total, message)
            max_documents: Read at most this many documents that are not settled, the
                highest PE numbers (the newest) first; the others are counted in
                `documents_deferred` and read by a later run. None reads them all.

        Returns:
            BulkSyncResult with counts and errors
        """
        start_time = time.time()
        result = BulkSyncResult()

        if work_types is None:
            work_types = [WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS]

        if years is None:
            years = [datetime.now().year]

        # Phase 1: Discover documents from EP Open Data API
        logger.info(f"[START] Bulk amendment sync: types={work_types}, years={years}")

        try:
            documents = await self.client.enumerate_all_documents(
                work_types=work_types,
                years=years,
                progress_callback=progress_callback,
            )
        except Exception as e:
            error_msg = f"Failed to enumerate documents: {e}"
            logger.error(f"[ERROR] {error_msg}")
            result.errors.append(error_msg)
            result.duration_seconds = time.time() - start_time
            await self.client.close()
            return result

        result.documents_discovered = len(documents)
        for d in documents:
            t = d.get("document_type") or "?"
            result.documents_listed_by_type[t] = result.documents_listed_by_type.get(t, 0) + 1
        logger.info(f"[INFO] Discovered {len(documents)} documents {result.documents_listed_by_type}")

        # What this run reads. Settled documents cost nothing and stay in the list (they
        # are counted as skipped below); the open ones are taken newest first up to the limit.
        if max_documents is not None and not force_refetch:
            open_docs = [d for d in documents
                         if d.get("identifier") and not self._is_settled(d["identifier"])]
            open_docs.sort(key=lambda d: d.get("pe_reference", ""), reverse=True)
            left = {d["identifier"] for d in open_docs[max_documents:]}
            if left:
                result.documents_deferred = len(left)
                documents = [d for d in documents if d.get("identifier") not in left]
                logger.info(f"[INFO] {len(left)} document(s) left for the next run "
                            f"(limit {max_documents} a run)")

        # Phase 1b: doceo answers plain HTTP with 202 and an EMPTY body for every
        # document, so the old code handed 0 bytes to the parser (raise_for_status
        # passes a 202) and recorded "failed". The documents are only reachable through
        # a browser that has cleared the host's challenge, so the whole batch is warmed
        # in one browser rather than launching one per document.
        needed = [
            d.get("doceo_url", "") for d in documents
            if d.get("identifier") and d.get("doceo_url")
            and (force_refetch or not self._is_settled(d["identifier"]))
        ]
        # The open data portal serves the same files without a challenge, and its record
        # says which formats exist, so it is asked first. doceo's browser is only for what
        # the portal could not supply: on 11 Nov 2026 doceo's front refused a whole address
        # (403 on every page) after about 500 documents read through it in 95 minutes.
        await self._prefetch_from_open_data(
            [d for d in documents if d.get("doceo_url") in set(needed)])
        await self._prefetch_walled_documents(
            [u for u in needed if u and u not in self._docx_cache and u not in self._fetch_facts])

        # Phase 2: Process each document
        for i, doc in enumerate(documents):
            ep_id = doc.get("identifier", "")
            pe_ref = doc.get("pe_reference", "")

            if not ep_id:
                continue

            # Skip what is settled: parsed, a format this parser cannot read, or a 404
            # asked about recently (unless forced)
            if not force_refetch and self._is_settled(ep_id):
                result.documents_skipped += 1
                continue

            try:
                count = await self._fetch_and_parse_document(doc)
                result.documents_parsed += 1
                result.amendments_stored += count

                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(
                        i + 1, len(documents),
                        f"Parsed {ep_id}: {count} amendments"
                    )

            except UnsupportedDocumentFormat as e:
                result.documents_unsupported += 1
                self._upsert_document_record(
                    doc, status="unsupported", error_message=str(e), total_amendments=0)
                self.db.commit()
                continue
            except DocumentNotFound as e:
                result.documents_not_found += 1
                self._upsert_document_record(
                    doc, status="not_found", error_message=str(e), total_amendments=0)
                self.db.commit()
                continue
            except Exception as e:
                error_msg = f"Failed {ep_id}: {str(e)}"
                logger.warning(f"[WARN] {error_msg}")
                result.document_errors.append(error_msg)
                result.documents_failed += 1

                # Record failure
                self._upsert_document_record(
                    doc, status="failed",
                    error_message=str(e), total_amendments=0,
                )
                self.db.commit()

        await self.client.close()

        result.duration_seconds = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] Bulk sync complete: {result.documents_parsed} parsed, "
            f"{result.documents_skipped} skipped, {result.documents_failed} failed, "
            f"{result.documents_unsupported} unsupported format, "
            f"{result.documents_not_found} not found, "
            f"{result.amendments_stored} amendments ({result.duration_seconds}s)"
        )

        return result

    async def _download(self, url: str) -> Optional[bytes]:
        """The bytes of a file on the open data portal, or None when it does not serve it."""
        try:
            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as http:
                for attempt in (1, 2):
                    response = await http.get(url)
                    if response.status_code in (429, 503) and attempt == 1:
                        await asyncio.sleep(30)
                        continue
                    break
            if response.status_code != 200:
                logger.debug(f"[INFO] {url}: HTTP {response.status_code}")
                return None
            return response.content
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[INFO] {url}: {type(e).__name__}")
            return None

    async def _detail(self, ep_id: str, doc_type: str) -> Dict[str, Any]:
        """The open data record of a document, read once a run; {} when it has none."""
        if ep_id not in self._details:
            try:
                detail = await self.client.get_document_detail(
                    ep_id, endpoint=_detail_endpoint(doc_type))
                self._details[ep_id] = detail if isinstance(detail, dict) else {}
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"[INFO] no open data record for {ep_id}: {type(exc).__name__}")
                self._details[ep_id] = {}
        return self._details[ep_id]

    async def _prefetch_from_open_data(self, documents: List[Dict[str, Any]]) -> None:
        """Fetch each document's .docx from the open data portal, where it lists one.

        A document the record lists as PDF only is noted as such: it has no .docx anywhere,
        and asking doceo for one is the 404 that used to be stored as 'not found'.
        """
        got = pdf_only = 0
        for doc in documents:
            ep_id, url = doc.get("identifier", ""), doc.get("doceo_url", "")
            if not ep_id or not url:
                continue
            files = (await self._detail(ep_id, doc.get("document_type", "AM"))).get("files") or {}
            if files.get("docx"):
                body = await self._download(files["docx"])
                if body and body[:2] == b"PK":
                    self._docx_cache[url] = body
                    got += 1
                await asyncio.sleep(OPEN_DATA_PACE)
            elif files.get("pdf"):
                self._fetch_facts[url] = (200, "pdf_only")
                self._pdf_urls[url] = files["pdf"]
                pdf_only += 1
        logger.info(f"[INFO] Open data portal supplied {got} document(s), "
                    f"{pdf_only} published as PDF only, of {len(documents)}")

    async def _prefetch_walled_documents(self, urls: List[str], chunk: int = 25) -> None:
        """Fetch doceo documents past the WAF, a chunk per browser.

        doceo returns 202 and zero bytes to plain HTTP, so a real browser has to clear
        the host's challenge first; fetch_bytes_isolated does that once per call and
        then pulls each document through the same cookie jar. It also reports the TRUE
        status, which matters beyond downloading: behind the WAF a missing document and
        a real one both looked like 202, so nothing could tell them apart.
        """
        if not urls:
            return
        try:
            import importlib.util
            import sys as _sys
            spec = importlib.util.spec_from_file_location(
                "waf_browser_fetcher",
                str(Path(__file__).resolve().parent / "waf_browser_fetcher.py"))
            waf = importlib.util.module_from_spec(spec)
            _sys.modules["waf_browser_fetcher"] = waf
            spec.loader.exec_module(waf)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WARN] browser fetcher unavailable ({e}); "
                           f"doceo documents cannot be read past the WAF")
            return

        got = missing = 0
        for start in range(0, len(urls), chunk):
            batch = urls[start:start + chunk]
            try:
                out = await asyncio.to_thread(
                    waf.fetch_bytes_isolated, batch,
                    warm_url="https://www.europarl.europa.eu/doceo/", timeout_s=600.0)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[WARN] browser batch {start}-{start+len(batch)} failed: {e}")
                continue
            for url, (status, body, err) in out.items():
                if body and body[:2] == b"PK":
                    self._docx_cache[url] = body
                    got += 1
                else:
                    missing += 1
                    kind = ("legacy_doc" if (body or b"")[:8] == OLE2_MAGIC
                            else "not_found" if status == 404 else "other")
                    self._fetch_facts[url] = (status, kind)
                    logger.debug(f"[INFO] {url}: status={status} bytes={len(body or b'')} {err or ''}")
        logger.info(f"[INFO] Browser warmed {got} document(s) past the WAF, "
                    f"{missing} not available")

    async def sync_incremental(self) -> BulkSyncResult:
        """
        Incremental sync: only current year, skip already-parsed docs.
        Designed to be called by the daily scheduler.
        """
        current_year = datetime.now().year
        result = await self.sync_all(
            years=[current_year],
            work_types=[WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS],
            force_refetch=False,
            max_documents=NIGHTLY_DOCUMENT_LIMIT,
        )
        # Then the documents held without their text, whatever year they are of. A failure
        # here is reported on the run and never undoes the sync above.
        try:
            filled = await self.fill_missing_text(limit=NIGHTLY_TEXT_LIMIT)
            result.texts_filled = filled["filled"]
            result.texts_unread = filled["unread"]
            result.texts_remaining = filled["remaining"]
        except Exception as e:  # noqa: BLE001
            self.db.rollback()
            result.document_errors.append(f"text fill stopped: {type(e).__name__}: {e}")
        finally:
            await self.client.close()
        return result

    async def fill_missing_text(self, limit: int = NIGHTLY_TEXT_LIMIT) -> Dict[str, int]:
        """Read the text of documents held without one, newest first, from the open data portal.

        For rows the sync stored before it kept the text (every document stored between
        2 Oct and 11 Nov 2026), and for documents with no .docx, whose text is their PDF.
        Only empty fields are written: text, an empty date, an empty procedure (on the
        document and on its amendments). A document stored as 'not found' whose record
        lists a PDF is a PDF-only document, and is marked so.

        Returns {"filled", "unread", "remaining"}: `unread` is rows asked this run that
        gave no text (no record, no file, or a file that could not be read).
        """
        no_text = func.coalesce(AmendmentDocument.text_body, "") == ""
        # A row that gave no text is stamped and left alone for a week, so the rows that
        # cannot be read never fill the nightly limit and starve the ones behind them.
        retry_before = datetime.now() - timedelta(days=TEXT_RETRY_DAYS)
        candidates = (
            self.db.query(AmendmentDocument)
            .filter(no_text, AmendmentDocument.ep_identifier.isnot(None),
                    AmendmentDocument.status.in_(("parsed", "unsupported", "not_found")),
                    or_(AmendmentDocument.body_fetched_at.is_(None),
                        AmendmentDocument.body_fetched_at < retry_before))
            .order_by(AmendmentDocument.document_date.desc().nullslast(),
                      AmendmentDocument.pe_reference.desc())
            .limit(limit).all()
        )
        filled = unread = 0
        for row in candidates:
            detail = await self._detail(row.ep_identifier, row.document_type or "AM")
            files = detail.get("files") or {}
            text, source = None, ""
            if files.get("docx"):
                text, source = text_from_docx(await self._download(files["docx"]) or b""), "docx"
            if text is None and files.get("pdf"):
                text, source = text_from_pdf(await self._download(files["pdf"]) or b""), "pdf"
            if files:
                await asyncio.sleep(OPEN_DATA_PACE)
            if text is None or len(text[0]) < MIN_CHARS:
                unread += 1
                row.body_fetched_at = datetime.now()
                self.db.commit()
                logger.info(f"[INFO] no text for {row.ep_identifier}: "
                            f"{'no file in its record' if not files else 'file not readable'}")
                continue
            row.text_body, row.body_html = text[0], text[1]
            row.body_fetched_at = datetime.now()
            if row.document_date is None:
                stated = text[2]
                raw = str(detail.get("date") or "")[:10]
                try:
                    row.document_date = datetime.strptime(raw, "%Y-%m-%d").date() if raw else stated
                except ValueError:
                    row.document_date = stated
            if not (row.procedure_reference or "").strip():
                cover = procedure_from_cover(text[0]) if source == "docx" else ""
                procedure = (cover if cover and not cover.startswith("0000/") else "") \
                    or detail.get("procedure_reference") or ""
                if not procedure and detail.get("parent_identifier"):
                    procedure = self._procedure_of(detail["parent_identifier"])
                if procedure:
                    row.procedure_reference = procedure
                    (self.db.query(MEPAmendment)
                     .filter(MEPAmendment.pe_reference == row.pe_reference,
                             func.coalesce(MEPAmendment.procedure_reference, "") == "")
                     .update({"procedure_reference": procedure}, synchronize_session=False))
            if row.status == "not_found" and source == "pdf":
                row.status = "unsupported"
                row.doceo_url = _pdf_address(row.doceo_url or "")
                row.error_message = (f"{row.ep_identifier} is published as PDF only (no .docx in "
                                     f"its open data record); its text is read from the PDF")
            self.db.commit()
            filled += 1
        remaining = (self.db.query(func.count(AmendmentDocument.id))
                     .filter(no_text, AmendmentDocument.ep_identifier.isnot(None),
                             AmendmentDocument.status.in_(("parsed", "unsupported", "not_found")))
                     .scalar() or 0)
        logger.info(f"[INFO] Document texts: {filled} read, {unread} not readable, "
                    f"{remaining} still without text")
        self.fill_missing_procedures()
        return {"filled": filled, "unread": unread, "remaining": remaining}

    def fill_missing_procedures(self) -> int:
        """Give a document held WITH its text and WITHOUT a procedure the one its cover names.

        No download: the text is already here. These are rows whose text was read by hand
        before the sync read covers (33 on 11 Nov 2026), and any row a later run leaves so.
        A text that came from a PDF is left alone: its cover cannot be trusted.
        """
        rows = (
            self.db.query(AmendmentDocument)
            .filter(func.coalesce(AmendmentDocument.text_body, "") != "",
                    func.coalesce(AmendmentDocument.procedure_reference, "") == "",
                    AmendmentDocument.status == "parsed")
            .all()
        )
        named = 0
        for row in rows:
            head = (row.text_body or "").lstrip()
            if head.startswith(_PDF_STAMPS):
                continue
            cover = procedure_from_cover(head)
            if not cover or cover.startswith("0000/"):
                continue
            row.procedure_reference = cover
            (self.db.query(MEPAmendment)
             .filter(MEPAmendment.pe_reference == row.pe_reference,
                     func.coalesce(MEPAmendment.procedure_reference, "") == "")
             .update({"procedure_reference": cover}, synchronize_session=False))
            named += 1
        if named:
            self.db.commit()
        logger.info(f"[INFO] Procedures read from the cover of held documents: {named} of {len(rows)}")
        return named

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Query amendment_documents table for aggregate stats.

        Returns:
            Dict with total_documents, parsed, failed, pending,
            total_amendments, last_sync, by_year, by_committee
        """
        # Total documents by status
        status_counts = (
            self.db.query(
                AmendmentDocument.status,
                func.count(AmendmentDocument.id),
            )
            .group_by(AmendmentDocument.status)
            .all()
        )
        status_map = {status: count for status, count in status_counts}

        # Total amendments
        total_amendments = self.db.query(func.count(MEPAmendment.id)).scalar() or 0

        # Last sync time
        last_sync = (
            self.db.query(func.max(AmendmentDocument.scraped_at)).scalar()
        )

        # By year (from document_date)
        year_counts = (
            self.db.query(
                func.extract("year", AmendmentDocument.document_date).label("year"),
                func.count(AmendmentDocument.id),
            )
            .filter(AmendmentDocument.document_date.isnot(None))
            .group_by("year")
            .all()
        )
        by_year = {str(int(y)): c for y, c in year_counts if y}

        # By committee
        committee_counts = (
            self.db.query(
                AmendmentDocument.committee_code,
                func.count(AmendmentDocument.id),
            )
            .group_by(AmendmentDocument.committee_code)
            .all()
        )
        by_committee = {code: count for code, count in committee_counts if code}

        return {
            "total_documents": sum(status_map.values()),
            "parsed": status_map.get("parsed", 0),
            "failed": status_map.get("failed", 0),
            "pending": status_map.get("pending", 0),
            "total_amendments": total_amendments,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "by_year": by_year,
            "by_committee": by_committee,
        }

    def _is_settled(self, ep_identifier: str) -> bool:
        """True when the nightly run should leave this document alone: it is parsed, it is
        in a format this parser cannot read, or doceo said 404 less than a week ago.

        A `failed` document is NOT settled: it is tried again every night.
        """
        row = (
            self.db.query(AmendmentDocument.status, AmendmentDocument.scraped_at)
            .filter(AmendmentDocument.ep_identifier == ep_identifier)
            .first()
        )
        if row is None:
            return False
        status, scraped_at = row
        if status in ("parsed", "unsupported"):
            return True
        if status == "not_found" and scraped_at is not None:
            age = datetime.now() - scraped_at.replace(tzinfo=None)
            return age.days < NOT_FOUND_RETRY_DAYS
        return False

    def _procedure_of(self, ep_identifier: str) -> str:
        """The procedure reference stored for a document already held, or ''."""
        row = (
            self.db.query(AmendmentDocument.procedure_reference)
            .filter(AmendmentDocument.ep_identifier == ep_identifier)
            .first()
        )
        return (row[0] or "") if row else ""

    def _is_already_parsed(self, ep_identifier: str) -> bool:
        """Check if a document with this EP identifier is already parsed."""
        exists = (
            self.db.query(AmendmentDocument.id)
            .filter(
                AmendmentDocument.ep_identifier == ep_identifier,
                AmendmentDocument.status == "parsed",
            )
            .first()
        )
        return exists is not None

    async def _fetch_and_parse_document(
        self,
        doc: Dict[str, Any],
    ) -> int:
        """
        Download DOCX, parse amendments, and upsert to database.

        Returns:
            Number of amendments stored
        """
        ep_id = doc.get("identifier", "")
        doceo_url = doc.get("doceo_url", "")
        committee = doc.get("committee_code", "")
        pe_reference = doc.get("pe_reference", "")
        procedure_ref = doc.get("procedure_reference", "")
        doc_type = doc.get("document_type", "AM")

        if not doceo_url:
            raise ValueError(f"No doceo URL for {ep_id}")

        logger.info(f"[INFO] Fetching {doc_type} document: {ep_id} ({pe_reference})")

        # The record first: its date and procedure are stored with the document whatever
        # happens to the file, including when the file turns out not to be a .docx.
        #
        # Discovery builds stubs from identifiers alone and never sees a date, so every
        # amendment stored this way arrived with document_date NULL: 5,678 of the 5,695
        # rows from the first working run. /parliament/amendments filters on that column,
        # so undated rows are invisible to every date query. An amendment document lives
        # under /documents (it 404s under /committee-documents, so until 11 Nov 2026 every
        # one was stored undated). A missing record is a gap to report, never a reason to
        # drop the document.
        detail = await self._detail(ep_id, doc_type)
        if not procedure_ref:
            procedure_ref = detail.get("procedure_reference") or ""
        date_str = doc.get("date", "")
        if not date_str:
            # Verified against the live endpoint: the field is "date" (AFCO-PR-630640 ->
            # 2018-11-23). The others are tried in case a type carries a different one.
            for key in ("date", "document_date", "date_document", "activity_date"):
                value = detail.get(key)
                if isinstance(value, list):
                    value = value[0] if value else None
                if value:
                    date_str = str(value)
                    # _upsert_document_record re-derives the date from this same dict, so
                    # the resolved value has to go back into it or the document row is
                    # written undated while the amendments are not.
                    doc["date"] = date_str
                    break

        # Download DOCX. Prefer the bytes already fetched (open data portal, or the browser
        # past doceo's WAF).
        docx_bytes = self._docx_cache.pop(doceo_url, None)
        # What is already known about this address is the true answer: say that, instead
        # of asking again over plain HTTP (202, zero bytes) and blaming the WAF for a
        # document that arrived whole in a format this parser does not read.
        status_seen, kind = self._fetch_facts.get(doceo_url, (None, None))
        if docx_bytes is None and kind in ("pdf_only", "legacy_doc"):
            # No .docx to parse amendments from, but the PDF edition is the document's own
            # text: store it, so the document is served with a body and not a line of
            # metadata.
            pdf_url = self._pdf_urls.get(doceo_url) or (detail.get("files") or {}).get("pdf")
            if pdf_url:
                parsed_pdf = text_from_pdf(await self._download(pdf_url) or b"")
                if parsed_pdf and len(parsed_pdf[0]) >= MIN_CHARS:
                    doc["_text_body"], doc["_body_html"] = parsed_pdf[0], parsed_pdf[1]
            # No cover to read a procedure from (a PDF's text breaks the reference): the
            # record's, then the parent's.
            if not procedure_ref and detail.get("parent_identifier"):
                procedure_ref = self._procedure_of(detail["parent_identifier"])
            if procedure_ref and not doc.get("procedure_reference"):
                doc["procedure_reference"] = procedure_ref
            if kind == "pdf_only":
                # Its public address is the PDF: the .docx address answers 404.
                doc["doceo_url"] = _pdf_address(doceo_url)
                raise UnsupportedDocumentFormat(
                    f"{ep_id} is published as PDF only (no .docx in its open data record); "
                    f"this parser reads amendments from DOCX only")
            raise UnsupportedDocumentFormat(
                f"{doceo_url} is a legacy Word .doc (OLE2) served under a .docx address; "
                f"this parser reads DOCX only")
        if docx_bytes is None and kind == "not_found":
            raise DocumentNotFound(f"{doceo_url} answered HTTP 404 at doceo")
        if docx_bytes is None:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
                response = await http.get(doceo_url)
                response.raise_for_status()
                docx_bytes = response.content
        # A DOCX is a zip. 202-with-nothing is the WAF, and an HTML body is an error
        # page; both used to reach the parser and be recorded as a parse failure, which
        # reads as "this document is broken" rather than "we never got it".
        if not docx_bytes:
            raise ValueError(
                f"{doceo_url} returned an empty body: the document is behind the WAF "
                f"and the browser fetch did not supply it")
        if docx_bytes[:2] != b"PK":
            raise ValueError(
                f"{doceo_url} did not return a DOCX (first bytes {docx_bytes[:8]!r}, "
                f"{len(docx_bytes)} bytes): a wall or an error page, not a document")

        # The document's own text, from the bytes already in hand. Until 11 Nov 2026 the
        # file was parsed for amendments and thrown away, and nothing scheduled ever read
        # it again: every document stored after 2 Oct was served with no text.
        text = text_from_docx(docx_bytes)
        if text and len(text[0]) >= MIN_CHARS:
            doc["_text_body"], doc["_body_html"] = text[0], text[1]

        # The procedure. The document's cover states it and is the authority: of 1,250
        # documents held with both, the cover agreed with the stored value on 1,225, named
        # several on 13, and on the 12 where it differed the cover was right each time.
        # Then the record's title, then the parent's (the report or opinion it amends).
        cover = procedure_from_cover(text[0]) if text else ""
        if cover and not cover.startswith("0000/"):
            procedure_ref = cover
        if not procedure_ref and detail.get("parent_identifier"):
            procedure_ref = self._procedure_of(detail["parent_identifier"])
        if procedure_ref:
            doc["procedure_reference"] = procedure_ref

        doc_date = None
        if date_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    doc_date = datetime.strptime(date_str[:10], fmt[:len(date_str[:10])]).date()
                    break
                except ValueError:
                    continue

        # Generate a PE reference if missing
        if not pe_reference:
            # Use ep_identifier as a fallback PE reference
            pe_reference = ep_id

        # Parse DOCX
        parsed_amendments = self.parser.parse_docx(
            docx_bytes=docx_bytes,
            committee=committee,
            pe_reference=pe_reference,
            procedure_ref=procedure_ref,
            rapporteur_name=doc.get("rapporteur_name"),
        )

        # Store amendments
        stored_count = 0
        for pa in parsed_amendments:
            try:
                self._upsert_amendment(pa, doceo_url, doc_date)
                stored_count += 1
            except Exception as e:
                logger.warning(f"[WARN] Failed to store AM{pa.amendment_number}: {e}")

        # Record document as parsed
        self._upsert_document_record(
            doc, status="parsed",
            error_message=None, total_amendments=stored_count,
        )

        self.db.commit()
        logger.info(f"[OK] {ep_id}: {stored_count}/{len(parsed_amendments)} amendments stored")

        return stored_count

    def _upsert_amendment(
        self,
        pa: Any,
        source_url: str,
        doc_date: Optional[Any] = None,
    ) -> None:
        """Insert or update a single amendment record."""
        stmt = pg_insert(MEPAmendment).values(
            id=uuid4(),
            procedure_reference=pa.procedure_reference,
            committee_code=pa.committee,
            pe_reference=pa.pe_reference,
            amendment_number=pa.amendment_number,
            author_names=pa.authors,
            political_group=pa.political_group,
            on_behalf_of_group=pa.on_behalf_of_group,
            element_type=pa.element_type,
            element_number=pa.element_number,
            element_reference=pa.element_reference_text,
            amendment_type=pa.amendment_type,
            original_text=pa.original_text,
            proposed_text=pa.proposed_text,
            justification=pa.justification,
            original_language=pa.original_language,
            source_url=source_url,
            source_format="docx",
            parsing_confidence=pa.parsing_confidence,
            document_date=doc_date,
        ).on_conflict_do_update(
            constraint="uq_mep_amendment_pe_num",
            set_={
                "author_names": pa.authors,
                "political_group": pa.political_group,
                "on_behalf_of_group": pa.on_behalf_of_group,
                "element_type": pa.element_type,
                "element_number": pa.element_number,
                "element_reference": pa.element_reference_text,
                "amendment_type": pa.amendment_type,
                "original_text": pa.original_text,
                "proposed_text": pa.proposed_text,
                "justification": pa.justification,
                "parsing_confidence": pa.parsing_confidence,
                "updated_at": datetime.now(),
            },
        )
        self.db.execute(stmt)

    def _upsert_document_record(
        self,
        doc: Dict[str, Any],
        status: str,
        error_message: Optional[str],
        total_amendments: int,
    ) -> None:
        """Insert or update a document tracking record."""
        ep_id = doc.get("identifier", "")
        pe_reference = doc.get("pe_reference", "") or ep_id
        committee = doc.get("committee_code", "")
        procedure_ref = doc.get("procedure_reference", "")
        doc_type = doc.get("document_type", "AM")
        doceo_url = doc.get("doceo_url", "")

        # Parse date
        doc_date = None
        date_str = doc.get("date", "")
        if date_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    doc_date = datetime.strptime(date_str[:10], fmt[:len(date_str[:10])]).date()
                    break
                except ValueError:
                    continue

        # The text read this run, when there is one. Never written as NULL over a text
        # already held, and stamped only when a text arrives.
        text_body = doc.get("_text_body") or None
        body_html = doc.get("_body_html") or None
        fetched_at = datetime.now() if text_body else None

        stmt = pg_insert(AmendmentDocument).values(
            id=uuid4(),
            text_body=text_body,
            body_html=body_html,
            body_fetched_at=fetched_at,
            procedure_reference=procedure_ref,
            committee_code=committee,
            pe_reference=pe_reference,
            document_type=doc_type,
            document_date=doc_date,
            doceo_url=doceo_url,
            rapporteur_name=doc.get("rapporteur_name"),
            total_amendments=total_amendments,
            status=status,
            error_message=error_message,
            ep_identifier=ep_id,
        ).on_conflict_do_update(
            index_elements=["pe_reference"],
            set_={
                "total_amendments": total_amendments,
                "status": status,
                "error_message": error_message,
                "ep_identifier": ep_id,
                # The same address on every run, except for a document found to be
                # published as PDF only, whose .docx address was a 404.
                "doceo_url": doceo_url,
                "text_body": func.coalesce(text_body, AmendmentDocument.text_body),
                "body_html": func.coalesce(body_html, AmendmentDocument.body_html),
                "body_fetched_at": func.coalesce(fetched_at, AmendmentDocument.body_fetched_at),
                # A row first stored before its English record existed kept an empty
                # procedure for ever (21 of the 24 draft reports of October 2026): the
                # clause never wrote it. An empty one is filled; a stated one is left to
                # the run that reads the cover, never blanked.
                "procedure_reference": func.coalesce(
                    func.nullif(procedure_ref or "", ""), AmendmentDocument.procedure_reference),
                # The date was absent from this clause, so a row created before the date
                # was resolvable kept document_date NULL for ever, however many times it
                # was re-synced: 1,145 of 1,365 document rows and 5,678 amendments stored
                # today. COALESCE so a document that genuinely has no date upstream is
                # never overwritten with NULL by a later run that could not read one.
                "document_date": func.coalesce(
                    doc_date, AmendmentDocument.document_date),
                "scraped_at": datetime.now(),
            },
        )
        self.db.execute(stmt)
