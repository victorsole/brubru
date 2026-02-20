"""
Collect EU Institution Emails - All Who is Who Institutions

Parses EU Who is Who PDFs for all remaining institutions.
For PDFs with emails: extracts directly.
For PDFs without emails: extracts names and generates using pattern.

Usage:
    # Export all CSVs
    python scripts/collect_all_institutions.py

    # Send campaign to a specific institution
    python scripts/collect_all_institutions.py --send --institution eeas

    # Send campaign to all institutions
    python scripts/collect_all_institutions.py --send --institution all

    # Dry run
    python scripts/collect_all_institutions.py --send --institution eeas --dry-run
"""

import csv
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EMAIL_DIR = os.path.join(PROJECT_ROOT, "data", "emails")

# Institution configs: code, full name, email domain, extraction method
INSTITUTIONS = {
    "eeas": {
        "name": "European External Action Service",
        "domain": "eeas.europa.eu",
        "method": "emails_from_pdf",
    },
    "edps": {
        "name": "European Data Protection Supervisor",
        "domain": "edps.europa.eu",
        "method": "emails_from_pdf",
    },
    "agencies": {
        "name": "EU Agencies and Other Bodies",
        "code": "AGEN_OTH",
        "domain": None,  # multiple domains
        "method": "emails_from_pdf",
    },
    "curia": {
        "name": "Court of Justice of the EU",
        "domain": "curia.europa.eu",
        "method": "names_to_emails",
    },
    "ecb": {
        "name": "European Central Bank",
        "domain": "ecb.europa.eu",
        "method": "names_to_emails",
    },
    "eca": {
        "name": "European Court of Auditors",
        "domain": "eca.europa.eu",
        "method": "names_to_emails",
    },
    "eib": {
        "name": "European Investment Bank",
        "domain": "eib.org",
        "method": "names_to_emails",
    },
    "omb": {
        "name": "European Ombudsman",
        "domain": "ombudsman.europa.eu",
        "method": "names_to_emails",
    },
    "eesc": {
        "name": "European Economic and Social Committee",
        "domain": "eesc.europa.eu",
        "method": "emails_from_pdf",
    },
    "cor": {
        "name": "European Committee of the Regions",
        "domain": "cor.europa.eu",
        "method": "emails_from_pdf",
    },
}

# Skip list for generic/functional emails
SKIP_EMAILS = {
    "eca-info@eca.europa.eu",
    "info@eif.org",
    "int@eesc.europa.eu",
}

# Skip patterns (functional mailboxes, not people)
SKIP_PATTERNS = [
    r"^info@",
    r"^press@",
    r"^contact@",
    r"^communication@",
    r"^secretariat@",
    r"^int@",
    r"^hr@",
    r"^recruitment@",
    r"^webmaster@",
]


