"""
Committee Work Sync Service

Syncs EP Committee 'Work in Progress' data to the Brubru database.

Usage:
    from services.scrapers.committee_work_sync_service import CommitteeWorkSyncService

    sync = CommitteeWorkSyncService()
    result = await sync.sync_all()
    print(f"Added: {result['added']}, Updated: {result['updated']}")

Created: January 2026
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Callable
import re

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.committee_work import (
    CommitteeWorkItem,
    CommitteeWorkStatusHistory,
    ProcedureTypeEnum,
    CommitteeRoleEnum,
    CommitteeWorkStatusEnum,
)
from models.legislative_train import LegislativeCarriage
from services.scrapers.committee_work_scraper import CommitteeWorkInProgressScraper
from schemas.scrapers.committee_work_schemas import ScrapedCommitteeWorkItem
from knowledge_base.ep_committees import EP_COMMITTEE_CODES

logger = logging.getLogger(__name__)


# Map scraped status text to enum
STATUS_TEXT_TO_ENUM = {
    'in committee': CommitteeWorkStatusEnum.IN_COMMITTEE,
    'awaiting': CommitteeWorkStatusEnum.AWAITING_VOTE,
    'awaiting vote': CommitteeWorkStatusEnum.AWAITING_VOTE,
    'tabled': CommitteeWorkStatusEnum.TABLED,
    'adopted': CommitteeWorkStatusEnum.ADOPTED,
    'rejected': CommitteeWorkStatusEnum.REJECTED,
    'withdrawn': CommitteeWorkStatusEnum.WITHDRAWN,
    'pending': CommitteeWorkStatusEnum.PENDING,
    'completed': CommitteeWorkStatusEnum.COMPLETED,
}

# Relevance scores by procedure type
RELEVANCE_SCORES = {
    ProcedureTypeEnum.COD: 100,
    ProcedureTypeEnum.APP: 80,
    ProcedureTypeEnum.CNS: 70,
    ProcedureTypeEnum.NLE: 50,
    ProcedureTypeEnum.INI: 40,
}


class CommitteeWorkSyncService:
    """
    Service to sync EP Committee Work in Progress data to the database.

    Supports:
    - Syncing single committee
    - Syncing all committees
    - Optional progress callback for UI feedback
    - Linking to existing LegislativeCarriage records via OEIL ref
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the sync service.

        Args:
            db: Optional database session. If not provided, creates new session.
        """
        self.scraper = CommitteeWorkInProgressScraper()
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
        max_pages_per_committee: int = 5,
        skip_existing: bool = False,
        committees: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all committees to the database.

        Args:
            max_pages_per_committee: Max pages to scrape per committee
            skip_existing: If True, skip items that already exist (no update)
            committees: Optional list of specific committee codes to sync
            progress_callback: Optional callback(current, total, message)

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info("[START] Committee Work sync: Scraping all committees...")

        try:
            # Scrape all committees
            items = await self.scraper.scrape_all_committees(
                max_pages_per_committee=max_pages_per_committee,
                committees=committees,
                progress_callback=progress_callback
            )

            logger.info(f"[INFO] Scraped {len(items)} items from committees")

            # Remove duplicates by (procedure_ref, committee_code)
            seen_keys: Set[str] = set()
            unique_items: List[ScrapedCommitteeWorkItem] = []
            for item in items:
                key = f"{item.procedure_ref}:{item.committee_code}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique items to process: {len(unique_items)}")

            # Process items
            result = await self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] Committee Work sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_committee(
        self,
        committee_code: str,
        max_pages: int = 10,
        skip_existing: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync a single committee.

        Args:
            committee_code: Committee code (e.g., "AFET")
            max_pages: Max pages to scrape
            skip_existing: If True, skip existing items
            progress_callback: Optional progress callback

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        committee_code = committee_code.upper()

        if committee_code not in EP_COMMITTEE_CODES:
            raise ValueError(f"Invalid committee code: {committee_code}")

        logger.info(f"[START] Syncing committee {committee_code}...")

        try:
            items = await self.scraper.scrape_committee(
                committee_code,
                max_pages=max_pages,
                progress_callback=progress_callback
            )

            logger.info(f"[INFO] Scraped {len(items)} items from {committee_code}")

            result = await self._process_items(items, skip_existing)

            logger.info(
                f"[OK] Committee {committee_code} sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def _process_items(
        self,
        items: List[ScrapedCommitteeWorkItem],
        skip_existing: bool
    ) -> Dict[str, Any]:
        """
        Process scraped items and save to database.
        """
        result = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'status_changes': 0,
            'items': []
        }

        batch_count = 0
        BATCH_SIZE = 50

        for item in items:
            try:
                # Check if already exists
                existing = self.db.query(CommitteeWorkItem).filter(
                    CommitteeWorkItem.procedure_ref == item.procedure_ref,
                    CommitteeWorkItem.committee_code == item.committee_code
                ).first()

                if existing:
                    if skip_existing:
                        result['skipped'] += 1
                        continue
                    else:
                        # Update existing
                        status_changed = self._update_work_item(existing, item)
                        if status_changed:
                            result['status_changes'] += 1
                        result['updated'] += 1
                        result['items'].append({
                            'procedure_ref': item.procedure_ref,
                            'committee_code': item.committee_code,
                            'action': 'updated',
                            'status_changed': status_changed
                        })
                else:
                    # Create new
                    work_item = self._create_work_item(item)
                    self.db.add(work_item)
                    result['added'] += 1
                    result['items'].append({
                        'procedure_ref': item.procedure_ref,
                        'committee_code': item.committee_code,
                        'title': item.title[:100],
                        'action': 'added'
                    })

                batch_count += 1

                # Commit in batches
                if batch_count >= BATCH_SIZE:
                    self.db.commit()
                    batch_count = 0

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {item.procedure_ref}: {e}")
                self.db.rollback()
                result['errors'] += 1

        # Final commit
        if batch_count > 0:
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"[ERROR] Final commit failed: {e}")
                self.db.rollback()

        return result

    def _create_work_item(self, item: ScrapedCommitteeWorkItem) -> CommitteeWorkItem:
        """
        Create a new CommitteeWorkItem from scraped data.
        """
        # Map procedure type
        try:
            procedure_type = ProcedureTypeEnum(item.procedure_type.value)
        except (ValueError, AttributeError):
            procedure_type = ProcedureTypeEnum.INI

        # Map committee role
        try:
            committee_role = CommitteeRoleEnum(item.committee_role.value)
        except (ValueError, AttributeError):
            committee_role = CommitteeRoleEnum.LEAD

        # Map status
        status = self._map_status(item.status)

        # Calculate relevance score
        relevance_score = RELEVANCE_SCORES.get(procedure_type, 40)

        # Try to find linked LegislativeCarriage
        legislative_carriage_id = None
        carriage = self.db.query(LegislativeCarriage).filter(
            LegislativeCarriage.oeil_procedure_ref == item.procedure_ref
        ).first()
        if carriage:
            legislative_carriage_id = carriage.id

        now = datetime.now()

        work_item = CommitteeWorkItem(
            procedure_ref=item.procedure_ref,
            committee_code=item.committee_code,
            title=item.title,
            description=item.description,
            procedure_type=procedure_type,
            committee_role=committee_role,
            relevance_score=relevance_score,
            rapporteur_name=item.rapporteur_name,
            rapporteur_mep_id=item.rapporteur_mep_id,
            status=status,
            status_text=item.status,
            oeil_url=item.oeil_url,
            ep_page_url=item.ep_page_url,
            source_url=item.source_url,
            legislative_carriage_id=legislative_carriage_id,
            scraped_at=item.scraped_at,
            first_seen=now,
            last_updated=now,
        )

        return work_item

    def _update_work_item(
        self,
        existing: CommitteeWorkItem,
        item: ScrapedCommitteeWorkItem
    ) -> bool:
        """
        Update existing work item with new scraped data.

        Returns:
            True if status changed, False otherwise
        """
        status_changed = False
        old_status = existing.status
        new_status = self._map_status(item.status)

        # Check for status change
        if old_status != new_status:
            status_changed = True
            # Record status change history
            history = CommitteeWorkStatusHistory(
                work_item_id=existing.id,
                old_status=old_status,
                new_status=new_status,
                changed_at=datetime.now(),
                detected_during_sync=True
            )
            self.db.add(history)
            existing.status = new_status

        # Update other fields
        existing.status_text = item.status
        existing.rapporteur_name = item.rapporteur_name
        existing.rapporteur_mep_id = item.rapporteur_mep_id
        existing.oeil_url = item.oeil_url
        existing.ep_page_url = item.ep_page_url
        existing.source_url = item.source_url
        existing.scraped_at = item.scraped_at
        existing.last_updated = datetime.now()

        # Try to link to LegislativeCarriage if not already linked
        if not existing.legislative_carriage_id:
            carriage = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == item.procedure_ref
            ).first()
            if carriage:
                existing.legislative_carriage_id = carriage.id

        return status_changed

    def _map_status(self, status_text: Optional[str]) -> CommitteeWorkStatusEnum:
        """
        Map status text to enum.
        """
        if not status_text:
            return CommitteeWorkStatusEnum.UNKNOWN

        status_lower = status_text.lower().strip()

        # Direct match
        if status_lower in STATUS_TEXT_TO_ENUM:
            return STATUS_TEXT_TO_ENUM[status_lower]

        # Partial match
        for key, enum_value in STATUS_TEXT_TO_ENUM.items():
            if key in status_lower:
                return enum_value

        return CommitteeWorkStatusEnum.UNKNOWN


# Convenience function
async def sync_committee_work(
    committees: Optional[List[str]] = None,
    max_pages: int = 5,
    skip_existing: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to sync committee work.

    Usage:
        from services.scrapers.committee_work_sync_service import sync_committee_work
        result = await sync_committee_work(committees=['AFET', 'LIBE'])
    """
    service = CommitteeWorkSyncService()
    return await service.sync_all(
        max_pages_per_committee=max_pages,
        committees=committees,
        skip_existing=skip_existing
    )
