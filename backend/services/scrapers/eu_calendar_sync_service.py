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
from datetime import datetime, date, timedelta
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

        # Council meetings.
        # Static JSON (European Council summit dates) — cheap, kept for coverage.
        result = self.sync_council_json(2026)
        results.append(result)
        # LIVE Council + European Council scrape from consilium. The static JSON
        # above froze at Feb 2026 and silently no-ops (load_council_meetings
        # returns nothing for the current year), which left Council stale for
        # months even though sync_all runs twice daily via brubru-cron-sync.
        # sync_council_meetings is synchronous (headless-Chromium WAF fetcher),
        # so call it directly — no asyncio, no event loop.
        try:
            results.append(self.sync_council_meetings(months_ahead=6))
        except Exception as e:
            logger.warning(f"[WARN] Council live sync skipped in sync_all: {e}")

        # ECB Governing Council meetings
        result = self.sync_ecb_meetings(2026)
        results.append(result)

        # Commission DG + executive-agency events (the ~50 DG event-page URLs)
        try:
            results.append(self.sync_dg_events())
        except Exception as e:
            logger.warning(f"[WARN] DG events sync skipped in sync_all: {e}")

        # Individual Commissioner agendas (their scheduled meetings)
        try:
            results.append(self.sync_commissioner_agendas())
        except Exception as e:
            logger.warning(f"[WARN] Commissioner agenda sync skipped in sync_all: {e}")

        # College tentative-agenda enrichment (what the College will adopt)
        import asyncio as _asyncio
        try:
            results.append(_asyncio.run(self.sync_college_agendas()))
        except RuntimeError:
            pass  # already inside a running loop (handled by the committee block below)
        except Exception as e:
            logger.warning(f"[WARN] College agenda sync skipped in sync_all: {e}")

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

    async def sync_euagenda(
        self,
        max_events: int = 200,
        include_details: bool = True,
    ) -> Dict[str, Any]:
        """Sync third-party events from euagenda.eu (think tanks, conferences,
        webinars, training). Institution=THIRD_PARTY, source='euagenda'.
        """
        start_time = time.time()
        result = {"source": "euagenda", "added": 0, "updated": 0, "skipped": 0, "errors": 0}
        try:
            from services.scrapers.euagenda_scraper import EuAgendaScraper

            scraper = EuAgendaScraper()
            events = await scraper.scrape_upcoming(
                max_events=max_events, include_details=include_details
            )

            db = self._get_db()
            try:
                for ev in events:
                    # Filter out events without a parseable start_date (we only
                    # want actionable calendar entries)
                    if not ev.start_date:
                        result["skipped"] += 1
                        continue
                    event_data = {
                        "institution": "THIRD_PARTY",
                        "event_type": ev.event_type,
                        "title": ev.title,
                        "description": ev.description or ev.subtitle,
                        "start_date": ev.start_date,
                        "end_date": ev.end_date,
                        "start_time": ev.start_time,
                        "end_time": ev.end_time,
                        "all_day": ev.all_day,
                        "status": "scheduled",
                        "source_url": ev.source_url,
                        "source": "euagenda",
                        "external_id": ev.external_id,
                        "organiser": ev.organiser,
                        "venue": ev.venue,
                        "policy_areas": ev.policy_areas or [],
                    }
                    try:
                        self._upsert_event(db, event_data, result)
                    except Exception as e:
                        logger.warning(f"[WARN] Failed to upsert euagenda event: {e}")
                        result["errors"] += 1
                db.commit()
            finally:
                if self._should_close_db():
                    db.close()
        except Exception as e:
            logger.exception("[euagenda] sync failed: %s", e)
            result["errors"] += 1

        elapsed = time.time() - start_time
        result["elapsed_seconds"] = round(elapsed, 1)
        return result

    def sync_dg_events(self) -> Dict[str, Any]:
        """Sync European Commission DG + executive-agency events into the calendar.

        Iterates the DG_EVENT_SOURCES registry (the ~50 DG/agency event-page URLs),
        scrapes each (ECL 'What's on' markup; SPA fallback), and upserts events
        tagged institution=COMMISSION + commission_dg=<code> so they are filterable
        by department and by the user's Policy Interests. source='dg_events:<DG>'.
        """
        start_time = time.time()
        from services.scrapers.dg_events_sources import DG_EVENT_SOURCES
        from services.scrapers.dg_events_scraper import scrape_source

        result = {"source": "dg_events", "added": 0, "updated": 0, "skipped": 0,
                  "errors": 0, "sources": 0, "sources_empty": 0}
        db = self._get_db()
        try:
            for src in DG_EVENT_SOURCES:
                try:
                    events = scrape_source(src)
                except Exception as e:
                    logger.warning(f"[dg_events] source failed {src['url']}: {e}")
                    result["errors"] += 1
                    continue
                result["sources"] += 1
                if not events:
                    result["sources_empty"] += 1
                for ev in events:
                    try:
                        self._upsert_event(db, ev, result)
                    except Exception as e:
                        logger.warning(f"[dg_events] upsert failed: {e}")
                        result["errors"] += 1
                db.commit()
        finally:
            if self._should_close_db():
                db.close()

        result["elapsed_seconds"] = round(time.time() - start_time, 1)
        return result

    # Commissioner slug -> their Commission DG (shared taxonomy), so commissioner
    # agenda items are filterable under Institution=Commission -> Department=<DG>
    # and by Policy Interest. von der Leyen College 2024-2029. Unmapped = None
    # (still PI-matched by keyword on the meeting title).
    COMMISSIONER_DG = {
        "teresa-ribera-rodriguez": "COMP", "henna-virkkunen": "CNECT",
        "stephane-sejourne": "GROW", "kaja-kallas": "EEAS", "roxana-minzatu": "EMPL",
        "raffaele-fitto": "REGIO", "maros-sefcovic": "TRADE", "valdis-dombrovskis": "ECFIN",
        "oliver-varhelyi": "SANTE", "wopke-hoekstra": "CLIMA", "andrius-kubilius": "DEFIS",
        "marta-kos": "NEAR", "jozef-sikela": "INTPA", "costas-kadis": "MARE",
        "maria-luis-albuquerque": "FISMA", "hadja-lahbib": "JUST",
        "magnus-brunner": "HOME", "jessika-roswall": "ENV", "piotr-serafin": "BUDG",
        "dan-jorgensen": "ENER", "ekaterina-zaharieva": "RTD", "michael-mcgrath": "JUST",
        "apostolos-tzitzikostas": "MOVE", "christophe-hansen": "AGRI", "glenn-micallef": "EAC",
    }

    def sync_commissioner_agendas(self, days_ahead: int = 45, days_back: int = 14) -> Dict[str, Any]:
        """Sync individual Commissioners' published agenda items into the calendar
        (institution=COMMISSION, event_type=commissioner_meeting, commission_dg from
        COMMISSIONER_DG). Forward + recent window. Source='commissioner_agenda'."""
        import asyncio
        result = {"source": "commissioner_agenda", "added": 0, "updated": 0,
                  "skipped": 0, "errors": 0, "commissioners": 0}
        db = self._get_db()
        df, dt = date.today() - timedelta(days=days_back), date.today() + timedelta(days=days_ahead)

        import hashlib

        async def _run():
            from services.api_clients.commissioner_agenda_client import (
                get_commissioner_agenda_client, load_commissioner_profiles,
            )
            cli = get_commissioner_agenda_client()
            for p in load_commissioner_profiles():
                try:
                    _prof, items = await cli.fetch_agenda(p.slug, date_from=df, date_to=dt, db=db)
                except Exception as e:
                    logger.warning(f"[commissioner-agenda] {p.slug} failed: {e}")
                    result["errors"] += 1
                    continue
                result["commissioners"] += 1
                dg = self.COMMISSIONER_DG.get(p.slug)
                seen = set()  # dedupe within this commissioner (HTML + RSS overlap)
                for it in items:
                    if not it.date:
                        continue
                    # STABLE id (hashlib, not Python hash()) so re-syncs update, not duplicate.
                    tkey = hashlib.md5((it.title or "").encode("utf-8")).hexdigest()[:10]
                    ext = f"commissioner:{p.slug}:{it.date.isoformat()}:{tkey}"
                    if ext in seen:
                        continue
                    seen.add(ext)
                    ev = {
                        "institution": "COMMISSION",
                        "event_type": "commissioner_meeting",
                        "title": it.title,
                        "start_date": it.date,
                        "all_day": True,
                        "commission_dg": dg,
                        "venue": it.location or None,
                        "organiser": p.name,
                        "source": "commissioner_agenda",
                        "external_id": ext,
                        "source_url": it.detail_url or p.bio_url,
                    }
                    try:
                        self._upsert_event(db, ev, result)
                    except Exception as e:
                        logger.warning(f"[commissioner-agenda] upsert failed: {e}")
                        result["errors"] += 1
                # commit per commissioner so one bad row never loses the whole run
                try:
                    db.commit()
                except Exception as e:
                    logger.warning(f"[commissioner-agenda] commit failed for %s: %s", p.slug, e)
                    db.rollback()

        try:
            asyncio.run(_run())
        finally:
            if self._should_close_db():
                db.close()
        return result

    def sync_bespoke_events(self) -> Dict[str, Any]:
        """Sync the all-EU bodies' event pages (non-ECL, non-RSS) into the calendar.

        Council comes from the future-meetings page (config+date parsed from URL) and
        is deduped cross-source against the existing council_calendar rows. The other
        bodies use a per-source link_re + nearest-date pairing. Upcoming only. NO LLM.
        source='bespoke_events:<BODY>' / 'council_future_meetings'.
        """
        start_time = time.time()
        from services.scrapers.bespoke_events_scraper import (
            BESPOKE_EVENT_SOURCES, scrape_event_source,
        )
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

        result = {"source": "bespoke_events", "added": 0, "updated": 0, "skipped": 0,
                  "errors": 0, "sources": 0, "sources_empty": 0}
        db = self._get_db()
        try:
            with WafBrowserFetcher(settle_ms=8000, networkidle_ms=20000) as fetcher:
                for src in BESPOKE_EVENT_SOURCES:
                    try:
                        events = scrape_event_source(src, fetcher)
                    except Exception as e:
                        logger.warning(f"[bespoke_events] source failed {src['url']}: {e}")
                        result["errors"] += 1
                        continue
                    result["sources"] += 1
                    if not events:
                        result["sources_empty"] += 1
                    for ev in events:
                        try:
                            dedup = ev.pop("_dedup", None)
                            if dedup and self._event_exists(db, ev, dedup):
                                result["skipped"] += 1
                                continue
                            self._upsert_event(db, ev, result)
                        except Exception as e:
                            logger.warning(f"[bespoke_events] upsert failed: {e}")
                            result["errors"] += 1
                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"[bespoke_events] commit failed {src['institution']}: {e}")
                        result["errors"] += 1
        finally:
            if self._should_close_db():
                db.close()

        result["elapsed_seconds"] = round(time.time() - start_time, 1)
        return result

    def _event_exists(self, db: Session, ev: Dict[str, Any], fields) -> bool:
        """Cross-source existence check (any source) on the given fields + institution.

        Used so the bespoke Council source does not duplicate meetings the existing
        council_calendar source already has.
        """
        filters = [EUCalendarEvent.institution == InstitutionEnum(ev["institution"])]
        for f in fields:
            val = ev.get(f)
            if f == "event_type":
                val = EventTypeEnum(val)
            filters.append(getattr(EUCalendarEvent, f) == val)
        return db.query(EUCalendarEvent.id).filter(*filters).first() is not None

    def sync_council_meetings(self, months_ahead: int = 6) -> Dict[str, Any]:
        """Sync Council + European Council meetings from the live consilium
        calendar. SYNCHRONOUS: the scraper renders the WAF-protected page with
        sync Playwright, which must not run inside an asyncio loop."""
        start_time = time.time()
        result = {"source": "council_calendar", "added": 0, "updated": 0, "skipped": 0, "errors": 0}

        try:
            from services.scrapers.council_calendar_scraper import CouncilCalendarScraper

            scraper = CouncilCalendarScraper()
            events_data = scraper.scrape_meetings(months_ahead)

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
            # Third-party event fields
            if event_data.get("organiser") and existing.organiser != event_data.get("organiser"):
                existing.organiser = event_data.get("organiser")
                changed = True
            if event_data.get("venue") and existing.venue != event_data.get("venue"):
                existing.venue = event_data.get("venue")
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
            organiser=event_data.get("organiser"),
            venue=event_data.get("venue"),
        )
        db.add(event)
        result["added"] += 1
