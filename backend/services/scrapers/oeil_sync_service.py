"""
OEIL Sync Service

Automatically syncs new legislative procedures from OEIL XML feeds
to the Brubru database.

Usage:
    from services.scrapers.oeil_sync_service import OEILSyncService

    sync = OEILSyncService()
    result = await sync.sync_all()
    print(f"Added: {result['added']}, Updated: {result['updated']}")
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage,
    CarriageStatusEnum,
    TextTypeEnum,
    CarriageSourceEnum
)
from services.api_clients.oeil_client import OEILClient, OEILFeedItem

logger = logging.getLogger(__name__)


# Committee name to code mapping
COMMITTEE_NAME_TO_CODE = {
    "Foreign Affairs": "AFET",
    "Development": "DEVE",
    "International Trade": "INTA",
    "Budgets": "BUDG",
    "Budgetary Control": "CONT",
    "Economic and Monetary Affairs": "ECON",
    "Employment and Social Affairs": "EMPL",
    "Environment, Public Health and Food Safety": "ENVI",
    "Environment, Climate and Food Safety": "ENVI",
    "Industry, Research and Energy": "ITRE",
    "Internal Market and Consumer Protection": "IMCO",
    "Transport and Tourism": "TRAN",
    "Regional Development": "REGI",
    "Agriculture and Rural Development": "AGRI",
    "Fisheries": "PECH",
    "Culture and Education": "CULT",
    "Legal Affairs": "JURI",
    "Civil Liberties, Justice and Home Affairs": "LIBE",
    "Constitutional Affairs": "AFCO",
    "Women's Rights and Gender Equality": "FEMM",
    "Petitions": "PETI",
    "Security and Defence": "SEDE",
    "Subcommittee on Human Rights": "DROI",
}

# Procedure type to text type mapping
PROCEDURE_TYPE_TO_TEXT_TYPE = {
    "COD": TextTypeEnum.LEGISLATIVE,
    "CNS": TextTypeEnum.LEGISLATIVE,
    "APP": TextTypeEnum.LEGISLATIVE,
    "NLE": TextTypeEnum.LEGISLATIVE,
    "BUD": TextTypeEnum.NON_LEGISLATIVE,
    "INI": TextTypeEnum.NON_LEGISLATIVE,
    "RSP": TextTypeEnum.NON_LEGISLATIVE,
    "DEA": TextTypeEnum.NON_LEGISLATIVE,
    "IMM": TextTypeEnum.NON_LEGISLATIVE,
}


class OEILSyncService:
    """
    Service to sync OEIL XML feeds to the legislative carriages database.

    Supports:
    - Latest procedures (COD, INI, RSP, DEA, etc.)
    - Latest documents (COM, SWD)
    - Latest committee reports
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the sync service.

        Args:
            db: Optional database session. If not provided, creates new session.
        """
        self.client = OEILClient()
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        """Get or create database session"""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def sync_all(
        self,
        procedures_days: int = 7,
        documents_days: int = 7,
        reports_days: int = 30,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync all OEIL XML feeds to the database.

        Args:
            procedures_days: Days to look back for procedures
            documents_days: Days to look back for documents
            reports_days: Days to look back for reports
            skip_existing: If True, skip items that already exist in DB

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info("[START] OEIL sync: Fetching all XML feeds...")

        try:
            # Fetch all feeds
            feeds = await self.client.get_all_latest_xml(
                procedures_days=procedures_days,
                documents_days=documents_days,
                reports_days=reports_days
            )

            logger.info(
                f"[INFO] Fetched: {len(feeds['procedures'])} procedures, "
                f"{len(feeds['documents'])} documents, {len(feeds['reports'])} reports"
            )

            # Combine all items
            all_items = (
                feeds['procedures'] +
                feeds['documents'] +
                feeds['reports']
            )

            # Remove duplicates by reference
            seen_refs: Set[str] = set()
            unique_items: List[OEILFeedItem] = []
            for item in all_items:
                if item.reference not in seen_refs:
                    seen_refs.add(item.reference)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique items to process: {len(unique_items)}")

            # Process items
            result = await self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] OEIL sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def sync_procedures(
        self,
        max_days: int = 7,
        filter_types: Optional[List[str]] = None,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync only latest procedures.

        Args:
            max_days: Days to look back
            filter_types: Optional list of procedure types (COD, INI, etc.)
            skip_existing: If True, skip items that already exist
        """
        logger.info(f"[START] Syncing procedures (max_days={max_days})...")

        try:
            items = await self.client.get_latest_procedures_xml(
                max_days=max_days,
                filter_types=filter_types
            )
            return await self._process_items(items, skip_existing)
        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def sync_documents(
        self,
        max_days: int = 7,
        max_count: int = 50,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync only latest COM/SWD documents.
        """
        logger.info(f"[START] Syncing documents (max_days={max_days})...")

        try:
            items = await self.client.get_latest_documents_xml(
                max_days=max_days,
                max_count=max_count
            )
            return await self._process_items(items, skip_existing)
        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def _process_items(
        self,
        items: List[OEILFeedItem],
        skip_existing: bool
    ) -> Dict[str, Any]:
        """
        Process a list of OEIL feed items.
        """
        result = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'items': []
        }

        for item in items:
            try:
                # Check if already exists
                existing = self.db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.oeil_procedure_ref == item.reference
                ).first()

                if existing:
                    if skip_existing:
                        result['skipped'] += 1
                        continue
                    else:
                        # Update existing
                        self._update_carriage(existing, item)
                        result['updated'] += 1
                        result['items'].append({
                            'reference': item.reference,
                            'action': 'updated'
                        })
                else:
                    # Create new
                    carriage = self._create_carriage(item)
                    self.db.add(carriage)
                    result['added'] += 1
                    result['items'].append({
                        'reference': item.reference,
                        'title': item.title,
                        'action': 'added'
                    })

                self.db.commit()

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {item.reference}: {e}")
                self.db.rollback()
                result['errors'] += 1

        return result

    def _create_carriage(self, item: OEILFeedItem) -> LegislativeCarriage:
        """
        Create a new LegislativeCarriage from an OEIL feed item.
        """
        # Generate file_id from reference
        file_id = item.reference.lower()
        file_id = re.sub(r'[/()]', '-', file_id)
        file_id = re.sub(r'-+', '-', file_id).strip('-')

        # Determine text type
        proc_type = item.procedure_type
        text_type = PROCEDURE_TYPE_TO_TEXT_TYPE.get(proc_type, TextTypeEnum.UNKNOWN)

        # Determine status - if it has an OEIL ref, it's at least tabled
        status = CarriageStatusEnum.TABLED

        # Get committee code
        lead_committee = None
        if item.committees:
            committee_name = item.committees[0]
            lead_committee = COMMITTEE_NAME_TO_CODE.get(committee_name)

        # Build description based on procedure type
        description = self._generate_description(item)

        now = datetime.now(timezone.utc)

        carriage = LegislativeCarriage(
            id=uuid.uuid4(),
            file_id=file_id,
            title=item.title,
            description=description,
            current_status=status,
            text_type=text_type,
            oeil_procedure_ref=item.reference,
            source=CarriageSourceEnum.OEIL_DIRECT,
            lead_committee=lead_committee,
            url=item.link,
            scraped_at=now,
            first_seen=now,
            last_updated=now,
        )

        return carriage

    def _update_carriage(self, carriage: LegislativeCarriage, item: OEILFeedItem) -> None:
        """
        Update an existing carriage with new OEIL data.
        """
        # Update committee if we have new data
        if item.committees:
            committee_name = item.committees[0]
            committee_code = COMMITTEE_NAME_TO_CODE.get(committee_name)
            if committee_code:
                carriage.lead_committee = committee_code

        # Update URL if changed
        if item.link:
            carriage.url = item.link

        carriage.last_updated = datetime.now(timezone.utc)

    def _generate_description(self, item: OEILFeedItem) -> str:
        """
        Generate a description based on procedure type.
        """
        proc_type = item.procedure_type

        if proc_type == 'COD':
            return f"Ordinary legislative procedure (codecision): {item.title}"
        elif proc_type == 'CNS':
            return f"Consultation procedure: {item.title}"
        elif proc_type == 'INI':
            return f"Own-initiative report: {item.title}"
        elif proc_type == 'RSP':
            return f"Resolution/Objection: {item.title}"
        elif proc_type == 'DEA':
            return f"Delegated act: {item.title}"
        elif proc_type == 'IMM':
            return f"Immunity request: {item.title}"
        elif proc_type == 'BUD':
            return f"Budgetary procedure: {item.title}"
        elif item.is_com_document:
            return f"Commission document: {item.title}"
        else:
            return item.title


    async def sync_single_procedure(
        self,
        procedure_ref: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Look up and sync a single procedure by reference.

        Useful for adding procedures older than the 30-day XML feed window.

        Args:
            procedure_ref: OEIL procedure reference (e.g. "2025/0726(COD)")
            force: If True, update even if already exists

        Returns:
            Result dict with status and details
        """
        logger.info(f"[START] Looking up single procedure: {procedure_ref}")

        try:
            # Check if already exists
            existing = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == procedure_ref
            ).first()

            if existing and not force:
                logger.info(f"[INFO] Procedure {procedure_ref} already exists, skipping")
                return {
                    'status': 'skipped',
                    'reference': procedure_ref,
                    'title': existing.title,
                    'message': 'Already exists in database'
                }

            # Look up from OEIL page
            item = await self.client.lookup_procedure(procedure_ref)
            if not item:
                return {
                    'status': 'not_found',
                    'reference': procedure_ref,
                    'message': 'Procedure not found on OEIL'
                }

            if existing and force:
                self._update_carriage(existing, item)
                self.db.commit()
                logger.info(f"[OK] Updated procedure {procedure_ref}")
                return {
                    'status': 'updated',
                    'reference': procedure_ref,
                    'title': item.title
                }
            else:
                carriage = self._create_carriage(item)
                self.db.add(carriage)
                self.db.commit()
                logger.info(f"[OK] Added procedure {procedure_ref}: {item.title[:80]}")
                return {
                    'status': 'added',
                    'reference': procedure_ref,
                    'title': item.title
                }

        except Exception as e:
            logger.error(f"[ERROR] Failed to sync procedure {procedure_ref}: {e}")
            self.db.rollback()
            return {
                'status': 'error',
                'reference': procedure_ref,
                'message': str(e)
            }
        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()


# Convenience function for running sync
async def sync_oeil_feeds(
    procedures_days: int = 7,
    documents_days: int = 7,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to sync OEIL feeds.

    Usage:
        from services.scrapers.oeil_sync_service import sync_oeil_feeds
        result = await sync_oeil_feeds()
    """
    service = OEILSyncService()
    return await service.sync_all(
        procedures_days=procedures_days,
        documents_days=documents_days,
        skip_existing=skip_existing
    )
