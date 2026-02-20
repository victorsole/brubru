"""
VC Fund Outreach Campaign

Sends tailored emails to VC funds using the EC's venture capital consultation
(deadline 12 March 2026) as a hook. Follows the same patterns as
send_lobby_campaign.py and collect_institution_emails.py.

Usage:
    # List all funds
    python3.12 scripts/send_vc_campaign.py --list

    # Preview what would be sent
    python3.12 scripts/send_vc_campaign.py --dry-run
    python3.12 scripts/send_vc_campaign.py --dry-run --market belgium --tier 1

    # Test templates (send to hello@beresol.eu)
    python3.12 scripts/send_vc_campaign.py --test-templates

    # Send initial outreach
    python3.12 scripts/send_vc_campaign.py --send --market belgium --tier 1

    # Send follow-ups
    python3.12 scripts/send_vc_campaign.py --send --followup 1 --market belgium

    # Send to specific fund
    python3.12 scripts/send_vc_campaign.py --send --fund fortino
"""

import argparse
import json
import logging
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "emails")
VC_FUNDS_FILE = os.path.join(DATA_DIR, "vc_funds.json")

CONSULTATION_URL = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14579-Venture-and-growth-capital-funds-review_en"
CONSULTATION_DEADLINE = "12 March 2026"

MARKET_LABELS = {
    "belgium": "Belgium",
    "spain": "Spain",
    "france": "France",
    "netherlands": "Netherlands",
    "italy": "Italy",
    "us": "United States",
}


def load_funds(
    market: str = None,
    tier: int = None,
    fund_id: str = None,
    require_email: bool = False,
) -> list[dict]:
    """Load VC fund data from JSON, optionally filtered."""
    with open(VC_FUNDS_FILE, "r", encoding="utf-8") as f:
        funds = json.load(f)

    if fund_id:
        funds = [f for f in funds if f["id"] == fund_id]
    if market:
        funds = [f for f in funds if f["market"] == market.lower()]
    if tier:
        funds = [f for f in funds if f["tier"] == tier]
    if require_email:
        funds = [
            f for f in funds
            if any(c.get("email") for c in f.get("contacts", []))
        ]

    return funds


# ---------------------------------------------------------------------------
# HTML Email Builder (reuses lobby campaign pattern)
# ---------------------------------------------------------------------------

COLORS = ["#0693e3", "#059669", "#9b51e0", "#d97706"]


def _build_email_html(
    subject: str,
    header_subtitle: str,
    greeting: str,
    intro: str,
    section_heading: str,
    features: list[tuple[str, str]],
    closing: str,
    cta_text: str,
    cta_url: str,
    sign_off: str,
) -> str:
    """Build table-based HTML email following existing Brubru patterns."""
    features_html = ""
    for i, (_, feat_text) in enumerate(features):
        color = COLORS[i % len(COLORS)]
        features_html += f"""
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:{color};font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        {feat_text}
                                    </td>
                                </tr>"""

    return f"""\
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
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">{header_subtitle}</p>
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

                            <p style="color:#475569;font-size:15px;line-height:1.6;margin:0 0 24px;">
                                {closing}
                            </p>

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="{cta_url}"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        {cta_text}
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#475569;font-size:14px;line-height:1.6;margin:20px 0 0;">
                                {sign_off}
                            </p>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                You received this email because we believe our EU policy intelligence tools may be relevant to your investment activities. If this is not relevant, we apologise for the intrusion and will not contact you again.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f1f5f9;padding:20px 40px;text-align:center;">
                            <p style="color:#94a3b8;font-size:12px;margin:0;">
                                Beresol BV &middot; EU Public Affairs &middot; Brussels &middot;
                                <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
    </body>
    </html>"""


# ---------------------------------------------------------------------------
# Template Variants
# ---------------------------------------------------------------------------

