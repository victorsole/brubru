#!/usr/bin/env python3
"""
Send Brussels EU Bubble Campaign Emails

Personalised outreach to EU media journalists, EP press officers,
and trade association leaders.

Send date: Monday 2 March 2026

Usage:
    # Preview
    python -m scripts.send_brussels_campaign_emails --preview
    python -m scripts.send_brussels_campaign_emails --preview --segment journalists
    python -m scripts.send_brussels_campaign_emails --preview --segment ep-press
    python -m scripts.send_brussels_campaign_emails --preview --segment trade-associations

    # Dry run
    python -m scripts.send_brussels_campaign_emails --dry-run
    python -m scripts.send_brussels_campaign_emails --dry-run --segment journalists

    # Send
    python -m scripts.send_brussels_campaign_emails --send --segment journalists
    python -m scripts.send_brussels_campaign_emails --send  # all segments
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
<strong>Victor Sol&eacute; Ferioli</strong><br/>
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


# ─── Styling constants ────────────────────────────────────────────────────────

_P = 'style="color:#475569;font-size:16px;line-height:1.7;margin:0 0 16px;"'
_UL = 'style="color:#475569;font-size:16px;line-height:1.8;margin:0 0 16px;padding-left:24px;"'
_LI = ""  # inherit from ul


# ─── Journalist email builder ────────────────────────────────────────────────

# Beat-specific hooks (referenced by beat key)
BEAT_HOOKS = {
    "tech_digital": (
        "{outlet}'s coverage of EU digital regulation is among the most detailed "
        "in Brussels. I thought you'd find it relevant that an AI platform now "
        "tracks the AI Act, DSA/DMA enforcement, Data Act, and Cyber Resilience "
        "Act in real-time &mdash; the same files you cover daily."
    ),
    "trade": (
        "Your trade policy reporting for {outlet} covers some of the most "
        "consequential EU dossiers right now. Brubru tracks CBAM, trade defence "
        "instruments, FTA negotiations, and related economic files systematically "
        "&mdash; something I thought might be relevant for your reporting."
    ),
    "energy_climate": (
        "Your energy and climate coverage for {outlet} touches some of the EU's "
        "most active legislative files. Brubru tracks Fit for 55, ETS reform, "
        "renewable energy directives, and related sustainability dossiers in "
        "real-time &mdash; I thought it might be relevant to your work."
    ),
    "ep_institutional": (
        "Your EP and institutional affairs reporting for {outlet} requires "
        "tracking complex procedures across multiple committees. Brubru monitors "
        "all 26 EP committee work programmes with procedure-level status updates "
        "&mdash; I thought you'd find it relevant."
    ),
    "finance": (
        "Your financial services coverage for {outlet} tracks technically complex "
        "EU regulation. Brubru monitors PSD3/PSR, MiCA, DORA, Banking Union, and "
        "AML packages with real-time updates from EP committees and Council "
        "&mdash; I thought it might be relevant to your reporting."
    ),
    "defence_security": (
        "Your defence and security reporting for {outlet} covers an increasingly "
        "active EU legislative agenda. Brubru tracks the European Defence "
        "Industrial Strategy, dual-use regulation, NIS2, and Cyber Resilience Act "
        "alongside 490+ other EU legislative files &mdash; I thought you'd find "
        "it relevant."
    ),
    "agriculture_food": (
        "Your agriculture and food policy coverage for {outlet} tracks dossiers "
        "from CAP reform to food safety regulation. Brubru monitors these files "
        "alongside sustainability and trade regulation in real-time &mdash; I "
        "thought it might be relevant."
    ),
    "automotive": (
        "Your automotive sector reporting for {outlet} covers CO2 standards, "
        "Euro 7, and electrification policy. Brubru tracks these regulatory files "
        "with real-time updates from EP committees, Council, and Commission "
        "&mdash; I thought you'd find it relevant."
    ),
    "editorial": (
        "I'm reaching out because {outlet} covers EU policy extensively. Brubru "
        "is an AI-powered EU legislative intelligence platform built in Brussels "
        "&mdash; I thought your team might find it relevant, either as a "
        "newsroom research tool or as a story about Brussels-built policy tech."
    ),
}

# Beat-specific feature bullet points
BEAT_FEATURES = {
    "tech_digital": [
        "<strong>AI Act and digital regulation:</strong> tracks AI Act implementation, DSA/DMA enforcement, Data Act, and Cyber Resilience Act with committee-level updates and timeline predictions.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any legislative procedure, with political group analysis and alignment comparison.",
        "<strong>Policy briefing generation:</strong> drafts position papers, MEP briefings, and talking points from live legislative data.",
        "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings with deep-links to tracked files.",
    ],
    "trade": [
        "<strong>Legislative monitoring:</strong> tracks 500+ EU files across the Legislative Train, OEIL, EUR-Lex, and 26 EP committee work programmes.",
        "<strong>Trade and economic dossiers:</strong> monitors CBAM, trade defence instruments, FTA negotiations, and related economic regulation.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis.",
        "<strong>EU Calendar:</strong> unified calendar covering all institutional events with deep-links to tracked files.",
    ],
    "energy_climate": [
        "<strong>Energy and climate tracking:</strong> monitors Fit for 55, ETS reform, renewable energy directives, and related sustainability files.",
        "<strong>Consultation monitoring:</strong> tracks the EC &lsquo;Have Your Say&rsquo; portal with upcoming deadlines and AI-generated response analysis.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for energy and climate dossiers with political group analysis.",
        "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings.",
    ],
    "ep_institutional": [
        "<strong>Committee work monitoring:</strong> tracks all 26 EP committees' work in progress with procedure references, lead MEPs, and status updates.",
        "<strong>Legislative predictions:</strong> AI-powered timeline predictions, EP plenary vote forecasts, and political group position analysis.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group breakdown.",
        "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings.",
    ],
    "finance": [
        "<strong>Financial regulation tracking:</strong> monitors PSD3/PSR, MiCA, DORA, Banking Union, AML packages, and related dossiers.",
        "<strong>Legislative monitoring:</strong> tracks 500+ EU files with real-time updates from EP committees and Council.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ECON procedures with political group analysis.",
        "<strong>EU Calendar:</strong> unified calendar covering all institutional events with deep-links to tracked files.",
    ],
    "defence_security": [
        "<strong>Defence and security tracking:</strong> monitors the European Defence Industrial Strategy, dual-use regulation, NIS2, and Cyber Resilience Act.",
        "<strong>Legislative monitoring:</strong> tracks 500+ EU files including emerging security and defence dossiers.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis.",
        "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings.",
    ],
    "agriculture_food": [
        "<strong>Agriculture and food tracking:</strong> monitors CAP reform, food safety, sustainability regulation, and PPWR.",
        "<strong>Legislative monitoring:</strong> tracks 500+ EU files across agricultural, environmental, and trade dossiers.",
        "<strong>Consultation tracking:</strong> monitors the EC &lsquo;Have Your Say&rsquo; portal with upcoming deadlines.",
        "<strong>EU Calendar:</strong> unified calendar covering all institutional events with deep-links to tracked files.",
    ],
    "automotive": [
        "<strong>Automotive regulation tracking:</strong> monitors CO2 standards, Euro 7, ETS2, and e-mobility regulation.",
        "<strong>Legislative monitoring:</strong> tracks 500+ EU files across transport, environmental, and industrial dossiers.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis.",
        "<strong>EU Calendar:</strong> unified calendar covering all institutional events with deep-links to tracked files.",
    ],
    "editorial": [
        "<strong>Real-time legislative monitoring:</strong> tracks 500+ EU files across the Legislative Train, OEIL, EUR-Lex, and 26 EP committee work programmes.",
        "<strong>Policy briefing generation:</strong> drafts position papers, MEP briefings, talking points, and consultation responses from live legislative data.",
        "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis and alignment comparison.",
        "<strong>Legislative predictions:</strong> AI-powered timeline predictions, EP plenary vote forecasts, and Council QMV calculations.",
    ],
}

JOURNALIST_CTA = (
    "Brubru is built by Beresol, a Brussels-based company. Not a Silicon Valley "
    "product trying to understand EU institutions &mdash; we live in the bubble. "
    "Happy to offer a demo or provide more detail for a piece. You can also try "
    'it directly at <a href="https://brubru.beresol.eu" style="color:#0693e3;'
    'text-decoration:none;">brubru.beresol.eu</a>.'
)


def _journalist_body(first_name: str, outlet: str, beat: str) -> str:
    hook = BEAT_HOOKS[beat].format(outlet=outlet)
    features = BEAT_FEATURES[beat]
    features_html = "\n".join(f"<li>{f}</li>" for f in features)
    return _wrap_html(
        f'<p {_P}>Dear {first_name},</p>\n\n'
        f'<p {_P}>I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an '
        f'AI-powered EU legislative intelligence platform built in Brussels.</p>\n\n'
        f'<p {_P}>{hook}</p>\n\n'
        f'<p {_P}>Brubru provides:</p>\n\n'
        f'<ul {_UL}>\n{features_html}\n</ul>\n\n'
        f'<p {_P}>{JOURNALIST_CTA}</p>'
    )


def _journalist_subject(first_name: str, beat: str, outlet: str) -> str:
    beat_labels = {
        "tech_digital": "EU tech regulation intelligence",
        "trade": "EU trade policy intelligence",
        "energy_climate": "EU energy and climate policy intelligence",
        "ep_institutional": "EU institutional affairs intelligence",
        "finance": "EU financial regulation intelligence",
        "defence_security": "EU defence and security policy intelligence",
        "agriculture_food": "EU agriculture policy intelligence",
        "automotive": "EU automotive regulation intelligence",
        "editorial": "EU legislative intelligence (built in Brussels)",
    }
    return f"{first_name} — AI-powered {beat_labels[beat]}"


# ─── Journalist email data ───────────────────────────────────────────────────

JOURNALIST_EMAILS = [
    # ── POLITICO Europe ──────────────────────────────────────────────────────
    # Tier 1: Tech & Digital
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Pieter Haeck",
     "email": "phaeck@politico.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Clothilde Goujard",
     "email": "cgoujard@politico.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Antoaneta Roussi",
     "email": "aroussi@politico.eu", "beat": "defence_security", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Laura Kayali",
     "email": "lkayali@politico.eu", "beat": "defence_security", "confidence": "HIGH"},
    # Tier 2: EU Policy & Economy
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Sarah Wheaton",
     "email": "swheaton@politico.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Barbara Moens",
     "email": "bmoens@politico.eu", "beat": "trade", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Carlo Martuscelli",
     "email": "cmartuscelli@politico.eu", "beat": "finance", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Gregorio Sorgi",
     "email": "gsorgi@politico.eu", "beat": "finance", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Giorgio Leali",
     "email": "gleali@politico.eu", "beat": "ep_institutional", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Zoya Sheftalovich",
     "email": "zsheftalovich@politico.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Maia de la Baume",
     "email": "mdelabaume@politico.eu", "beat": "ep_institutional", "confidence": "HIGH"},
    # Tier 3: Energy, Climate, Agriculture
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Karl Mathiesen",
     "email": "kmathiesen@politico.eu", "beat": "energy_climate", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Leonie Cater",
     "email": "lcater@politico.eu", "beat": "energy_climate", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Jakob Weizman",
     "email": "jweizman@politico.eu", "beat": "energy_climate", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Hanne Cokelaere",
     "email": "hcokelaere@politico.eu", "beat": "agriculture_food", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Jordyn Dahl",
     "email": "jdahl@politico.eu", "beat": "automotive", "confidence": "HIGH"},
    # Tier 4: Editors & Playbook
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Jamil Anderlini",
     "email": "janderlini@politico.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Kate Day",
     "email": "kday@politico.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Doug Busvine",
     "email": "dbusvine@politico.eu", "beat": "trade", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Suzanne Lynch",
     "email": "slynch@politico.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "POLITICO Europe", "contact": "Jakob Hanke Vela",
     "email": "jhankevela@politico.eu", "beat": "trade", "confidence": "HIGH"},

    # ── Euractiv ─────────────────────────────────────────────────────────────
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Matthew Karnitschnig",
     "email": "matthew.karnitschnig@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Elisa Braun",
     "email": "elisa.braun@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Joshua Posaner",
     "email": "joshua.posaner@euractiv.com", "beat": "defence_security", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Angelo Di Mambro",
     "email": "angelo.dimambro@euractiv.com", "beat": "agriculture_food", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Theo Bourgery-Gonse",
     "email": "theo.bourgery@euractiv.com", "beat": "tech_digital", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Nikolaus Kurmayer",
     "email": "nikolaus.kurmayer@euractiv.com", "beat": "energy_climate", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Brian Maguire",
     "email": "brian.maguire@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Emma Pirnay",
     "email": "emma.pirnay@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Sarantis Michalopoulos",
     "email": "sarantis.michalopoulos@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "Euractiv", "contact": "Julia Tar",
     "email": "julia.tar@euractiv.com", "beat": "editorial", "confidence": "MEDIUM"},

    # ── EUobserver ───────────────────────────────────────────────────────────
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Lisbeth Kirk",
     "email": "lk@euobserver.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Koert Debeuf",
     "email": "kd@euobserver.com", "beat": "editorial", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Andrew Rettman",
     "email": "ar@euobserver.com", "beat": "defence_security", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Nikolaj Nielsen",
     "email": "nn@euobserver.com", "beat": "ep_institutional", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Wester van Gaal",
     "email": "wvg@euobserver.com", "beat": "energy_climate", "confidence": "MEDIUM"},
    {"segment": "journalists", "outlet": "EUobserver", "contact": "Benjamin Fox",
     "email": "bf@euobserver.com", "beat": "editorial", "confidence": "MEDIUM"},

    # ── Financial Times ──────────────────────────────────────────────────────
    {"segment": "journalists", "outlet": "Financial Times", "contact": "Henry Foy",
     "email": "henry.foy@ft.com", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Financial Times", "contact": "Alice Hancock",
     "email": "alice.hancock@ft.com", "beat": "energy_climate", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Financial Times", "contact": "Andy Bounds",
     "email": "andy.bounds@ft.com", "beat": "trade", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Financial Times", "contact": "Valentina Pop",
     "email": "valentina.pop@ft.com", "beat": "ep_institutional", "confidence": "HIGH"},

    # ── Sifted ───────────────────────────────────────────────────────────────
    {"segment": "journalists", "outlet": "Sifted", "contact": "John Thornhill",
     "email": "john@sifted.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Amy Lewin",
     "email": "amy@sifted.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Martin Coulter",
     "email": "martin@sifted.eu", "beat": "editorial", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Freya Pratty",
     "email": "freya@sifted.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Mimi Billing",
     "email": "mimi@sifted.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Miriam Partington",
     "email": "miriam@sifted.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Anne Sraders",
     "email": "anne@sifted.eu", "beat": "defence_security", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Daphne Leprince-Ringuet",
     "email": "daphne@sifted.eu", "beat": "tech_digital", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Tom Matsuda",
     "email": "tom@sifted.eu", "beat": "finance", "confidence": "HIGH"},
    {"segment": "journalists", "outlet": "Sifted", "contact": "Eanna Kelly",
     "email": "eanna@sifted.eu", "beat": "tech_digital", "confidence": "HIGH"},

    # ── The European Correspondent ───────────────────────────────────────────
    {"segment": "journalists", "outlet": "The European Correspondent", "contact": "Julius Fintelmann",
     "email": "team@europeancorrespondent.com", "beat": "editorial", "confidence": "LOW"},
    {"segment": "journalists", "outlet": "The European Correspondent", "contact": "Zuzanna Stawiska",
     "email": "zuzanna.stawiska@europeancorrespondent.com", "beat": "editorial", "confidence": "MEDIUM"},

    # ── Contexte ─────────────────────────────────────────────────────────────
    {"segment": "journalists", "outlet": "Contexte", "contact": "Louise Guillot",
     "email": "lguillot@contexte.com", "beat": "editorial", "confidence": "MEDIUM"},
]

# Build subject + html_body for each journalist
for _j in JOURNALIST_EMAILS:
    _first = _j["contact"].split()[0]
    _j["subject"] = _journalist_subject(_first, _j["beat"], _j["outlet"])
    _j["html_body"] = _journalist_body(_first, _j["outlet"], _j["beat"])


# ─── EP Press Officer email builder ──────────────────────────────────────────

COMMITTEE_NAMES = {
    "AFET": "Committee on Foreign Affairs",
    "SEDE": "Subcommittee on Security and Defence",
    "DROI": "Subcommittee on Human Rights",
    "DEVE": "Committee on Development",
    "INTA": "Committee on International Trade",
    "BUDG": "Committee on Budgets",
    "CONT": "Committee on Budgetary Control",
    "ECON": "Committee on Economic and Monetary Affairs",
    "FISC": "Subcommittee on Tax Matters",
    "EMPL": "Committee on Employment and Social Affairs",
    "HOUS": "Subcommittee on Housing",
    "ENVI": "Committee on the Environment, Public Health and Food Safety",
    "SANT": "Subcommittee on Public Health",
    "ITRE": "Committee on Industry, Research and Energy",
    "IMCO": "Committee on the Internal Market and Consumer Protection",
    "EUDS": "Subcommittee on the European Digital Space",
    "TRAN": "Committee on Transport and Tourism",
    "REGI": "Committee on Regional Development",
    "LIBE": "Committee on Civil Liberties, Justice and Home Affairs",
    "AGRI": "Committee on Agriculture and Rural Development",
    "PECH": "Committee on Fisheries",
    "CULT": "Committee on Culture and Education",
    "JURI": "Committee on Legal Affairs",
    "FEMM": "Committee on Women's Rights and Gender Equality",
    "AFCO": "Committee on Constitutional Affairs",
    "PETI": "Committee on Petitions",
}

# Dossier examples per committee for personalisation
COMMITTEE_DOSSIERS = {
    "AFET": "foreign policy instruments, neighbourhood policy, and EU external action",
    "SEDE": "the European Defence Industrial Strategy, dual-use regulation, and PESCO",
    "DROI": "human rights instruments and democracy support",
    "DEVE": "development cooperation, humanitarian aid, and the Neighbourhood, Development and International Cooperation Instrument",
    "INTA": "trade agreements, trade defence instruments, CBAM, and investment screening",
    "BUDG": "the EU budget, MFF, and financial regulation",
    "CONT": "EU budget discharge, fraud prevention, and OLAF oversight",
    "ECON": "PSD3, MiCA, DORA, Banking Union, AML packages, and Solvency II",
    "FISC": "tax harmonisation, BEFIT, and anti-tax avoidance directives",
    "EMPL": "platform work directive, social rights, and labour mobility",
    "HOUS": "housing affordability and urban development policy",
    "ENVI": "the Green Deal, Fit for 55, ETS reform, REACH, and circular economy regulation",
    "SANT": "the pharmaceutical package, EHDS, HTA regulation, and Critical Medicines Act",
    "ITRE": "the AI Act, Data Act, Chips Act, and EU industrial strategy",
    "IMCO": "DSA/DMA enforcement, product safety, and single market regulation",
    "EUDS": "digital services regulation and platform governance",
    "TRAN": "transport decarbonisation, TEN-T, and aviation regulation",
    "REGI": "cohesion policy, structural funds, and territorial development",
    "LIBE": "migration policy, asylum reform, Schengen governance, and fundamental rights",
    "AGRI": "CAP reform, food safety, and rural development",
    "PECH": "Common Fisheries Policy, sustainable fishing, and maritime governance",
    "CULT": "media regulation, copyright, and cultural policy",
    "JURI": "corporate due diligence, AI liability, and intellectual property",
    "FEMM": "gender equality directives and anti-discrimination legislation",
    "AFCO": "EU treaty reform, institutional governance, and electoral law",
    "PETI": "citizens' petitions and EU ombudsman oversight",
}


def _ep_press_body(first_name: str, committees: list[str]) -> str:
    primary = committees[0]
    committee_full = COMMITTEE_NAMES.get(primary, primary)
    codes = "/".join(committees)

    if len(committees) > 1:
        all_names = " and the ".join(COMMITTEE_NAMES.get(c, c) for c in committees)
        committee_ref = f"the {all_names} ({codes})"
    else:
        committee_ref = f"the {committee_full} ({codes})"

    dossiers = COMMITTEE_DOSSIERS.get(primary, "key EU legislative files")

    return _wrap_html(
        f'<p {_P}>Dear {first_name},</p>\n\n'
        f'<p {_P}>I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an '
        f'AI-powered EU legislative intelligence platform built in Brussels.</p>\n\n'
        f'<p {_P}>I\'m writing because Brubru tracks the work of {committee_ref} '
        f'in real-time, including ongoing procedures, rapporteur assignments, and '
        f'legislative timelines. For dossiers like {dossiers}, our platform provides '
        f'committee-level updates as they happen.</p>\n\n'
        f'<p {_P}>A few capabilities that might be relevant for your press work:</p>\n\n'
        f'<ul {_UL}>\n'
        f'<li><strong>Committee work monitoring:</strong> tracks all 26 EP committees\' '
        f'work in progress with procedure references, lead MEPs, and status updates.</li>\n'
        f'<li><strong>Legislative predictions:</strong> AI-powered outcome predictions '
        f'for legislative files, including EP group position breakdowns and timeline forecasts.</li>\n'
        f'<li><strong>Amendment intelligence:</strong> drafts amendments in Akoma Ntoso XML '
        f'(the EU institutional standard) and analyses existing amendment sets with political '
        f'group breakdown.</li>\n'
        f'<li><strong>Instant policy briefings:</strong> generates MEP briefings, talking '
        f'points, or procedure summaries on demand.</li>\n'
        f'</ul>\n\n'
        f'<p {_P}>I\'d be happy to show you how Brubru could complement {codes}\'s '
        f'press operations. You can also try it directly at '
        f'<a href="https://brubru.beresol.eu" style="color:#0693e3;text-decoration:none;">'
        f'brubru.beresol.eu</a>.</p>'
    )


def _ep_press_subject(committees: list[str]) -> str:
    codes = "/".join(committees)
    return f"Brubru: AI tool tracking {codes} committee work in real-time"


# ─── EP Press Officer email data ─────────────────────────────────────────────

EP_PRESS_EMAILS = [
    # Head of Unit
    {"segment": "ep-press", "contact": "Neil Corlett",
     "email": "neil.corlett@europarl.europa.eu", "committees": ["AFET"],
     "confidence": "CONFIRMED", "role": "Head of Unit"},
    # Editorial Coordinators
    {"segment": "ep-press", "contact": "Federico De Girolamo",
     "email": "federico.degirolamo@europarl.europa.eu", "committees": ["AFET"],
     "confidence": "CONFIRMED", "role": "Editorial Coordinator (Italian)"},
    {"segment": "ep-press", "contact": "Andreas Kleiner",
     "email": "andreas.kleiner@europarl.europa.eu", "committees": ["AFET"],
     "confidence": "CONFIRMED", "role": "Editorial Coordinator (German)"},
    {"segment": "ep-press", "contact": "Estefania Narrillos",
     "email": "estefania.narrillos@europarl.europa.eu", "committees": ["AFET"],
     "confidence": "CONFIRMED", "role": "Editorial Coordinator (Spanish)"},
    # Press Officers by Committee
    {"segment": "ep-press", "contact": "Viktor Almqvist",
     "email": "viktor.almqvist@europarl.europa.eu", "committees": ["AFET", "SEDE"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Snjezana Kobescak Modis",
     "email": "snjezana.kobescak@europarl.europa.eu", "committees": ["AFET", "SEDE"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Elodie Laborie",
     "email": "elodie.laborie@europarl.europa.eu", "committees": ["DROI"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Eoghan Walsh",
     "email": "eoghan.walsh@europarl.europa.eu", "committees": ["DEVE"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Lieven Cosijn",
     "email": "lieven.cosijn@europarl.europa.eu", "committees": ["INTA"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Eszter Zalan",
     "email": "eszter.zalan@europarl.europa.eu", "committees": ["BUDG"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Janis Krastins",
     "email": "janis.krastins@europarl.europa.eu", "committees": ["CONT"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "John Schranz",
     "email": "john.schranz@europarl.europa.eu", "committees": ["ECON", "FISC"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Dorota Kolinska",
     "email": "dorota.kolinska@europarl.europa.eu", "committees": ["ECON"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Arianne Sikken",
     "email": "arianne.sikken@europarl.europa.eu", "committees": ["EMPL", "HOUS"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Thomas Haahr",
     "email": "thomas.haahr@europarl.europa.eu", "committees": ["ENVI"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Dana Popp",
     "email": "dana.popp@europarl.europa.eu", "committees": ["ENVI", "SANT"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Baptiste Chatain",
     "email": "baptiste.chatain@europarl.europa.eu", "committees": ["ITRE"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Yasmina Yakimova",
     "email": "yasmina.yakimova@europarl.europa.eu", "committees": ["IMCO", "EUDS"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Maris Kurme",
     "email": "maris.kurme@europarl.europa.eu", "committees": ["IMCO"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Gediminas Vilkas",
     "email": "gediminas.vilkas@europarl.europa.eu", "committees": ["TRAN"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Janne Ojamo",
     "email": "janne.ojamo@europarl.europa.eu", "committees": ["REGI", "LIBE"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Hana Raissi",
     "email": "hana.raissi@europarl.europa.eu", "committees": ["AGRI"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Raquel Ramalho Lopes",
     "email": "raquel.lopes@europarl.europa.eu", "committees": ["PECH", "CULT"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Martina Vass",
     "email": "martina.vass@europarl.europa.eu", "committees": ["JURI"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Polona Tedesko",
     "email": "polona.tedesko@europarl.europa.eu", "committees": ["LIBE", "FEMM"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Kyriakos Klosidis",
     "email": "kyriakos.klosidis@europarl.europa.eu", "committees": ["LIBE", "AFCO", "EUDS"],
     "confidence": "CONFIRMED"},
    {"segment": "ep-press", "contact": "Alessio Incorvaia",
     "email": "alessio.incorvaia@europarl.europa.eu", "committees": ["PETI", "HOUS"],
     "confidence": "CONFIRMED"},
]

# Build subject + html_body for each EP press officer
for _ep in EP_PRESS_EMAILS:
    _first = _ep["contact"].split()[0]
    _ep["subject"] = _ep_press_subject(_ep["committees"])
    _ep["html_body"] = _ep_press_body(_first, _ep["committees"])


# ─── Trade Association email builder ─────────────────────────────────────────

def _trade_assoc_body(first_name: str, org_name: str, hook: str,
                      features: list[str]) -> str:
    features_html = "\n".join(f"<li>{f}</li>" for f in features)
    return _wrap_html(
        f'<p {_P}>Dear {first_name},</p>\n\n'
        f'<p {_P}>{hook}</p>\n\n'
        f'<p {_P}>Brubru provides:</p>\n\n'
        f'<ul {_UL}>\n{features_html}\n</ul>\n\n'
        f'<p {_P}>For an organisation managing as many EU dossiers as {org_name}, '
        f'Brubru provides the systematic monitoring layer that frees your policy '
        f'team for strategic work.</p>\n\n'
        f'<p {_P}>Would a 15-minute demo be useful? You can also try it directly at '
        f'<a href="https://brubru.beresol.eu" style="color:#0693e3;text-decoration:none;">'
        f'brubru.beresol.eu</a>.</p>'
    )


# ─── Trade Association email data ────────────────────────────────────────────

TRADE_ASSOC_EMAILS = [
    {
        "segment": "trade-associations",
        "org": "DIGITALEUROPE",
        "contact": "Gabriel Daia",
        "email": "gabriel.daia@digitaleurope.org",
        "confidence": "HIGH",
        "subject": "DIGITALEUROPE: AI-powered EU digital regulation intelligence",
        "html_body": _trade_assoc_body(
            "Gabriel", "DIGITALEUROPE",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. DIGITALEUROPE "
            "tracks the most complex digital regulation dossiers in the EU, from the "
            "AI Act to DSA/DMA, Data Act, and Cyber Resilience Act. Brubru was built "
            "precisely for this kind of multi-dossier monitoring.",
            [
                "<strong>AI Act and digital regulation:</strong> tracks AI Act delegated acts, DSA/DMA enforcement, Data Act implementation, and CRA in real-time with committee-level updates.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any legislative procedure, with political group analysis and alignment comparison against your positions.",
                "<strong>Policy briefing generation:</strong> drafts consultation responses, position papers, and MEP briefings from live legislative data.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings with deep-links to tracked files.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "DIGITALEUROPE",
        "contact": "Cecilia Bonefeld-Dahl",
        "email": "cecilia.bonefeld-dahl@digitaleurope.org",
        "confidence": "HIGH",
        "subject": "Brubru: AI-powered legislative intelligence for DIGITALEUROPE",
        "html_body": _trade_assoc_body(
            "Cecilia", "DIGITALEUROPE",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. Managing "
            "DIGITALEUROPE's advocacy across AI Act, DSA/DMA, Data Act, CRA, and "
            "the broader digital regulation landscape requires systematic monitoring "
            "of dozens of active procedures simultaneously.",
            [
                "<strong>Digital regulation tracking:</strong> monitors the AI Act, DSA/DMA, Data Act, CRA, and related dossiers with real-time updates from EP committees, Council, and Commission.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis &mdash; useful for identifying allies and tracking opposition.",
                "<strong>Document generation:</strong> drafts position papers, MEP briefings, talking points, and consultation responses tailored to your policy objectives.",
                "<strong>Consultation tracking:</strong> monitors the EC &lsquo;Have Your Say&rsquo; portal with upcoming deadlines across all digital policy areas.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "EBF",
        "contact": "Wim Mijs",
        "email": "w.mijs@ebf.eu",
        "confidence": "HIGH",
        "subject": "EBF: AI-powered EU financial regulation intelligence",
        "html_body": _trade_assoc_body(
            "Wim", "EBF",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. The EBF manages "
            "advocacy across an exceptionally wide range of financial services "
            "dossiers &mdash; from Banking Union and AML packages to MiCA, DORA, and "
            "PSD3/PSR. Brubru tracks all of these systematically.",
            [
                "<strong>Financial regulation tracking:</strong> monitors PSD3/PSR, MiCA, DORA, Banking Union, AML packages, Solvency II, and related dossiers with real-time updates.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ECON and related procedures with political group analysis.",
                "<strong>Document generation:</strong> drafts consultation responses, position papers, and MEP briefings from live legislative data.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council ECOFIN, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "EBF",
        "contact": "R. Barthet",
        "email": "r.barthet@ebf.eu",
        "confidence": "HIGH",
        "subject": "EBF: EU banking regulation intelligence powered by AI",
        "html_body": _trade_assoc_body(
            "R.", "EBF",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. I\'m reaching out "
            "because Brubru tracks the full range of EU financial services regulation "
            "that the EBF covers, from Banking Union and AML to digital finance.",
            [
                "<strong>Financial regulation tracking:</strong> monitors PSD3/PSR, MiCA, DORA, Banking Union, AML packages, and related dossiers in real-time.",
                "<strong>Policy briefing generation:</strong> drafts consultation responses, position papers, and talking points from live legislative data.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any legislative procedure with political group analysis.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council meetings, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "ACEA",
        "contact": "Massimiliano Vascotto",
        "email": "mva@acea.auto",
        "confidence": "HIGH",
        "subject": "ACEA: AI-powered EU automotive regulation intelligence",
        "html_body": _trade_assoc_body(
            "Massimiliano", "ACEA",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. ACEA\'s advocacy "
            "spans CO2 standards, Euro 7, ETS2, e-mobility regulation, and automotive "
            "supply chain dossiers &mdash; all files that Brubru monitors systematically.",
            [
                "<strong>Automotive regulation tracking:</strong> monitors CO2 standards, Euro 7, ETS2, e-mobility, and related dossiers with committee-level updates.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ENVI, ITRE, and TRAN procedures with political group analysis.",
                "<strong>Document generation:</strong> drafts consultation responses, position papers, and MEP briefings tailored to your policy objectives.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council TTE, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "ACEA",
        "contact": "Camille Lamarque",
        "email": "cl@acea.auto",
        "confidence": "HIGH",
        "subject": "ACEA: EU automotive policy intelligence powered by AI",
        "html_body": _trade_assoc_body(
            "Camille", "ACEA",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. I\'m reaching out "
            "because Brubru tracks the automotive regulatory dossiers ACEA covers, "
            "from CO2 standards and Euro 7 to ETS2 and electrification policy.",
            [
                "<strong>Automotive regulation tracking:</strong> monitors CO2 standards, Euro 7, ETS2, and e-mobility regulation in real-time.",
                "<strong>Legislative monitoring:</strong> tracks 500+ EU files across transport, environmental, and industrial dossiers.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for any procedure with political group analysis.",
                "<strong>Policy briefing generation:</strong> drafts position papers, MEP briefings, and consultation responses from live data.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "Concawe/FuelsEurope",
        "contact": "Alain Mathuren",
        "email": "alain@concawe.eu",
        "confidence": "MEDIUM",
        "subject": "FuelsEurope: AI-powered EU energy regulation intelligence",
        "html_body": _trade_assoc_body(
            "Alain", "FuelsEurope",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. FuelsEurope\'s "
            "advocacy covers fuel regulation, refining policy, and the broader Fit "
            "for 55 package &mdash; dossiers that Brubru tracks in real-time.",
            [
                "<strong>Energy regulation tracking:</strong> monitors Fit for 55, ETS reform, fuel quality directives, and renewable energy regulation.",
                "<strong>Consultation monitoring:</strong> tracks the EC &lsquo;Have Your Say&rsquo; portal with upcoming energy policy deadlines.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ENVI and ITRE procedures with political group analysis.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council TTE, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "GSMA Europe",
        "contact": "Elsa Sependa",
        "email": "gsmaeurope@gsma.com",
        "confidence": "MEDIUM",
        "subject": "GSMA Europe: AI-powered EU digital and telecom regulation intelligence",
        "html_body": _trade_assoc_body(
            "Elsa", "GSMA Europe",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. GSMA Europe\'s "
            "policy work on connectivity, spectrum regulation, and the Digital "
            "Networks Act covers some of the EU's most active digital dossiers.",
            [
                "<strong>Telecom and digital regulation:</strong> monitors the Digital Networks Act, spectrum regulation, connectivity policy, and related dossiers.",
                "<strong>Legislative monitoring:</strong> tracks 500+ EU files across digital, industrial, and trade dossiers.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ITRE and IMCO procedures with political group analysis.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council TTE, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "CEFIC",
        "contact": "Marco Mensink",
        "email": "mvo@cefic.be",
        "confidence": "HIGH",
        "subject": "CEFIC: AI-powered EU chemicals and sustainability regulation intelligence",
        "html_body": _trade_assoc_body(
            "Marco", "CEFIC",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. CEFIC\'s advocacy "
            "spans REACH, CLP, PFAS restriction, industrial emissions, and the broader "
            "Green Deal package &mdash; an exceptionally wide regulatory landscape.",
            [
                "<strong>Chemicals and sustainability tracking:</strong> monitors REACH revision, CLP, PFAS restriction proposals, IED, and related Green Deal files.",
                "<strong>Consultation monitoring:</strong> tracks the EC &lsquo;Have Your Say&rsquo; portal with upcoming chemicals and environmental policy deadlines.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ENVI procedures with political group analysis.",
                "<strong>Document generation:</strong> drafts consultation responses, position papers, and MEP briefings from live legislative data.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "EFPIA",
        "contact": "Nathalie Moll",
        "email": "reception@efpia.eu",
        "confidence": "LOW",
        "subject": "EFPIA: AI-powered EU pharmaceutical regulation intelligence",
        "html_body": _trade_assoc_body(
            "Nathalie", "EFPIA",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. EFPIA manages "
            "advocacy across the pharmaceutical legislation revision, EHDS, HTA "
            "Regulation, Critical Medicines Act, SPC reform, and IP policy &mdash; "
            "dossiers that Brubru tracks systematically.",
            [
                "<strong>Pharmaceutical regulation tracking:</strong> monitors the pharma package revision, EHDS, HTA Regulation, Critical Medicines Act, and related dossiers.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ENVI and ITRE procedures with political group analysis.",
                "<strong>Document generation:</strong> drafts consultation responses, position papers, and MEP briefings from live legislative data.",
                "<strong>EU Calendar:</strong> unified calendar covering EP plenary, Council EPSCO, and Commission college meetings.",
            ],
        ),
    },
    {
        "segment": "trade-associations",
        "org": "MedTech Europe",
        "contact": "Oliver Bisazza",
        "email": "info@medtecheurope.org",
        "confidence": "LOW",
        "subject": "MedTech Europe: AI-powered EU health regulation intelligence",
        "html_body": _trade_assoc_body(
            "Oliver", "MedTech Europe",
            "I\'m Victor Sol&eacute; Ferioli, founder of Brubru &mdash; an AI-powered "
            "EU legislative intelligence platform built in Brussels. MedTech Europe "
            "covers MDR, IVDR, EHDS, the AI Act\'s health provisions, and related "
            "dossiers &mdash; a complex regulatory landscape that Brubru monitors "
            "in real-time.",
            [
                "<strong>Health regulation tracking:</strong> monitors MDR, IVDR, EHDS, AI Act health provisions, HTA Regulation, and related dossiers.",
                "<strong>Legislative monitoring:</strong> tracks 500+ EU files with updates from EP committees, Council, and Commission.",
                "<strong>Amendment intelligence:</strong> fetches all MEP amendments for ENVI and ITRE procedures with political group analysis.",
                "<strong>Document generation:</strong> drafts consultation responses and position papers from live legislative data.",
            ],
        ),
    },
]


# ─── Combined list + helpers ─────────────────────────────────────────────────

ALL_EMAILS = JOURNALIST_EMAILS + EP_PRESS_EMAILS + TRADE_ASSOC_EMAILS

SEGMENT_MAP = {
    "journalists": JOURNALIST_EMAILS,
    "ep-press": EP_PRESS_EMAILS,
    "trade-associations": TRADE_ASSOC_EMAILS,
}


def _filter_emails(segment: str = None) -> list[dict]:
    if segment:
        return SEGMENT_MAP.get(segment, [])
    return ALL_EMAILS


def preview_emails(segment: str = None):
    emails = _filter_emails(segment)
    label = segment or "all segments"

    if not emails:
        print(f"[WARN] No emails for segment '{segment}'")
        print(f"  Available segments: {', '.join(SEGMENT_MAP.keys())}")
        return

    print(f"\n{'='*60}")
    print(f"  BRUSSELS CAMPAIGN EMAILS - Preview ({label})")
    print(f"  {len(emails)} email(s)")
    print(f"{'='*60}\n")

    for i, e in enumerate(emails, 1):
        seg = e.get("segment", "?")
        org = e.get("outlet") or e.get("org") or ""
        print(f"  {i}. [{seg}] {org}")
        print(f"     To: {e['contact']} <{e['email']}>")
        print(f"     Subject: {e['subject']}")
        print(f"     Confidence: {e.get('confidence', 'N/A')}")
        print()


def send_emails(segment: str = None, dry_run: bool = False):
    service = get_email_service()
    emails = _filter_emails(segment)
    label = segment or "all segments"

    if not emails:
        print(f"[WARN] No emails for segment '{segment}'")
        return

    if dry_run:
        print("\n[DRY RUN] No emails will actually be sent.\n")

    print(f"\n{'='*60}")
    print(f"  SENDING BRUSSELS CAMPAIGN EMAILS ({label})")
    print(f"  {len(emails)} email(s) | {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'='*60}\n")

    if not dry_run and not service.is_configured:
        print("[ERROR] SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return

    sent = 0
    failed = []

    for e in emails:
        org = e.get("outlet") or e.get("org") or e.get("segment")
        label_str = f"[{e['segment']}] {org} ({e['contact']} <{e['email']}>)"

        if dry_run:
            print(f"  [DRY-RUN] Would send to {label_str}")
            print(f"            Subject: {e['subject']}")
            sent += 1
        else:
            print(f"  [SENDING] {label_str}...")
            success = service.send(
                to=e["email"],
                subject=e["subject"],
                html_body=e["html_body"],
            )
            if success:
                print(f"  [OK] Sent to {e['contact']}")
                sent += 1
            else:
                print(f"  [FAILED] {e['contact']} ({e['email']})")
                failed.append(f"{e['contact']} ({e['email']})")

            # 2-second delay between sends
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {sent} sent, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Send Brussels EU Bubble campaign emails")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without sending")
    group.add_argument("--send", action="store_true", help="Actually send the emails")
    group.add_argument("--preview", action="store_true", help="Show email summary only")
    parser.add_argument("--segment", choices=["journalists", "ep-press", "trade-associations"],
                        help="Filter by segment")
    args = parser.parse_args()

    if args.preview:
        preview_emails(segment=args.segment)
    elif args.dry_run:
        send_emails(segment=args.segment, dry_run=True)
    elif args.send:
        send_emails(segment=args.segment, dry_run=False)


if __name__ == "__main__":
    main()
