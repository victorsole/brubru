#!/usr/bin/env python3
"""
Send Tier 1 Trade Association Outreach Emails

Personalised emails to heads of public affairs at 6 target companies.
Each email has a unique subject and body.

Usage:
    # Preview (dry run, no emails sent)
    python -m scripts.send_trade_association_emails --dry-run

    # Send all Tier 1 emails
    python -m scripts.send_trade_association_emails --send

    # Send to a specific company only
    python -m scripts.send_trade_association_emails --send --company nvidia
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.email_service import get_email_service


# ─── Tier 1 Email Data ───────────────────────────────────────────────────────

TIER_1_EMAILS = [
    {
        "company": "NVIDIA",
        "contact": "Alberto Mittestainer",
        "email": "albertomitt@nvidia.com",
        "confidence": "HIGH",
        "subject": "NVIDIA's EU policy capacity -- an AI-native complement",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Alberto,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed NVIDIA is recruiting a Government Affairs Manager for Brussels to handle AI legislation monitoring, trade association tracking, and EU institutional engagement.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">While you search for the right person, <strong>Brubru</strong> &mdash; our AI-powered EU policy intelligence platform &mdash; already does several of those tasks:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>AI legislation tracking:</strong> Monitors the AI Act, DORA, NIS2, and 490+ other EU legislative files in real-time, with EP committee work programmes and Council position updates</li>
<li><strong>Policy briefings on demand:</strong> Generates policy impact analyses, position papers, and consultation response drafts &mdash; in minutes, not days</li>
<li><strong>Trade association intelligence:</strong> Tracks EU institutional outputs, Official Journal publications, and EC public consultations relevant to your portfolio</li>
<li><strong>Amendment drafting:</strong> Drafts EU legislative amendments in proper Akoma Ntoso XML format &mdash; the standard used by EU institutions</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru costs a fraction of a full-time hire and can augment your existing team immediately &mdash; no recruitment timeline, no onboarding period.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a 15-minute demo be useful? I can show you exactly how it handles AI Act monitoring and generate a sample policy briefing tailored to NVIDIA's interests.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
    {
        "company": "Xiaomi",
        "contact": "Natalia Ares",
        "email": "aresnatalia@xiaomi.com",
        "confidence": "MEDIUM",
        "subject": "Xiaomi Brussels -- AI support for your EU policy team",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Natalia,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Xiaomi is recruiting a Government Relations Manager for Brussels to monitor EU automotive, e-mobility, digital, and trade policy &mdash; and to draft position papers and consultation responses for the European Commission, Parliament, and Council.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">These are precisely the tasks Brubru was built to handle. Brubru is an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Monitors EU legislative developments</strong> across automotive, digital, and trade policy files &mdash; with real-time updates from the EP, Council, and Commission</li>
<li><strong>Drafts consultation responses and position papers</strong> tailored to your company's regulatory objectives</li>
<li><strong>Tracks 26 EP committee work programmes</strong> and flags relevant hearings, votes, and amendment deadlines</li>
<li><strong>Generates policy briefings</strong> that translate complex regulatory developments into clear, business-relevant insights</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Whether as a bridge while you recruit or as a permanent augmentation to your Brussels team, Brubru delivers policy intelligence at a fraction of the cost of a full-time hire.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Happy to show you a 15-minute demo tailored to Xiaomi's EU regulatory landscape.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
    {
        "company": "PayPal",
        "contact": "Mathilde Bonneau",
        "email": "mbonneau@paypal.com",
        "confidence": "MEDIUM",
        "subject": "PayPal Brussels -- EU policy intelligence that scales with your team",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Mathilde,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed PayPal is expanding its Brussels Government Relations team with a new Manager role covering EU fintech, payments, digital, and AML policy.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">While you build out the team, <strong>Brubru</strong> &mdash; our AI-powered EU policy platform &mdash; can provide immediate coverage:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Financial services regulation tracking:</strong> Real-time monitoring of PSD3, MiCA, DORA, AML packages, and related EU legislative files</li>
<li><strong>Consultation response drafting:</strong> AI-generated first drafts tailored to PayPal's policy positions, ready for your team's review</li>
<li><strong>Policy briefings:</strong> Complex regulatory developments translated into clear, actionable insights for internal stakeholders</li>
<li><strong>Trade association intelligence:</strong> Track outputs from industry associations and coordinate your positions across multiple policy files</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru augments your team's capacity instantly &mdash; no recruitment timeline, no onboarding. It's already used by EU policy professionals tracking 490+ legislative files.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief demo focused on financial services regulation be useful?</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
    {
        "company": "Linklaters",
        "contact": "Bernd Meyring",
        "email": "bernd.meyring@linklaters.com",
        "confidence": "HIGH",
        "subject": "Linklaters Brussels -- AI-powered EU legislative intelligence",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Bernd,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Linklaters is recruiting an EU Law &amp; Policy Advisor for Brussels to monitor EU legislation, prepare policy briefings for lawyers and clients, and manage knowledge resources on EU regulatory developments.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">This is precisely what Brubru delivers. Brubru is an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Tracks EU legislative processes in real-time</strong> &mdash; from early-stage Commission proposals through EP committee votes to Council positions and trilogues</li>
<li><strong>Generates policy briefings and client alerts</strong> &mdash; translating complex regulatory developments into clear, actionable summaries</li>
<li><strong>Monitors 490+ legislative files and 26 EP committees</strong> &mdash; flagging relevant developments across competition, digital, sustainability, company law, and other dossiers</li>
<li><strong>Drafts consultation responses and position papers</strong> &mdash; providing first drafts that your lawyers can refine for client-facing outputs</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a law firm managing multiple EU dossiers across practice groups, Brubru provides the always-on legislative intelligence that complements your EU Law &amp; Policy team &mdash; at a fraction of a full-time hire.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I'd welcome the opportunity to show you a 15-minute demo tailored to Linklaters' EU practice areas.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
    {
        "company": "GS1",
        "contact": "Francesca Poggiali",
        "email": "francesca.poggiali@gs1.org",
        "confidence": "HIGH",
        "subject": "GS1 Brussels -- track DPP, CSRD, PPWR and more with AI",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Francesca,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed GS1 is recruiting a Public Policy Senior Manager for Brussels to track EU policy across Digital Product Passport, CSRD, PPWR, product safety, traceability, and trade digitalisation &mdash; and to engage with EU institutions on these dossiers.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Managing this many interconnected EU files simultaneously is exactly why we built Brubru. It's an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Tracks multiple EU dossiers in parallel</strong> &mdash; DPP, CSRD, PPWR, product safety, and traceability files with real-time updates from EP committees, Council working parties, and Commission proceedings</li>
<li><strong>Generates policy impact analyses</strong> &mdash; showing how changes in one file (e.g. PPWR packaging requirements) affect related dossiers (DPP data standards, CSRD reporting obligations)</li>
<li><strong>Drafts consultation responses and policy positions</strong> &mdash; providing structured first drafts aligned to your organisation's standards expertise</li>
<li><strong>Monitors all 26 EP committee work programmes</strong> &mdash; flagging hearings, votes, and amendment deadlines relevant to your portfolio of dossiers</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For an organisation tracking as many interconnected EU files as GS1, Brubru provides the systematic coverage that even a well-resourced policy team struggles to maintain manually.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a demo focused on your current dossier portfolio be useful?</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
    {
        "company": "POLITICO Europe",
        "contact": "Riccardo Dugulin",
        "email": "rdugulin@politico.eu",
        "confidence": "MEDIUM",
        "subject": "POLITICO PRAD -- AI-augmented EU policy analysis",
        "html_body": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Riccardo,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed POLITICO's Research and Analysis Division is recruiting an EU Policy Analyst for financial services to monitor legislation, produce data-driven policy insights, and deliver strategic intelligence.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru, our AI-powered EU policy intelligence platform, was built for precisely this workflow:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Automated legislative monitoring:</strong> Tracks 490+ EU legislative files, EP committee votes, Council positions, and Commission proceedings in real-time</li>
<li><strong>Data-driven predictions:</strong> AI-generated legislative timeline predictions, EP plenary vote forecasts, and Council QMV calculations</li>
<li><strong>Policy brief generation:</strong> Translates complex regulatory developments into clear, structured analyses &mdash; ready for editorial refinement</li>
<li><strong>Cross-dossier intelligence:</strong> Connects related legislative files across policy areas, identifying political drivers and institutional dynamics</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a division that produces "ready-to-use reports distilling complex regulatory developments into clear, digestible insights" (your words), Brubru provides the underlying intelligence infrastructure that scales your analysts' output.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I would welcome a conversation about how Brubru could complement PRAD's analytical workflow.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:24px 0 4px;">Best regards,</p>
<p style="color:#1e293b;font-size:16px;line-height:1.4;margin:0;">
<strong>Victor Sole Ferioli</strong><br/>
Founder &amp; Director, Beresol BV<br/>
Brussels | <a href="mailto:hello@beresol.eu" style="color:#0693e3;text-decoration:none;">hello@beresol.eu</a>
</p>
</td></tr>

<tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
<p style="color:#94a3b8;font-size:12px;margin:0;">Beresol &middot; EU Public Affairs &middot; <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a></p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>""",
    },
]


