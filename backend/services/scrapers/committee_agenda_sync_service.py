"""
Committee Agenda Sync Service.

Syncs scraped EP committee draft agendas into eu_calendar_events,
cross-referencing with CommitteeWorkItem records for procedure refs.

Created: February 2026
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.eu_calendar import (
    EUCalendarEvent,
    EventTypeEnum,
    EventStatusEnum,
    InstitutionEnum,
)
from models.committee_work import CommitteeWorkItem, CommitteeWorkStatusEnum
from knowledge_base.ep_committees import EP_COMMITTEE_BY_CODE
from services.scrapers.committee_agenda_scraper import CommitteeAgendaScraper
from schemas.scrapers.committee_agenda_schemas import ScrapedCommitteeAgenda

logger = logging.getLogger(__name__)


class CommitteeAgendaSyncService:
    """
    Syncs committee draft agendas into calendar events.

    For each agenda:
    1. Scrape metadata from EP latest-documents page
    2. Cross-reference committee_code with CommitteeWorkItem records
       to populate procedure_refs
    3. Upsert into eu_calendar_events
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        return SessionLocal()

    def _should_close_db(self) -> bool:
        return self._db is None

    async def sync_committee_agendas(
        self,
        committee_codes: Optional[List[str]] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync committee agendas from EP website into calendar events.

        Args:
            committee_codes: Optional list of committee codes to sync.
                           Defaults to all 26 committees.
            verbose: If True, log detailed progress.

        Returns:
            Dict with added/updated/skipped/errors counts.
        """
        start_time = time.time()
        result = {
            "source": "ep_committee_agenda",
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        try:
            # 1. Scrape agendas
            scraper = CommitteeAgendaScraper()
            agendas = await scraper.scrape_all_committees(committee_codes)

            if not agendas:
                logger.info("[INFO] No committee agendas found")
                result["duration_seconds"] = round(time.time() - start_time, 2)
                return result

            # 2. Deduplicate agendas by external_id (same committee + date)
            #    The EP page can list multiple document versions for the same meeting.
            seen_keys: Dict[str, ScrapedCommitteeAgenda] = {}
            for agenda in agendas:
                key = f"{agenda.committee_code}_{agenda.meeting_date.isoformat()}"
                if key not in seen_keys:
                    seen_keys[key] = agenda
            unique_agendas = list(seen_keys.values())
            if len(unique_agendas) < len(agendas):
                logger.info(
                    f"[INFO] Deduplicated {len(agendas)} -> {len(unique_agendas)} agendas"
                )

            # 3. Process each agenda
            db = self._get_db()
            try:
                for agenda in unique_agendas:
                    try:
                        self._process_agenda(db, agenda, result, verbose)
                    except Exception as e:
                        logger.warning(
                            f"[WARN] Failed to process agenda "
                            f"{agenda.committee_code} {agenda.meeting_date}: {e}"
                        )
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] Committee agenda sync failed: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] Committee agendas: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped, "
            f"{result['errors']} errors"
        )
        return result

    def _process_agenda(
        self,
        db: Session,
        agenda: ScrapedCommitteeAgenda,
        result: Dict[str, int],
        verbose: bool = False,
    ) -> None:
        """Process a single scraped agenda into a calendar event."""
        committee = EP_COMMITTEE_BY_CODE.get(agenda.committee_code)
        if not committee:
            result["skipped"] += 1
            return

        # Build external_id for deduplication
        external_id = (
            f"ep_cm_{agenda.committee_code}_{agenda.meeting_date.isoformat()}"
        )
        source = "ep_committee_agenda"

        # Cross-reference with CommitteeWorkItem to get procedure_refs
        procedure_refs = self._get_procedure_refs(db, agenda.committee_code)

        if verbose:
            logger.info(
                f"  {agenda.committee_code} {agenda.meeting_date}: "
                f"{len(procedure_refs)} procedure refs"
            )

        # Build event title and description
        title = f"{agenda.committee_code}: {committee.name} Committee Meeting"
        description = (
            f"Meeting of the {committee.full_name}. "
            f"Draft agenda published."
        )

        # Check for existing event
        existing = (
            db.query(EUCalendarEvent)
            .filter(
                EUCalendarEvent.source == source,
                EUCalendarEvent.external_id == external_id,
            )
            .first()
        )

        if existing:
            # Update if procedure_refs or URLs changed
            changed = False
            if (
                procedure_refs
                and set(existing.procedure_refs or []) != set(procedure_refs)
            ):
                existing.procedure_refs = procedure_refs
                changed = True
            if agenda.pdf_url and existing.agenda_url != agenda.pdf_url:
                existing.agenda_url = agenda.pdf_url
                changed = True
            if agenda.source_url and existing.source_url != agenda.source_url:
                existing.source_url = agenda.source_url
                changed = True

            if changed:
                existing.last_updated = datetime.now()
                result["updated"] += 1
            else:
                result["skipped"] += 1
            return

        # Create new calendar event
        event = EUCalendarEvent(
            institution=InstitutionEnum.EP,
            event_type=EventTypeEnum.COMMITTEE_MEETING,
            title=title,
            description=description,
            start_date=agenda.meeting_date,
            all_day=True,
            status=EventStatusEnum.CONFIRMED,
            ep_committee_code=agenda.committee_code,
            source_url=agenda.source_url,
            agenda_url=agenda.pdf_url,
            procedure_refs=procedure_refs,
            related_documents={},
            source=source,
            external_id=external_id,
        )
        db.add(event)
        result["added"] += 1

    def _get_procedure_refs(
        self, db: Session, committee_code: str
    ) -> List[str]:
        """
        Cross-reference committee code with active CommitteeWorkItem records
        to get procedure references.

        Returns procedure_refs for items that are actively being worked on
        (in_committee, awaiting_vote, tabled).
        """
        active_statuses = [
            CommitteeWorkStatusEnum.IN_COMMITTEE,
            CommitteeWorkStatusEnum.AWAITING_VOTE,
            CommitteeWorkStatusEnum.TABLED,
        ]

        try:
            items = (
                db.query(CommitteeWorkItem.procedure_ref)
                .filter(
                    CommitteeWorkItem.committee_code == committee_code,
                    CommitteeWorkItem.status.in_(active_statuses),
                )
                .distinct()
                .all()
            )
            return [item[0] for item in items if item[0]]
        except Exception as e:
            logger.warning(
                f"[WARN] Failed to get procedure refs for {committee_code}: {e}"
            )
            return []
