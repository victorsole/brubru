#!/usr/bin/env python3
"""
Send Trade Association Outreach Emails (Tiers 1-3)

Personalised emails to heads of public affairs at target companies.
Each email has a unique subject and body.

Usage:
    # Preview
    python -m scripts.send_trade_association_emails --preview
    python -m scripts.send_trade_association_emails --preview --tier 2

    # Dry run
    python -m scripts.send_trade_association_emails --dry-run --tier 2

    # Send
    python -m scripts.send_trade_association_emails --send --tier 1
    python -m scripts.send_trade_association_emails --send --tier 2 --tier 3
    python -m scripts.send_trade_association_emails --send --company nvidia
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.email_service import get_email_service


# ─── HTML wrapper ─────────────────────────────────────────────────────────────

def _wrap_html(body_content: str) -> str:
    """Wrap email body content in the standard Brubru HTML email shell."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

<tr><td style="padding:40px;">
{body_content}

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
</body></html>"""


# ─── Tier 1 Email Data ───────────────────────────────────────────────────────

TIER_1_EMAILS = [
    {
        "tier": 1,
        "company": "NVIDIA",
        "contact": "Alberto Mittestainer",
        "email": "albertomitt@nvidia.com",
        "confidence": "HIGH",
        "subject": "NVIDIA's EU policy capacity: an AI-native complement",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Alberto,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed NVIDIA is recruiting a Government Affairs Manager for Brussels to handle AI legislation monitoring, trade association tracking, and EU institutional engagement.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">While you search for the right person, <strong>Brubru</strong>, our AI-powered EU policy intelligence platform, already does several of those tasks:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Legislation tracking:</strong> monitors the AI Act, DORA, NIS2, and 490+ other EU legislative files, with 26 EP committee work programmes and EC public consultations.</li>
<li><strong>Document generation:</strong> drafts position papers, MEP briefings, EP resolutions, talking points, and consultation responses tailored to your policy objectives.</li>
<li><strong>Amendment tools:</strong> drafts EU legislative amendments in Akoma Ntoso XML format, tracks all MEP amendments across procedures, and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
<li><strong>EU officials directory:</strong> access information on officials across all EU institutions to support your institutional engagement.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru costs a fraction of a full-time hire and can augment your existing team immediately: no recruitment timeline, no onboarding period.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a 15-minute demo be useful? I can show you exactly how it handles AI Act monitoring and generate a sample policy briefing tailored to NVIDIA's interests.</p>"""),
    },
    {
        "tier": 1,
        "company": "Xiaomi",
        "contact": "Natalia Ares",
        "email": "aresnatalia@xiaomi.com",
        "confidence": "MEDIUM",
        "subject": "Xiaomi Brussels: AI support for your EU policy team",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Natalia,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Xiaomi is recruiting a Government Relations Manager for Brussels to monitor EU automotive, e-mobility, digital, and trade policy, and to draft position papers and consultation responses for the European Commission, Parliament, and Council.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">These are precisely the tasks Brubru was built to handle. Brubru is an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Monitors EU legislative developments:</strong> tracks automotive, digital, and trade policy files with updates from the EP, Council, and Commission, plus 26 EP committee work programmes.</li>
<li><strong>Drafts key documents:</strong> generates position papers, MEP briefings, EP resolutions, talking points, and consultation responses tailored to your company's regulatory objectives.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Whether as a bridge while you recruit or as a permanent augmentation to your Brussels team, Brubru delivers policy intelligence at a fraction of the cost of a full-time hire.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Happy to show you a 15-minute demo tailored to Xiaomi's EU regulatory landscape.</p>"""),
    },
    {
        "tier": 1,
        "company": "PayPal",
        "contact": "Mathilde Bonneau",
        "email": "mbonneau@paypal.com",
        "confidence": "MEDIUM",
        "subject": "PayPal Brussels: EU policy intelligence that scales with your team",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Mathilde,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed PayPal is expanding its Brussels Government Relations team with a new Manager role covering EU fintech, payments, digital, and AML policy.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">While you build out the team, <strong>Brubru</strong>, our AI-powered EU policy platform, can provide immediate coverage:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Financial services regulation tracking:</strong> monitors PSD3, MiCA, DORA, AML packages, and related EU legislative files across 26 EP committee work programmes.</li>
<li><strong>Document generation:</strong> drafts consultation responses, position papers, MEP briefings, and talking points tailored to PayPal's policy positions.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru augments your team's capacity instantly: no recruitment timeline, no onboarding. It's already used by EU policy professionals tracking 490+ legislative files.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief demo focused on financial services regulation be useful?</p>"""),
    },
    {
        "tier": 1,
        "company": "Linklaters",
        "contact": "Bernd Meyring",
        "email": "bernd.meyring@linklaters.com",
        "confidence": "HIGH",
        "subject": "Linklaters Brussels: AI-powered EU legislative intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Bernd,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Linklaters is recruiting an EU Law &amp; Policy Advisor for Brussels to monitor EU legislation, prepare policy briefings for lawyers and clients, and manage knowledge resources on EU regulatory developments.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">This is precisely what Brubru delivers. Brubru is an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Legislation tracking:</strong> monitors 490+ EU legislative files and 26 EP committee work programmes, from early-stage Commission proposals through EP committee votes to Council positions.</li>
<li><strong>Document generation:</strong> drafts position papers, MEP briefings, EP resolutions, talking points, and consultation responses that your lawyers can refine for client-facing outputs.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies across competition, digital, sustainability, and other dossiers.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a law firm managing multiple EU dossiers across practice groups, Brubru provides always-on legislative intelligence that complements your EU Law &amp; Policy team at a fraction of a full-time hire.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I'd welcome the opportunity to show you a 15-minute demo tailored to Linklaters' EU practice areas.</p>"""),
    },
    {
        "tier": 1,
        "company": "GS1",
        "contact": "Nora Kaci",
        "email": "nora.kaci@gs1.org",
        "confidence": "HIGH",
        "subject": "GS1 Brussels: track DPP, CSRD, PPWR and more with AI",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Nora,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed GS1 is recruiting a Public Policy Senior Manager for Brussels to track EU policy across Digital Product Passport, CSRD, PPWR, product safety, traceability, and trade digitalisation, and to engage with EU institutions on these dossiers.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Managing this many interconnected EU files simultaneously is exactly why we built Brubru. It's an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Tracks multiple EU dossiers in parallel:</strong> DPP, CSRD, PPWR, product safety, and traceability files with updates from EP committees, Council working parties, and Commission proceedings.</li>
<li><strong>Document generation:</strong> drafts consultation responses, position papers, MEP briefings, and talking points aligned to your organisation's standards expertise.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For an organisation tracking as many interconnected EU files as GS1, Brubru provides the systematic coverage that even a well-resourced policy team struggles to maintain manually.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a demo focused on your current dossier portfolio be useful?</p>"""),
    },
    {
        "tier": 1,
        "company": "POLITICO Europe",
        "contact": "Riccardo Dugulin",
        "email": "rdugulin@politico.eu",
        "confidence": "MEDIUM",
        "subject": "POLITICO PRAD: AI-augmented EU policy analysis",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Riccardo,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed POLITICO's Research and Analysis Division is recruiting an EU Policy Analyst for financial services to monitor legislation, produce data-driven policy insights, and deliver strategic intelligence.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru, our AI-powered EU policy intelligence platform, was built for precisely this workflow:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Automated legislative monitoring:</strong> tracks 490+ EU legislative files, EP committee votes, Council positions, and Commission proceedings.</li>
<li><strong>Data-driven predictions:</strong> AI-generated legislative timeline predictions, EP plenary vote forecasts, and Council QMV calculations.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure, with filtering by political group, author, and committee, plus alignment analysis against policy positions.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a division that produces "ready-to-use reports distilling complex regulatory developments into clear, digestible insights" (your words), Brubru provides the underlying intelligence infrastructure that scales your analysts' output.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I would welcome a conversation about how Brubru could complement PRAD's analytical workflow.</p>"""),
    },
]


# ─── Tier 2 Email Data ───────────────────────────────────────────────────────

TIER_2_EMAILS = [
    {
        "tier": 2,
        "company": "Uber",
        "contact": "Sophie Bonnecarrere",
        "email": "EUPublicPolicy@uber.com",
        "confidence": "LOW",
        "subject": "Uber's EU policy team: AI-powered legislative intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Sophie,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Uber is recruiting a Head of Public Policy for Northern Europe to lead advocacy campaigns, monitor legislation across tech, mobility, and labour law, and influence policy trends across eight European markets.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Managing policy across that many jurisdictions simultaneously is exactly why we built Brubru. It's an AI-powered EU policy intelligence platform that:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Legislation tracking:</strong> monitors 490+ EU legislative files across digital, mobility, AI, gig economy, and sustainability dossiers, with 26 EP committee work programmes.</li>
<li><strong>Document generation:</strong> drafts position papers, MEP briefings, EP resolutions, talking points, and consultation responses tailored to your policy objectives.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a team managing policy influence across multiple countries and policy domains, Brubru provides the systematic intelligence layer that keeps you ahead of developments at a fraction of the cost of additional headcount.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief demo be useful?</p>"""),
    },
    {
        "tier": 2,
        "company": "Amazon",
        "contact": "James Waterworth",
        "email": "jwaterworth@amazon.com",
        "confidence": "MEDIUM",
        "subject": "Amazon Brussels: AI-powered EU policy intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear James,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Amazon is recruiting a Corporate Communications Policy Manager for Brussels to develop EU policy communications strategies and support Amazon's engagement with EU institutions.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru, our AI-powered EU policy intelligence platform, provides several capabilities relevant to your team's workflow:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Legislation tracking:</strong> monitors 490+ EU legislative files across digital markets, AI regulation, data governance, sustainability, and competition dossiers, with 26 EP committee work programmes.</li>
<li><strong>Document generation:</strong> drafts position papers, MEP briefings, talking points, and consultation responses from live legislative data, ready for your team's review.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a team managing EU policy communications across multiple dossiers, Brubru provides the intelligence infrastructure that accelerates your workflow.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief conversation be useful?</p>"""),
    },
    {
        "tier": 2,
        "company": "NBCUniversal",
        "contact": "Beatrice Flammini",
        "email": "beatrice.flammini@nbcuni.com",
        "confidence": "MEDIUM-HIGH",
        "subject": "NBCUniversal Brussels: AI-powered EU regulatory intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Beatrice,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed NBCUniversal is recruiting a Manager for Government &amp; Regulatory Affairs in Brussels to monitor EU copyright, AI, broadcasting, streaming, and media regulation, and to coordinate with trade associations like MPA and the European VOD Coalition.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru, our AI-powered EU policy intelligence platform, provides:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Media regulation tracking:</strong> monitors copyright, AI, content protection, media regulation, DSA, and DMA dossiers with updates from EP committees, Council, and Commission.</li>
<li><strong>Document generation:</strong> drafts position papers, MEP briefings, talking points, and consultation responses tailored to your regulatory objectives.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for media and digital regulation files and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a team managing regulatory affairs across multiple EU media and digital dossiers, Brubru provides the systematic coverage that complements your Brussels office.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Happy to arrange a 15-minute demo tailored to your regulatory portfolio.</p>"""),
    },
    {
        "tier": 2,
        "company": "Vantive",
        "contact": "Andrew M. Whitman",
        "email": "andrew.whitman@vantive.com",
        "confidence": "MEDIUM",
        "subject": "Vantive EU affairs: AI-powered healthcare policy intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Andrew,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Vantive is recruiting a Senior Manager for Government Affairs covering France, Benelux, and the EU to monitor healthcare policy, engage with EU institutions, and drive renal care advocacy.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Brubru, our AI-powered EU policy intelligence platform, offers capabilities relevant to your European policy team:</p>

<ul style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;">
<li><strong>Healthcare regulation tracking:</strong> monitors HTA regulation, EHDS, pharmaceutical legislation review, medical device regulation, and related dossiers with updates from EP committees, Council, and Commission.</li>
<li><strong>Document generation:</strong> drafts consultation responses, position papers, MEP briefings, and talking points tailored to your healthcare policy objectives.</li>
<li><strong>MEP amendment tracking:</strong> fetches all MEP amendments for any legislative procedure and compares them against your positions to identify political allies.</li>
<li><strong>EU Calendar:</strong> unified calendar covering EP plenary sessions, Council meetings, and Commission college meetings, with a daily digest and deep-links to tracked legislative files.</li>
</ul>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a newly independent company building its European government affairs function, Brubru provides immediate policy intelligence capacity while you recruit and onboard your team.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief conversation be valuable?</p>"""),
    },
]


