"""
Texts Adopted Sync Service

Syncs EP Texts Adopted data to the Brubru database.

Usage:
    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService

    sync = TextsAdoptedSyncService()
    result = await sync.sync_rss()
    print(f"Added: {result['added']}, Updated: {result['updated']}")

Created: February 2026
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Callable

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.text_adopted import (
    TextAdopted,
    UserTextAdoptedTrack,
    TextTypeEnum,
)
from models.legislative_train import LegislativeCarriage
from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
from schemas.scrapers.texts_adopted_schemas import (
    ScrapedTextAdopted,
    PARLIAMENTARY_TERMS,
)

logger = logging.getLogger(__name__)


class TextsAdoptedSyncService:
    """
    Service to sync EP Texts Adopted data to the database.

    Supports:
    - Syncing from RSS feed (recent texts)
    - Syncing a single parliamentary term (historical backfill)
    - Syncing all terms
    - Optional progress callback for UI feedback
    - Linking to existing LegislativeCarriage records via procedure ref
    """

    def __init__(self, db: Optional[Session] = None):
        self.scraper = TextsAdoptedScraper()
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        """Get or create database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def sync_rss(
        self,
        skip_existing: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync from RSS feed (recent adopted texts).

        Args:
            skip_existing: If True, skip items that already exist
            progress_callback: Optional callback(current, total, message)

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info("[START] Texts Adopted RSS sync...")

        try:
            items = await self.scraper.fetch_rss()
            logger.info(f"[INFO] Fetched {len(items)} items from RSS")

            result = await self._process_items(items, skip_existing, progress_callback)

            logger.info(
                f"[OK] RSS sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_term(
        self,
        term: int = 10,
        max_dates: Optional[int] = None,
        skip_existing: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all texts from a parliamentary term via TOC pages.

        Args:
            term: Parliamentary term number (4-10)
            max_dates: Max plenary dates to scrape (None = all)
            skip_existing: If True, skip existing items
            progress_callback: Optional callback(current, total, message)

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        if term not in PARLIAMENTARY_TERMS:
            raise ValueError(f"Invalid term: {term}. Valid: {list(PARLIAMENTARY_TERMS.keys())}")

        logger.info(f"[START] Texts Adopted sync for term {term}...")

        try:
            items = await self.scraper.scrape_term(
                term=term,
                max_dates=max_dates,
                progress_callback=progress_callback
            )

            logger.info(f"[INFO] Scraped {len(items)} items from term {term}")

            # Deduplicate by ta_reference
            seen: Set[str] = set()
            unique_items: List[ScrapedTextAdopted] = []
            for item in items:
                if item.ta_reference not in seen:
                    seen.add(item.ta_reference)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique items to process: {len(unique_items)}")

            result = await self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] Term {term} sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def sync_all(
        self,
        terms: Optional[List[int]] = None,
        max_dates_per_term: Optional[int] = None,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync multiple parliamentary terms.

        Args:
            terms: List of term numbers to sync (default: all 4-10)
            max_dates_per_term: Max dates per term (None = all)
            skip_existing: If True, skip existing items (default: True for backfill)
            progress_callback: Optional callback

        Returns:
            Aggregated summary dict
        """
        terms_to_sync = terms or list(PARLIAMENTARY_TERMS.keys())
        logger.info(f"[START] Syncing terms: {terms_to_sync}")

        totals = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'terms_synced': 0,
            'items': []
        }

        try:
            for term in sorted(terms_to_sync, reverse=True):
                try:
                    result = await self.sync_term(
                        term=term,
                        max_dates=max_dates_per_term,
                        skip_existing=skip_existing,
                        progress_callback=progress_callback
                    )
                    totals['added'] += result['added']
                    totals['updated'] += result['updated']
                    totals['skipped'] += result['skipped']
                    totals['errors'] += result['errors']
                    totals['terms_synced'] += 1
                except Exception as e:
                    logger.error(f"[ERROR] Failed to sync term {term}: {e}")
                    totals['errors'] += 1

            logger.info(
                f"[OK] All terms sync complete: "
                f"terms={totals['terms_synced']}, added={totals['added']}, "
                f"updated={totals['updated']}, errors={totals['errors']}"
            )

            return totals

        finally:
            if self._owns_db and self._db:
                self._db.close()

    async def _process_items(
        self,
        items: List[ScrapedTextAdopted],
        skip_existing: bool,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """Process scraped items and save to database."""
        result = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'items': []
        }

        batch_count = 0
        BATCH_SIZE = 50
        total = len(items)

        for i, item in enumerate(items):
            if progress_callback and i % 10 == 0:
                progress_callback(i + 1, total, f"Processing {item.ta_reference}")

            try:
                # Check if already exists
                existing = self.db.query(TextAdopted).filter(
                    TextAdopted.ta_reference == item.ta_reference
                ).first()

                if existing:
                    if skip_existing:
                        result['skipped'] += 1
                        continue
                    else:
                        # Update existing
                        self._update_text(existing, item)
                        result['updated'] += 1
                        result['items'].append({
                            'ta_reference': item.ta_reference,
                            'action': 'updated'
                        })
                else:
                    # Create new
                    text = self._create_text(item)
                    self.db.add(text)
                    result['added'] += 1
                    result['items'].append({
                        'ta_reference': item.ta_reference,
                        'title': item.title[:100],
                        'action': 'added'
                    })

                batch_count += 1

                # Commit in batches
                if batch_count >= BATCH_SIZE:
                    self.db.commit()
                    batch_count = 0

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {item.ta_reference}: {e}")
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

    def _create_text(self, item: ScrapedTextAdopted) -> TextAdopted:
        """Create a new TextAdopted from scraped data."""
        # Map text type
        try:
            text_type = TextTypeEnum(item.text_type)
        except (ValueError, AttributeError):
            text_type = TextTypeEnum.OTHER

        # Try to find linked LegislativeCarriage
        legislative_carriage_id = None
        if item.procedure_ref:
            carriage = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == item.procedure_ref
            ).first()
            if carriage:
                legislative_carriage_id = carriage.id

        now = datetime.now()

        return TextAdopted(
            ta_reference=item.ta_reference,
            title=item.title,
            description=item.description,
            text_type=text_type.value,
            procedure_ref=item.procedure_ref,
            parliamentary_term=item.parliamentary_term,
            adoption_date=item.adoption_date,
            source_url=item.source_url,
            full_text_url=item.full_text_url,
            pdf_url=item.pdf_url,
            legislative_carriage_id=legislative_carriage_id,
            scraped_at=item.scraped_at,
            first_seen=now,
            last_updated=now,
        )

    def _update_text(self, existing: TextAdopted, item: ScrapedTextAdopted):
        """Update an existing TextAdopted with new scraped data."""
        existing.title = item.title
        if item.description:
            existing.description = item.description
        if item.procedure_ref and not existing.procedure_ref:
            existing.procedure_ref = item.procedure_ref
        existing.source_url = item.source_url
        if item.full_text_url:
            existing.full_text_url = item.full_text_url
        if item.pdf_url:
            existing.pdf_url = item.pdf_url
        existing.scraped_at = item.scraped_at
        existing.last_updated = datetime.now()

        # Try to link to LegislativeCarriage if not already linked
        if not existing.legislative_carriage_id and existing.procedure_ref:
            carriage = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == existing.procedure_ref
            ).first()
            if carriage:
                existing.legislative_carriage_id = carriage.id


# Convenience functions
async def sync_texts_adopted_rss(skip_existing: bool = False) -> Dict[str, Any]:
    """Sync from RSS feed."""
    service = TextsAdoptedSyncService()
    return await service.sync_rss(skip_existing=skip_existing)


async def sync_texts_adopted_term(term: int = 10, max_dates: int = None) -> Dict[str, Any]:
    """Sync a specific parliamentary term."""
    service = TextsAdoptedSyncService()
    return await service.sync_term(term=term, max_dates=max_dates)
