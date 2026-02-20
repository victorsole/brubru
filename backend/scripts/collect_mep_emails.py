"""
Collect MEP Emails

Fetches all current (10th term) MEPs from the EP Open Data API,
retrieves their verified emails, country, and political group,
and exports to CSV.

Usage:
    # Export CSV only
    python scripts/collect_mep_emails.py

    # Export CSV and send a campaign email (BCC)
    python scripts/collect_mep_emails.py --send

    # Dry run (preview without sending)
    python scripts/collect_mep_emails.py --send --dry-run
"""

import asyncio
import csv
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

EP_API_BASE = "https://data.europarl.europa.eu/api/v2"
PARLIAMENTARY_TERM = 10  # Current term (2024-2029)
CONCURRENCY = 10  # Parallel requests to EP API


# ---------------------------------------------------------------------------
# Known political group org IDs -> readable names (10th term)
# ---------------------------------------------------------------------------
POLITICAL_GROUP_MAP = {
    # 10th parliamentary term (2024-2029)
    "org/7018": "EPP",           # ~188 seats
    "org/7038": "S&D",           # ~136 seats
    "org/7037": "ECR",           # ~78 seats
    "org/7150": "PfE",           # ~84 seats
    "org/7035": "Renew",         # ~77 seats
    "org/7028": "Greens/EFA",    # ~53 seats
    "org/7036": "The Left",      # ~46 seats
    "org/7151": "ESN",           # ~25 seats
    "org/6561": "NI",
    "org/6737": "NI",
}


def normalize_name_for_email(name: str) -> str:
    """
    Normalize a name for email fallback generation.
    Remove accents, lowercase, replace spaces with dots.
    """
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower().strip()
    normalized = normalized.replace(" ", ".")
    normalized = re.sub(r"[^a-z0-9.\-]", "", normalized)
    normalized = re.sub(r"\.{2,}", ".", normalized)
    return normalized


async def fetch_current_mep_ids() -> list[dict]:
    """Fetch list of all current MEPs (IDs and names) from EP API."""
    logger.info(f"[INFO] Fetching current term ({PARLIAMENTARY_TERM}) MEPs from EP Open Data API...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{EP_API_BASE}/meps",
            params={
                "format": "application/ld+json",
                "offset": 0,
                "limit": 800,
                "parliamentary-term": PARLIAMENTARY_TERM,
            },
        )
        resp.raise_for_status()

    data = resp.json()
    meps = data.get("data", [])
    logger.info(f"[INFO] Found {len(meps)} current MEPs")
    return meps


