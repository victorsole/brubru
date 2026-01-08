"""
eCertis Evidence Data Extraction Script

Extracts ESPD criteria and evidence requirements from the European Commission's
eCertis REST API for all EU member states.

Source: https://ec.europa.eu/tools/ecertis/
API Docs: https://ec.europa.eu/tools/ecertis/assets/ECERTIS_REST_API.pdf

Usage:
    python -m backend.scripts.extract_ecertis
    python -m backend.scripts.extract_ecertis --countries be fr de
"""

import httpx
import json
import argparse
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ECERTIS_BASE_URL = "https://ec.europa.eu/growth/tools-databases/ecertisrest"

# All 27 EU member states
EU_COUNTRIES = [
    "at",  # Austria
    "be",  # Belgium
    "bg",  # Bulgaria
    "hr",  # Croatia
    "cy",  # Cyprus
    "cz",  # Czechia
    "dk",  # Denmark
    "ee",  # Estonia
    "fi",  # Finland
    "fr",  # France
    "de",  # Germany
    "gr",  # Greece
    "hu",  # Hungary
    "ie",  # Ireland
    "it",  # Italy
    "lv",  # Latvia
    "lt",  # Lithuania
    "lu",  # Luxembourg
    "mt",  # Malta
    "nl",  # Netherlands
    "pl",  # Poland
    "pt",  # Portugal
    "ro",  # Romania
    "sk",  # Slovakia
    "si",  # Slovenia
    "es",  # Spain
    "se",  # Sweden
]

COUNTRY_NAMES = {
    "at": "Austria", "be": "Belgium", "bg": "Bulgaria", "hr": "Croatia",
    "cy": "Cyprus", "cz": "Czechia", "dk": "Denmark", "ee": "Estonia",
    "fi": "Finland", "fr": "France", "de": "Germany", "gr": "Greece",
    "hu": "Hungary", "ie": "Ireland", "it": "Italy", "lv": "Latvia",
    "lt": "Lithuania", "lu": "Luxembourg", "mt": "Malta", "nl": "Netherlands",
    "pl": "Poland", "pt": "Portugal", "ro": "Romania", "sk": "Slovakia",
    "si": "Slovenia", "es": "Spain", "se": "Sweden"
}


async def fetch_country_criteria_list(
    client: httpx.AsyncClient,
    country: str
) -> List[Dict[str, Any]]:
    """Fetch list of all criteria for a country."""
    url = f"{ECERTIS_BASE_URL}/criteria"
    params = {"nationalEntity": country}

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("criterion", [])
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch criteria list for {country}: {e}")
        return []


async def fetch_criterion_details(
    client: httpx.AsyncClient,
    criterion_id: str
) -> Optional[Dict[str, Any]]:
    """Fetch detailed information for a single criterion including evidence."""
    url = f"{ECERTIS_BASE_URL}/criteria/{criterion_id}"

    try:
        response = await client.get(url)
        response.raise_for_status()

        # Check if response has content
        if not response.text or response.text.strip() == "":
            logger.warning(f"Empty response for criterion {criterion_id}")
            return None

        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch criterion {criterion_id}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON for criterion {criterion_id}: {e}")
        return None


async def fetch_country_data(
    client: httpx.AsyncClient,
    country: str,
    fetch_details: bool = True
) -> Dict[str, Any]:
    """
    Fetch all criteria and optionally their details for a country.

    Args:
        client: HTTP client
        country: 2-letter country code
        fetch_details: If True, fetch full details for each criterion

    Returns:
        {
            "country_code": "be",
            "country_name": "Belgium",
            "extraction_date": "2025-11-27T...",
            "criteria_count": 56,
            "criteria": [...]
        }
    """
    logger.info(f"Fetching criteria for {COUNTRY_NAMES.get(country, country).upper()}...")

    # Get criteria list
    criteria_list = await fetch_country_criteria_list(client, country)

    if not criteria_list:
        logger.warning(f"No criteria found for {country}")
        return {
            "country_code": country,
            "country_name": COUNTRY_NAMES.get(country, country),
            "extraction_date": datetime.now().isoformat(),
            "criteria_count": 0,
            "criteria": []
        }

    # Optionally fetch details for each criterion
    if fetch_details:
        detailed_criteria = []
        for i, criterion in enumerate(criteria_list):
            criterion_id = criterion.get("Id", {}).get("value")
            if criterion_id:
                details = await fetch_criterion_details(client, criterion_id)
                if details:
                    detailed_criteria.append(details)

                # Progress indicator
                if (i + 1) % 10 == 0:
                    logger.info(f"  {country}: {i + 1}/{len(criteria_list)} criteria fetched")

                # Small delay to be respectful to the API
                await asyncio.sleep(0.1)

        criteria = detailed_criteria
    else:
        criteria = criteria_list

    return {
        "country_code": country,
        "country_name": COUNTRY_NAMES.get(country, country),
        "extraction_date": datetime.now().isoformat(),
        "criteria_count": len(criteria),
        "criteria": criteria
    }


async def extract_ecertis(
    output_dir: Path,
    countries: List[str] = None,
    fetch_details: bool = True
) -> Dict[str, int]:
    """
    Extract eCertis data for specified countries.

    Args:
        output_dir: Output directory for JSON files
        countries: List of country codes (defaults to all EU)
        fetch_details: Whether to fetch full criterion details

    Returns:
        Dict mapping country code to criteria count
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if countries is None:
        countries = EU_COUNTRIES

    results = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for country in countries:
            data = await fetch_country_data(client, country, fetch_details)

            output_file = output_dir / f"criteria_{country}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            results[country] = data["criteria_count"]
            logger.info(f"✓ {COUNTRY_NAMES.get(country, country)}: {data['criteria_count']} criteria → {output_file.name}")

            # Delay between countries
            await asyncio.sleep(0.5)

    return results


def create_summary(results: Dict[str, int], output_dir: Path):
    """Create a summary JSON file."""
    summary = {
        "source": "eCertis REST API",
        "api_url": ECERTIS_BASE_URL,
        "extraction_date": datetime.now().isoformat(),
        "countries": {
            code: {
                "name": COUNTRY_NAMES.get(code, code),
                "criteria_count": count
            }
            for code, count in results.items()
        },
        "total_countries": len(results),
        "total_criteria": sum(results.values())
    }

    summary_file = output_dir / "ecertis_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ Summary written to {summary_file}")


async def main_async(args):
    """Async main function."""
    output_dir = Path(args.output)

    countries = args.countries if args.countries else None

    results = await extract_ecertis(
        output_dir,
        countries=countries,
        fetch_details=not args.list_only
    )

    if results:
        create_summary(results, output_dir)
        total = sum(results.values())
        logger.info(f"\n✓ Extraction complete: {len(results)} countries, {total} total criteria")
    else:
        logger.error("No data was extracted")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Extract eCertis evidence data from EU API"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backend/knowledge_base/tenders/ecertis",
        help="Output directory for JSON files"
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        help="Specific country codes to extract (e.g., be fr de)"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only fetch criteria list, not full details"
    )

    args = parser.parse_args()

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    exit(main())
