"""
Collect EU Transparency Register Organizations

Downloads data for all ~16,870 lobby organizations from the EU Transparency
Register, using LobbyFacts CSV exports for rich per-org data.

Strategy:
1. Scrape the register's alphabetical listing via plain HTTP (no Playwright needed)
   - URL: ec.europa.eu/transparencyregister/public/alphabetical/REGISTRANTS/LATIN/{letter}/{page}
   - Returns HTML with 10 orgs per page, ~1,688 total pages
2. Batch-download per-org CSVs from LobbyFacts (/csv_export/{reg_id})
3. Consolidate into a single CSV

Usage:
    # Full pipeline (scrape IDs + download LobbyFacts data)
    python3.12 scripts/collect_lobby_orgs.py

    # Only scrape registration IDs (skip LobbyFacts download)
    python3.12 scripts/collect_lobby_orgs.py --ids-only

    # Only download LobbyFacts data (assumes IDs file exists)
    python3.12 scripts/collect_lobby_orgs.py --download-only

    # Resume interrupted download (skip already-fetched orgs)
    python3.12 scripts/collect_lobby_orgs.py --download-only --resume
"""

import asyncio
import csv
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "emails"
IDS_FILE = DATA_DIR / "lobby_org_ids.json"
RAW_CSV = DATA_DIR / "lobby_orgs_raw.csv"

LOBBYFACTS_CSV_URL = "https://www.lobbyfacts.eu/csv_export/{reg_id}"
REGISTER_ALPHA_URL = "https://ec.europa.eu/transparencyregister/public/alphabetical/REGISTRANTS/LATIN/{letter}/{page}?lang=en"

CONCURRENCY = 15  # Parallel LobbyFacts requests
LOBBYFACTS_DELAY = 0.3  # Seconds between batches
REGISTER_DELAY = 0.2  # Seconds between register page requests

LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Pre-computed page counts per letter (from live probing 2026-02-11)
LETTER_PAGES = {
    "a": 192, "b": 82, "c": 139, "d": 63, "e": 202, "f": 115,
    "g": 53, "h": 42, "i": 100, "j": 12, "k": 31, "l": 44,
    "m": 61, "n": 49, "o": 37, "p": 67, "q": 5, "r": 48,
    "s": 131, "t": 78, "u": 42, "v": 45, "w": 30, "x": 3,
    "y": 5, "z": 12,
}


# ---------------------------------------------------------------------------
# Phase 1a: Scrape registration IDs from the Transparency Register
# ---------------------------------------------------------------------------

async def scrape_registration_ids() -> list[str]:
    """
    Scrape all registration IDs from the Transparency Register's alphabetical
    listing using plain HTTP. No Playwright needed.

    The register's backend API returns HTML with 10 orgs per page.
    Pattern: ec.europa.eu/transparencyregister/public/alphabetical/REGISTRANTS/LATIN/{letter}/{page}
    """
    import httpx

    logger.info("[START] Scraping registration IDs from Transparency Register...")

    all_ids: set[str] = set()
    reg_id_pattern = re.compile(
        r'data-ecl-table-header="REG number:"[^>]*>(\d{10,14}-\d{2})<'
    )

    total_pages = sum(LETTER_PAGES.values())
    pages_done = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        for letter in LETTERS:
            max_page = LETTER_PAGES.get(letter, 50)
            letter_ids = set()

            for page in range(max_page):
                url = REGISTER_ALPHA_URL.format(letter=letter, page=page)
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.info(f"[WARN] {letter.upper()} page {page}: HTTP {resp.status_code}")
                        break

                    ids = reg_id_pattern.findall(resp.text)
                    if not ids:
                        # No more orgs on this page - we've reached the end
                        break

                    letter_ids.update(ids)

                except httpx.TimeoutException:
                    logger.info(f"[WARN] Timeout on {letter.upper()} page {page}, retrying...")
                    await asyncio.sleep(2)
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            ids = reg_id_pattern.findall(resp.text)
                            letter_ids.update(ids)
                    except Exception:
                        logger.info(f"[WARN] Retry failed for {letter.upper()} page {page}")

                except Exception as e:
                    logger.info(f"[WARN] Error on {letter.upper()} page {page}: {e}")

                pages_done += 1
                if pages_done % 100 == 0:
                    logger.info(f"[INFO] Progress: {pages_done}/{total_pages} pages, {len(all_ids) + len(letter_ids)} IDs")

                # Rate limiting
                await asyncio.sleep(REGISTER_DELAY)

            all_ids.update(letter_ids)
            logger.info(f"[OK] Letter {letter.upper()}: {len(letter_ids)} orgs ({len(all_ids)} total)")

    sorted_ids = sorted(all_ids)
    logger.info(f"[OK] Scraped {len(sorted_ids)} registration IDs from the register")
    return sorted_ids


# ---------------------------------------------------------------------------
# Phase 1b: Download per-org data from LobbyFacts CSV exports
# ---------------------------------------------------------------------------

LOBBYFACTS_FIELDS = [
    "identification_code", "original_name", "state_date", "members", "goals",
    "networking", "acronym", "legal_status", "web_site_url", "code_of_conduct",
    "info_members", "activity_eu_legislative", "activity_expert_groups",
    "activity_inter_groups", "activity_other", "activity_relevant_comm",
    "members_25", "members_fte", "number_of_natural_persons", "registration_date",
    "start_date", "end_date", "eur_sources_procurement", "eur_sources_procurement_src",
    "eur_sources_grants", "eur_sources_grants_src", "other_financial_information",
    "total", "total_public_financing", "infranational_sources", "national_sources",
    "total_other_sources", "contributions", "donations", "min", "max",
    "calculated_cost", "main_category", "sub_category",
    "head_title", "head_first_name", "head_last_name", "head_position",
    "legal_title", "legal_first_name", "legal_last_name", "legal_position",
    "eu_title", "eu_first_name", "eu_last_name", "eu_position",
    "be_address_1", "be_address_2", "be_postal_code", "be_city", "be_country", "be_phone",
    "head_address_1", "head_address_2", "head_postal_code", "head_city",
    "head_country", "head_phone", "url",
]


