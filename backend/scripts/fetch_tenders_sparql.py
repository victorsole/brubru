"""
Fetch Tenders via SPARQL

Simple script to fetch tenders using the TED SPARQL endpoint.
This is more reliable than the REST API for initial data loading.

Usage:
    python -m backend.scripts.fetch_tenders_sparql --days 30 --limit 50
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import Tender
from backend.services.tenders.ted_sparql_client import TEDSPARQLClient
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Language patterns for country detection (EU countries)
LANGUAGE_PATTERNS = {
    'ES': [r'\b(servicio|suministro|contrato|acuerdo|marco|gestión|vigilancia|contratación)\b'],
    'IT': [r'\b(fornitura|servizio|procedura|aperta|gara|affidamento|aziend[ae]|sanitari[ae])\b'],
    'DE': [r'\b(dienstleistung|lieferung|vergabe|beschaffung|rahmenvertrag|bekanntmachung)\b'],
    'FR': [r'\b(fourniture|marché|service|prestations|accord|cadre|attribution)\b'],
    'PT': [r'\b(fornecimento|aquisição|serviços|contratação|procedimento)\b'],
    'NL': [r'\b(levering|diensten|aanbesteding|raamovereenkomst)\b'],
    'PL': [r'\b(dostaw[ay]|usług[ai]|zamówieni[ae]|przetarg)\b'],
    'RO': [r'\b(furnizare|servicii|achiziție|contract[e]?)\b'],
    'EL': [r'\b(προμήθεια|υπηρεσι|σύμβαση|διαγωνισμ)\b'],
    'BG': [r'\b(доставка|услуги|договор|обществен[а]?)\b'],
    'HU': [r'\b(beszerzés|szolgáltatás|szerződés)\b'],
    'CS': [r'\b(dodávk[ay]|služb[ay]|zakázk[ay]|veřejn)\b'],
    'SK': [r'\b(dodávk[ay]|služieb|zákazk[ay])\b'],
    'SV': [r'\b(upphandling|tjänst|leverans|ramavtal)\b'],
    'DA': [r'\b(udbud|tjenesteydelse|leverance|rammeaftale)\b'],
    'FI': [r'\b(hankinta|palvelu|toimitus|puitejärjestely)\b'],
    'LT': [r'\b(paslaugų|tiekimo|pirkimo|sutart)\b'],
    'LV': [r'\b(pakalpojum|piegād|iepirkum)\b'],
    'ET': [r'\b(teenus|hange|tarne)\b'],
    'SL': [r'\b(dobav|storitev|naročil)\b'],
    'HR': [r'\b(nabav|uslug|ugovor)\b'],
}


def detect_country_from_text(text: str) -> str:
    """Detect country code from text language patterns."""
    if not text:
        return None

    text_lower = text.lower()
    scores = {}

    for country, patterns in LANGUAGE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            score += matches
        if score > 0:
            scores[country] = score

    if scores:
        # Return country with highest score
        return max(scores, key=scores.get)

    return None


async def fetch_and_save_tenders(
    days_back: int = 30,
    countries: List[str] = None,
    limit: int = 100
) -> Dict[str, int]:
    """
    Fetch tenders from TED SPARQL endpoint and save to database.

    Args:
        days_back: Number of days to look back
        countries: List of country names (e.g., ["Belgium", "Netherlands"])
        limit: Maximum number of tenders to fetch

    Returns:
        Statistics dictionary
    """
    stats = {
        "fetched": 0,
        "new": 0,
        "updated": 0,
        "errors": 0
    }

    db = SessionLocal()

    try:
        # Calculate date range
        date_to = datetime.now(timezone.utc).date()
        date_from = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()

        logger.info(f"Fetching tenders from {date_from} to {date_to}")
        logger.info(f"Countries: {countries or 'All EU'}")
        logger.info(f"Limit: {limit}")

        # Initialize SPARQL client
        async with TEDSPARQLClient() as client:
            # Fetch tenders by date range
            results = await client.get_tenders_by_date_range(
                date_from=date_from,
                date_to=date_to,
                countries=countries,
                limit=limit
            )

            logger.info(f"SPARQL query returned {len(results)} results")
            stats["fetched"] = len(results)

            # Track seen publication numbers to handle duplicates in results
            seen_pub_numbers = set()

            # Process each result
            for i, result in enumerate(results, 1):
                try:
                    # Extract data from SPARQL result (base client already extracts values)
                    pub_number = result.get("publicationNumber", "")

                    if not pub_number:
                        logger.warning(f"Skipping result {i}: no publication number")
                        continue

                    # Skip duplicates within this batch
                    if pub_number in seen_pub_numbers:
                        continue
                    seen_pub_numbers.add(pub_number)

                    # Check if tender already exists
                    existing = db.query(Tender).filter(
                        Tender.publication_number == pub_number
                    ).first()

                    if existing:
                        logger.debug(f"Tender {pub_number} already exists, updating...")
                        _update_tender_from_sparql(existing, result)
                        stats["updated"] += 1
                    else:
                        logger.info(f"Creating new tender {pub_number}")
                        tender = _create_tender_from_sparql(result)
                        db.add(tender)
                        stats["new"] += 1

                    # Commit every 10 tenders
                    if i % 10 == 0:
                        db.commit()
                        logger.info(f"Processed {i}/{len(results)} tenders")

                except Exception as e:
                    logger.error(f"Error processing tender {i}: {e}")
                    stats["errors"] += 1
                    continue

            # Final commit
            db.commit()

    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        db.rollback()
        raise

    finally:
        db.close()

    return stats


def _parse_datetime(dt_str: str) -> datetime:
    """Parse a datetime string from SPARQL, handling various formats."""
    if not dt_str:
        return None
    try:
        # Try ISO format first
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        try:
            # Try parsing just date
            return datetime.strptime(dt_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None


def _create_tender_from_sparql(result: Dict[str, Any]) -> Tender:
    """Create a Tender model from SPARQL query result."""

    # Helper to extract value - base client already extracts values directly
    def get_val(key: str, default=None):
        return result.get(key, default)

    pub_number = get_val("publicationNumber", "")

    # Parse dates
    pub_date = _parse_datetime(get_val("publicationDate"))
    submission_deadline = _parse_datetime(get_val("submissionDeadline"))

    # Parse value
    estimated_value = None
    if get_val("estimatedValue"):
        try:
            estimated_value = float(get_val("estimatedValue"))
        except (ValueError, TypeError):
            pass

    # Extract CPV code - ensure it's a string
    cpv_code = get_val("cpvCode")
    cpv_codes = [cpv_code] if cpv_code else None

    # Country: prefer ISO code, fallback to name, NUTS code, or language detection
    buyer_country = get_val("countryCode") or get_val("countryName")
    if not buyer_country:
        # NUTS codes start with 2-letter country code (e.g., "DE123", "FR100")
        nuts_code = get_val("nutsCode")
        if nuts_code and len(nuts_code) >= 2:
            buyer_country = nuts_code[:2].upper()

    if not buyer_country:
        # Last resort: detect from title/description language
        title = get_val("title", "")
        description = get_val("description", "")
        combined_text = f"{title} {description}"
        buyer_country = detect_country_from_text(combined_text)

    # Get NUTS code if available
    nuts_code = get_val("nutsCode")
    nuts_codes = [nuts_code] if nuts_code else None

    tender = Tender(
        publication_number=pub_number,
        title=get_val("title", "Untitled Tender"),
        description=get_val("description"),
        official_name=get_val("buyerName"),
        buyer_country=buyer_country,
        publication_date=pub_date,
        submission_deadline=submission_deadline,
        cpv_main=cpv_code,
        cpv_codes=cpv_codes,
        nuts_codes=nuts_codes,
        procedure_type=get_val("procedureType"),
        estimated_value=estimated_value,
        estimated_value_currency=get_val("currency", "EUR"),
        ted_url=f"https://ted.europa.eu/en/notice/-/detail/{pub_number}",
        status="open",
        source="ted_sparql",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    return tender


def _update_tender_from_sparql(tender: Tender, result: Dict[str, Any]):
    """Update existing tender with SPARQL data."""

    def get_val(key: str, default=None):
        return result.get(key, default)

    # Update fields if available
    if get_val("title"):
        tender.title = get_val("title")

    if get_val("description"):
        tender.description = get_val("description")

    if get_val("buyerName"):
        tender.official_name = get_val("buyerName")

    # Update country - try NUTS code or language detection
    country = get_val("countryCode") or get_val("countryName")
    if not country:
        nuts_code = get_val("nutsCode")
        if nuts_code and len(nuts_code) >= 2:
            country = nuts_code[:2].upper()
    if not country:
        # Detect from title/description
        title = get_val("title", "")
        description = get_val("description", "")
        combined_text = f"{title} {description}"
        country = detect_country_from_text(combined_text)
    if country:
        tender.buyer_country = country

    # Update NUTS codes
    nuts_code = get_val("nutsCode")
    if nuts_code:
        tender.nuts_codes = [nuts_code]

    # Update CPV code
    cpv_code = get_val("cpvCode")
    if cpv_code:
        tender.cpv_main = cpv_code
        tender.cpv_codes = [cpv_code]

    # Update procedure type
    if get_val("procedureType"):
        tender.procedure_type = get_val("procedureType")

    # Update value
    if get_val("estimatedValue"):
        try:
            tender.estimated_value = float(get_val("estimatedValue"))
            tender.estimated_value_currency = get_val("currency", "EUR")
        except (ValueError, TypeError):
            pass

    # Update deadline
    deadline = _parse_datetime(get_val("submissionDeadline"))
    if deadline:
        tender.submission_deadline = deadline

    tender.updated_at = datetime.now(timezone.utc)
    tender.last_synced_at = datetime.now(timezone.utc)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch tenders from TED via SPARQL"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)"
    )
    parser.add_argument(
        "--countries", "-c",
        type=str,
        help="Comma-separated country names (e.g., 'Belgium,Netherlands')"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum number of tenders to fetch (default: 100)"
    )

    args = parser.parse_args()

    # Parse countries
    countries = None
    if args.countries:
        countries = [c.strip() for c in args.countries.split(",")]

    logger.info("=" * 60)
    logger.info("TENDERATOR - Fetch Tenders via SPARQL")
    logger.info("=" * 60)

    try:
        stats = await fetch_and_save_tenders(
            days_back=args.days,
            countries=countries,
            limit=args.limit
        )

        logger.info("=" * 60)
        logger.info("FETCH COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Fetched:  {stats['fetched']}")
        logger.info(f"New:      {stats['new']}")
        logger.info(f"Updated:  {stats['updated']}")
        logger.info(f"Errors:   {stats['errors']}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