# ─── Tier 3 Email Data (shorter, more direct) ────────────────────────────────

TIER_3_EMAILS = [
    {
        "tier": 3,
        "company": "Accenture",
        "contact": "Mattia Dalle Vedove",
        "email": "mattia.dalle-vedove@accenture.com",
        "confidence": "MEDIUM",
        "subject": "Accenture Brussels: EU policy intelligence for your GR team",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Mattia,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Accenture is recruiting an EU Government Relations Associate Director for Brussels. Brubru, our AI-powered EU policy intelligence platform, tracks 490+ EU legislative files in real-time, drafts consultation responses and position papers, tracks all MEP amendments with political alignment analysis, and provides a unified EU Calendar covering all institutional events.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Happy to show you a 15-minute demo. Would that be useful?</p>"""),
    },
    {
        "tier": 3,
        "company": "Thales",
        "contact": "Nadia Koeniguer",
        "email": "nadia.koeniguer@thalesgroup.com",
        "confidence": "HIGH",
        "subject": "Thales Brussels: AI-powered EU defence and security policy tracking",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Nadia,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Thales is recruiting a Public Affairs Manager for Belgium. Brubru, our AI-powered EU policy intelligence platform, provides real-time tracking of EU defence, security, and aerospace legislative files, including the European Defence Industrial Strategy and related dossiers.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">With 490+ legislative files monitored, document generation (position papers, MEP briefings, consultation responses), MEP amendment tracking with political alignment analysis, and a unified EU Calendar covering all institutional events, Brubru augments your public affairs team's capacity.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief demo tailored to defence and space dossiers be useful?</p>"""),
    },
    {
        "tier": 3,
        "company": "Eutelsat",
        "contact": "Flora Seube",
        "email": "flora.seube@eutelsat.com",
        "confidence": "HIGH",
        "subject": "Eutelsat Brussels: EU space and telecom policy intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Flora,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Eutelsat is expanding its Brussels EU affairs function. Brubru, our AI-powered EU policy intelligence platform, tracks EU legislative developments in real-time across space, telecom, and digital regulation dossiers, with document generation (position papers, MEP briefings, consultation responses), MEP amendment tracking with political alignment analysis, and a unified EU Calendar covering all institutional events.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a team navigating the evolving EU space and defence regulatory landscape, Brubru provides systematic intelligence coverage. Would a 15-minute demo be useful?</p>"""),
    },
    {
        "tier": 3,
        "company": "FTI Consulting",
        "contact": "Emmanouil Patavos",
        "email": "emmanouil.patavos@fticonsulting.com",
        "confidence": "CONFIRMED",
        "subject": "FTI TMT Brussels: AI policy intelligence for your client work",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Emmanouil,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed FTI Consulting is recruiting a Senior Consultant for your TMT practice in Brussels. Brubru, our AI-powered EU policy intelligence platform, could be a valuable tool for your client advisory work: real-time monitoring of 490+ legislative files, document generation (position papers, MEP briefings, consultation responses), MEP amendment tracking with political alignment analysis, and a unified EU Calendar covering all institutional events.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">For a consultancy managing multiple TMT clients simultaneously, Brubru provides the systematic EU intelligence layer that scales with your portfolio.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Would a brief conversation about how it could complement your practice be useful?</p>"""),
    },
    {
        "tier": 3,
        "company": "Novelis",
        "contact": "Novelis EU Affairs team",
        "email": "pascale.rouhier@novelis.com",
        "confidence": "LOW",
        "subject": "Novelis Brussels: EU sustainability policy intelligence",
        "html_body": _wrap_html("""
<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">Dear Novelis EU Affairs team,</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">I noticed Novelis is recruiting an EU Affairs Manager for Brussels. Brubru, our AI-powered EU policy intelligence platform, tracks EU sustainability, circular economy, CBAM, packaging, and industrial policy dossiers in real-time, with document generation (position papers, MEP briefings, consultation responses), MEP amendment tracking with political alignment analysis, and a unified EU Calendar covering all institutional events.</p>

<p style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;">As you build out your Brussels team, Brubru provides immediate policy intelligence capacity. Would a demo be useful?</p>"""),
    },
]


