"""
Collect EU Institution Emails - Commission & Council

Parses the EU Who is Who PDFs to extract staff emails.
- Commission: emails directly from PDF (@ec.europa.eu)
- Council: names from PDF, emails generated as firstname.lastname@consilium.europa.eu

Usage:
    # Download PDFs and export CSVs
    python scripts/collect_institution_emails.py

    # Send campaign to Commission staff
    python scripts/collect_institution_emails.py --send --institution com

    # Send campaign to Council staff
    python scripts/collect_institution_emails.py --send --institution consil

    # Dry run
    python scripts/collect_institution_emails.py --send --institution com --dry-run
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

PDF_URLS = {
    "com": "https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_COM_EN.pdf",
    "consil": "https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_CONSIL_EN.pdf",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def normalize_for_email(name: str) -> str:
    """Normalize name for email: remove accents, lowercase, replace spaces with dots."""
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower().strip()
    normalized = normalized.replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9.\-]", "", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def download_pdf(institution: str) -> str:
    """Download a Who is Who PDF if not already cached."""
    import httpx

    pdf_path = os.path.join("/tmp", f"EUWhoiswho_{institution.upper()}_EN.pdf")

    if os.path.exists(pdf_path):
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        if size_mb > 0.5:
            logger.info(f"[INFO] Using cached PDF: {pdf_path} ({size_mb:.1f} MB)")
            return pdf_path

    url = PDF_URLS[institution]
    logger.info(f"[INFO] Downloading {url}...")
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        with open(pdf_path, "wb") as f:
            f.write(resp.content)

    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    logger.info(f"[OK] Downloaded {pdf_path} ({size_mb:.1f} MB)")
    return pdf_path


def extract_commission_emails(pdf_path: str) -> list[dict]:
    """Extract emails and associated names/DGs from Commission PDF."""
    import fitz

    doc = fitz.open(pdf_path)
    logger.info(f"[INFO] Parsing Commission PDF ({len(doc)} pages)...")

    # First pass: collect all emails
    all_emails = set()
    for page in doc:
        text = page.get_text()
        emails = re.findall(r"[\w.\-]+@ec\.europa\.eu", text, re.IGNORECASE)
        all_emails.update(e.lower() for e in emails)

    # Second pass: extract names + emails + DG context per page
    staff = []
    seen_emails = set()
    current_dg = ""

    name_pattern = re.compile(
        r"(?:Mr|Ms)\s+([\w\-\' ]+?)\s+((?:[A-Z][A-Z\-\' ]+)+)"
    )

    for page_num in range(17, len(doc)):  # Skip cover/maps (first 17 pages)
        page = doc[page_num]
        text = page.get_text()
        lines = text.split("\n")

        # Detect current DG from page headers
        for line in lines:
            line_s = line.strip()
            if line_s.startswith("DG ") and "—" in line_s:
                current_dg = line_s.split("—")[0].strip()
            elif line_s.startswith("SG —") or line_s.startswith("SJ —"):
                current_dg = line_s.split("—")[0].strip()
            elif line_s.startswith("OLAF —"):
                current_dg = "OLAF"

        # Find emails on this page
        page_emails = re.findall(
            r"[\w.\-]+@ec\.europa\.eu", text, re.IGNORECASE
        )

        for email in page_emails:
            email_lower = email.lower()
            if email_lower in seen_emails:
                continue
            seen_emails.add(email_lower)

            # Try to extract a name from the email
            local_part = email_lower.split("@")[0]
            # Typical patterns: firstname.lastname, firstname.LASTNAME
            parts = local_part.replace("-", ".").split(".")
            if len(parts) >= 2:
                given = parts[0].title()
                family = ".".join(parts[1:]).title()
                full_name = f"{given} {family}"
            else:
                full_name = local_part.title()

            staff.append({
                "full_name": full_name,
                "email": email_lower,
                "institution": "European Commission",
                "department": current_dg,
                "position": "",
            })

    doc.close()
    logger.info(f"[OK] Extracted {len(staff)} Commission emails")
    return staff


def extract_council_staff(pdf_path: str) -> list[dict]:
    """Extract staff names from Council General Secretariat and generate emails."""
    import fitz

    doc = fitz.open(pdf_path)
    logger.info(f"[INFO] Parsing Council PDF ({len(doc)} pages)...")

    # Find the General Secretariat section start (actual content, not ToC)
    # Look for the page with the address, not just the title mention
    gs_start_page = None
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if "General Secretariat of the Council" in text and "consilium.europa.eu" in text:
            gs_start_page = page_num
            break

    if gs_start_page is None:
        logger.error("[ERROR] Could not find General Secretariat section")
        doc.close()
        return []

    logger.info(f"[INFO] General Secretariat starts at page {gs_start_page + 1}")

    staff = []
    seen_names = set()
    current_dg = ""

    name_pattern = re.compile(
        r"(?:Mr|Ms)\s+([\w\-\'\u00C0-\u024F]+(?:\s+[\w\-\'\u00C0-\u024F]+)*?)"
        r"\s+((?:[A-Z\u00C0-\u024F][A-Z\u00C0-\u024F\-\' ]+)+)"
    )

    for page_num in range(gs_start_page, len(doc)):
        page = doc[page_num]
        text = page.get_text()
        lines = text.split("\n")

        for line in lines:
            line_s = line.strip()

            # Detect DG context
            if line_s.startswith("DG ") and "—" in line_s:
                current_dg = line_s.split("—")[0].strip()

            m = name_pattern.match(line_s)
            if m:
                given_name = m.group(1).strip()
                family_name = m.group(2).strip()

                # Normalize family name: "VAN DEN HEUVEL" -> "Van Den Heuvel"
                name_key = f"{given_name}|{family_name}"
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                # Generate email
                given_norm = normalize_for_email(given_name)
                family_norm = normalize_for_email(family_name)
                email = f"{given_norm}.{family_norm}@consilium.europa.eu"

                # Clean up double dots or leading/trailing dots
                email = re.sub(r"\.{2,}", ".", email)
                email = email.replace(".-", "-").replace("-.", ".")

                full_name = f"{given_name} {family_name.title()}"

                staff.append({
                    "full_name": full_name,
                    "email": email,
                    "institution": "Council of the EU",
                    "department": current_dg,
                    "position": "",
                })

    doc.close()
    logger.info(f"[OK] Extracted {len(staff)} Council staff")
    return staff


def export_csv(staff: list[dict], output_path: str) -> str:
    """Export staff list to CSV."""
    fieldnames = ["full_name", "email", "institution", "department", "position"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for person in staff:
            writer.writerow({k: person.get(k, "") for k in fieldnames})

    return output_path


def send_bcc_campaign(
    recipients: list[str],
    subject: str,
    html_body: str,
    dry_run: bool = True,
) -> dict:
    """Send email to all recipients via BCC using Gmail SMTP."""
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


def _build_institution_email(
    subject: str,
    subtitle: str,
    greeting: str,
    intro: str,
    section_heading: str,
    features: list[tuple[str, str]],
    cta_text: str = "Try Brubru for free",
    free_notice: str = "Brubru is free to use. No credit card required.",
    unsubscribe: str = "If you no longer wish to receive emails from us, simply reply to this message.",
) -> dict:
    """Build an HTML email from components. Returns {subject, html_body}."""
    colors = ["#0693e3", "#9b51e0", "#059669", "#d97706"]
    features_html = ""
    for i, (_, feat_text) in enumerate(features):
        color = colors[i % len(colors)]
        features_html += f"""
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:{color};font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        {feat_text}
                                    </td>
                                </tr>"""

    html_body = f"""\
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
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">{subtitle}</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">{greeting}</h1>
                            <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 20px;">
                                {intro}
                            </p>

                            <h2 style="color:#1e293b;font-size:17px;margin:24px 0 12px;">{section_heading}</h2>
                            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                {features_html}
                            </table>

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="https://brubru.beresol.eu"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        {cta_text}
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#475569;font-size:14px;line-height:1.6;margin:20px 0 0;">
                                {free_notice}
                            </p>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                {unsubscribe}
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
    </html>"""

    return {"subject": subject, "html_body": html_body}


# ---------------------------------------------------------------------------
# Institution-specific email templates
# ---------------------------------------------------------------------------

INSTITUTION_EMAILS = {
    "eeas": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU external action professionals",
        subtitle="AI-powered tools for EU foreign policy and diplomacy",
        greeting="Dear Colleague,",
        intro=(
            "Working on EU external action means navigating an ever-growing body of "
            "sanctions regimes, trade agreements, enlargement frameworks, and CFSP/CSDP decisions. "
            "<strong>Brubru</strong> is a free AI assistant built specifically for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It can help you find answers faster and stay on top of legislative developments "
            "that shape the EU's role in the world."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Instant policy answers</strong> &mdash; ask about sanctions frameworks, "
                "trade agreements like EU-Mercosur, enlargement criteria, or CFSP legal bases, "
                "and get sourced answers in seconds"
            )),
            ("purple", (
                "<strong>Track legislative developments</strong> &mdash; monitor AFET, SEDE, INTA, "
                "and DEVE committee work in progress, plus RSS feeds from 15+ EU sources including "
                "the Council and EEAS newsroom"
            )),
            ("green", (
                "<strong>Generate briefing documents</strong> &mdash; produce talking points, "
                "country briefings, and position papers on foreign policy topics in seconds"
            )),
            ("gold", (
                "<strong>Cross-reference EU law</strong> &mdash; search across regulations, "
                "directives, and Council decisions to find the legal basis you need"
            )),
        ],
    ),
    "agencies": lambda: _build_institution_email(
        subject="Brubru - AI assistant for EU agency professionals",
        subtitle="AI-powered tools for EU regulatory and policy work",
        greeting="Dear Colleague,",
        intro=(
            "EU agencies play a critical role in implementing and monitoring EU legislation, "
            "from pharmaceutical regulation to cybersecurity, from food safety to intellectual property. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It helps you quickly navigate the legislative landscape that shapes your agency's mandate."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Understand the legislative context</strong> &mdash; ask about the regulations, "
                "directives, and delegated acts relevant to your agency's work, with cited sources from "
                "EUR-Lex and EP documents"
            )),
            ("purple", (
                "<strong>Track legislative files in progress</strong> &mdash; monitor EP committee work, "
                "Council positions, and trilogue developments on files that affect your agency's remit"
            )),
            ("green", (
                "<strong>Draft and review amendments</strong> &mdash; use the Amendator to analyse "
                "proposed amendments to legislation your agency helps implement"
            )),
            ("gold", (
                "<strong>Generate policy documents</strong> &mdash; produce briefings, summaries, and "
                "talking points on regulatory topics in seconds"
            )),
        ],
    ),
    "eib": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU investment and development professionals",
        subtitle="AI-powered tools for EU investment policy",
        greeting="Dear Colleague,",
        intro=(
            "The EIB Group operates at the intersection of EU policy and finance, "
            "where understanding the latest legislative frameworks is essential &mdash; "
            "from the Green Deal Investment Plan and REPowerEU to CBAM, InvestEU, and cohesion policy. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It helps you stay ahead of the legislation that shapes EU investment priorities."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Navigate EU investment legislation</strong> &mdash; ask about InvestEU, "
                "cohesion policy frameworks, REPowerEU, CBAM, or the Green Bond Standard, "
                "and get sourced answers in seconds"
            )),
            ("purple", (
                "<strong>Track legislative developments</strong> &mdash; monitor BUDG, ECON, ITRE, "
                "and REGI committee work in progress, plus RSS feeds from 15+ EU sources"
            )),
            ("green", (
                "<strong>Generate policy briefings</strong> &mdash; produce talking points, "
                "position papers, and investment policy summaries in seconds"
            )),
            ("gold", (
                "<strong>Cross-reference the regulatory framework</strong> &mdash; search across "
                "EU regulations, directives, and delegated acts to understand the legal context "
                "behind EIB lending priorities"
            )),
        ],
    ),
    "ecb": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU financial policy professionals",
        subtitle="AI-powered tools for EU financial regulation",
        greeting="Dear Colleague,",
        intro=(
            "Monetary policy and financial regulation are increasingly shaped by EU legislation &mdash; "
            "from MiCA and the digital euro framework to PSD3, the AML package, and Banking Union reforms. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It helps you quickly navigate the legislative landscape that underpins the ECB's supervisory "
            "and policy work."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Instant answers on financial regulation</strong> &mdash; ask about MiCA, PSD3, "
                "the AML package, Basel implementation, Solvency II review, or Capital Markets Union, "
                "and get sourced answers from EUR-Lex and EP documents"
            )),
            ("purple", (
                "<strong>Track ECON and FISC committee work</strong> &mdash; monitor legislative files "
                "in progress, Council positions, and trilogue developments on financial regulation"
            )),
            ("green", (
                "<strong>Analyse proposed amendments</strong> &mdash; use the Amendator to review "
                "amendments to financial legislation and understand their policy implications"
            )),
            ("gold", (
                "<strong>Generate briefings and summaries</strong> &mdash; produce talking points "
                "and policy papers on EU financial regulation topics in seconds"
            )),
        ],
    ),
    "eca": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU audit and accountability professionals",
        subtitle="AI-powered tools for EU budget and audit work",
        greeting="Dear Colleague,",
        intro=(
            "Auditing EU spending requires a deep understanding of the legislative frameworks "
            "that govern how funds are allocated and spent &mdash; from the MFF and Recovery and "
            "Resilience Facility to CAP spending rules, cohesion policy, and the EU's financial regulation. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It can help you quickly navigate the regulatory context behind the programmes you audit."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Navigate EU financial legislation</strong> &mdash; ask about the Financial Regulation, "
                "MFF frameworks, RRF conditionality, CAP spending rules, or cohesion policy requirements, "
                "with sourced answers from EUR-Lex"
            )),
            ("purple", (
                "<strong>Track BUDG and CONT committee work</strong> &mdash; monitor EP budgetary control "
                "activities, legislative amendments to spending programmes, and Council positions"
            )),
            ("green", (
                "<strong>Cross-reference legal bases</strong> &mdash; search across regulations, "
                "directives, and delegated acts to understand the compliance framework for EU programmes"
            )),
            ("gold", (
                "<strong>Generate briefings and summaries</strong> &mdash; produce policy papers "
                "and talking points on EU budget and accountability topics in seconds"
            )),
        ],
    ),
    "eesc": lambda: _build_institution_email(
        subject="Brubru - AI tools for EESC policy professionals",
        subtitle="AI-powered tools for EU economic and social policy",
        greeting="Dear Colleague,",
        intro=(
            "The EESC's opinions shape EU legislation by bringing the voice of organised civil society, "
            "employers, and workers into the legislative process. Staying on top of the proposals you need "
            "to examine &mdash; across employment, the single market, climate, digital, and beyond &mdash; "
            "is a growing challenge. <strong>Brubru</strong> is a free AI assistant built for EU policy "
            "professionals by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It helps you prepare faster and dig deeper into the files that matter."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Understand legislative proposals</strong> &mdash; ask about any regulation, "
                "directive, or Commission proposal under examination, and get sourced answers "
                "from EUR-Lex and EP documents"
            )),
            ("purple", (
                "<strong>Track EP committee work</strong> &mdash; monitor how Parliament is handling "
                "the same files the EESC is examining, including amendments and rapporteur positions"
            )),
            ("green", (
                "<strong>Draft and analyse amendments</strong> &mdash; use the Amendator to review "
                "proposed changes to legislation and understand their impact on employers, workers, "
                "and civil society"
            )),
            ("gold", (
                "<strong>Generate opinion briefings</strong> &mdash; produce background papers, "
                "talking points, and policy summaries to support opinion drafting"
            )),
        ],
    ),
    "omb": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU transparency and governance professionals",
        subtitle="AI-powered tools for EU good governance",
        greeting="Dear Colleague,",
        intro=(
            "The Ombudsman's work on transparency, access to documents, and good administration "
            "requires navigating a complex web of EU regulations and institutional practices. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It can help you quickly find the legislative provisions and institutional rules "
            "relevant to your investigations."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Navigate EU institutional rules</strong> &mdash; ask about access to documents "
                "regulations, the EU Staff Regulations, the Code of Good Administrative Behaviour, "
                "or transparency frameworks, with sourced answers"
            )),
            ("purple", (
                "<strong>Track governance-related legislation</strong> &mdash; monitor AFCO and LIBE "
                "committee work on transparency, rule of law, and institutional reform files"
            )),
            ("green", (
                "<strong>Cross-reference legal frameworks</strong> &mdash; search across Treaty provisions, "
                "regulations, and inter-institutional agreements relevant to good administration"
            )),
            ("gold", (
                "<strong>Generate briefings</strong> &mdash; produce summaries and talking points "
                "on governance and transparency topics in seconds"
            )),
        ],
    ),
    "cor": lambda: _build_institution_email(
        subject="Brubru - AI tools for EU regional policy professionals",
        subtitle="AI-powered tools for EU cohesion and regional policy",
        greeting="Dear Colleague,",
        intro=(
            "The Committee of the Regions ensures that regional and local perspectives are heard "
            "in the EU legislative process &mdash; on cohesion policy, structural funds, "
            "the just transition, urban development, and cross-border cooperation. "
            "<strong>Brubru</strong> is a free AI assistant built for EU policy professionals "
            "by <strong>Beresol</strong>, a Brussels-based public affairs consultancy. "
            "It helps you stay on top of the legislative files that affect Europe's regions and cities."
        ),
        section_heading="How Brubru can support your work:",
        features=[
            ("blue", (
                "<strong>Understand regional policy legislation</strong> &mdash; ask about cohesion policy "
                "frameworks, ERDF, ESF+, the Just Transition Fund, or Interreg programmes, "
                "with sourced answers from EUR-Lex"
            )),
            ("purple", (
                "<strong>Track REGI committee work</strong> &mdash; monitor EP regional development "
                "committee activities, plus RSS feeds from 15+ EU sources on cohesion and structural funds"
            )),
            ("green", (
                "<strong>Analyse legislative proposals</strong> &mdash; use the Amendator to review "
                "amendments to cohesion and regional policy files and their impact on local authorities"
            )),
            ("gold", (
                "<strong>Generate opinion briefings</strong> &mdash; produce policy papers, talking points, "
                "and summaries to support CoR opinion drafting in seconds"
            )),
        ],
    ),
}


def build_brubru_intro_email(institution: str = "generic") -> dict:
    """Build an introduction email, tailored to the institution if available."""
    if institution in INSTITUTION_EMAILS:
        return INSTITUTION_EMAILS[institution]()

    # Fallback generic email (used for COM, CONSIL, and others)
    return _build_institution_email(
        subject="Brubru - Your AI-powered EU policy assistant",
        subtitle="Your AI-powered EU policy assistant",
        greeting="Dear Colleague,",
        intro=(
            "We are pleased to introduce <strong>Brubru</strong>, a new AI assistant designed "
            "specifically for EU policy professionals. Built by <strong>Beresol</strong>, a Brussels-based "
            "EU public affairs consultancy, Brubru helps you work smarter with EU legislation."
        ),
        section_heading="What Brubru can do for you:",
        features=[
            ("blue", (
                "<strong>Answer EU policy questions</strong> &mdash; ask anything about regulations, "
                "directives, or institutional processes, with sources"
            )),
            ("purple", (
                "<strong>Track EU legislation</strong> &mdash; monitor legislative files, RSS feeds "
                "from 15+ EU sources, and committee work in progress"
            )),
            ("green", (
                "<strong>Draft amendments</strong> &mdash; use the Amendator to create professional "
                "legislative amendments with AI assistance"
            )),
            ("gold", (
                "<strong>Generate documents</strong> &mdash; position papers, MEP briefings, "
                "and talking points in seconds"
            )),
        ],
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect EU institution emails from Who is Who PDFs"
    )
    parser.add_argument(
        "--institution", "-i",
        choices=["com", "consil", "eeas", "agencies", "eib", "ecb", "both"],
        default="both",
        help="Institution to process (default: both = com+consil)",
    )
    parser.add_argument("--send", action="store_true", help="Send campaign email")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d")
    institutions = (
        ["com", "consil"] if args.institution == "both" else [args.institution]
    )

    for inst in institutions:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {inst.upper()}")
        logger.info(f"{'='*60}")

        # Download PDF
        pdf_path = download_pdf(inst)

        # Extract data
        if inst == "com":
            staff = extract_commission_emails(pdf_path)
        else:
            staff = extract_council_staff(pdf_path)

        if not staff:
            logger.warning(f"[WARN] No staff found for {inst}")
            continue

        # Export CSV
        csv_path = os.path.join(SCRIPT_DIR, f"{inst}_emails_{timestamp}.csv")
        export_csv(staff, csv_path)
        logger.info(f"[OK] Exported {len(staff)} entries to {csv_path}")

        # Summary
        depts = {}
        for s in staff:
            d = s["department"] or "Unknown"
            depts[d] = depts.get(d, 0) + 1
        logger.info(f"[INFO] Departments:")
        for d, count in sorted(depts.items(), key=lambda x: -x[1]):
            logger.info(f"  {d}: {count}")

        # Send campaign
        if args.send:
            emails = [s["email"] for s in staff if s["email"]]
            email_data = build_brubru_intro_email(inst)
            result = send_bcc_campaign(
                recipients=emails,
                subject=email_data["subject"],
                html_body=email_data["html_body"],
                dry_run=args.dry_run,
            )
            logger.info(f"[RESULT] {result}")


def send_from_csv(institution: str, dry_run: bool = True):
    """Send campaign using pre-existing CSV in data/emails/."""
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "data", "emails",
    )
    csv_path = os.path.join(data_dir, f"{institution}_emails.csv")

    if not os.path.exists(csv_path):
        logger.error(f"[ERROR] CSV not found: {csv_path}")
        return {"sent": 0, "failed": 0}

    emails = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("email"):
                emails.append(row["email"])

    logger.info(f"[OK] Loaded {len(emails)} emails from {csv_path}")

    email_data = build_brubru_intro_email(institution)
    logger.info(f"[INFO] Subject: {email_data['subject']}")

    return send_bcc_campaign(
        recipients=emails,
        subject=email_data["subject"],
        html_body=email_data["html_body"],
        dry_run=dry_run,
    )


if __name__ == "__main__":
    main()
