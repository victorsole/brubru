"""
Scrape contact emails for EU Transparency Register orgs that lack one.

Two-tier:
  Tier A — orgs with website: extract homepage + common contact paths, regex-match
           emails (prefer info@/contacto@/hola@ on the org's own domain). Decodes
           Cloudflare email-protection obfuscation.

  Tier B — orgs without website: Tavily search "{org_name} contacto correo electrónico"
           and extract from the top result.

Writes back to transparency_register_orgs.contact_email (only when empty).

Usage:
    python3.12 scripts/scrape_eutr_emails.py --country spain --limit 50 --dry-run
    python3.12 scripts/scrape_eutr_emails.py --country spain --limit 50          # write to DB
"""
import argparse
import logging
import os
import re
import sys
import time
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
CF_EMAIL_PROTECT_RE = re.compile(r"/cdn-cgi/l/email-protection#([a-fA-F0-9]+)")
CF_DATA_CFEMAIL_RE = re.compile(r'data-cfemail="([a-fA-F0-9]+)"')

PREFERRED_LOCALPART = ("contacto", "info", "hola", "secretaria", "comunicacion", "comunicación", "press", "prensa")
EXCLUDE_LOCALPART = ("noreply", "no-reply", "donotreply", "no-responder")

CONTACT_PATHS = ("", "/contacto", "/contact", "/contact-us", "/es/contacto", "/sobre-nosotros", "/quienes-somos", "/aviso-legal", "/about")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36"


def _decode_cf_email(hex_str: str) -> Optional[str]:
    """Decode Cloudflare email-protection obfuscation."""
    try:
        data = bytes.fromhex(hex_str)
        if len(data) < 2:
            return None
        key = data[0]
        return "".join(chr(b ^ key) for b in data[1:])
    except (ValueError, UnicodeDecodeError):
        return None


def _extract_emails_from_html(html: str, target_domain: Optional[str] = None) -> List[str]:
    """Extract candidate emails from HTML text. Decodes CF obfuscation. Filters by target_domain when given."""
    emails: Set[str] = set()
    # 1. Plain regex on raw text
    for m in EMAIL_RE.finditer(html):
        emails.add(m.group(0).lower())
    # 2. Cloudflare email-protection
    for m in CF_EMAIL_PROTECT_RE.finditer(html):
        decoded = _decode_cf_email(m.group(1))
        if decoded and EMAIL_RE.fullmatch(decoded):
            emails.add(decoded.lower())
    for m in CF_DATA_CFEMAIL_RE.finditer(html):
        decoded = _decode_cf_email(m.group(1))
        if decoded and EMAIL_RE.fullmatch(decoded):
            emails.add(decoded.lower())
    # 3. Filter
    out = []
    for e in emails:
        local = e.split("@", 1)[0]
        if any(local.startswith(x) for x in EXCLUDE_LOCALPART):
            continue
        if target_domain and not e.endswith(target_domain):
            continue
        out.append(e)
    return out


def _rank_email(email: str) -> int:
    """Lower rank = better. Prefer contacto@, info@, hola@, etc."""
    local = email.split("@", 1)[0]
    for i, p in enumerate(PREFERRED_LOCALPART):
        if local.startswith(p):
            return i
    return 100  # other


def _fetch(url: str, timeout: int = 8) -> Optional[str]:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es,en"}, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:  # noqa: BLE001
        return None
    return None


def _normalise_url(raw: str) -> Optional[str]:
    """Normalise a website value: prepend scheme if missing, lower-case host."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def _domain_of(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return parsed.netloc.lower().lstrip("www.")


def tier_a_scrape(name: str, website: str) -> Optional[Tuple[str, str]]:
    """Try to extract an email from the org's own website. Returns (email, source_url) or None."""
    base = _normalise_url(website)
    if not base:
        return None
    domain = _domain_of(base)
    candidates: Set[str] = set()
    for path in CONTACT_PATHS:
        url = base + path
        html = _fetch(url)
        if not html:
            continue
        emails = _extract_emails_from_html(html, target_domain=domain)
        if emails:
            candidates.update(emails)
            # We can stop after finding any email — but keep scanning for a "preferred" one
            # if the first hit is a personal email
            if any(_rank_email(e) < 100 for e in emails):
                break
    if not candidates:
        return None
    best = sorted(candidates, key=_rank_email)[0]
    return best, base


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape EUTR contact emails")
    parser.add_argument("--country", default="spain", help="Country filter (default: spain)")
    parser.add_argument("--limit", type=int, default=50, help="Max orgs to process")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument("--clusters", default="trade,climate,energy,agriculture,finance,research,digital,social",
                        help="Comma-separated policy clusters to include")
    args = parser.parse_args()

    clusters = tuple(c.strip() for c in args.clusters.split(",") if c.strip())

    db = SessionLocal()
    try:
        rows = db.execute(text(f"""
            SELECT id, name, website, policy_cluster
            FROM transparency_register_orgs
            WHERE (country ILIKE :country OR country = 'ES')
              AND (contact_email IS NULL OR contact_email = '')
              AND website IS NOT NULL AND website != ''
              AND policy_cluster IN :clusters
            ORDER BY calculated_cost DESC NULLS LAST
            LIMIT :limit
        """).bindparams(country=args.country, clusters=clusters, limit=args.limit)).fetchall()

        print(f"[INFO] Processing {len(rows)} orgs (Tier A — has website)")
        found = 0
        not_found = 0
        for i, row in enumerate(rows, 1):
            org_id, org_name, website, cluster = row
            try:
                result = tier_a_scrape(org_name, website)
            except Exception as e:  # noqa: BLE001
                print(f"  [{i:3d}/{len(rows)}] [{cluster:12s}] ERR     {org_name[:50]:<50s} | {e}")
                continue

            if result:
                email, source = result
                found += 1
                print(f"  [{i:3d}/{len(rows)}] [{cluster:12s}] FOUND   {org_name[:50]:<50s} | {email}")
                if not args.dry_run:
                    db.execute(
                        text("UPDATE transparency_register_orgs SET contact_email = :e WHERE id = :id"),
                        {"e": email, "id": org_id},
                    )
            else:
                not_found += 1
                print(f"  [{i:3d}/{len(rows)}] [{cluster:12s}] miss    {org_name[:50]:<50s} | {website}")
            time.sleep(0.3)  # politeness

        if not args.dry_run:
            db.commit()
        print(f"\n[OK] Found {found}/{len(rows)} ({100*found//max(len(rows),1)}% yield). Not found: {not_found}.")
        if args.dry_run:
            print("[DRY RUN] No DB writes.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