# ─── Combined list ────────────────────────────────────────────────────────────

ALL_EMAILS = TIER_1_EMAILS + TIER_2_EMAILS + TIER_3_EMAILS


def _filter_emails(tiers: list[int] = None, company: str = None) -> list[dict]:
    """Filter emails by tier and/or company."""
    emails = ALL_EMAILS
    if company:
        emails = [e for e in emails if e["company"].lower() == company.lower()]
    if tiers:
        emails = [e for e in emails if e["tier"] in tiers]
    return emails


def preview_emails(tiers: list[int] = None, company_filter: str = None):
    """Print a summary of all emails to be sent."""
    emails = _filter_emails(tiers=tiers, company=company_filter)

    if not emails:
        print(f"[WARN] No emails match the filters")
        print(f"  Available: {', '.join(e['company'] for e in ALL_EMAILS)}")
        return

    tier_label = f"Tier(s) {', '.join(str(t) for t in tiers)}" if tiers else "All tiers"
    print(f"\n{'='*60}")
    print(f"  TRADE ASSOCIATION EMAILS - Preview ({tier_label})")
    print(f"  {len(emails)} email(s) to send")
    print(f"{'='*60}\n")

    for i, e in enumerate(emails, 1):
        print(f"  {i}. [{e['tier']}] {e['company']}")
        print(f"     To: {e['contact']} <{e['email']}>")
        print(f"     Subject: {e['subject']}")
        print(f"     Confidence: {e['confidence']}")
        print()


