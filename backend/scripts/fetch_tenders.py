"""
Fetch Tenders Script

Scheduled job to fetch new EU public procurement tenders from TED.
Designed to run weekly or bi-weekly to keep the database updated.

Usage:
    # Fetch tenders from last 7 days (default)
    python -m backend.scripts.fetch_tenders

    # Fetch with custom parameters
    python -m backend.scripts.fetch_tenders --days 14 --max-value 5000000

    # Fetch for specific countries
    python -m backend.scripts.fetch_tenders --countries BE,FR,DE

    # Dry run (don't save to database)
    python -m backend.scripts.fetch_tenders --dry-run
"""

import asyncio
import argparse
import logging
import sys
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# backend/ on the path, then bare imports. This is the convention every script
# the cron actually runs uses (sync_eu_calendar, sync_consultations,
# auto_archive_old_items). The `backend.`-prefixed form this file used could not
# import at all: models/__init__ imports models/user, which does
# `from core.database import Base`, and a bare `core` needs backend/ on the
# path. That ImportError is why the TED fetch was never scheduled.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal  # noqa: E402
from models.tender import Tender, TenderFetchJob  # noqa: E402
from services.tenders.ted_client import TEDClient, ProcedureType  # noqa: E402
from services.tenders.eforms_parser import EFormsParser  # noqa: E402
from services.tenders.sme_scorer import SMEScorer  # noqa: E402
from services.tenders.country_codes import normalise_country  # noqa: E402

# Stream only. A FileHandler here wrote tender_fetch.log into whatever the cwd
# was, which under cron is backend/ -- a log file nobody reads, in the repo.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Default SME-friendly filter settings
DEFAULT_MAX_VALUE = 5_000_000  # €5M
DEFAULT_DAYS_BACK = 7
DEFAULT_MIN_DEADLINE_DAYS = 14  # At least 2 weeks to deadline

# CPV codes particularly relevant for SMEs
SME_FRIENDLY_CPV_PREFIXES = [
    "72",  # IT services
    "79",  # Business services
    "73",  # Research and development
    "80",  # Education and training
    "85",  # Health and social services
    "90",  # Environmental services
    "71",  # Architectural, engineering services
    "50",  # Repair and maintenance
    "48",  # Software packages
    "64",  # Postal and telecommunications
]


