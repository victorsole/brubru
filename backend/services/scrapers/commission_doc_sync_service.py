"""
Commission Document Sync Service

Syncs Commission documents from EUR-Lex (fallback) or the RegDoc API
to the Brubru database.

When the RegDoc API returns (target: mid-March 2026), the data source
inside get_latest_with_fallback() will swap automatically.

Usage:
    from services.scrapers.commission_doc_sync_service import CommissionDocSyncService

    service = CommissionDocSyncService()
    result = await service.sync_all(days=14)
    print(f"Added: {result['added']}, Skipped: {result['skipped']}")

Created: February 2026
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
import uuid

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.commission_document import CommissionDocument
from services.api_clients.commission_doc_register_client import (
    get_commission_doc_register_client,
    CommissionDocRegisterClient,
)
from schemas.scrapers.commission_doc_register_schemas import (
    CommissionDocItem,
    CommissionDocType,
)

logger = logging.getLogger(__name__)


class CommissionDocSyncService:
    """
    Service to sync Commission documents to the database.

    Uses get_latest_with_fallback() which:
    - Tries the RegDoc API first
    - Falls back to EUR-Lex RSS feeds (COM proposals + OJ legislation)
    """

    def __init__(self, db: Optional[Session] = None):
        self.client = get_commission_doc_register_client()
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        """Get or create database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def sync_all(
        self,
        days: int = 7,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync all available Commission documents to the database.

        Fetches COM proposals and OJ legislation via EUR-Lex fallback
        (or RegDoc API when available), deduplicates by reference,
        and writes to the commission_documents table.

        Args:
            days: How many days back to search.
            skip_existing: If True, skip items already in the database.

        Returns:
            Summary dict with added, updated, skipped, errors counts.
        """
        logger.info(f"[START] Commission doc sync (days={days})...")

        try:
            # Fetch COM proposals
            com_items = await self.client.get_latest_with_fallback(
                doc_type=CommissionDocType.COM,
                days=days
            )
            logger.info(f"[INFO] Fetched {len(com_items)} COM proposals")

            # Fetch OJ legislation
            oj_items = await self.client.get_latest_with_fallback(
                doc_type=CommissionDocType.OJ,
                days=days
            )
            logger.info(f"[INFO] Fetched {len(oj_items)} OJ legislation items")

            # Fetch SWD documents via SPARQL
            swd_items = await self.client.get_latest_with_fallback(
                doc_type=CommissionDocType.SWD,
                days=days
            )
            logger.info(f"[INFO] Fetched {len(swd_items)} SWD documents")

            # Fetch JOIN documents via SPARQL
            join_items = await self.client.get_latest_with_fallback(
                doc_type=CommissionDocType.JOIN,
                days=days
            )
            logger.info(f"[INFO] Fetched {len(join_items)} JOIN documents")

            # Combine and deduplicate by reference
            all_items = com_items + oj_items + swd_items + join_items
            seen_refs: Set[str] = set()
            unique_items: List[CommissionDocItem] = []
            for item in all_items:
                ref = item.reference.strip()
                if ref and ref not in seen_refs:
                    seen_refs.add(ref)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique items to process: {len(unique_items)}")

            # Process items
            result = self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] Commission doc sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    def _process_items(
        self,
        items: List[CommissionDocItem],
        skip_existing: bool
    ) -> Dict[str, Any]:
        """Process a list of Commission document items."""
        result = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }

        for item in items:
            try:
                # Check if already exists by reference
                existing = self.db.query(CommissionDocument).filter(
                    CommissionDocument.reference == item.reference.strip()
                ).first()

                if existing:
                    if skip_existing:
                        result['skipped'] += 1
                        continue
                    else:
                        # Update existing
                        self._update_document(existing, item)
                        result['updated'] += 1
                else:
                    # Create new
                    doc = self._create_document(item)
                    self.db.add(doc)
                    result['added'] += 1

                self.db.commit()

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {item.reference}: {e}")
                self.db.rollback()
                result['errors'] += 1

        return result

    def _create_document(self, item: CommissionDocItem) -> CommissionDocument:
        """Create a new CommissionDocument from a fetched item."""
        now = datetime.now(timezone.utc)

        # Parse publication date
        pub_date = None
        if item.publication_date:
            if isinstance(item.publication_date, str):
                try:
                    pub_date = datetime.fromisoformat(item.publication_date.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pub_date = None
            elif isinstance(item.publication_date, datetime):
                pub_date = item.publication_date
            else:
                try:
                    pub_date = datetime.combine(item.publication_date, datetime.min.time())
                except (ValueError, TypeError):
                    pub_date = None

        # Extract procedure reference from title if present
        procedure_ref = item.procedure_ref
        if not procedure_ref and item.title:
            proc_match = re.search(r'\d{4}/\d{4}\([A-Z]{3}\)', item.title)
            if proc_match:
                procedure_ref = proc_match.group(0)

        return CommissionDocument(
            id=uuid.uuid4(),
            reference=item.reference.strip(),
            title=item.title,
            doc_type=item.doc_type.value if hasattr(item.doc_type, 'value') else item.doc_type,
            publication_date=pub_date,
            dg_responsible=item.dg_responsible,
            procedure_ref=procedure_ref,
            languages=item.languages if item.languages else ['EN'],
            portal_url=item.portal_url,
            celex=None,  # Will be populated when RegDoc API returns
            scraped_at=now,
            first_seen=now,
            last_updated=now,
        )

    def _update_document(self, doc: CommissionDocument, item: CommissionDocItem) -> None:
        """Update an existing Commission document with new data."""
        if item.title and item.title != doc.title:
            doc.title = item.title
        if item.portal_url and not doc.portal_url:
            doc.portal_url = item.portal_url
        if item.dg_responsible and not doc.dg_responsible:
            doc.dg_responsible = item.dg_responsible
        doc.last_updated = datetime.now(timezone.utc)

    # =========================================================================
    # Enrichment (fills in missing data from RegDoc API)
    # =========================================================================

    @staticmethod
    def _to_api_reference(db_reference: str) -> Optional[str]:
        """
        Convert a database reference to the format expected by the RegDoc API.

        The RegDoc API expects references like COM(2026)90, SWD(2025)420.
        Our DB may store CELEX numbers (e.g. 52026PC0090) or references
        with spaces (e.g. SWD(2026) 65).

        Returns None if the reference cannot be converted.
        """
        ref = db_reference.strip()

        # Already in document reference format (COM(...), SWD(...), etc.)
        # Just strip internal spaces: "SWD(2026) 65" -> "SWD(2026)65"
        doc_ref_match = re.match(
            r'(COM|SWD|SEC|C|JOIN)\((\d{4})\)\s*(\d+)', ref
        )
        if doc_ref_match:
            prefix = doc_ref_match.group(1)
            year = doc_ref_match.group(2)
            number = doc_ref_match.group(3)
            return f"{prefix}({year}){number}"

        # CELEX format for COM proposals: 5YYYYPCNNNN -> COM(YYYY)NNN
        celex_com = re.match(r'5(\d{4})PC(\d+)', ref)
        if celex_com:
            year = celex_com.group(1)
            number = str(int(celex_com.group(2)))  # strip leading zeros
            return f"COM({year}){number}"

        # CELEX format for SWD: 5YYYYSCNNNN -> SWD(YYYY)NNN
        celex_swd = re.match(r'5(\d{4})SC(\d+)', ref)
        if celex_swd:
            year = celex_swd.group(1)
            number = str(int(celex_swd.group(2)))
            return f"SWD({year}){number}"

        # CELEX format for JOIN: 5YYYYJCNNNN -> JOIN(YYYY)NNN
        celex_join = re.match(r'5(\d{4})JC(\d+)', ref)
        if celex_join:
            year = celex_join.group(1)
            number = str(int(celex_join.group(2)))
            return f"JOIN({year}){number}"

        # OJ/adopted legislation CELEX (3YYYYRNNNN etc.) - not in RegDoc register
        if re.match(r'^3\d{4}[A-Z]\d+', ref):
            return None

        return None

    async def enrich_documents(
        self,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Enrich existing documents with data from the RegDoc API.

        Finds documents with placeholder titles (starting with "SWD document")
        or missing DG info, then calls the RegDoc API to fill in the gaps.

        Args:
            limit: Maximum number of documents to enrich per run.

        Returns:
            Summary dict with enriched, skipped, errors counts.
        """
        logger.info(f"[START] Commission doc enrichment (limit={limit})...")

        result = {
            'enriched': 0,
            'skipped': 0,
            'errors': 0,
        }

        try:
            # Find documents needing enrichment:
            # 1. Placeholder titles (SWD/JOIN documents from SPARQL)
            # 2. Missing DG responsible
            from sqlalchemy import or_

            docs_to_enrich = self.db.query(CommissionDocument).filter(
                or_(
                    CommissionDocument.title.like('SWD document%'),
                    CommissionDocument.title.like('JOIN document%'),
                    CommissionDocument.dg_responsible.is_(None),
                )
            ).limit(limit).all()

            logger.info(f"[INFO] Found {len(docs_to_enrich)} documents to enrich")

            for doc in docs_to_enrich:
                try:
                    # Convert DB reference to API format
                    api_ref = self._to_api_reference(doc.reference)
                    if not api_ref:
                        result['skipped'] += 1
                        continue

                    enriched = await self.client.fetch_document_by_reference(api_ref)

                    if not enriched:
                        result['skipped'] += 1
                        continue

                    updated = False

                    # Update title if we had a placeholder or CELEX-only title
                    if (
                        enriched.title
                        and enriched.title != enriched.reference
                        and (
                            doc.title.startswith('SWD document')
                            or doc.title.startswith('JOIN document')
                            or doc.title.startswith('CELEX:')
                            or not doc.title
                        )
                    ):
                        doc.title = enriched.title
                        updated = True

                    # Fill in DG responsible
                    if enriched.dg_responsible and not doc.dg_responsible:
                        doc.dg_responsible = enriched.dg_responsible
                        updated = True

                    # Update languages if more complete
                    if enriched.languages and len(enriched.languages) > len(doc.languages or []):
                        doc.languages = enriched.languages
                        updated = True

                    if updated:
                        doc.last_updated = datetime.now(timezone.utc)
                        self.db.commit()
                        result['enriched'] += 1
                        logger.info(f"[OK] Enriched {doc.reference}")
                    else:
                        result['skipped'] += 1

                except Exception as e:
                    logger.error(f"[ERROR] Failed to enrich {doc.reference}: {e}")
                    self.db.rollback()
                    result['errors'] += 1

            logger.info(
                f"[OK] Enrichment complete: "
                f"enriched={result['enriched']}, skipped={result['skipped']}, "
                f"errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()