def send_emails(tiers: list[int] = None, company_filter: str = None, dry_run: bool = False):
    """Send the outreach emails."""
    service = get_email_service()

    emails = _filter_emails(tiers=tiers, company=company_filter)

    if not emails:
        print(f"[WARN] No emails match the filters")
        return

    if dry_run:
        print("\n[DRY RUN] No emails will actually be sent.\n")

    tier_label = f"Tier(s) {', '.join(str(t) for t in tiers)}" if tiers else "All tiers"
    print(f"\n{'='*60}")
    print(f"  SENDING TRADE ASSOCIATION EMAILS ({tier_label})")
    print(f"  {len(emails)} email(s) | {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    if not dry_run and not service.is_configured:
        print("[ERROR] SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return

    sent = 0
    failed = []

    for e in emails:
        label = f"[{e['tier']}] {e['company']} ({e['contact']} <{e['email']}>)"

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
    parser = argparse.ArgumentParser(description="Send trade association outreach emails")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without sending")
    group.add_argument("--send", action="store_true", help="Actually send the emails")
    group.add_argument("--preview", action="store_true", help="Show email summary only")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], action="append",
                        help="Filter by tier (can be repeated, e.g. --tier 2 --tier 3)")
    parser.add_argument("--company", type=str, help="Send to a specific company only")
    args = parser.parse_args()

    if args.preview:
        preview_emails(tiers=args.tier, company_filter=args.company)
    elif args.dry_run:
        send_emails(tiers=args.tier, company_filter=args.company, dry_run=True)
    elif args.send:
        send_emails(tiers=args.tier, company_filter=args.company, dry_run=False)


if __name__ == "__main__":
    main()