def build_consultation_email(fund: dict) -> dict:
    """
    Default template: EC consultation hook.
    Subject: "Input deadline: EC venture capital consultation - March 12"
    """
    name = fund["name"]
    hook = fund.get("hook", "")

    subject = f"Input deadline: EC venture capital consultation - {CONSULTATION_DEADLINE}"

    intro = (
        f"The European Commission's targeted consultation on venture and growth capital funds reform "
        f"closes on <strong>{CONSULTATION_DEADLINE}</strong>. This will directly shape EU funding rules "
        f"affecting your portfolio companies and fund operations across Europe."
    )

    if hook:
        intro += f"<br><br>{hook}"

    features = [
        ("blue", f"<strong>Deadline urgency:</strong> Only weeks remain to submit input on rules that will govern European VC for the next decade"),
        ("green", f"<strong>Direct impact:</strong> The consultation reviews the &euro;500M AIFMD threshold, EuVECA investment flexibility, and cross-border fundraising barriers"),
        ("purple", f"<strong>Your voice matters:</strong> EC consultations typically receive under 2,000 submissions &mdash; fund-level perspectives add valuable granularity beyond industry association responses"),
    ]

    closing = (
        f"At Beresol, we help investment funds and policy professionals engage effectively with EU policymakers. "
        f"We can handle the complexity of EU consultation responses so you don't navigate Brussels bureaucracy alone."
    )

    html_body = _build_email_html(
        subject=subject,
        header_subtitle="AI-powered EU policy intelligence",
        greeting=f"Dear {name} team,",
        intro=intro,
        section_heading="Why this consultation matters for your fund:",
        features=features,
        closing=closing,
        cta_text="Book a 15-minute call",
        cta_url="mailto:hello@beresol.eu?subject=VC%20Consultation%20-%20" + name.replace(" ", "%20"),
        sign_off="Best regards,<br>Victor Sole Ferioli<br>Founder & Director, Beresol BV<br>Brussels, Belgium",
    )

    return {"subject": subject, "html_body": html_body}


def build_portfolio_email(fund: dict) -> dict:
    """
    Portfolio company hook: for funds with adjacent investments.
    Subject: "[Fund], the advocacy side of [portfolio]'s thesis"
    """
    name = fund["name"]
    hook = fund.get("hook", "")
    portfolio = fund.get("portfolio_highlight", "your portfolio")

    # Extract first company name from portfolio highlight
    first_company = portfolio.split("(")[0].split(",")[0].strip()

    subject = f"{name}, the advocacy side of {first_company}'s thesis"

    intro = (
        f"{hook}"
        f"<br><br>"
        f"The EC's venture capital consultation (deadline {CONSULTATION_DEADLINE}) asks questions "
        f"that will affect every fund in your portfolio. At Beresol, we've built "
        f"<strong>Brubru</strong> &mdash; an AI-powered EU advocacy platform that does for policy "
        f"engagement what your portfolio companies do for their respective markets."
    )

    features = [
        ("blue", f"<strong>Policy intelligence:</strong> Track 490+ legislative files, 26 EP committee work programmes, and EC public consultations in real-time"),
        ("green", f"<strong>Amendment drafting:</strong> Draft EU legislative amendments in proper Akoma Ntoso XML format &mdash; the standard used by EU institutions"),
        ("purple", f"<strong>Compliance analysis:</strong> AI-powered gap analysis against AI Act, DORA, MiCA, SFDR, AIFMD II, and other EU regulations"),
        ("gold", f"<strong>Predictions:</strong> AI-generated legislative timeline predictions, EP vote forecasts, and Council QMV calculations"),
    ]

    closing = (
        f"Given your thesis and portfolio, would a brief conversation about the consultation and our approach be valuable?"
    )

    html_body = _build_email_html(
        subject=subject,
        header_subtitle="AI-powered EU policy intelligence",
        greeting=f"Dear {name} team,",
        intro=intro,
        section_heading="What Brubru does:",
        features=features,
        closing=closing,
        cta_text="Book a 15-minute call",
        cta_url="mailto:hello@beresol.eu?subject=VC%20Consultation%20-%20" + name.replace(" ", "%20"),
        sign_off="Best regards,<br>Victor Sole Ferioli<br>Founder & Director, Beresol BV<br>Brussels, Belgium",
    )

    return {"subject": subject, "html_body": html_body}


