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

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy import select, func
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

logger = logging.getLogger(__name__)


@dataclass
class BulkSyncResult:
    """Summary of a bulk sync operation."""
    documents_discovered: int = 0
    documents_skipped: int = 0  # already parsed
    documents_parsed: int = 0
    documents_failed: int = 0
    amendments_stored: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


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

    async def sync_all(
        self,
        years: Optional[List[int]] = None,
        work_types: Optional[List[str]] = None,
        force_refetch: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> BulkSyncResult:
        """
        Full bulk sync: enumerate documents from EP Open Data API,
        download and parse DOCX files, upsert amendments.

        Args:
            years: Years to fetch (defaults to current year)
            work_types: Document types (defaults to AM + PR)
            force_refetch: Re-parse even if already done
            progress_callback: Optional callback(current, total, message)

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
        logger.info(f"[INFO] Discovered {len(documents)} documents")

        # Phase 2: Process each document
        for i, doc in enumerate(documents):
            ep_id = doc.get("identifier", "")
            pe_ref = doc.get("pe_reference", "")

            if not ep_id:
                continue

            # Skip already parsed (unless forced)
            if not force_refetch and self._is_already_parsed(ep_id):
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

            except Exception as e:
                error_msg = f"Failed {ep_id}: {str(e)}"
                logger.warning(f"[WARN] {error_msg}")
                result.errors.append(error_msg)
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
            f"{result.amendments_stored} amendments ({result.duration_seconds}s)"
        )

        return result

    async def sync_incremental(self) -> BulkSyncResult:
        """
        Incremental sync: only current year, skip already-parsed docs.
        Designed to be called by the daily scheduler.
        """
        current_year = datetime.now().year
        return await self.sync_all(
            years=[current_year],
            work_types=[WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS],
            force_refetch=False,
        )

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

        # Download DOCX
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
            response = await http.get(doceo_url)
            response.raise_for_status()
            docx_bytes = response.content

        # Parse date
        doc_date = None
        date_str = doc.get("date", "")
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

        stmt = pg_insert(AmendmentDocument).values(
            id=uuid4(),
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
                "scraped_at": datetime.now(),
            },
        )
        self.db.execute(stmt)
