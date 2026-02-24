"""
EU Calendar Sync Service.

Coordinates syncing calendar events from all sources into the database.
Follows the committee_work_sync_service.py pattern.

Sources:
- EP Calendar JSON (local files)
- Council meetings calendar (web scraper)
- Commission college meetings (generator)

Created: February 2026
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from core.database import get_db, SessionLocal
from models.eu_calendar import (
    EUCalendarEvent,
    InstitutionEnum,
    EventTypeEnum,
    EventStatusEnum,
)
from knowledge_base.eu_calendar_institutions import get_policy_areas_for_event
from services.scrapers.ep_calendar_loader import load_ep_calendar
from services.scrapers.ec_college_scraper import generate_college_meetings
from services.scrapers.council_calendar_loader import load_council_meetings, load_ecb_meetings

logger = logging.getLogger(__name__)


class EUCalendarSyncService:
    """Syncs EU calendar events from all sources."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def _get_db(self) -> Session:
        if self._db:
            return self._db
        return SessionLocal()

    def _should_close_db(self) -> bool:
        return self._db is None

    def sync_all(self) -> Dict[str, Any]:
        """Sync from all sources."""
        results = []

        # EP Calendar (2025 + 2026)
        for year in [2025, 2026]:
            result = self.sync_ep_calendar(year)
            results.append(result)

        # Commission college meetings
        result = self.sync_ec_college(months_ahead=6)
        results.append(result)

        # Council meetings (static JSON)
        result = self.sync_council_json(2026)
        results.append(result)

        # ECB Governing Council meetings
        result = self.sync_ecb_meetings(2026)
        results.append(result)

        # EP Committee agendas (async)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, schedule as task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    agenda_result = loop.run_in_executor(
                        pool,
                        lambda: asyncio.run(self.sync_committee_agendas())
                    )
            else:
                agenda_result = loop.run_until_complete(self.sync_committee_agendas())
                results.append(agenda_result)
        except RuntimeError:
            # No event loop, create one
            agenda_result = asyncio.run(self.sync_committee_agendas())
            results.append(agenda_result)
        except Exception as e:
            logger.warning(f"[WARN] Committee agenda sync skipped in sync_all: {e}")

        total_added = sum(r["added"] for r in results)
        total_updated = sum(r["updated"] for r in results)
        total_errors = sum(r["errors"] for r in results)

        logger.info(
            f"[OK] Calendar sync complete: "
            f"{total_added} added, {total_updated} updated, {total_errors} errors"
        )

        return {
            "results": results,
            "total_added": total_added,
            "total_updated": total_updated,
            "total_errors": total_errors,
        }

    def sync_ep_calendar(self, year: int) -> Dict[str, Any]:
        """Sync EP calendar events for a specific year."""
        start_time = time.time()
        result = {"source": f"ep_calendar_{year}", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            events_data = load_ep_calendar(year)
            if not events_data:
                logger.warning(f"[WARN] No EP calendar data for {year}")
                return result

            db = self._get_db()
            try:
                for event_data in events_data:
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert EP event: {e}")
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] EP calendar sync failed for {year}: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] EP {year}: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped"
        )
        return result

    def sync_ec_college(self, months_ahead: int = 6) -> Dict[str, Any]:
        """Sync Commission college meeting events."""
        start_time = time.time()
        result = {"source": "ec_college", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            events_data = generate_college_meetings(months_ahead)

            db = self._get_db()
            try:
                for event_data in events_data:
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert EC college event: {e}")
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] EC college sync failed: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] EC College: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped"
        )
        return result

    def sync_council_json(self, year: int) -> Dict[str, Any]:
        """Sync Council/European Council meetings from static JSON."""
        start_time = time.time()
        result = {"source": f"council_json_{year}", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            events_data = load_council_meetings(year)
            if not events_data:
                logger.warning(f"[WARN] No Council meeting data for {year}")
                return result

            db = self._get_db()
            try:
                for event_data in events_data:
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert Council event: {e}")
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] Council JSON sync failed for {year}: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] Council {year}: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped"
        )
        return result

    def sync_ecb_meetings(self, year: int) -> Dict[str, Any]:
        """Sync ECB Governing Council meetings from static JSON."""
        start_time = time.time()
        result = {"source": f"ecb_calendar_{year}", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            events_data = load_ecb_meetings(year)
            if not events_data:
                logger.warning(f"[WARN] No ECB meeting data for {year}")
                return result

            db = self._get_db()
            try:
                for event_data in events_data:
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert ECB event: {e}")
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] ECB calendar sync failed for {year}: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] ECB {year}: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped"
        )
        return result

    async def sync_committee_agendas(
        self,
        committee_codes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Sync EP committee draft agendas into calendar events."""
        from services.scrapers.committee_agenda_sync_service import (
            CommitteeAgendaSyncService,
        )
        service = CommitteeAgendaSyncService(db=self._db)
        return await service.sync_committee_agendas(committee_codes)

    async def sync_college_agendas(
        self,
        days_back: int = 90,
        year: int = 2026,
    ) -> Dict[str, Any]:
        """Sync published Commission College agendas (OJ documents)."""
        from services.scrapers.college_oj_sync_service import (
            CollegeOJSyncService,
        )
        service = CollegeOJSyncService(db=self._db)
        return await service.sync_college_agendas(days_back=days_back, year=year)

    async def sync_council_meetings(self, months_ahead: int = 6) -> Dict[str, Any]:
        """Sync Council meetings (async scraper)."""
        start_time = time.time()
        result = {"source": "council_calendar", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            from services.scrapers.council_calendar_scraper import CouncilCalendarScraper

            scraper = CouncilCalendarScraper()
            events_data = await scraper.scrape_meetings(months_ahead)

            db = self._get_db()
            try:
                for event_data in events_data:
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert Council event: {e}")
                        result["errors"] += 1

                db.commit()
            finally:
                if self._should_close_db():
                    db.close()

        except Exception as e:
            logger.error(f"[ERROR] Council calendar sync failed: {e}")
            result["errors"] += 1

        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            f"[OK] Council: {result['added']} added, "
            f"{result['updated']} updated, {result['skipped']} skipped"
        )
        return result

    def _upsert_event(
        self, db: Session, event_data: Dict[str, Any], result: Dict[str, int]
    ) -> None:
        """Insert or update a single event. Deduplicates by (source, external_id)."""
        source = event_data.get("source")
        external_id = event_data.get("external_id")

        if not source or not external_id:
            result["skipped"] += 1
            return

        # Compute policy areas
        policy_areas = get_policy_areas_for_event(
            ep_committee_code=event_data.get("ep_committee_code"),
            council_configuration=event_data.get("council_configuration"),
            explicit_areas=event_data.get("policy_areas"),
        )

        # Check for existing
        existing = (
            db.query(EUCalendarEvent)
            .filter(
                EUCalendarEvent.source == source,
                EUCalendarEvent.external_id == external_id,
            )
            .first()
        )

        if existing:
            # Update if title or date changed
            changed = False
            if existing.title != event_data.get("title"):
                existing.title = event_data.get("title")
                changed = True
            if existing.start_date != event_data.get("start_date"):
                existing.start_date = event_data.get("start_date")
                changed = True
            if event_data.get("end_date") and existing.end_date != event_data.get("end_date"):
                existing.end_date = event_data.get("end_date")
                changed = True
            if event_data.get("description") and existing.description != event_data.get("description"):
                existing.description = event_data.get("description")
                changed = True
            if event_data.get("source_url") and existing.source_url != event_data.get("source_url"):
                existing.source_url = event_data.get("source_url")
                changed = True
            if event_data.get("agenda_url") and existing.agenda_url != event_data.get("agenda_url"):
                existing.agenda_url = event_data.get("agenda_url")
                changed = True
            if policy_areas and existing.policy_areas != policy_areas:
                existing.policy_areas = policy_areas
                changed = True

            if changed:
                existing.last_updated = datetime.now()
                result["updated"] += 1
            else:
                result["skipped"] += 1
            return

        # Create new event
        event = EUCalendarEvent(
            institution=InstitutionEnum(event_data["institution"]),
            event_type=EventTypeEnum(event_data["event_type"]),
            title=event_data["title"],
            description=event_data.get("description"),
            start_date=event_data["start_date"],
            end_date=event_data.get("end_date"),
            start_time=event_data.get("start_time"),
            end_time=event_data.get("end_time"),
            all_day=event_data.get("all_day", True),
            council_configuration=event_data.get("council_configuration"),
            ep_activity_type=event_data.get("ep_activity_type"),
            ep_committee_code=event_data.get("ep_committee_code"),
            commission_dg=event_data.get("commission_dg"),
            policy_areas=policy_areas,
            status=EventStatusEnum(event_data.get("status", "scheduled")),
            source_url=event_data.get("source_url"),
            agenda_url=event_data.get("agenda_url"),
            procedure_refs=event_data.get("procedure_refs", []),
            related_documents=event_data.get("related_documents", {}),
            source=source,
            external_id=external_id,
        )
        db.add(event)
        result["added"] += 1