def build_us_gap_email(fund: dict) -> dict:
    """
    US fund template: regulatory navigation gap framing.
    Subject: "EU regulatory intelligence for [Fund]'s European portfolio"
    """
    name = fund["name"]
    hook = fund.get("hook", "")
    portfolio = fund.get("portfolio_highlight", "your European portfolio companies")

    subject = f"EU regulatory intelligence for {name}'s European portfolio"

    intro = (
        f"US venture capital firms investing in Europe face a structural disadvantage: "
        f"they lack in-house EU regulatory expertise. Unlike European counterparts, "
        f"US VCs typically rely on external advisors for compliance questions and have "
        f"no systematic policy intelligence."
    )

    if hook:
        intro += f"<br><br>{hook}"

    features = [
        ("blue", f"<strong>AI Act compliance:</strong> Your portfolio companies deploying AI in Europe face mandatory risk classification, conformity assessments, and transparency requirements by August 2026"),
        ("green", f"<strong>Financial regulation:</strong> MiCA (crypto), DORA (operational resilience), SFDR (sustainability disclosure), AIFMD II (fund management) &mdash; all with imminent compliance deadlines"),
        ("purple", f"<strong>Policy shaping:</strong> The EC's venture capital consultation (deadline {CONSULTATION_DEADLINE}) will reshape how US funds operate in Europe &mdash; your input matters"),
        ("gold", f"<strong>Portfolio-level intelligence:</strong> One platform covering all EU regulatory touchpoints across your European investments, instead of fragmented external advice"),
    ]

    closing = (
        f"General Catalyst US has the Policy Institute. a16z has dedicated government affairs. "
        f"Beresol can be your EU policy infrastructure &mdash; regulatory intelligence for your "
        f"European portfolio at a fraction of the cost of traditional Brussels consultancies."
    )

    html_body = _build_email_html(
        subject=subject,
        header_subtitle="AI-powered EU policy intelligence",
        greeting=f"Dear {name} team,",
        intro=intro,
        section_heading="What your European portfolio faces:",
        features=features,
        closing=closing,
        cta_text="Book a 15-minute call",
        cta_url="mailto:hello@beresol.eu?subject=EU%20Regulatory%20Intelligence%20-%20" + name.replace(" ", "%20"),
        sign_off="Best regards,<br>Victor Sole Ferioli<br>Founder & Director, Beresol BV<br>Brussels, Belgium",
    )

    return {"subject": subject, "html_body": html_body}


# ---------------------------------------------------------------------------
# Follow-up Templates
# ---------------------------------------------------------------------------

