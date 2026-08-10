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
from datetime import datetime, timedelta, timezone
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
from services.tenders.ted_client import TEDClient  # noqa: E402
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
        dry_run: bool = False
    ):
        self.max_value = max_value
        self.min_deadline_days = min_deadline_days
        self.include_framework = include_framework
        self.dry_run = dry_run

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
        max_results: int = 1000
    ) -> Dict[str, Any]:
        """
        Fetch tenders from TED API with SME-friendly filters.

        Args:
            days_back: Number of days to look back
            countries: Filter by country codes (e.g., ['BE', 'FR', 'DE'])
            cpv_codes: Filter by CPV code prefixes
            max_results: Maximum number of results to fetch

        Returns:
            Statistics dictionary with fetch results
        """
        logger.info(f"Starting tender fetch: days_back={days_back}, max_value={self.max_value}")

        # Create fetch job record
        job = self._create_fetch_job(days_back, countries, cpv_codes)

        try:
            async with TEDClient() as client:
                # Use SME-friendly search
                all_notices = []
                page = 1

                while len(all_notices) < max_results:
                    logger.info(f"Fetching page {page}...")

                    result = await client.search_sme_friendly(
                        cpv_codes=cpv_codes,
                        countries=countries,
                        max_value=self.max_value,
                        min_deadline_days=self.min_deadline_days,
                        # `days_back` used to reach only the fetch-job record,
                        # never the query, so every run swept the same open
                        # backlog regardless of what the caller asked for.
                        published_since_days=days_back,
                        page=page,
                        page_size=50  # Reduced page size to avoid rate limits
                    )

                    notices = result.get("notices", [])
                    if not notices:
                        break

                    all_notices.extend(notices)
                    self.stats["fetched"] = len(all_notices)

                    total_pages = result.get("total_pages", 1)
                    if page >= total_pages or page >= 10:  # Max 10 pages
                        break

                    page += 1
                    await asyncio.sleep(2.0)  # More conservative rate limiting to avoid 429

                logger.info(f"Fetched {len(all_notices)} notices from TED API")

                # Process each notice
                for i, notice in enumerate(all_notices):
                    try:
                        await self._process_notice(notice, client)

                        if (i + 1) % 50 == 0:
                            logger.info(f"Processed {i + 1}/{len(all_notices)} notices")

                    except Exception as e:
                        self.stats["errors"] += 1
                        self.stats["error_details"].append(str(e))
                        logger.error(f"Error processing notice: {e}")

                # Commit all changes
                if not self.dry_run:
                    self.db.commit()

                # Update job status
                job.status = "completed"
                job.tenders_found = self.stats["fetched"]
                job.tenders_new = self.stats["new"]
                job.tenders_updated = self.stats["updated"]

        except Exception as e:
            logger.error(f"Fetch job failed: {e}")
            job.status = "failed"
            job.errors = [str(e)]
            self.stats["error_details"].append(str(e))

        finally:
            from datetime import timezone
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                # Make started_at timezone-aware if it isn't
                if job.started_at.tzinfo is None:
                    started = job.started_at.replace(tzinfo=timezone.utc)
                else:
                    started = job.started_at
                job.duration_seconds = (job.completed_at - started).total_seconds()

            if not self.dry_run:
                self.db.commit()

            self.db.close()

        self._log_summary()
        return self.stats

    async def _process_notice(self, notice: Dict[str, Any], client: TEDClient):
        """Process a single notice from the API."""
        # TED API v3 uses different field names
        publication_number = (
            notice.get("publication-number") or
            notice.get("ND") or
            notice.get("publicationNumber")
        )

        if not publication_number:
            self.stats["skipped"] += 1
            return

        # Check if already exists
        existing = self.db.query(Tender).filter(
            Tender.publication_number == publication_number
        ).first()

        if existing:
            # Update existing tender
            self._update_tender(existing, notice)
            self.stats["updated"] += 1

            # Backfill XML if missing
            if not existing.xml_content:
                try:
                    xml_content = await client.get_notice_xml(publication_number)
                    if xml_content:
                        existing.xml_content = xml_content
                        # Re-parse to extract award criteria
                        try:
                            parsed = self.parser.parse_to_tender_dict(xml_content, publication_number)
                            if parsed.get("award_criteria"):
                                existing.award_criteria = parsed.get("award_criteria")
                                existing.award_criteria_type = parsed.get("award_criteria_type")
                            if parsed.get("description") and not existing.description:
                                existing.description = parsed.get("description")
                            if parsed.get("selection_criteria"):
                                existing.selection_criteria = parsed.get("selection_criteria")
                            if parsed.get("minimum_requirements"):
                                existing.minimum_requirements = parsed.get("minimum_requirements")
                        except Exception as e:
                            logger.warning(f"XML parsing failed for backfill {publication_number}: {e}")
                    await asyncio.sleep(0.5)  # Rate limit
                except Exception as e:
                    logger.debug(f"Could not backfill XML for {publication_number}: {e}")
        else:
            # Fetch full XML for new tenders
            xml_content = None
            try:
                xml_content = await client.get_notice_xml(publication_number)
                await asyncio.sleep(0.5)  # Rate limit XML fetches
            except Exception as e:
                logger.warning(f"Could not fetch XML for {publication_number}: {e}")

            # Create new tender
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

        if self.stats["error_details"]:
            logger.info("Error details:")
            for err in self.stats["error_details"][:5]:
                logger.info(f"  - {err}")

        logger.info("=" * 60)


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
        default=1000,
        help="Maximum number of results to fetch (default: 1000)"
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
        dry_run=args.dry_run
    )

    stats = await fetcher.fetch_tenders(
        days_back=args.days,
        countries=countries,
        cpv_codes=cpv_codes,
        max_results=args.max_results
    )

    # Exit with error code if there were failures
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