def preview_emails(company_filter: str = None):
    """Print a summary of all emails to be sent."""
    emails = TIER_1_EMAILS
    if company_filter:
        emails = [e for e in emails if e["company"].lower() == company_filter.lower()]

    if not emails:
        print(f"[WARN] No company found matching '{company_filter}'")
        print(f"  Available: {', '.join(e['company'] for e in TIER_1_EMAILS)}")
        return

    print(f"\n{'='*60}")
    print(f"  TIER 1 TRADE ASSOCIATION EMAILS - Preview")
    print(f"  {len(emails)} email(s) to send")
    print(f"{'='*60}\n")

    for i, e in enumerate(emails, 1):
        print(f"  {i}. {e['company']}")
        print(f"     To: {e['contact']} <{e['email']}>")
        print(f"     Subject: {e['subject']}")
        print(f"     Confidence: {e['confidence']}")
        print()


def send_emails(company_filter: str = None, dry_run: bool = False):
    """Send the Tier 1 outreach emails."""
    service = get_email_service()

    emails = TIER_1_EMAILS
    if company_filter:
        emails = [e for e in emails if e["company"].lower() == company_filter.lower()]

    if not emails:
        print(f"[WARN] No company found matching '{company_filter}'")
        return

    if dry_run:
        print("\n[DRY RUN] No emails will actually be sent.\n")

    print(f"\n{'='*60}")
    print(f"  SENDING TIER 1 TRADE ASSOCIATION EMAILS")
    print(f"  {len(emails)} email(s) | {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    if not dry_run and not service.is_configured:
        print("[ERROR] SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return

    sent = 0
    failed = []

    for e in emails:
        label = f"{e['company']} ({e['contact']} <{e['email']}>)"

        if dry_run:
            print(f"  [DRY-RUN] Would send to {label}")
            print(f"            Subject: {e['subject']}")
            sent += 1
        else:
            print(f"  [SENDING] {label}...")
            success = service.send(
                to=e["email"],
                subject=e["subject"],
                html_body=e["html_body"],
            )
            if success:
                print(f"  [OK] Sent to {e['company']}")
                sent += 1
            else:
                print(f"  [FAILED] {e['company']}")
                failed.append(e["company"])

            # 2-second delay between sends to avoid rate limiting
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {sent} sent, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Send Tier 1 trade association outreach emails")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without sending")
    group.add_argument("--send", action="store_true", help="Actually send the emails")
    group.add_argument("--preview", action="store_true", help="Show email summary only")
    parser.add_argument("--company", type=str, help="Send to a specific company only (e.g. nvidia, paypal)")
    args = parser.parse_args()

    if args.preview:
        preview_emails(company_filter=args.company)
    elif args.dry_run:
        send_emails(company_filter=args.company, dry_run=True)
    elif args.send:
        send_emails(company_filter=args.company, dry_run=False)


if __name__ == "__main__":
    main()