def build_followup_email(fund: dict, phase: int) -> dict:
    """Build follow-up email for a given phase (1-4)."""
    name = fund["name"]

    if phase == 1:
        # Day 3-4: Share specific consultation insight
        subject = f"Key data point from the EC venture capital consultation"
        intro = (
            f"Quick follow-up on the EC consultation closing {CONSULTATION_DEADLINE}. "
            f"One data point that may interest you:"
            f"<br><br>"
            f"EU pension funds allocate <strong>0.02-0.12%</strong> to venture capital versus "
            f"<strong>1.9%</strong> in the US. If EU pensions reached just 10% allocation to "
            f"alternatives, this would unlock <strong>&euro;124 billion</strong>. "
            f"The consultation explicitly asks whether the IORPs Directive should be reformed "
            f"to enable this."
            f"<br><br>"
            f"This is the kind of structural change that affects every European fund manager. "
            f"Would a 15-minute call to discuss whether submitting a response makes sense for {name}?"
        )

    elif phase == 2:
        # Day 7: Mention engagement
        subject = f"European VCs are responding to the EC consultation"
        intro = (
            f"Several European fund managers are preparing responses to the EC's venture capital "
            f"consultation (deadline {CONSULTATION_DEADLINE}). The Commission is reviewing whether "
            f"the &euro;500M AIFMD threshold &mdash; set in 2011 &mdash; should be raised as high as "
            f"&euro;10B, and whether EuVECA funds should be allowed venture debt and post-IPO positions."
            f"<br><br>"
            f"With approximately 2,000 or fewer responses expected, each submission carries weight. "
            f"Major industry associations will respond, but fund-level perspectives add valuable granularity."
            f"<br><br>"
            f"Would it be useful to explore whether {name} should submit an independent response?"
        )

    elif phase == 3:
        # Day 10: Deadline emphasis
        subject = f"EC venture capital consultation closes {CONSULTATION_DEADLINE}"
        intro = (
            f"The European Commission's consultation on venture and growth capital reform "
            f"closes on <strong>{CONSULTATION_DEADLINE}</strong>. Legislative proposals are expected "
            f"in Q3 2026, meaning responses submitted now will shape regulations affecting "
            f"European VC for the next decade."
            f"<br><br>"
            f"Missing this window means waiting for the next regulatory cycle &mdash; typically 5-7 years."
            f"<br><br>"
            f"If {name} would like to submit a response, we can handle the technical drafting. "
            f"Happy to discuss in a brief call."
        )

    else:
        # Day 14: Break-up email
        subject = f"Last note on the EC consultation"
        intro = (
            f"I understand timing may not be right. I wanted to let you know that we're available "
            f"if {name} ever needs EU policy intelligence or consultation support in the future."
            f"<br><br>"
            f"Brubru is free to use at <a href='https://brubru.beresol.eu' style='color:#0693e3;'>brubru.beresol.eu</a> "
            f"&mdash; no signup required for basic features. Feel free to try it anytime."
            f"<br><br>"
            f"Wishing you a productive quarter."
        )

    html_body = _build_email_html(
        subject=subject,
        header_subtitle="AI-powered EU policy intelligence",
        greeting=f"Dear {name} team,",
        intro=intro,
        section_heading="" if phase == 4 else "",
        features=[] if phase >= 3 else [
            ("blue", f"<strong>Free to use:</strong> Brubru is available at brubru.beresol.eu &mdash; no signup required for basic features"),
        ],
        closing="" if phase == 4 else "",
        cta_text="Try Brubru" if phase == 4 else "Book a 15-minute call",
        cta_url="https://brubru.beresol.eu" if phase == 4 else "mailto:hello@beresol.eu?subject=VC%20Consultation%20-%20" + name.replace(" ", "%20"),
        sign_off="Best regards,<br>Victor Sole Ferioli<br>Founder & Director, Beresol BV",
    )

    return {"subject": subject, "html_body": html_body}


# ---------------------------------------------------------------------------
# Template Dispatcher
# ---------------------------------------------------------------------------

TEMPLATE_BUILDERS = {
    "consultation": build_consultation_email,
    "portfolio": build_portfolio_email,
    "us_gap": build_us_gap_email,
}


def build_email_for_fund(fund: dict, followup: int = None) -> dict:
    """Build the appropriate email for a fund based on its template type."""
    if followup:
        return build_followup_email(fund, followup)

    template_type = fund.get("template", "consultation")
    builder = TEMPLATE_BUILDERS.get(template_type, build_consultation_email)
    return builder(fund)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_individual(fund: dict, email: str, subject: str, html_body: str, dry_run: bool = True) -> bool:
    """Send a personalised email to a single recipient."""
    from services.email_service import get_email_service

    if dry_run:
        logger.info(f"  [DRY-RUN] Would send to {email}")
        return True

    svc = get_email_service()
    if not svc.is_configured:
        logger.error("[ERROR] SMTP not configured")
        return False

    success = svc.send(
        to=email,
        subject=subject,
        html_body=html_body,
    )

    if success:
        logger.info(f"  [OK] Sent to {email}")
    else:
        logger.error(f"  [ERROR] Failed to send to {email}")

    return success


