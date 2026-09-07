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
from sqlalchemy import or_, text

from core.database import SessionLocal
from models.legislative_train import (
    LegislativeCarriage,
    CarriageStatusEnum,
    TextTypeEnum,
    CarriageSourceEnum
)
from services.api_clients.eurlex_client import EURLexClient
from services.tracking.policy_area_classifier import classify

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

    # ------------------------------------------------------------------
    # CELEX -> OEIL procedure, by LOOKUP in verified EP data. Never derived.
    # ------------------------------------------------------------------
    _PROPOSAL_CELEX = re.compile(r"^5(\d{4})PC(\d{4})$")

    def _procedure_ref_for_celex(self, celex: str) -> Optional[str]:
        """Return the OEIL procedure a proposal CELEX belongs to, or None.

        Why this exists (7 September 2026). Dedup here used to run on
        `celex_numbers` and `file_id` only. A carriage created by the OEIL or
        Legislative Train path carries an `oeil_procedure_ref` and often NO celex,
        so the celex lookup missed it and this service created a SECOND row for the
        same procedure. Three files ended up duplicated that way -- Digital Networks
        Act, Industrial Accelerator Act and EU Inc. -- with users tracking both
        copies and Position Analysis producing two disagreeing snapshots.

        This is a LOOKUP, not a derivation. `feedback_celex_vs_oeil` forbids deriving
        a CELEX from an OEIL reference because the counters are independent; that is
        the opposite direction and is not what happens here. The CELEX -> COM step is
        a mechanical restatement of the same document number (5YYYYPCNNNN is the
        CELEX form of COM(YYYY)NNNN), and the COM -> procedure step is read from
        `ep_emeeting_documents`, which is the European Parliament's own committee
        agenda data. If the store does not hold it, this returns None and the caller
        behaves exactly as before.

        Verified on the three real duplicates: 3 of 3 resolve correctly.
        """
        # Coerce defensively: the try/except below wraps only the DB call, so a
        # non-string reaching re.match would raise straight past it. Caught by the
        # hostile-input test, 7 September 2026.
        if not isinstance(celex, str):
            return None
        m = self._PROPOSAL_CELEX.match(celex)
        if not m:
            return None
        year, num = m.group(1), m.group(2)
        # The store is inconsistent about zero-padding, so try both forms.
        variants = [f"COM({year}){num}", f"COM({year}){int(num)}"]
        try:
            return self.db.execute(text(
                """
                SELECT DISTINCT procedure_ref
                  FROM ep_emeeting_documents
                 WHERE doc_kind = 'commission_document'
                   AND reference = ANY(:v)
                   AND procedure_ref IS NOT NULL
                 LIMIT 1
                """
            ), {"v": variants}).scalar()
        except Exception as e:  # noqa: BLE001
            # A lookup failure must never break the sync; it only means we fall
            # back to the previous celex-only behaviour.
            logger.warning("[eurlex-sync] procedure lookup failed for %s: %s: %s",
                           celex, type(e).__name__, e)
            return None

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

                # Second chance: the same procedure may already exist under an OEIL
                # reference with no celex at all (OEIL_DIRECT and LEGISLATIVE_TRAIN
                # rows usually have one and not the other). Without this, the celex
                # lookup above misses it and we create a duplicate carriage.
                if not existing:
                    proc_ref = self._procedure_ref_for_celex(celex)
                    if proc_ref:
                        existing = self.db.query(LegislativeCarriage).filter(
                            LegislativeCarriage.oeil_procedure_ref == proc_ref
                        ).first()
                        if existing:
                            logger.info(
                                "[eurlex-sync] %s belongs to %s, which already has a "
                                "carriage; updating it instead of creating a duplicate",
                                celex, proc_ref)

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

        # Classify Policy Interest from title + description (same classifier the OEIL sync
        # uses). EUR-Lex rows have no committee; classify returns [] for CELEX-only/
        # keyword-less titles rather than guessing — honest empties stay empty.
        policy_areas = classify(title or "", description or "")

        carriage = LegislativeCarriage(
            id=uuid.uuid4(),
            file_id=file_id,
            title=title,
            description=description,
            current_status=status,
            text_type=text_type,
            celex_numbers=[celex],  # Store as array
            policy_areas=policy_areas,
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

        # Backfill Policy Interest on re-sync if still empty (and a signal now exists).
        if not carriage.policy_areas:
            pis = classify(carriage.title or "", carriage.description or "")
            if pis:
                carriage.policy_areas = pis

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
