"""
Load Historical Tenders Script

Uses TED SPARQL endpoint to fetch historical tender data (last 6-12 months).
Best for bulk data loads and analytics queries.

Usage:
    # Load last 6 months of data
    python -m backend.scripts.load_historical_tenders

    # Load last 12 months for specific countries
    python -m backend.scripts.load_historical_tenders --months 12 --countries FR,DE,BE

    # Load with specific CPV codes (IT services)
    python -m backend.scripts.load_historical_tenders --cpv 72,48

    # Dry run
    python -m backend.scripts.load_historical_tenders --dry-run
"""

import asyncio
import argparse
import logging
import sys
import csv
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import Tender, TenderFetchJob
from backend.services.tenders.ted_sparql_client import TEDSPARQLClient
from backend.services.tenders.sme_scorer import SMEScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('historical_tender_load.log')
    ]
)
logger = logging.getLogger(__name__)


# Default settings
DEFAULT_MONTHS_BACK = 6
DEFAULT_BATCH_SIZE = 500
DEFAULT_MAX_VALUE = 5_000_000  # €5M for SME filter


class HistoricalTenderLoader:
    """
    Loads historical tender data from TED SPARQL endpoint.

    Uses eProcurement Ontology (ePO) to query:
    - Historical tenders by date range
    - Tenders by country
    - Tenders by CPV code
    - Awarded contracts for analytics
    """

    def __init__(
        self,
        max_value: float = DEFAULT_MAX_VALUE,
        dry_run: bool = False
    ):
        self.max_value = max_value
        self.dry_run = dry_run
        self.scorer = SMEScorer()
        self.db = SessionLocal()

        # Statistics
        self.stats = {
            "queried": 0,
            "new": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": []
        }

    async def load_historical_data(
        self,
        months_back: int = DEFAULT_MONTHS_BACK,
        countries: Optional[List[str]] = None,
        cpv_prefixes: Optional[List[str]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> Dict[str, Any]:
        """
        Load historical tender data from SPARQL endpoint.

        Args:
            months_back: Number of months to look back
            countries: Filter by country names (e.g., ['France', 'Germany'])
            cpv_prefixes: Filter by CPV code prefixes
            batch_size: Number of results per query

        Returns:
            Statistics dictionary with load results
        """
        logger.info(f"Starting historical data load: months={months_back}")

        date_from = date.today() - timedelta(days=months_back * 30)
        date_to = date.today()

        # Create fetch job record
        job = self._create_fetch_job(months_back, countries, cpv_prefixes)

        try:
            async with TEDSPARQLClient() as client:
                # Map country codes to names if provided
                country_names = self._get_country_names(countries) if countries else None

                if country_names:
                    # Query by each country
                    for country in country_names:
                        logger.info(f"Loading tenders for {country}...")
                        await self._load_by_country(client, country, batch_size)
                else:
                    # Query by date range
                    logger.info(f"Loading tenders from {date_from} to {date_to}...")
                    await self._load_by_date_range(client, date_from, date_to, batch_size)

                # Also load awarded contracts for analytics
                logger.info("Loading awarded contracts for analytics...")
                await self._load_awarded_contracts(client, date_from, date_to, batch_size)

                # Commit all changes
                if not self.dry_run:
                    self.db.commit()

                # Update job status
                job.status = "completed"
                job.tenders_found = self.stats["queried"]
                job.tenders_new = self.stats["new"]

        except Exception as e:
            logger.error(f"Historical load failed: {e}")
            job.status = "failed"
            job.errors = [str(e)]
            self.stats["error_details"].append(str(e))

        finally:
            job.completed_at = datetime.utcnow()
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()

            if not self.dry_run:
                self.db.commit()

            self.db.close()

        self._log_summary()
        return self.stats

    async def _load_by_country(
        self,
        client: TEDSPARQLClient,
        country: str,
        limit: int
    ):
        """Load tenders for a specific country."""
        try:
            results = await client.get_tenders_by_country(country, limit=limit)
            await self._process_sparql_results(results)
        except Exception as e:
            logger.error(f"Failed to load tenders for {country}: {e}")
            self.stats["errors"] += 1
            self.stats["error_details"].append(f"Country {country}: {str(e)}")

    async def _load_by_date_range(
        self,
        client: TEDSPARQLClient,
        date_from: date,
        date_to: date,
        limit: int
    ):
        """Load tenders by date range."""
        try:
            results = await client.get_tenders_by_date_range(
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )
            await self._process_sparql_results(results)
        except Exception as e:
            logger.error(f"Failed to load tenders by date range: {e}")
            self.stats["errors"] += 1
            self.stats["error_details"].append(f"Date range: {str(e)}")

    async def _load_awarded_contracts(
        self,
        client: TEDSPARQLClient,
        date_from: date,
        date_to: date,
        limit: int
    ):
        """Load awarded contracts for analytics."""
        try:
            results = await client.get_awarded_contracts(
                date_from=date_from,
                date_to=date_to,
                limit=limit
            )

            if results and "results" in results:
                bindings = results.get("results", {}).get("bindings", [])
                logger.info(f"Found {len(bindings)} awarded contracts")

                for binding in bindings:
                    pub_num = binding.get("publicationNumber", {}).get("value")
                    if not pub_num:
                        continue

                    # Check if exists
                    existing = self.db.query(Tender).filter(
                        Tender.publication_number == pub_num
                    ).first()

                    if existing:
                        # Update status to awarded
                        existing.status = "awarded"
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new entry as awarded
                        tender = self._create_tender_from_sparql(binding, status="awarded")
                        if tender and not self.dry_run:
                            self.db.add(tender)
                            self.stats["new"] += 1

                    self.stats["queried"] += 1

        except Exception as e:
            logger.error(f"Failed to load awarded contracts: {e}")
            self.stats["error_details"].append(f"Awarded contracts: {str(e)}")

    async def _process_sparql_results(self, results: Dict[str, Any]):
        """Process SPARQL query results."""
        if not results or "results" not in results:
            return

        bindings = results.get("results", {}).get("bindings", [])
        logger.info(f"Processing {len(bindings)} SPARQL results...")

        for binding in bindings:
            try:
                pub_num = binding.get("publicationNumber", {}).get("value")
                if not pub_num:
                    self.stats["skipped"] += 1
                    continue

                # Check if already exists
                existing = self.db.query(Tender).filter(
                    Tender.publication_number == pub_num
                ).first()

                if existing:
                    self.stats["skipped"] += 1
                    continue

                # Create new tender from SPARQL data
                tender = self._create_tender_from_sparql(binding)
                if tender and not self.dry_run:
                    self.db.add(tender)
                    self.stats["new"] += 1

                self.stats["queried"] += 1

            except Exception as e:
                self.stats["errors"] += 1
                self.stats["error_details"].append(str(e))

    def _create_tender_from_sparql(
        self,
        binding: Dict[str, Any],
        status: str = "open"
    ) -> Optional[Tender]:
        """Create a Tender from SPARQL result binding."""
        pub_num = binding.get("publicationNumber", {}).get("value")
        if not pub_num:
            return None

        # Extract values from SPARQL binding
        title = binding.get("title", {}).get("value", "")
        description = binding.get("description", {}).get("value")
        legal_name = binding.get("legalName", {}).get("value")
        pub_date_str = binding.get("publicationDate", {}).get("value")
        value_str = binding.get("estimatedValue", {}).get("value")
        currency = binding.get("currency", {}).get("value", "EUR")

        # Parse publication date
        pub_date = None
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Parse value
        estimated_value = None
        if value_str:
            try:
                estimated_value = float(value_str)
            except ValueError:
                pass

        tender = Tender(
            publication_number=pub_num,
            title=title,
            description=description,
            official_name=legal_name,
            publication_date=pub_date,
            estimated_value=estimated_value,
            estimated_value_currency=currency,
            ted_url=f"https://ted.europa.eu/udl?uri=TED:NOTICE:{pub_num}:TEXT:EN:HTML",
            status=status,
            source="ted_sparql",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Calculate SME score
        sme_analysis = self.scorer.get_sme_analysis({
            "estimated_value": estimated_value,
            "procedure_type": None,
            "submission_deadline": None,
            "has_lots": False,
            "lot_count": 0
        })
        tender.sme_suitability_score = sme_analysis.get("sme_suitability_score")

        return tender

    def _create_fetch_job(
        self,
        months_back: int,
        countries: Optional[List[str]],
        cpv_prefixes: Optional[List[str]]
    ) -> TenderFetchJob:
        """Create a fetch job record."""
        import uuid

        job = TenderFetchJob(
            job_id=str(uuid.uuid4())[:8],
            job_type="historical",
            source="ted_sparql",
            query_params={
                "months_back": months_back,
                "countries": countries,
                "cpv_prefixes": cpv_prefixes,
                "max_value": self.max_value
            },
            status="running",
            started_at=datetime.utcnow()
        )

        if not self.dry_run:
            self.db.add(job)
            self.db.commit()

        return job

    def _get_country_names(self, country_codes: List[str]) -> List[str]:
        """Map ISO country codes to full names for SPARQL."""
        code_to_name = {
            "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
            "CY": "Cyprus", "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia",
            "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
            "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia",
            "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
            "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
            "SI": "Slovenia", "ES": "Spain", "SE": "Sweden"
        }
        return [code_to_name.get(code.upper(), code) for code in country_codes]

    def _log_summary(self):
        """Log load summary."""
        logger.info("=" * 60)
        logger.info("HISTORICAL TENDER LOAD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total queried:  {self.stats['queried']}")
        logger.info(f"New tenders:    {self.stats['new']}")
        logger.info(f"Skipped:        {self.stats['skipped']}")
        logger.info(f"Errors:         {self.stats['errors']}")

        if self.stats["error_details"]:
            logger.info("Error details:")
            for err in self.stats["error_details"][:5]:
                logger.info(f"  - {err}")

        logger.info("=" * 60)


async def load_awarded_contracts_csv():
    """
    Load awarded contracts from existing CSV file.
    File: backend/knowledge_base/tenders/awarded_contracts_2025_EC.csv
    """
    csv_path = Path("backend/knowledge_base/tenders/awarded_contracts_2025_EC.csv")

    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return

    logger.info(f"Loading awarded contracts from {csv_path}...")

    db = SessionLocal()
    loaded = 0
    skipped = 0

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                pub_num = row.get("Publication Number", row.get("publication_number"))
                if not pub_num:
                    skipped += 1
                    continue

                # Check if exists
                existing = db.query(Tender).filter(
                    Tender.publication_number == pub_num
                ).first()

                if existing:
                    skipped += 1
                    continue

                # Create tender from CSV
                tender = Tender(
                    publication_number=pub_num,
                    title=row.get("Title", row.get("title", "")),
                    official_name=row.get("Buyer", row.get("buyer")),
                    buyer_country=row.get("Country", row.get("country")),
                    cpv_main=row.get("CPV", row.get("cpv")),
                    estimated_value=_parse_float(row.get("Value", row.get("value"))),
                    status="awarded",
                    source="csv_import",
                    ted_url=f"https://ted.europa.eu/udl?uri=TED:NOTICE:{pub_num}:TEXT:EN:HTML",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                db.add(tender)
                loaded += 1

                if loaded % 100 == 0:
                    db.commit()
                    logger.info(f"Loaded {loaded} contracts...")

        db.commit()
        logger.info(f"CSV import complete: {loaded} loaded, {skipped} skipped")

    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        db.rollback()

    finally:
        db.close()


def _parse_float(value: str) -> Optional[float]:
    """Parse float from string, handling various formats."""
    if not value:
        return None
    try:
        # Remove currency symbols and thousand separators
        cleaned = value.replace("€", "").replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except ValueError:
        return None


async def main():
    """Main entry point for the historical load script."""
    parser = argparse.ArgumentParser(
        description="Load historical EU tender data from TED SPARQL endpoint"
    )
    parser.add_argument(
        "--months", "-m",
        type=int,
        default=DEFAULT_MONTHS_BACK,
        help=f"Number of months to look back (default: {DEFAULT_MONTHS_BACK})"
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
        "--batch-size", "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size per query (default: {DEFAULT_BATCH_SIZE})"
    )
    parser.add_argument(
        "--max-value", "-v",
        type=float,
        default=DEFAULT_MAX_VALUE,
        help=f"Maximum tender value filter (default: {DEFAULT_MAX_VALUE})"
    )
    parser.add_argument(
        "--load-csv",
        action="store_true",
        help="Also load awarded contracts from CSV file"
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Only load from CSV, skip SPARQL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save to database"
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
    cpv_prefixes = args.cpv.split(",") if args.cpv else None

    logger.info("=" * 60)
    logger.info("TENDERATOR - Historical Data Load")
    logger.info("=" * 60)
    logger.info(f"Months back:    {args.months}")
    logger.info(f"Countries:      {countries or 'All EU'}")
    logger.info(f"CPV prefixes:   {cpv_prefixes or 'All'}")
    logger.info(f"Batch size:     {args.batch_size}")
    logger.info(f"Max value:      €{args.max_value:,.0f}")
    logger.info(f"Dry run:        {args.dry_run}")
    logger.info("=" * 60)

    # Load from CSV if requested
    if args.load_csv or args.csv_only:
        await load_awarded_contracts_csv()

    # Skip SPARQL if CSV only
    if args.csv_only:
        return

    # Load from SPARQL
    loader = HistoricalTenderLoader(
        max_value=args.max_value,
        dry_run=args.dry_run
    )

    stats = await loader.load_historical_data(
        months_back=args.months,
        countries=countries,
        cpv_prefixes=cpv_prefixes,
        batch_size=args.batch_size
    )

    # Exit with error code if there were failures
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
