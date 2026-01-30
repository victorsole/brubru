"""
Consultation Sync Service

Syncs EC Public Consultations data to the Brubru database.

Usage:
    from services.scrapers.consultation_sync_service import ConsultationSyncService

    sync = ConsultationSyncService()
    result = await sync.sync_all()
    print(f"Added: {result['added']}, Updated: {result['updated']}")

Created: January 2026
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Set, Callable

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.public_consultation import (
    PublicConsultation,
    ConsultationDocument,
    ConsultationStatusHistory,
    ConsultationTypeEnum,
    ConsultationStatusEnum,
    DocumentTypeEnum,
)
from services.scrapers.public_consultation_scraper import (
    PublicConsultationScraper,
    get_public_consultation_scraper,
)
from schemas.scrapers.public_consultation_schemas import (
    ScrapedConsultationItem,
    ConsultationType,
    ConsultationStatus,
    DocumentType,
)
from knowledge_base.ec_consultations import (
    calculate_relevance_score,
    PolicyArea,
)

logger = logging.getLogger(__name__)


# Batch size for database commits
BATCH_SIZE = 50


class ConsultationSyncService:
    """
    Service to sync EC Public Consultations to the database.

    Supports:
    - Syncing open, closed, and outcome consultations
    - Status change detection and history tracking
    - Document metadata extraction
    - Deduplication by initiative_id
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the sync service.

        Args:
            db: Optional database session. If not provided, creates new session.
        """
        self.scraper = get_public_consultation_scraper()
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
        max_pages_per_status: int = 5,
        skip_existing: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all consultations to the database.

        Args:
            max_pages_per_status: Max pages to fetch per status
            skip_existing: If True, skip items that already exist (no update)
            progress_callback: Optional callback(current, total, message)

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info("[START] Consultation sync: Fetching all consultations...")

        try:
            # Fetch all consultations
            items = await self.scraper.get_all_consultations(
                max_pages_per_status=max_pages_per_status,
                progress_callback=progress_callback
            )

            logger.info(f"[INFO] Scraped {len(items)} consultations")

            # Remove duplicates by initiative_id
            seen_ids: Set[str] = set()
            unique_items: List[ScrapedConsultationItem] = []
            for item in items:
                if item.initiative_id not in seen_ids:
                    seen_ids.add(item.initiative_id)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique consultations to process: {len(unique_items)}")

            # Process items
            result = await self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] Consultation sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_open(
        self,
        max_pages: int = 10,
        skip_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Sync open consultations only.

        Args:
            max_pages: Max pages to fetch
            skip_existing: If True, skip existing items

        Returns:
            Summary dict
        """
        logger.info("[START] Syncing open consultations...")

        try:
            items = await self.scraper.get_open_consultations(max_pages=max_pages)
            logger.info(f"[INFO] Scraped {len(items)} open consultations")
            return await self._process_items(items, skip_existing)

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_closed(
        self,
        max_pages: int = 5,
        skip_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Sync closed consultations.

        Args:
            max_pages: Max pages to fetch
            skip_existing: If True, skip existing items

        Returns:
            Summary dict
        """
        logger.info("[START] Syncing closed consultations...")

        try:
            items = await self.scraper.get_closed_consultations(max_pages=max_pages)
            logger.info(f"[INFO] Scraped {len(items)} closed consultations")
            return await self._process_items(items, skip_existing)

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_outcomes(
        self,
        max_pages: int = 3
    ) -> Dict[str, Any]:
        """
        Check for and sync consultation outcomes.

        Args:
            max_pages: Max pages to fetch

        Returns:
            Summary dict
        """
        logger.info("[START] Syncing consultation outcomes...")

        try:
            items = await self.scraper.get_consultations_with_outcome(max_pages=max_pages)
            logger.info(f"[INFO] Scraped {len(items)} consultations with outcomes")
            return await self._process_items(items, skip_existing=False)

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def _process_items(
        self,
        items: List[ScrapedConsultationItem],
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

        for item in items:
            try:
                # Check if already exists
                existing = self.db.query(PublicConsultation).filter(
                    PublicConsultation.initiative_id == item.initiative_id
                ).first()

                if existing:
                    if skip_existing:
                        result['skipped'] += 1
                        continue
                    else:
                        # Update existing
                        status_changed = self._update_consultation(existing, item)
                        if status_changed:
                            result['status_changes'] += 1
                        result['updated'] += 1
                        result['items'].append({
                            'initiative_id': item.initiative_id,
                            'action': 'updated',
                            'status_changed': status_changed
                        })
                else:
                    # Create new
                    consultation = self._create_consultation(item)
                    self.db.add(consultation)
                    result['added'] += 1
                    result['items'].append({
                        'initiative_id': item.initiative_id,
                        'title': item.title[:100],
                        'action': 'added'
                    })

                batch_count += 1

                # Commit in batches
                if batch_count >= BATCH_SIZE:
                    self.db.commit()
                    batch_count = 0

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {item.initiative_id}: {e}")
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

    def _create_consultation(self, item: ScrapedConsultationItem) -> PublicConsultation:
        """
        Create a new PublicConsultation from scraped data.
        """
        # Map consultation type
        consultation_type = self._map_consultation_type(item.consultation_type)

        # Map status
        status = self._map_status(item.status)

        # Calculate relevance score
        relevance_score = self._calculate_relevance(item)

        now = datetime.now()

        consultation = PublicConsultation(
            initiative_id=item.initiative_id,
            publication_id=item.publication_id,
            title=item.title,
            short_title=item.short_title,
            description=item.description,
            consultation_type=consultation_type,
            status=status,
            dg_responsible=item.dg_responsible,
            policy_areas=item.policy_areas,
            start_date=item.start_date,
            end_date=item.end_date,
            feedback_count=item.feedback_count,
            portal_url=item.portal_url,
            feedback_url=item.feedback_url,
            relevance_score=relevance_score,
            scraped_at=item.scraped_at,
            first_seen=now,
            last_updated=now,
        )

        return consultation

    def _update_consultation(
        self,
        existing: PublicConsultation,
        item: ScrapedConsultationItem
    ) -> bool:
        """
        Update existing consultation with new scraped data.

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
            history = ConsultationStatusHistory(
                consultation_id=existing.id,
                old_status=old_status,
                new_status=new_status,
                changed_at=datetime.now(),
                detected_during_sync=True
            )
            self.db.add(history)
            existing.status = new_status

        # Update other fields
        existing.title = item.title
        existing.short_title = item.short_title
        existing.description = item.description
        existing.consultation_type = self._map_consultation_type(item.consultation_type)
        existing.dg_responsible = item.dg_responsible
        existing.policy_areas = item.policy_areas
        existing.start_date = item.start_date
        existing.end_date = item.end_date
        existing.feedback_count = item.feedback_count
        existing.portal_url = item.portal_url
        existing.feedback_url = item.feedback_url
        existing.relevance_score = self._calculate_relevance(item)
        existing.scraped_at = item.scraped_at
        existing.last_updated = datetime.now()

        return status_changed

    def _map_consultation_type(self, type_val) -> ConsultationTypeEnum:
        """Map scraped consultation type to enum."""
        if isinstance(type_val, str):
            try:
                return ConsultationTypeEnum(type_val)
            except ValueError:
                pass
        elif hasattr(type_val, 'value'):
            try:
                return ConsultationTypeEnum(type_val.value)
            except ValueError:
                pass
        return ConsultationTypeEnum.INITIATIVE

    def _map_status(self, status_val) -> ConsultationStatusEnum:
        """Map scraped status to enum."""
        if isinstance(status_val, str):
            try:
                return ConsultationStatusEnum(status_val)
            except ValueError:
                pass
        elif hasattr(status_val, 'value'):
            try:
                return ConsultationStatusEnum(status_val.value)
            except ValueError:
                pass
        return ConsultationStatusEnum.OPEN

    def _calculate_relevance(self, item: ScrapedConsultationItem) -> int:
        """Calculate relevance score for a consultation."""
        # Get primary policy area
        policy_area = PolicyArea.OTHER
        if item.policy_areas:
            try:
                policy_area = PolicyArea(item.policy_areas[0])
            except ValueError:
                pass

        # Calculate days remaining
        days_remaining = None
        if item.end_date:
            days_remaining = (item.end_date - date.today()).days

        return calculate_relevance_score(
            item.consultation_type,
            policy_area,
            days_remaining
        )


# Convenience function
async def sync_consultations(
    status: Optional[str] = None,
    max_pages: int = 5,
    skip_existing: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to sync consultations.

    Usage:
        from services.scrapers.consultation_sync_service import sync_consultations
        result = await sync_consultations(status='open')
    """
    service = ConsultationSyncService()

    if status == 'open':
        return await service.sync_open(max_pages=max_pages, skip_existing=skip_existing)
    elif status == 'closed':
        return await service.sync_closed(max_pages=max_pages, skip_existing=skip_existing)
    elif status == 'outcome':
        return await service.sync_outcomes(max_pages=max_pages)
    else:
        return await service.sync_all(
            max_pages_per_status=max_pages,
            skip_existing=skip_existing
        )