def normalize_for_email(name: str) -> str:
    """Normalize name for email generation."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower().strip()
    # Replace spaces with dots for email
    normalized = normalized.replace(" ", ".")
    normalized = re.sub(r"[^a-z0-9.\-]", "", normalized)
    normalized = re.sub(r"\.{2,}", ".", normalized)
    return normalized


def download_pdf(code: str) -> str:
    """Download a Who is Who PDF."""
    import httpx

    pdf_path = f"/tmp/EUWhoiswho_{code}_EN.pdf"

    if os.path.exists(pdf_path):
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        if size_mb > 0.1:
            return pdf_path

    url = f"https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_{code}_EN.pdf"
    logger.info(f"[INFO] Downloading {code} PDF...")
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(resp.content)

    return pdf_path


def is_functional_email(email: str) -> bool:
    """Check if an email is a functional mailbox (not a person)."""
    if email in SKIP_EMAILS:
        return True
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, email):
            return True
    return False


def extract_emails_from_pdf(pdf_path: str, domain: str | None) -> list[dict]:
    """Extract emails directly from PDF, optionally filtering by domain."""
    import fitz

    doc = fitz.open(pdf_path)
    emails = set()

    for page in doc:
        text = page.get_text()
        found = re.findall(r"[\w.\-]+@[\w.\-]+\.\w+", text, re.IGNORECASE)
        for e in found:
            e_lower = e.lower()
            if "publications.europa.eu" in e_lower or "whoiswho" in e_lower:
                continue
            if is_functional_email(e_lower):
                continue
            if domain:
                if domain in e_lower:
                    emails.add(e_lower)
            else:
                # For agencies, accept any .europa.eu or known agency domains
                if ".europa.eu" in e_lower or ".eu" in e_lower:
                    emails.add(e_lower)

    doc.close()

    staff = []
    for email in sorted(emails):
        local_part = email.split("@")[0]
        parts = local_part.replace("-", ".").split(".")
        if len(parts) >= 2:
            given = parts[0].title()
            family = " ".join(p.title() for p in parts[1:])
            full_name = f"{given} {family}"
        else:
            full_name = local_part.title()

        staff.append({
            "full_name": full_name,
            "email": email,
        })

    return staff


def extract_names_generate_emails(pdf_path: str, domain: str) -> list[dict]:
    """Extract names from PDF and generate emails using domain pattern."""
    import fitz

    doc = fitz.open(pdf_path)

    name_pattern = re.compile(
        r"(?:Mr|Ms)\s+([\w\-\'\u00C0-\u024F]+(?:\s+[\w\-\'\u00C0-\u024F]+)*?)"
        r"\s+((?:[A-Z\u00C0-\u024F][A-Z\u00C0-\u024F\-\' ]+)+)"
    )

    staff = []
    seen = set()

    # Skip initial pages (cover, maps, building codes)
    start_page = 0
    for page_num in range(min(15, len(doc))):
        page = doc[page_num]
        text = page.get_text()
        if name_pattern.search(text):
            start_page = page_num
            break

    for page_num in range(start_page, len(doc)):
        page = doc[page_num]
        text = page.get_text()

        for line in text.split("\n"):
            m = name_pattern.match(line.strip())
            if m:
                given = m.group(1).strip()
                family = m.group(2).strip()

                key = f"{given}|{family}"
                if key in seen:
                    continue
                seen.add(key)

                given_norm = normalize_for_email(given)
                family_norm = normalize_for_email(family)
                email = f"{given_norm}.{family_norm}@{domain}"
                email = re.sub(r"\.{2,}", ".", email)

                full_name = f"{given} {family.title()}"

                staff.append({
                    "full_name": full_name,
                    "email": email,
                })

    doc.close()
    return staff


def export_csv(staff: list[dict], institution_key: str) -> str:
    """Export staff list to CSV in data/emails/."""
    os.makedirs(EMAIL_DIR, exist_ok=True)
    csv_path = os.path.join(EMAIL_DIR, f"{institution_key}_emails.csv")

    config = INSTITUTIONS[institution_key]
    fieldnames = ["full_name", "email", "institution", "department"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for person in staff:
            writer.writerow({
                "full_name": person.get("full_name", ""),
                "email": person.get("email", ""),
                "institution": config["name"],
                "department": person.get("department", ""),
            })

    return csv_path


def send_bcc_campaign(
    recipients: list[str],
    subject: str,
    html_body: str,
    dry_run: bool = True,
) -> dict:
    """Send email to all recipients via BCC."""
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
        logger.info(f"[DRY-RUN] Batches: {(len(recipients) + 89) // 90}")
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
        msg["To"] = svc.user
        msg["Subject"] = subject

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
    """Build an introduction email about Brubru."""
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
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" style="margin-bottom:12px;" />
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">Your AI-powered EU policy assistant</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">Dear Colleague,</h1>
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


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect emails from all EU Who is Who institutions"
    )
    parser.add_argument(
        "--institution", "-i",
        default="all",
        help="Institution key or 'all' (default: all)",
    )
    parser.add_argument("--send", action="store_true", help="Send campaign email")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    args = parser.parse_args()

    if args.institution == "all":
        keys = list(INSTITUTIONS.keys())
    else:
        keys = [args.institution]

    grand_total = 0

    for key in keys:
        config = INSTITUTIONS[key]
        code = config.get("code", key.upper())

        logger.info(f"\n{'='*60}")
        logger.info(f"{config['name']} ({code})")
        logger.info(f"{'='*60}")

        pdf_path = download_pdf(code)

        if config["method"] == "emails_from_pdf":
            staff = extract_emails_from_pdf(pdf_path, config["domain"])
        else:
            staff = extract_names_generate_emails(pdf_path, config["domain"])

        if not staff:
            logger.warning(f"[WARN] No staff found for {key}")
            continue

        csv_path = export_csv(staff, key)
        logger.info(f"[OK] {len(staff)} entries -> {csv_path}")
        grand_total += len(staff)

        if args.send:
            emails = [s["email"] for s in staff]
            email_data = build_brubru_intro_email()
            result = send_bcc_campaign(
                recipients=emails,
                subject=email_data["subject"],
                html_body=email_data["html_body"],
                dry_run=args.dry_run,
            )
            logger.info(f"[RESULT] {result}")

    logger.info(f"\n{'='*60}")
    logger.info(f"GRAND TOTAL: {grand_total} emails across {len(keys)} institutions")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
