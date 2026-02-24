"""
College OJ (Ordre du Jour) Sync Service.

Enriches existing Commission College meeting calendar events with
published agenda data from the EC Register of Commission Documents.
Creates new events for past meetings that aren't in the calendar yet.

For each published OJ document:
1. Scrape metadata from RegDoc API (sequential OJ reference lookup)
2. Match to existing commission_college_meeting calendar event by date
   (with +/-1 day tolerance for Strasbourg Tuesday meetings)
3. If found: update event with agenda_url, related_documents, status
4. If not found: create new event (backfill past meetings)

Created: February 2026
"""

import logging
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.eu_calendar import (
    EUCalendarEvent,
    EventTypeEnum,
    EventStatusEnum,
    InstitutionEnum,
)
from services.scrapers.college_oj_scraper import CollegeOJScraper
from schemas.scrapers.college_oj_schemas import ScrapedCollegeAgenda

logger = logging.getLogger(__name__)


class CollegeOJSyncService:
    """
    Syncs Commission College published agendas into calendar events.

    For each OJ document found:
    1. Match to existing commission_college_meeting event by date
    2. If matched: enrich with agenda metadata
    3. If not matched: create new event (backfills past meetings)
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        return SessionLocal()

    def _should_close_db(self) -> bool:
        return self._db is None

    async def sync_college_agendas(
        self,
        days_back: int = 90,
        year: int = 2026,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync published Commission College agendas.

        Enriches existing commission_college_meeting calendar events
        with OJ document metadata. Creates events for past meetings
        that aren't in the calendar yet.

        Args:
            days_back: How many days back to scan for agendas.
            year: Year for OJ references.
            verbose: If True, log detailed progress.

        Returns:
            Dict with added/updated/skipped/errors counts.
        """
        start_time = time.time()
        result = {
            "source": "college_oj",
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        try:
            # 1. Scrape OJ documents
            scraper = CollegeOJScraper()
            date_from = date.today() - timedelta(days=days_back)
            date_to = date.today() + timedelta(days=7)  # Include near-future

            agendas = await scraper.scrape_for_date_range(
                date_from=date_from,
                date_to=date_to,
                year=year,
            )

            if not agendas:
                logger.info("[INFO] No College OJ agendas found")
                result["duration_seconds"] = round(time.time() - start_time, 2)
                return result

            logger.info(
                f"[INFO] Found {len(agendas)} College agendas to process"
            )

            # 2. Process each agenda
            db = self._get_db()
            try:
                for agenda in agendas:
                    try:
                        self._process_agenda(db, agenda, result, verbose)
                    except Exception as e:
                        logger.warning(
                            f"[WARN] Failed to process {agenda.oj_reference}: {e}"
                        )
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] College OJ sync failed: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] College OJ: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped, "
            f"{result['errors']} errors"
        )
        return result

    def _find_matching_event(
        self,
        db: Session,
        agenda: ScrapedCollegeAgenda,
    ) -> Optional[EUCalendarEvent]:
        """
        Find an existing calendar event matching this OJ agenda.

        Search strategy (in order):
        1. Exact match by external_id (ec_college_YYYY-MM-DD)
        2. Exact match by date + institution + event_type
        3. Fuzzy match: +/-1 day tolerance (handles Strasbourg Tuesday meetings)
        """
        # 1. Exact external_id match
        expected_id = f"ec_college_{agenda.meeting_date.isoformat()}"
        existing = (
            db.query(EUCalendarEvent)
            .filter(
                EUCalendarEvent.source == "ec_college",
                EUCalendarEvent.external_id == expected_id,
            )
            .first()
        )
        if existing:
            return existing

        # 2. Exact date match (any source)
        existing = (
            db.query(EUCalendarEvent)
            .filter(
                EUCalendarEvent.institution == InstitutionEnum.COMMISSION,
                EUCalendarEvent.event_type == EventTypeEnum.COMMISSION_COLLEGE_MEETING,
                EUCalendarEvent.start_date == agenda.meeting_date,
            )
            .first()
        )
        if existing:
            return existing

        # 3. Fuzzy match: +/-1 day (Strasbourg meetings are often Tuesday
        #    while the generator creates Wednesday events)
        for delta in [-1, 1]:
            nearby_date = agenda.meeting_date + timedelta(days=delta)
            nearby_id = f"ec_college_{nearby_date.isoformat()}"
            existing = (
                db.query(EUCalendarEvent)
                .filter(
                    EUCalendarEvent.source == "ec_college",
                    EUCalendarEvent.external_id == nearby_id,
                )
                .first()
            )
            if existing:
                return existing

        return None

    def _process_agenda(
        self,
        db: Session,
        agenda: ScrapedCollegeAgenda,
        result: Dict[str, int],
        verbose: bool = False,
    ) -> None:
        """Process a single OJ agenda: enrich existing event or create new one."""

        existing = self._find_matching_event(db, agenda)

        if existing:
            self._enrich_event(existing, agenda, result, verbose)
        else:
            self._create_event(db, agenda, result, verbose)

    def _build_oj_metadata(self, agenda: ScrapedCollegeAgenda) -> Dict[str, Any]:
        """Build the related_documents.college_oj metadata dict."""
        return {
            "oj_reference": agenda.oj_reference,
            "meeting_number": agenda.meeting_number,
            "location": agenda.location,
            "publication_date": (
                agenda.publication_date.isoformat()
                if agenda.publication_date else None
            ),
            "title": agenda.title,
            "ers_id": agenda.ers_id,
            "languages": agenda.languages,
            "detail_url": agenda.detail_url,
        }

    def _build_description(self, agenda: ScrapedCollegeAgenda) -> str:
        """Build event description from OJ metadata."""
        return (
            f"Weekly meeting of the College of Commissioners"
            f" ({agenda.location or 'location TBC'})."
            f" Meeting {agenda.meeting_number}."
            f" The agenda (OJ document) has been published."
        )

    def _enrich_event(
        self,
        existing: EUCalendarEvent,
        agenda: ScrapedCollegeAgenda,
        result: Dict[str, int],
        verbose: bool = False,
    ) -> None:
        """Enrich an existing calendar event with OJ data."""
        changed = False

        # Update agenda_url
        if existing.agenda_url != agenda.detail_url:
            existing.agenda_url = agenda.detail_url
            changed = True

        # Enrich related_documents
        oj_metadata = self._build_oj_metadata(agenda)
        current_docs = existing.related_documents or {}
        if current_docs.get("college_oj") != oj_metadata:
            current_docs["college_oj"] = oj_metadata
            existing.related_documents = current_docs
            changed = True

        # Update description
        new_description = self._build_description(agenda)
        if existing.description != new_description:
            existing.description = new_description
            changed = True

        # Correct the start_date if it was off by a day (Strasbourg)
        if existing.start_date != agenda.meeting_date:
            existing.start_date = agenda.meeting_date
            changed = True

        # Update status
        today = date.today()
        new_status = (
            EventStatusEnum.COMPLETED
            if agenda.meeting_date < today
            else EventStatusEnum.CONFIRMED
        )
        if existing.status != new_status:
            existing.status = new_status
            changed = True

        if changed:
            existing.last_updated = datetime.now()
            result["updated"] += 1
            if verbose:
                logger.info(
                    f"  {agenda.oj_reference}: Enriched event for "
                    f"{agenda.meeting_date} ({agenda.location})"
                )
        else:
            result["skipped"] += 1

    def _create_event(
        self,
        db: Session,
        agenda: ScrapedCollegeAgenda,
        result: Dict[str, int],
        verbose: bool = False,
    ) -> None:
        """Create a new calendar event from a published OJ agenda (backfill)."""

        # Use a unique external_id based on OJ reference to avoid duplicates
        external_id = f"college_oj_{agenda.oj_reference}"

        # Check if we already created this event from a previous sync
        dup = (
            db.query(EUCalendarEvent)
            .filter(
                EUCalendarEvent.source == "college_oj",
                EUCalendarEvent.external_id == external_id,
            )
            .first()
        )
        if dup:
            result["skipped"] += 1
            return

        today = date.today()
        status = (
            EventStatusEnum.COMPLETED
            if agenda.meeting_date < today
            else EventStatusEnum.CONFIRMED
        )

        event = EUCalendarEvent(
            institution=InstitutionEnum.COMMISSION,
            event_type=EventTypeEnum.COMMISSION_COLLEGE_MEETING,
            title="College of Commissioners \u2014 Weekly Meeting",
            description=self._build_description(agenda),
            start_date=agenda.meeting_date,
            all_day=True,
            status=status,
            agenda_url=agenda.detail_url,
            related_documents={"college_oj": self._build_oj_metadata(agenda)},
            procedure_refs=[],
            source="college_oj",
            external_id=external_id,
            source_url=agenda.detail_url,
        )
        db.add(event)
        result["added"] += 1

        if verbose:
            logger.info(
                f"  {agenda.oj_reference}: Created event for "
                f"{agenda.meeting_date} ({agenda.location})"
            )