async def download_lobbyfacts_csvs(reg_ids: list[str], resume: bool = False) -> list[dict]:
    """
    Download per-org CSV data from LobbyFacts for each registration ID.
    Returns the LATEST entry per org (most recent state_date).
    """
    import httpx

    existing_ids = set()
    if resume and RAW_CSV.exists():
        with open(RAW_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row.get("identification_code", ""))
        logger.info(f"[RESUME] {len(existing_ids)} orgs already downloaded")

    remaining = [rid for rid in reg_ids if rid not in existing_ids]
    logger.info(f"[START] Downloading LobbyFacts data for {len(remaining)} orgs...")

    sem = asyncio.Semaphore(CONCURRENCY)
    all_orgs = []
    failed = 0
    empty = 0

    async def fetch_one(client: httpx.AsyncClient, reg_id: str) -> dict | None:
        nonlocal failed, empty
        url = LOBBYFACTS_CSV_URL.format(reg_id=reg_id)
        async with sem:
            try:
                resp = await client.get(url, timeout=30.0)
                if resp.status_code != 200:
                    failed += 1
                    return None

                text = resp.text.strip()
                if text == "no data found." or not text:
                    empty += 1
                    return None

                # Parse CSV - take the LAST row (most recent state_date)
                reader = csv.DictReader(io.StringIO(text))
                rows = list(reader)
                if not rows:
                    empty += 1
                    return None

                # Return the most recent entry
                return rows[-1]

            except Exception:
                failed += 1
                return None

    async with httpx.AsyncClient(
        headers={"User-Agent": "Brubru/1.0 (EU policy research)"},
        follow_redirects=True,
    ) as client:
        # Process in chunks to avoid overwhelming LobbyFacts
        CHUNK_SIZE = 50
        for i in range(0, len(remaining), CHUNK_SIZE):
            chunk = remaining[i : i + CHUNK_SIZE]
            tasks = [fetch_one(client, rid) for rid in chunk]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    all_orgs.append(result)

            done = min(i + CHUNK_SIZE, len(remaining))
            if done % 500 == 0 or done == len(remaining):
                logger.info(f"[INFO] {done}/{len(remaining)} processed, {len(all_orgs)} valid, {failed} failed, {empty} empty")

            # Rate limiting
            await asyncio.sleep(LOBBYFACTS_DELAY)

    logger.info(f"[OK] Downloaded {len(all_orgs)} valid org records")
    return all_orgs


def _clean_field(value: str) -> str:
    """Strip newlines, collapse whitespace, and trim text fields."""
    if not value:
        return ""
    # Replace newlines and tabs with spaces, collapse multiple spaces
    cleaned = re.sub(r"[\r\n\t]+", " ", value)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


def save_orgs_csv(orgs: list[dict], append: bool = False):
    """Save org data to CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Use a subset of important fields for the output CSV
    output_fields = [
        "identification_code", "original_name", "acronym", "web_site_url",
        "main_category", "sub_category", "goals", "activity_eu_legislative",
        "members_fte", "calculated_cost", "head_country",
        "head_first_name", "head_last_name",
        "eu_first_name", "eu_last_name",
        "be_city", "be_phone", "head_phone",
        "registration_date",
    ]

    # Text fields that need newline stripping
    text_fields = {"original_name", "acronym", "goals", "activity_eu_legislative",
                   "main_category", "sub_category"}

    mode = "a" if append else "w"
    write_header = not append or not RAW_CSV.exists()

    with open(RAW_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for org in orgs:
            row = {}
            for k in output_fields:
                val = org.get(k, "")
                row[k] = _clean_field(val) if k in text_fields else val
            writer.writerow(row)

    logger.info(f"[OK] Saved to {RAW_CSV}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Collect EU Transparency Register org data")
    parser.add_argument("--ids-only", action="store_true", help="Only scrape registration IDs")
    parser.add_argument("--download-only", action="store_true", help="Only download LobbyFacts data")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted download")
    parser.add_argument("--ids-file", type=str, help="Path to JSON file with registration IDs")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Get registration IDs
    if args.download_only:
        ids_path = Path(args.ids_file) if args.ids_file else IDS_FILE
        if not ids_path.exists():
            logger.error(f"[ERROR] IDs file not found: {ids_path}")
            logger.error("Run without --download-only first to scrape IDs")
            return

        with open(ids_path, "r") as f:
            reg_ids = json.load(f)
        logger.info(f"[OK] Loaded {len(reg_ids)} registration IDs from {ids_path}")

    else:
        reg_ids = await scrape_registration_ids()

        # Save IDs for reuse
        with open(IDS_FILE, "w") as f:
            json.dump(reg_ids, f)
        logger.info(f"[OK] Saved {len(reg_ids)} IDs to {IDS_FILE}")

        if args.ids_only:
            return

    # Step 2: Download LobbyFacts data
    orgs = await download_lobbyfacts_csvs(reg_ids, resume=args.resume)

    # Step 3: Save to CSV
    save_orgs_csv(orgs, append=args.resume)

    logger.info(f"\n[DONE] {len(orgs)} organizations collected")
    logger.info(f"  Output: {RAW_CSV}")


if __name__ == "__main__":
    asyncio.run(main())
