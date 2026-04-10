"""
Committee Minutes Sync Service

Syncs EP Committee meeting minutes to the Brubru database.

Usage:
    from services.scrapers.committee_minutes_sync_service import CommitteeMinutesSyncService

    sync = CommitteeMinutesSyncService()
    result = await sync.sync_all()
    print(f"Added: {result['added']}, Updated: {result['updated']}")

Created: April 2026
"""

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.committee_minutes import CommitteeMinutes
from services.scrapers.committee_minutes_scraper import (
    CommitteeMinutesScraper,
    ScrapedMinutesItem,
)

logger = logging.getLogger(__name__)

PROCEDURE_REF_PATTERN = re.compile(r'\b(\d{4}/\d{3,4}\([A-Z]{3,4}\))\b')


class CommitteeMinutesSyncService:
    """Syncs EP Committee minutes to PostgreSQL."""

    def __init__(self, db: Optional[Session] = None, enable_pdf_extraction: bool = False):
        self.scraper = CommitteeMinutesScraper()
        self._db = db
        self._owns_db = db is None
        self.enable_pdf_extraction = enable_pdf_extraction

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
            self._owns_db = True
        return self._db

    def close(self):
        if self._owns_db and self._db is not None:
            self._db.close()
            self._db = None

    async def sync_all(self, max_pages: int = 5, skip_existing: bool = True) -> Dict[str, Any]:
        """Sync minutes from the general listing page (all committees)."""
        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

        try:
            items = await self.scraper.scrape_all_minutes(max_pages=max_pages)
            logger.info(f"[INFO] Scraped {len(items)} minutes entries")

            for item in items:
                try:
                    result = self._upsert_minutes(item, skip_existing)
                    stats[result] += 1
                    self.db.flush()
                except Exception as e:
                    logger.warning(f"[WARN] Skipping {item.committee_code} {item.meeting_date}: {e}")
                    stats['errors'] += 1
                    self.db.rollback()

            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"[ERROR] Final commit failed: {e}")
                self.db.rollback()

        except Exception as e:
            logger.error(f"[ERROR] Sync failed: {e}")
            stats['errors'] += 1
        finally:
            self.close()

        logger.info(
            f"[OK] Committee minutes sync: "
            f"{stats['added']} added, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
        return stats

    def _upsert_minutes(self, item: ScrapedMinutesItem, skip_existing: bool) -> str:
        """Insert or update a single minutes record. Returns 'added', 'updated', or 'skipped'."""
        existing = (
            self.db.query(CommitteeMinutes)
            .filter(
                CommitteeMinutes.committee_code == item.committee_code,
                CommitteeMinutes.meeting_date == item.meeting_date,
            )
            .first()
        )

        if existing:
            if skip_existing and existing.pdf_url:
                return 'skipped'

            existing.title = item.title
            existing.pe_reference = item.pe_reference or existing.pe_reference
            existing.document_reference = item.document_reference or existing.document_reference
            existing.pdf_url = item.pdf_url or existing.pdf_url
            existing.doc_url = item.doc_url or existing.doc_url
            existing.publication_date = item.publication_date or existing.publication_date
            existing.meeting_date_end = item.meeting_date_end or existing.meeting_date_end
            existing.last_updated = datetime.utcnow()
            return 'updated'
        else:
            record = CommitteeMinutes(
                committee_code=item.committee_code,
                meeting_date=item.meeting_date,
                meeting_date_end=item.meeting_date_end,
                title=item.title,
                pe_reference=item.pe_reference,
                document_reference=item.document_reference,
                publication_date=item.publication_date,
                pdf_url=item.pdf_url,
                doc_url=item.doc_url,
                source_url=item.source_url,
            )
            self.db.add(record)
            return 'added'
