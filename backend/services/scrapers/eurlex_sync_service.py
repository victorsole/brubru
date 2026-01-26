"""
EUR-Lex Sync Service

Automatically syncs new legislation and proposals from EUR-Lex RSS feeds
to the Brubru database.

Usage:
    from services.scrapers.eurlex_sync_service import EURLexSyncService

    sync = EURLexSyncService()
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
from services.api_clients.eurlex_client import EURLexClient

logger = logging.getLogger(__name__)


# Document type code to TextTypeEnum mapping
DOC_TYPE_TO_TEXT_TYPE = {
    'Regulation': TextTypeEnum.LEGISLATIVE,
    'Directive': TextTypeEnum.LEGISLATIVE,
    'Decision': TextTypeEnum.LEGISLATIVE,
    'Recommendation': TextTypeEnum.NON_LEGISLATIVE,
    'Declaration': TextTypeEnum.NON_LEGISLATIVE,
    'R': TextTypeEnum.LEGISLATIVE,
    'L': TextTypeEnum.LEGISLATIVE,
    'D': TextTypeEnum.LEGISLATIVE,
    'H': TextTypeEnum.NON_LEGISLATIVE,
    'C': TextTypeEnum.NON_LEGISLATIVE,
}

# CELEX type code to full name
CELEX_TYPE_NAMES = {
    'R': 'Regulation',
    'L': 'Directive',
    'D': 'Decision',
    'H': 'Recommendation',
    'C': 'Declaration',
    'Q': 'Institutional Document',
    'PC': 'Proposal',
}


class EURLexSyncService:
    """
    Service to sync EUR-Lex RSS feeds to the legislative carriages database.

    Supports:
    - Parliament & Council legislation
    - Commission proposals
    - Official Journal entries
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the sync service.

        Args:
            db: Optional database session. If not provided, creates new session.
        """
        self.client = EURLexClient()
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
        legislation_days: int = 7,
        proposals_days: int = 7,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync all EUR-Lex RSS feeds to the database.

        Args:
            legislation_days: Days to look back for legislation
            proposals_days: Days to look back for proposals
            skip_existing: If True, skip items that already exist in DB

        Returns:
            Summary dict with added, updated, skipped, errors counts
        """
        logger.info("[START] EUR-Lex sync: Fetching RSS feeds...")

        try:
            # Fetch legislation (adopted acts)
            logger.info(f"[INFO] Fetching Parliament & Council legislation (last {legislation_days} days)...")
            legislation = await self.client.get_latest_legislation(days=legislation_days)
            logger.info(f"[INFO] Found {len(legislation)} legislation entries")

            # Fetch proposals (COM documents)
            logger.info(f"[INFO] Fetching Commission proposals (last {proposals_days} days)...")
            proposals = await self.client.get_latest_commission_proposals(days=proposals_days)
            logger.info(f"[INFO] Found {len(proposals)} proposal entries")

            # Combine and deduplicate
            all_items = legislation + proposals
            seen_celex: Set[str] = set()
            unique_items = []
            for item in all_items:
                celex = item.get('celex')
                if celex and celex not in seen_celex:
                    seen_celex.add(celex)
                    unique_items.append(item)

            logger.info(f"[INFO] Unique items to process: {len(unique_items)}")

            # Process items
            result = await self._process_items(unique_items, skip_existing)

            logger.info(
                f"[OK] EUR-Lex sync complete: "
                f"added={result['added']}, updated={result['updated']}, "
                f"skipped={result['skipped']}, errors={result['errors']}"
            )

            return result

        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def sync_legislation(
        self,
        max_days: int = 7,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync only Parliament & Council legislation.

        Args:
            max_days: Days to look back
            skip_existing: If True, skip items that already exist
        """
        logger.info(f"[START] Syncing legislation (max_days={max_days})...")

        try:
            items = await self.client.get_latest_legislation(days=max_days)
            return await self._process_items(items, skip_existing)
        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def sync_proposals(
        self,
        max_days: int = 7,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync only Commission proposals.
        """
        logger.info(f"[START] Syncing proposals (max_days={max_days})...")

        try:
            items = await self.client.get_latest_commission_proposals(days=max_days)
            return await self._process_items(items, skip_existing)
        finally:
            await self.client.close()
            if self._owns_db and self._db:
                self._db.close()

    async def _process_items(
        self,
        items: List[Dict[str, Any]],
        skip_existing: bool
    ) -> Dict[str, Any]:
        """
        Process a list of EUR-Lex items.
        """
        result = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'items': []
        }

        for item in items:
            celex = item.get('celex')
            if not celex:
                continue

            try:
                # Check if already exists by CELEX (in array) or file_id
                existing = self.db.query(LegislativeCarriage).filter(
                    or_(
                        LegislativeCarriage.celex_numbers.contains([celex]),
                        LegislativeCarriage.file_id == self._celex_to_file_id(celex)
                    )
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
                            'celex': celex,
                            'action': 'updated'
                        })
                else:
                    # Create new
                    carriage = self._create_carriage(item)
                    self.db.add(carriage)
                    result['added'] += 1
                    result['items'].append({
                        'celex': celex,
                        'title': item.get('title', ''),
                        'action': 'added'
                    })

                self.db.commit()

            except Exception as e:
                logger.error(f"[ERROR] Failed to process {celex}: {e}")
                self.db.rollback()
                result['errors'] += 1

        return result

    def _celex_to_file_id(self, celex: str) -> str:
        """Convert CELEX number to file_id format."""
        # Example: 32024R1689 -> 32024r1689
        return celex.lower()

    def _create_carriage(self, item: Dict[str, Any]) -> LegislativeCarriage:
        """
        Create a new LegislativeCarriage from a EUR-Lex item.
        """
        celex = item.get('celex', '')
        title = item.get('title', '')
        doc_type = item.get('doc_type')
        link = item.get('link', '')

        # Generate file_id from CELEX
        file_id = self._celex_to_file_id(celex)

        # Determine text type from doc_type
        text_type = DOC_TYPE_TO_TEXT_TYPE.get(doc_type, TextTypeEnum.UNKNOWN)

        # Determine status - adopted legislation vs proposals
        if celex.startswith('5'):
            # COM document (proposal)
            status = CarriageStatusEnum.TABLED
        elif celex.startswith('3'):
            # Adopted legislation
            status = CarriageStatusEnum.ADOPTED
        else:
            status = CarriageStatusEnum.TABLED

        # Build description
        description = self._generate_description(item)

        now = datetime.now(timezone.utc)

        carriage = LegislativeCarriage(
            id=uuid.uuid4(),
            file_id=file_id,
            title=title,
            description=description,
            current_status=status,
            text_type=text_type,
            celex_numbers=[celex],  # Store as array
            source=CarriageSourceEnum.EURLEX,
            url=link,
            scraped_at=now,
            first_seen=now,
            last_updated=now,
        )

        return carriage

    def _update_carriage(self, carriage: LegislativeCarriage, item: Dict[str, Any]) -> None:
        """
        Update an existing carriage with new EUR-Lex data.
        """
        # Update URL if changed
        link = item.get('link')
        if link:
            carriage.url = link

        # Add CELEX to array if not already present
        celex = item.get('celex')
        if celex:
            if not carriage.celex_numbers:
                carriage.celex_numbers = [celex]
            elif celex not in carriage.celex_numbers:
                carriage.celex_numbers = carriage.celex_numbers + [celex]

        carriage.last_updated = datetime.now(timezone.utc)

    def _generate_description(self, item: Dict[str, Any]) -> str:
        """
        Generate a description based on document type.
        """
        title = item.get('title', '')
        doc_type = item.get('doc_type', '')
        com_number = item.get('com_number', '')

        if com_number:
            return f"Commission proposal {com_number}: {title}"
        elif doc_type == 'Regulation':
            return f"Regulation: {title}"
        elif doc_type == 'Directive':
            return f"Directive: {title}"
        elif doc_type == 'Decision':
            return f"Decision: {title}"
        else:
            return title


# Convenience function for running sync
async def sync_eurlex_feeds(
    legislation_days: int = 7,
    proposals_days: int = 7,
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to sync EUR-Lex feeds.

    Usage:
        from services.scrapers.eurlex_sync_service import sync_eurlex_feeds
        result = await sync_eurlex_feeds()
    """
    service = EURLexSyncService()
    return await service.sync_all(
        legislation_days=legislation_days,
        proposals_days=proposals_days,
        skip_existing=skip_existing
    )