def send_fund_campaign(fund: dict, followup: int = None, dry_run: bool = True) -> dict:
    """Send campaign emails to all contacts of a fund."""
    template = build_email_for_fund(fund, followup=followup)
    emails = [c["email"] for c in fund.get("contacts", []) if c.get("email")]

    if not emails:
        logger.warning(f"  [SKIP] {fund['name']}: no email addresses")
        return {"sent": 0, "failed": 0, "skipped": True}

    phase_label = f"Follow-up {followup}" if followup else "Initial"
    logger.info(
        f"\n[SEND] {fund['name']} ({fund['market'].upper()}, Tier {fund['tier']}) "
        f"| {phase_label} | Template: {fund.get('template', 'consultation')} "
        f"| Recipients: {len(emails)}"
    )
    logger.info(f"[SEND] Subject: {template['subject']}")

    sent = 0
    failed = 0

    for email in emails:
        success = send_individual(fund, email, template["subject"], template["html_body"], dry_run=dry_run)
        if success:
            sent += 1
        else:
            failed += 1

        # Small delay between sends
        if not dry_run and len(emails) > 1:
            time.sleep(2)

    return {"sent": sent, "failed": failed, "skipped": False}


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def cmd_list(args):
    """List all funds with their details."""
    funds = load_funds(market=args.market, tier=args.tier, fund_id=args.fund)

    if not funds:
        logger.info("[INFO] No funds match the filters")
        return

    # Group by market
    by_market = {}
    for f in funds:
        by_market.setdefault(f["market"], []).append(f)

    total_contacts = 0
    total_with_email = 0

    for market in sorted(by_market.keys()):
        market_funds = by_market[market]
        logger.info(f"\n{'='*60}")
        logger.info(f"  {MARKET_LABELS.get(market, market.upper())}")
        logger.info(f"{'='*60}")

        for f in sorted(market_funds, key=lambda x: x["tier"]):
            contacts = f.get("contacts", [])
            emails = [c for c in contacts if c.get("email")]
            total_contacts += len(contacts)
            total_with_email += len(emails)

            email_status = f"{len(emails)}/{len(contacts)} emails" if contacts else "no contacts"
            logger.info(
                f"  Tier {f['tier']} | {f['name']:<30} | "
                f"Template: {f.get('template', 'consultation'):<14} | "
                f"{email_status}"
            )

    logger.info(f"\n{'='*60}")
    logger.info(f"  TOTAL: {len(funds)} funds, {total_contacts} contacts, {total_with_email} with email")
    logger.info(f"{'='*60}")


def cmd_test_templates(args):
    """Send all template variants to hello@beresol.eu for preview."""
    test_fund_consultation = {
        "id": "test", "name": "Test Fund", "market": "belgium", "tier": 1,
        "hook": "This is a test hook for the consultation template.",
        "portfolio_highlight": "TestCo (compliance tech)",
        "template": "consultation",
    }
    test_fund_portfolio = {**test_fund_consultation, "template": "portfolio"}
    test_fund_us = {**test_fund_consultation, "template": "us_gap", "market": "us", "name": "Test US Fund"}

    templates = [
        ("Consultation", build_consultation_email(test_fund_consultation)),
        ("Portfolio Hook", build_portfolio_email(test_fund_portfolio)),
        ("US Gap", build_us_gap_email(test_fund_us)),
        ("Follow-up 1", build_followup_email(test_fund_consultation, 1)),
        ("Follow-up 2", build_followup_email(test_fund_consultation, 2)),
        ("Follow-up 3", build_followup_email(test_fund_consultation, 3)),
        ("Follow-up 4 (Break-up)", build_followup_email(test_fund_consultation, 4)),
    ]

    from services.email_service import get_email_service
    svc = get_email_service()

    if not svc.is_configured:
        logger.error("[ERROR] SMTP not configured. Set SMTP_* environment variables.")
        return

    for label, template in templates:
        test_subject = f"[TEST] {label}: {template['subject']}"
        success = svc.send(
            to=svc.user,
            subject=test_subject,
            html_body=template["html_body"],
        )
        status = "[OK]" if success else "[ERROR]"
        logger.info(f"{status} {label}: {test_subject}")
        time.sleep(1)

    logger.info(f"\n[DONE] Sent {len(templates)} test emails to {svc.user}")