async def fetch_mep_detail(client: httpx.AsyncClient, mep_id: str, semaphore: asyncio.Semaphore) -> dict | None:
    """Fetch detailed info for a single MEP."""
    async with semaphore:
        try:
            await asyncio.sleep(0.1)  # Small delay to avoid rate limiting
            resp = await client.get(
                f"{EP_API_BASE}/meps/{mep_id}",
                params={"format": "application/ld+json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [None])[0]
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 403:
                logger.warning(f"[WARN] MEP {mep_id}: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.warning(f"[WARN] MEP {mep_id}: {e}")
            return None


def extract_mep_info(mep_detail: dict) -> dict:
    """Extract relevant fields from MEP detail API response."""
    # Email (can be a string or list)
    raw_email = mep_detail.get("hasEmail", "")
    if isinstance(raw_email, list):
        raw_email = raw_email[0] if raw_email else ""
    email = raw_email.replace("mailto:", "") if raw_email else ""

    # Fallback: generate from name
    if not email:
        given = mep_detail.get("givenName", "")
        family = mep_detail.get("familyName", "")
        if given and family:
            email = f"{normalize_name_for_email(given)}.{normalize_name_for_email(family)}@europarl.europa.eu"

    # Country from citizenship URI
    citizenship = mep_detail.get("citizenship", "")
    country = citizenship.split("/")[-1] if citizenship else ""

    # Current political group (membership with no endDate and EU_POLITICAL_GROUP classification)
    political_group = ""
    for m in mep_detail.get("hasMembership", []):
        cls = m.get("membershipClassification", "")
        if "EU_POLITICAL_GROUP" in cls:
            period = m.get("memberDuring", {})
            if not period.get("endDate"):
                org_id = m.get("organization", "")
                political_group = POLITICAL_GROUP_MAP.get(org_id, org_id)
                break

    # National party (current, same logic)
    national_party = ""
    for m in mep_detail.get("hasMembership", []):
        cls = m.get("membershipClassification", "")
        if "NATIONAL_POLITICAL_GROUP" in cls:
            period = m.get("memberDuring", {})
            if not period.get("endDate"):
                org_id = m.get("organization", "")
                national_party = POLITICAL_GROUP_MAP.get(org_id, org_id)
                break

    return {
        "id": mep_detail.get("identifier", ""),
        "full_name": mep_detail.get("label", ""),
        "given_name": mep_detail.get("givenName", ""),
        "family_name": mep_detail.get("familyName", ""),
        "email": email,
        "country": country,
        "political_group": political_group,
        "national_party": national_party,
        "profile_url": f"https://www.europarl.europa.eu/meps/en/{mep_detail.get('identifier', '')}",
    }


async def fetch_all_mep_details(mep_ids: list[str]) -> list[dict]:
    """Fetch details for all MEPs concurrently."""
    semaphore = asyncio.Semaphore(CONCURRENCY)
    client = httpx.AsyncClient(timeout=30.0)
    meps = []

    try:
        tasks = [fetch_mep_detail(client, mid, semaphore) for mid in mep_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception) or result is None:
                continue
            try:
                info = extract_mep_info(result)
                if info["email"]:
                    meps.append(info)
            except Exception as e:
                logger.warning(f"[WARN] Failed to parse MEP detail: {e}")

            if (i + 1) % 100 == 0 or (i + 1) == len(results):
                logger.info(f"[INFO] Processed {i + 1}/{len(results)} MEPs")
    finally:
        await client.aclose()

    return meps


def export_csv(meps: list[dict], output_path: str) -> str:
    """Export MEP list to CSV."""
    fieldnames = [
        "full_name", "email", "country", "political_group",
        "national_party", "id", "profile_url",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mep in meps:
            writer.writerow({k: mep.get(k, "") for k in fieldnames})

    return output_path


def send_bcc_campaign(
    recipients: list[str],
    subject: str,
    html_body: str,
    dry_run: bool = True,
) -> dict:
    """
    Send email to all recipients via BCC using Gmail SMTP.

    Gmail Workspace limits: ~2,000 recipients/day, ~100 per message.
    We split into batches of 90 to stay safe.
    """
    from services.email_service import get_email_service

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    svc = get_email_service()

    if not svc.is_configured:
        logger.error("[ERROR] SMTP not configured")
        return {"sent": 0, "failed": 0}

    if dry_run:
        logger.info(f"[DRY-RUN] Would send to {len(recipients)} recipients in BCC")
        logger.info(f"[DRY-RUN] Subject: {subject}")
        logger.info(f"[DRY-RUN] Batches: {(len(recipients) + 89) // 90}")
        logger.info(f"[DRY-RUN] First 10: {recipients[:10]}")
        return {"sent": 0, "failed": 0, "dry_run": True}

    BATCH_SIZE = 90
    total_sent = 0
    total_failed = 0

    for i in range(0, len(recipients), BATCH_SIZE):
        batch = recipients[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(recipients) + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"[SEND] Batch {batch_num}/{total_batches} ({len(batch)} recipients)")

        msg = MIMEMultipart("alternative")
        msg["From"] = svc._from_address()
        msg["To"] = svc.user  # Send to ourselves
        msg["Subject"] = subject
        # BCC is NOT added to headers (recipients get it via envelope)

        text_fallback = f"{subject}\n\nView this email in HTML for the full content."
        msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(svc.host, svc.port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(svc.user, svc.password)
                all_recipients = [svc.user] + batch
                server.sendmail(svc.user, all_recipients, msg.as_string())

            total_sent += len(batch)
            logger.info(f"[OK] Batch {batch_num} sent")

        except Exception as e:
            total_failed += len(batch)
            logger.error(f"[ERROR] Batch {batch_num} failed: {e}")

    logger.info(f"[DONE] Campaign: {total_sent} sent, {total_failed} failed")
    return {"sent": total_sent, "failed": total_failed}


def build_brubru_intro_email() -> dict:
    """Build an introduction email for MEPs about Brubru."""
    subject = "Brubru - Your AI-powered EU policy assistant"

    html_body = """\
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
            <tr><td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" style="margin-bottom:12px;" />
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">Your AI-powered EU policy assistant</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">Dear Member,</h1>
                            <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 20px;">
                                We are pleased to introduce <strong>Brubru</strong>, a new AI assistant designed
                                specifically for EU policy professionals. Built by <strong>Beresol</strong>, a Brussels-based
                                EU public affairs consultancy, Brubru helps you work smarter with EU legislation.
                            </p>

                            <h2 style="color:#1e293b;font-size:17px;margin:24px 0 12px;">What Brubru can do for you:</h2>
                            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#0693e3;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Answer EU policy questions</strong> &mdash; ask anything about regulations,
                                        directives, or institutional processes, with sources
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#9b51e0;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Track EU legislation</strong> &mdash; monitor legislative files, RSS feeds
                                        from 15+ EU sources, and committee work in progress
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#059669;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Draft amendments</strong> &mdash; use the Amendator to create professional
                                        legislative amendments with AI assistance
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#d97706;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Generate documents</strong> &mdash; position papers, MEP briefings,
                                        and talking points in seconds
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="https://brubru.beresol.eu"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        Try Brubru for free
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#475569;font-size:14px;line-height:1.6;margin:20px 0 0;">
                                Brubru is free to use. No credit card required.
                            </p>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                If you no longer wish to receive emails from us, simply reply to this message.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f1f5f9;padding:20px 40px;text-align:center;">
                            <p style="color:#94a3b8;font-size:12px;margin:0;">
                                Beresol &middot; EU Public Affairs &middot; Brussels &middot;
                                <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
    </body>
    </html>
    """

    return {"subject": subject, "html_body": html_body}


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Collect MEP emails and optionally send campaign")
    parser.add_argument("--output", "-o", default=None, help="CSV output path")
    parser.add_argument("--send", action="store_true", help="Send campaign email after collecting")
    parser.add_argument("--dry-run", action="store_true", help="Preview send without actually sending")
    parser.add_argument("--subject", default=None, help="Email subject (default: from template)")
    args = parser.parse_args()

    # 1. Get current MEP IDs
    mep_list = await fetch_current_mep_ids()
    mep_ids = [m["identifier"] for m in mep_list]

    if not mep_ids:
        logger.error("[ERROR] No MEPs found")
        return

    # 2. Fetch details (emails, countries, groups) concurrently
    logger.info(f"[INFO] Fetching details for {len(mep_ids)} MEPs ({CONCURRENCY} concurrent)...")
    meps = await fetch_all_mep_details(mep_ids)
    logger.info(f"[OK] Got emails for {len(meps)} MEPs")

    # 3. Export CSV
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"mep_emails_{timestamp}.csv",
        )

    export_csv(meps, output_path)
    logger.info(f"[OK] Exported to {output_path}")

    # Summary
    countries = {}
    for m in meps:
        c = m["country"] or "Unknown"
        countries[c] = countries.get(c, 0) + 1
    logger.info(f"[INFO] {len(countries)} countries represented")

    groups = {}
    for m in meps:
        g = m["political_group"] or "NI"
        groups[g] = groups.get(g, 0) + 1
    logger.info("[INFO] Political groups:")
    for g, count in sorted(groups.items(), key=lambda x: -x[1]):
        logger.info(f"  {g}: {count}")

    # 4. Optionally send campaign
    if args.send:
        emails = [m["email"] for m in meps if m["email"]]
        email_data = build_brubru_intro_email()
        subject = args.subject or email_data["subject"]

        result = send_bcc_campaign(
            recipients=emails,
            subject=subject,
            html_body=email_data["html_body"],
            dry_run=args.dry_run,
        )
        logger.info(f"[RESULT] {result}")


if __name__ == "__main__":
    asyncio.run(main())
