"""
Discover Contact Emails for EU Transparency Register Organizations

For each org in lobby_orgs_raw.csv that has a web_site_url:
1. Extract domain from URL
2. Check DNS MX records to verify domain accepts email
3. Try common generic contact patterns (info@, contact@, office@, eu@)
4. Score each email's validity based on MX check

Usage:
    # Full pipeline
    python3.12 scripts/collect_lobby_emails.py

    # Resume interrupted run
    python3.12 scripts/collect_lobby_emails.py --resume

    # Only process first N orgs (for testing)
    python3.12 scripts/collect_lobby_emails.py --limit 100
"""

import asyncio
import csv
import dns.resolver
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "emails"
RAW_CSV = DATA_DIR / "lobby_orgs_raw.csv"
OUTPUT_CSV = DATA_DIR / "lobby_orgs_emails.csv"

# Common generic email prefixes to try, in priority order
EMAIL_PREFIXES = ["info", "contact", "office", "eu", "europa", "brussels", "policy"]

CONCURRENCY = 30  # Parallel DNS lookups
MX_CACHE: dict[str, bool] = {}  # domain -> has MX records


# ---------------------------------------------------------------------------
# Domain extraction
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str | None:
    """Extract the root domain from a URL, stripping www. prefix."""
    if not url or not url.strip():
        return None

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        domain = parsed.hostname
        if not domain:
            return None

        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Basic validation
        if "." not in domain or len(domain) < 4:
            return None

        # Skip social media / generic platforms (not org domains)
        skip_domains = {
            "facebook.com", "twitter.com", "x.com", "linkedin.com",
            "instagram.com", "youtube.com", "github.com", "medium.com",
            "wordpress.com", "blogspot.com", "tumblr.com", "google.com",
            "europa.eu",  # Generic EU portal, not org-specific
        }
        if domain in skip_domains:
            return None

        return domain.lower()

    except Exception:
        return None


# ---------------------------------------------------------------------------
# MX record checking
# ---------------------------------------------------------------------------

async def check_mx(domain: str) -> bool:
    """Check if a domain has MX records (accepts email)."""
    if domain in MX_CACHE:
        return MX_CACHE[domain]

    try:
        loop = asyncio.get_event_loop()
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5

        # Run DNS query in thread pool to avoid blocking
        answers = await loop.run_in_executor(
            None, lambda: resolver.resolve(domain, "MX")
        )
        has_mx = len(answers) > 0
        MX_CACHE[domain] = has_mx
        return has_mx

    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        MX_CACHE[domain] = False
        return False

    except Exception:
        MX_CACHE[domain] = False
        return False


# ---------------------------------------------------------------------------
# Email generation
# ---------------------------------------------------------------------------

def generate_contact_emails(domain: str) -> list[str]:
    """Generate candidate contact email addresses for a domain."""
    return [f"{prefix}@{domain}" for prefix in EMAIL_PREFIXES]


async def find_best_email(domain: str) -> tuple[str | None, str]:
    """
    Find the most likely working contact email for a domain.
    Returns (email, method) tuple.

    Strategy:
    1. Check if domain has MX records
    2. If yes, return info@domain as the most common generic address
    """
    has_mx = await check_mx(domain)
    if not has_mx:
        return None, "no_mx"

    # info@ is the most universally used generic contact address
    return f"info@{domain}", "mx_verified"


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

async def process_orgs(limit: int = 0, resume: bool = False):
    """Process all orgs from raw CSV and discover contact emails."""

    if not RAW_CSV.exists():
        logger.error(f"[ERROR] Raw CSV not found: {RAW_CSV}")
        logger.error("Run collect_lobby_orgs.py first")
        return

    # Load raw orgs
    orgs = []
    with open(RAW_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            orgs.append(row)

    logger.info(f"[OK] Loaded {len(orgs)} orgs from {RAW_CSV}")

    if limit > 0:
        orgs = orgs[:limit]
        logger.info(f"[INFO] Limiting to first {limit} orgs")

    # Load already-processed orgs if resuming
    processed_ids = set()
    if resume and OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_ids.add(row.get("identification_code", ""))
        logger.info(f"[RESUME] {len(processed_ids)} orgs already processed")

    # Process each org
    results = []
    sem = asyncio.Semaphore(CONCURRENCY)
    no_url = 0
    no_domain = 0
    no_mx = 0
    found = 0

    async def process_one(org: dict) -> dict:
        nonlocal no_url, no_domain, no_mx, found

        result = dict(org)
        result["contact_email"] = ""
        result["email_method"] = ""
        result["domain"] = ""

        url = org.get("web_site_url", "").strip()
        if not url:
            no_url += 1
            result["email_method"] = "no_url"
            return result

        domain = extract_domain(url)
        if not domain:
            no_domain += 1
            result["email_method"] = "bad_url"
            return result

        result["domain"] = domain

        async with sem:
            email, method = await find_best_email(domain)

        result["contact_email"] = email or ""
        result["email_method"] = method

        if email:
            found += 1
        else:
            no_mx += 1

        return result

    # Process in batches for progress reporting
    BATCH = 500
    for i in range(0, len(orgs), BATCH):
        batch = orgs[i : i + BATCH]

        # Skip already-processed
        batch = [o for o in batch if o.get("identification_code", "") not in processed_ids]
        if not batch:
            continue

        tasks = [process_one(org) for org in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        done = min(i + BATCH, len(orgs))
        logger.info(f"[INFO] {done}/{len(orgs)} processed | found: {found}, no_url: {no_url}, no_domain: {no_domain}, no_mx: {no_mx}")

    # Only save orgs that have a valid email
    results_with_email = [r for r in results if r.get("contact_email")]
    save_results(results_with_email, append=resume)

    # Summary
    total_processed = len(results)
    with_email = len(results_with_email)
    rate = (with_email / total_processed * 100) if total_processed > 0 else 0

    logger.info(f"\n[DONE] Email discovery complete")
    logger.info(f"  Total orgs processed: {total_processed}")
    logger.info(f"  With email (saved): {with_email} ({rate:.1f}%)")
    logger.info(f"  No URL: {no_url}")
    logger.info(f"  Bad URL: {no_domain}")
    logger.info(f"  No MX: {no_mx}")
    logger.info(f"  Output: {OUTPUT_CSV}")


def _clean_field(value: str) -> str:
    """Strip newlines, collapse whitespace, and trim text fields."""
    if not value:
        return ""
    cleaned = re.sub(r"[\r\n\t]+", " ", value)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


def save_results(results: list[dict], append: bool = False):
    """Save results with email discovery data. Only orgs with emails should be passed in."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    output_fields = [
        "identification_code", "original_name", "acronym", "web_site_url",
        "domain", "contact_email", "email_method",
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
    write_header = not append or not OUTPUT_CSV.exists()

    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for r in results:
            row = {}
            for k in output_fields:
                val = r.get(k, "")
                row[k] = _clean_field(val) if k in text_fields else val
            writer.writerow(row)

    logger.info(f"[OK] Saved to {OUTPUT_CSV}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discover contact emails for lobby orgs")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted run")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N orgs")
    args = parser.parse_args()

    await process_orgs(limit=args.limit, resume=args.resume)


if __name__ == "__main__":
    asyncio.run(main())