def cmd_dry_run(args):
    """Preview what would be sent."""
    funds = load_funds(market=args.market, tier=args.tier, fund_id=args.fund)

    if not funds:
        logger.info("[INFO] No funds match the filters")
        return

    total_recipients = 0
    total_skipped = 0

    for fund in sorted(funds, key=lambda x: (x["tier"], x["market"])):
        contacts = fund.get("contacts", [])
        emails = [c["email"] for c in contacts if c.get("email")]

        if emails:
            phase = f"Follow-up {args.followup}" if args.followup else "Initial"
            template = build_email_for_fund(fund, followup=args.followup)
            logger.info(
                f"[DRY-RUN] {fund['name']:<30} | "
                f"{fund['market'].upper():<12} | Tier {fund['tier']} | "
                f"{phase:<14} | {len(emails)} recipients | "
                f"Subject: {template['subject'][:50]}..."
            )
            total_recipients += len(emails)
        else:
            logger.info(
                f"[SKIP]    {fund['name']:<30} | "
                f"{fund['market'].upper():<12} | Tier {fund['tier']} | "
                f"No email addresses"
            )
            total_skipped += 1

    logger.info(f"\n[SUMMARY] {total_recipients} recipients across {len(funds) - total_skipped} funds ({total_skipped} skipped)")


def cmd_send(args):
    """Send campaign emails."""
    funds = load_funds(market=args.market, tier=args.tier, fund_id=args.fund, require_email=True)

    if not funds:
        logger.info("[INFO] No funds with email addresses match the filters")
        return

    logger.info(f"\n[START] Sending to {len(funds)} funds")
    if args.followup:
        logger.info(f"[START] Phase: Follow-up {args.followup}")

    total_sent = 0
    total_failed = 0

    for fund in sorted(funds, key=lambda x: (x["tier"], x["market"])):
        result = send_fund_campaign(fund, followup=args.followup, dry_run=False)
        total_sent += result["sent"]
        total_failed += result["failed"]

        # Delay between funds
        time.sleep(3)

    logger.info(f"\n[DONE] Campaign complete: {total_sent} sent, {total_failed} failed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="VC Fund Outreach Campaign",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3.12 scripts/send_vc_campaign.py --list
  python3.12 scripts/send_vc_campaign.py --dry-run --market belgium --tier 1
  python3.12 scripts/send_vc_campaign.py --test-templates
  python3.12 scripts/send_vc_campaign.py --send --market belgium --tier 1
  python3.12 scripts/send_vc_campaign.py --send --followup 1 --market belgium
  python3.12 scripts/send_vc_campaign.py --send --fund fortino
        """,
    )

    # Mode flags (mutually exclusive)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="List all funds with details")
    mode.add_argument("--dry-run", action="store_true", help="Preview what would be sent")
    mode.add_argument("--test-templates", action="store_true", help="Send test emails to hello@beresol.eu")
    mode.add_argument("--send", action="store_true", help="Actually send emails")

    # Filters
    parser.add_argument("--market", type=str, help="Filter by market (belgium, spain, france, netherlands, italy, us)")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], help="Filter by tier (1, 2, 3)")
    parser.add_argument("--fund", type=str, help="Send to specific fund by ID")
    parser.add_argument("--followup", type=int, choices=[1, 2, 3, 4], help="Send follow-up N instead of initial")

    args = parser.parse_args()

    # Verify data file exists
    if not os.path.exists(VC_FUNDS_FILE):
        logger.error(f"[ERROR] VC funds data file not found: {VC_FUNDS_FILE}")
        logger.error(f"[ERROR] Expected at: data/emails/vc_funds.json")
        sys.exit(1)

    if args.list:
        cmd_list(args)
    elif args.dry_run:
        cmd_dry_run(args)
    elif args.test_templates:
        cmd_test_templates(args)
    elif args.send:
        cmd_send(args)


if __name__ == "__main__":
    main()