class TenderFetcher:
    """
    Fetches and processes tenders from TED API.

    Features:
    - SME-friendly filtering (value threshold, procedure type)
    - Automatic parsing and enrichment
    - Deduplication against existing database
    - Progress tracking and logging
    """

    def __init__(
        self,
        max_value: float = DEFAULT_MAX_VALUE,
        min_deadline_days: int = DEFAULT_MIN_DEADLINE_DAYS,
        include_framework: bool = False,
        dry_run: bool = False,
        xml_concurrency: int = 4,
        xml_rate: float = 8.0,
    ):
        self.max_value = max_value
        self.min_deadline_days = min_deadline_days
        self.include_framework = include_framework
        self.dry_run = dry_run
        # ted.europa.eu XML: at most `xml_rate` requests/second (default 8 =
        # 480/min, under TED's documented 700/min per IP), `xml_concurrency`
        # in flight. ~1,600 notices (a full day) take ~3.5 minutes.
        self.xml_concurrency = xml_concurrency
        self.xml_rate = xml_rate

        self.parser = EFormsParser()
        self.scorer = SMEScorer()
        self.db = SessionLocal()

        # Statistics
        self.stats = {
            "fetched": 0,
            "parsed": 0,
            "new": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": []
        }

    async def fetch_tenders(
        self,
        days_back: int = DEFAULT_DAYS_BACK,
        countries: Optional[List[str]] = None,
        cpv_codes: Optional[List[str]] = None,
        max_results: int = 0,
        dates: Optional[List["date_cls"]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch EVERY matching TED notice published in the window, one day at a time.

        Why per day and uncapped (fixed 15 Sep 2026): the daily cron ran
        `--days 2 --max-results 400`, and this loop requested 50 a page and
        stopped at `len >= max_results` (and at 10 pages regardless). TED returns
        the window oldest day first, so each run took the first 400 notices of
        the OLDEST day and never reached the rest: the table held exactly 400
        rows for 8, 9, 10 and 11 Sep while TED published 1,124 / 1,235 / 1,305 /
        1,297 matching notices on those days (open procedure, deadline >= 14 days
        out; 3,100-3,650 notices of every kind a day).

        Each day is now a separate `PD=YYYYMMDD` query scanned to exhaustion
        with TED's ITERATION cursor, checked against TED's own totalNoticeCount,
        and committed on its own, so one bad day cannot roll back the others.
        An incomplete day is recorded in stats["incomplete_days"] and makes the
        script exit non-zero (silence is not success).

        Args:
            days_back: days before today to include (today is always included)
            countries: Filter by country codes (e.g., ['BE', 'FR', 'DE'])
            cpv_codes: Filter by CPV code prefixes
            max_results: 0 (default) = no cap. A positive value is a deliberate
                truncation for ad-hoc runs; it is logged as such, and the days
                it cuts short are reported as incomplete.
        """
        logger.info(f"Starting tender fetch: days_back={days_back}, max_value={self.max_value}")

        job = self._create_fetch_job(days_back, countries, cpv_codes)
        self.stats.setdefault("days", {})
        self.stats.setdefault("incomplete_days", [])
        failed = False

        try:
            async with TEDClient() as client:
                today = datetime.now(timezone.utc).date()
                deadline_from = today + timedelta(days=self.min_deadline_days)
                days = dates or [today - timedelta(days=i) for i in range(days_back, -1, -1)]
                remaining = max_results if max_results and max_results > 0 else None

                for day in days:
                    query_string = client._build_query(
                        cpv_codes=cpv_codes,
                        countries=countries,
                        procedure_types=[ProcedureType.OPEN],
                        publication_date_from=day,
                        publication_date_to=day,
                        deadline_from=deadline_from,
                    )
                    scan = await client.fetch_all_notices(query_string)
                    notices = scan["notices"]
                    truncated = False
                    if remaining is not None and len(notices) > remaining:
                        logger.warning(
                            f"[WARN] --max-results truncates {day}: keeping {remaining} of {len(notices)}")
                        notices = notices[:remaining]
                        truncated = True
                    if remaining is not None:
                        remaining -= len(notices)

                    day_stats = {"ted_total": scan["total"], "fetched": len(notices),
                                 "complete": scan["complete"] and not truncated}
                    self.stats["days"][day.isoformat()] = day_stats
                    self.stats["fetched"] += len(notices)
                    logger.info(
                        f"[INFO] {day}: TED total {scan['total']}, fetched {len(notices)}"
                        f"{'' if day_stats['complete'] else ' (INCOMPLETE)'}")
                    if not day_stats["complete"]:
                        self.stats["incomplete_days"].append(day.isoformat())

                    await self._process_day(notices, client)
                    if not self.dry_run:
                        self.db.commit()

                    if remaining == 0:
                        break

                job.status = "completed" if not self.stats["incomplete_days"] else "incomplete"
                job.tenders_found = self.stats["fetched"]
                job.tenders_new = self.stats["new"]
                job.tenders_updated = self.stats["updated"]

        except Exception as e:
            failed = True
            logger.error(f"[ERROR] Fetch job failed: {e}")
            if not self.dry_run:
                self.db.rollback()
            job.status = "failed"
            job.errors = [str(e)]
            self.stats["error_details"].append(str(e))

        finally:
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                started = (job.started_at.replace(tzinfo=timezone.utc)
                           if job.started_at.tzinfo is None else job.started_at)
                job.duration_seconds = (job.completed_at - started).total_seconds()

            if not self.dry_run:
                self.db.commit()

            self.db.close()

        self.stats["failed"] = failed
        self._log_summary()
        return self.stats

    async def _process_day(self, notices: List[Dict[str, Any]], client: TEDClient):
        """Upsert one day's notices, fetching the XML they need in parallel.

        XML used to be fetched one notice at a time with a 0.5 s sleep, about
        0.75 s a notice, i.e. ~20 minutes for one full day of ~1,600 notices,
        which would not fit the cron's timeout once the cap was removed. The
        fetch is now bounded-concurrent (`xml_concurrency`, default 4) against
        ted.europa.eu, and the DB writes stay sequential on the one Session.
        """
        pubs = [self._publication_number(n) for n in notices]
        pubs = [p for p in pubs if p]
        has_xml: Dict[str, bool] = {}
        if pubs:
            for pub, xml_present in self.db.query(
                Tender.publication_number, Tender.xml_content.isnot(None)
            ).filter(Tender.publication_number.in_(pubs)).all():
                has_xml[pub] = bool(xml_present)
        # Hand the connection back BEFORE the XML downloads. A full day is
        # minutes of network work, and a Session held idle across it died on
        # 15 Sep 2026 with "SSL connection has been closed unexpectedly" at the
        # day's commit, losing the whole day (pool_pre_ping only runs on
        # checkout). Ending the transaction here makes the re-query below check
        # out a fresh, pinged connection.
        self.db.rollback()
        need_xml = [p for p in pubs if not has_xml.get(p)]
        xml_cache = await self._fetch_xml_batch(need_xml, client)

        existing: Dict[str, Tender] = {}
        if pubs:
            for t in self.db.query(Tender).filter(Tender.publication_number.in_(pubs)).all():
                existing[t.publication_number] = t

        for i, notice in enumerate(notices):
            try:
                await self._process_notice(notice, client, xml_cache=xml_cache, existing=existing)
                if (i + 1) % 250 == 0:
                    logger.info(f"Processed {i + 1}/{len(notices)} notices")
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["error_details"].append(str(e))
                logger.error(f"Error processing notice: {e}")

    async def _fetch_xml_batch(self, pubs: List[str], client: TEDClient) -> Dict[str, Optional[str]]:
        """Download eForms XML for `pubs`, paced and retried on HTTP 429.

        ted.europa.eu rate-limits the XML endpoint: an unpaced burst of 4 in
        flight (~18 req/s) got 566 x 429 out of 803 on 15 Sep 2026. Requests
        are therefore spaced to `xml_rate` per second across all workers, and a
        429 backs off (Retry-After, else 5/10/20/40 s) before retrying. A notice
        whose XML still cannot be fetched is counted in stats["xml_failed"]
        rather than stored silently as if TED had no XML for it.
        """
        import httpx

        sem = asyncio.Semaphore(max(1, self.xml_concurrency))
        lock = asyncio.Lock()
        interval = 1.0 / self.xml_rate if self.xml_rate and self.xml_rate > 0 else 0.0
        next_slot = [0.0]
        out: Dict[str, Optional[str]] = {}
        loop = asyncio.get_running_loop()

        async def paced():
            if not interval:
                return
            async with lock:
                now = loop.time()
                wait = next_slot[0] - now
                next_slot[0] = max(now, next_slot[0]) + interval
            if wait > 0:
                await asyncio.sleep(wait)

        async def one(pub: str):
            async with sem:
                for attempt in range(5):
                    await paced()
                    try:
                        out[pub] = await client.get_notice_xml(pub, raise_on_rate_limit=True)
                        return
                    except httpx.HTTPStatusError as e:
                        retry_after = e.response.headers.get("Retry-After")
                        try:
                            delay = float(retry_after) if retry_after else 5.0 * (2 ** attempt)
                        except ValueError:
                            delay = 5.0 * (2 ** attempt)
                        self.stats["xml_rate_limited"] = self.stats.get("xml_rate_limited", 0) + 1
                        await asyncio.sleep(delay)
                    except Exception as e:
                        logger.warning(f"Could not fetch XML for {pub}: {type(e).__name__}: {e}")
                        break
                out[pub] = None
                self.stats["xml_failed"] = self.stats.get("xml_failed", 0) + 1

        await asyncio.gather(*(one(p) for p in pubs))
        return out

    @staticmethod
    def _publication_number(notice: Dict[str, Any]) -> Optional[str]:
        return (notice.get("publication-number") or notice.get("ND")
                or notice.get("publicationNumber"))

    async def _process_notice(
        self,
        notice: Dict[str, Any],
        client: TEDClient,
        xml_cache: Optional[Dict[str, Optional[str]]] = None,
        existing: Optional[Dict[str, Tender]] = None,
    ):
        """Process a single notice from the API.

        `xml_cache` / `existing` are pre-fetched by `_process_day`; without them
        (a single-notice call) this falls back to a DB lookup and a direct fetch.
        """
        publication_number = self._publication_number(notice)

        if not publication_number:
            self.stats["skipped"] += 1
            return

        async def _xml() -> Optional[str]:
            if xml_cache is not None and publication_number in xml_cache:
                return xml_cache[publication_number]
            try:
                return await client.get_notice_xml(publication_number)
            except Exception as e:
                logger.warning(f"Could not fetch XML for {publication_number}: {e}")
                return None

        if existing is not None:
            row = existing.get(publication_number)
        else:
            row = self.db.query(Tender).filter(
                Tender.publication_number == publication_number
            ).first()

        if row:
            self._update_tender(row, notice)
            self.stats["updated"] += 1

            # Backfill XML if missing
            if not row.xml_content:
                xml_content = await _xml()
                if xml_content:
                    row.xml_content = xml_content
                    try:
                        parsed = self.parser.parse_to_tender_dict(xml_content, publication_number)
                        if parsed.get("award_criteria"):
                            row.award_criteria = parsed.get("award_criteria")
                            row.award_criteria_type = parsed.get("award_criteria_type")
                        if parsed.get("description") and not row.description:
                            row.description = parsed.get("description")
                        if parsed.get("selection_criteria"):
                            row.selection_criteria = parsed.get("selection_criteria")
                        if parsed.get("minimum_requirements"):
                            row.minimum_requirements = parsed.get("minimum_requirements")
                    except Exception as e:
                        logger.warning(f"XML parsing failed for backfill {publication_number}: {e}")
        else:
            xml_content = await _xml()
            tender = self._create_tender(notice, xml_content)

            if not self.dry_run:
                self.db.add(tender)

            self.stats["new"] += 1

        self.stats["parsed"] += 1

    def _create_tender(self, notice: Dict[str, Any], xml_content: Optional[str]) -> Tender:
        """Create a new Tender from API notice data."""
        # TED API v3 uses different field names
        publication_number = (
            notice.get("publication-number") or
            notice.get("ND") or
            notice.get("publicationNumber", "")
        )

        # Parse XML if available
        parsed_data = {}
        if xml_content:
            try:
                parsed_data = self.parser.parse_to_tender_dict(xml_content, publication_number)
            except Exception as e:
                logger.warning(f"XML parsing failed for {publication_number}: {e}")

        # Extract data from TED API v3 format
        # TI is a multilingual object - prefer English (could also be list or string)
        ti = notice.get("TI", {})
        if isinstance(ti, dict):
            title = self._extract_multilingual(ti)
        elif isinstance(ti, list):
            title = ti[0] if ti else ""
        else:
            title = str(ti) if ti else ""

        # CY is an array of 3-letter country codes. The old reverse lookup fell
        # back to `country_3[:2]`, which turns an unmapped "CZE" into "CZ" by
        # luck and an unmapped anything-else into two characters of nonsense
        # bound for a varchar(2) column the matcher hard-filters on.
        cy = notice.get("CY", [])
        country_2 = normalise_country(cy[0] if cy else None)

        # AU (buyer name) is multilingual
        au = notice.get("AU", {})
        official_name = self._extract_multilingual(au) if isinstance(au, dict) else str(au) if au else None

        # PC (CPV code) is an array - take first value
        pc = notice.get("PC", [])
        cpv_main = pc[0] if isinstance(pc, list) and pc else (pc if isinstance(pc, str) else None)

        # Build tender from API data + parsed XML
        tender = Tender(
            publication_number=publication_number,
            notice_id=notice.get("noticeId"),
            title=parsed_data.get("title") or title or "",
            description=parsed_data.get("description"),
            official_name=parsed_data.get("official_name") or official_name,
            buyer_country=normalise_country(parsed_data.get("buyer_country")) or country_2,
            procedure_type=parsed_data.get("procedure_type") or notice.get("PR") or notice.get("procedureType"),
            legal_basis=parsed_data.get("legal_basis"),
            cpv_codes=parsed_data.get("cpv_codes"),
            cpv_main=parsed_data.get("cpv_main") or cpv_main,
            nuts_codes=parsed_data.get("nuts_codes"),
            contract_nature=parsed_data.get("contract_nature"),
            # Value comes from the XML only. `TW` was used as a fallback here,
            # but in TED v3 TW is the buyer's TOWN, returned as a multilingual
            # dict of place names ({"mul": ["Marburg"]}). It happens to yield
            # None today because the values are lists, so nothing wrong was
            # stored -- but a town whose name parses as a number would land in
            # estimated_value, which the matcher scores on.
            estimated_value=parsed_data.get("estimated_value"),
            estimated_value_currency=parsed_data.get("currency", "EUR"),
            publication_date=self._parse_date(notice.get("PD") or notice.get("publicationDate")),
            submission_deadline=parsed_data.get("submission_deadline") or self._parse_date(notice.get("DD") or notice.get("deadline")),
            contract_duration_months=parsed_data.get("duration_months"),
            award_criteria=parsed_data.get("award_criteria"),
            has_lots=parsed_data.get("has_lots", False),
            lot_count=parsed_data.get("lot_count"),
            lots=parsed_data.get("lots"),
            ted_url=f"https://ted.europa.eu/en/notice/{publication_number}/html",
            xml_content=xml_content,
            status="open",
            source="ted_api",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        # Calculate SME suitability score
        sme_analysis = self._calculate_sme_score(tender, parsed_data)
        tender.sme_suitability_score = sme_analysis.get("sme_suitability_score")
        # `sme_score_breakdown` is not a mapped column; the breakdown was being
        # computed and dropped at commit. `sme_analysis` (JSONB) is the column.
        tender.sme_analysis = sme_analysis

        return tender

    def _update_tender(self, tender: Tender, notice: Dict[str, Any]):
        """Update an existing tender with new data."""
        if notice.get("title"):
            tender.title = notice["title"]

        if notice.get("deadline"):
            tender.submission_deadline = self._parse_date(notice["deadline"])

        tender.updated_at = datetime.now(timezone.utc)
        tender.last_synced_at = datetime.now(timezone.utc)

    def _calculate_sme_score(self, tender: Tender, parsed_data: Dict) -> Dict[str, Any]:
        """Calculate SME suitability score for a tender."""
        tender_data = {
            "estimated_value": tender.estimated_value,
            "procedure_type": tender.procedure_type,
            "submission_deadline": tender.submission_deadline.isoformat() if tender.submission_deadline else None,
            "has_lots": tender.has_lots,
            "lot_count": tender.lot_count,
            "cpv_codes": tender.cpv_codes,
            "buyer_country": tender.buyer_country,
            "is_framework": parsed_data.get("is_framework", False),
            "is_joint_procurement": parsed_data.get("is_joint_procurement", False),
        }

        return self.scorer.get_sme_analysis(tender_data)

    def _create_fetch_job(
        self,
        days_back: int,
        countries: Optional[List[str]],
        cpv_codes: Optional[List[str]]
    ) -> TenderFetchJob:
        """Create a fetch job record."""
        import uuid

        job = TenderFetchJob(
            job_id=str(uuid.uuid4())[:8],
            job_type="scheduled" if not self.dry_run else "manual",
            source="ted_api",
            query_params={
                "days_back": days_back,
                "countries": countries,
                "cpv_codes": cpv_codes,
                "max_value": self.max_value,
                "min_deadline_days": self.min_deadline_days,
                "include_framework": self.include_framework
            },
            status="running",
            started_at=datetime.now(timezone.utc)
        )

        if not self.dry_run:
            self.db.add(job)
            self.db.commit()

        return job

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date string/value to datetime."""
        if date_value is None:
            return None

        # Handle list (take first element)
        if isinstance(date_value, list):
            date_value = date_value[0] if date_value else None
            if date_value is None:
                return None

        # Handle datetime objects
        if isinstance(date_value, datetime):
            return date_value

        # Convert to string
        date_str = str(date_value)

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            pass

        return None

    def _extract_value(self, tw_value: Any) -> Optional[float]:
        """Extract numeric value from TED TW field (which can be dict or number)."""
        if tw_value is None:
            return None

        if isinstance(tw_value, (int, float)):
            return float(tw_value)

        if isinstance(tw_value, dict):
            # TED API v3 may return structured value like {"amount": 1000000, "currency": "EUR"}
            if "amount" in tw_value:
                try:
                    return float(tw_value["amount"])
                except (ValueError, TypeError):
                    pass
            # Or it might be {"value": 1000000}
            if "value" in tw_value:
                try:
                    return float(tw_value["value"])
                except (ValueError, TypeError):
                    pass
            # Try the first numeric value we find
            for key, val in tw_value.items():
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    try:
                        return float(val.replace(",", ".").replace(" ", ""))
                    except ValueError:
                        continue

        if isinstance(tw_value, str):
            try:
                return float(tw_value.replace(",", ".").replace(" ", ""))
            except ValueError:
                pass

        return None

    def _extract_multilingual(self, ml_value: Dict[str, Any]) -> Optional[str]:
        """Extract string from a multilingual dict, preferring English."""
        if not ml_value or not isinstance(ml_value, dict):
            return None

        # Try English first
        for key in ["eng", "ENG", "en", "EN"]:
            if key in ml_value:
                val = ml_value[key]
                if isinstance(val, list):
                    return val[0] if val else None
                return str(val) if val else None

        # Try any language
        for key, val in ml_value.items():
            if val:
                if isinstance(val, list):
                    return val[0] if val else None
                return str(val)

        return None

    def _log_summary(self):
        """Log fetch summary."""
        logger.info("=" * 60)
        logger.info("TENDER FETCH SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total fetched:  {self.stats['fetched']}")
        logger.info(f"Total parsed:   {self.stats['parsed']}")
        logger.info(f"New tenders:    {self.stats['new']}")
        logger.info(f"Updated:        {self.stats['updated']}")
        logger.info(f"Skipped:        {self.stats['skipped']}")
        logger.info(f"Errors:         {self.stats['errors']}")
        logger.info(f"XML 429 retries:{self.stats.get('xml_rate_limited', 0)}")
        logger.info(f"XML failed:     {self.stats.get('xml_failed', 0)}")

        if self.stats["error_details"]:
            logger.info("Error details:")
            for err in self.stats["error_details"][:5]:
                logger.info(f"  - {err}")

        logger.info("=" * 60)


def _date_range(from_date: Optional[str], to_date: Optional[str]) -> Optional[List[date_cls]]:
    """Inclusive list of dates for a backfill, or None to use --days."""
    if not from_date:
        return None
    start = date_cls.fromisoformat(from_date)
    end = date_cls.fromisoformat(to_date) if to_date else start
    if end < start:
        raise SystemExit("[ERROR] --to-date is before --from-date")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


async def main():
    """Main entry point for the fetch script."""
    parser = argparse.ArgumentParser(
        description="Fetch EU public procurement tenders from TED"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=DEFAULT_DAYS_BACK,
        help=f"Number of days to look back (default: {DEFAULT_DAYS_BACK})"
    )
    parser.add_argument(
        "--max-value", "-v",
        type=float,
        default=DEFAULT_MAX_VALUE,
        help=f"Maximum tender value in EUR (default: {DEFAULT_MAX_VALUE})"
    )
    parser.add_argument(
        "--countries", "-c",
        type=str,
        help="Comma-separated country codes (e.g., BE,FR,DE)"
    )
    parser.add_argument(
        "--cpv", "-p",
        type=str,
        help="Comma-separated CPV code prefixes (e.g., 72,79,73)"
    )
    parser.add_argument(
        "--max-results", "-m",
        type=int,
        default=0,
        help="Cap on notices fetched across the whole window (default: 0 = no cap). "
             "A cap truncates days and makes the run exit non-zero."
    )
    parser.add_argument(
        "--from-date",
        type=str,
        help="Backfill: first publication date YYYY-MM-DD (overrides --days)"
    )
    parser.add_argument(
        "--to-date",
        type=str,
        help="Backfill: last publication date YYYY-MM-DD (default: --from-date)"
    )
    parser.add_argument(
        "--xml-concurrency",
        type=int,
        default=4,
        help="Parallel XML downloads from ted.europa.eu (default: 4)"
    )
    parser.add_argument(
        "--xml-rate",
        type=float,
        default=8.0,
        help="Max XML requests per second across all workers (default: 8)"
    )
    parser.add_argument(
        "--include-framework",
        action="store_true",
        help="Include framework agreements (excluded by default)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save to database, just log what would be done"
    )
    parser.add_argument(
        "--verbose", "-V",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse countries and CPV codes
    countries = args.countries.split(",") if args.countries else None
    cpv_codes = args.cpv.split(",") if args.cpv else None

    logger.info("=" * 60)
    logger.info("TENDERATOR - EU Tender Fetch Job")
    logger.info("=" * 60)
    logger.info(f"Days back:      {args.days}")
    logger.info(f"Max value:      €{args.max_value:,.0f}")
    logger.info(f"Countries:      {countries or 'All EU'}")
    logger.info(f"CPV codes:      {cpv_codes or 'All'}")
    logger.info(f"Max results:    {args.max_results}")
    logger.info(f"Dry run:        {args.dry_run}")
    logger.info("=" * 60)

    fetcher = TenderFetcher(
        max_value=args.max_value,
        include_framework=args.include_framework,
        dry_run=args.dry_run,
        xml_concurrency=args.xml_concurrency,
        xml_rate=args.xml_rate,
    )

    stats = await fetcher.fetch_tenders(
        days_back=args.days,
        countries=countries,
        cpv_codes=cpv_codes,
        max_results=args.max_results,
        dates=_date_range(args.from_date, args.to_date),
    )

    # Non-zero on ANY failure: a crashed job, per-notice errors, or a day that
    # was not fetched in full. Until 15 Sep 2026 a failed TED search set
    # job.status="failed" and still exited 0, so the cron reported success.
    if stats.get("failed") or stats["errors"] > 0 or stats.get("incomplete_days"):
        if stats.get("incomplete_days"):
            logger.error(f"[ERROR] Incomplete TED days: {', '.join(stats['incomplete_days'])}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
