"""
Seed Joan Maria Piqué (ACM Brussels Office) - complete onboarding bundle.

Creates the user account, attaches 7 priority legislative carriages + 1 adopted text
to his My EU Bubble → My Files, seeds 6 MEUB Documents pre-filled with substantive
draft content, and flips his private_guide pointer to acm-catalonia (synced
separately via sync_private_guides_to_db.py).

Usage:
    cd backend && python3.12 scripts/seed_jmp_acm.py            # dry-run
    cd backend && python3.12 scripts/seed_jmp_acm.py --apply    # write DB

Idempotent: re-runs skip rows that already exist for this user.
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from passlib.context import CryptContext
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(f"{_REPO_ROOT}/.env")

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


USER_EMAIL = "jmp@bassons.eu"
USER_PASSWORD = "JMPBrubru2026"
USER_FULL_NAME = "Joan Maria Piqué"
USER_FIRST_NAME = "Joan"
USER_PREFERRED_NAME = "Joan"
USER_ORG = "Associació Catalana de Municipis (ACM)"
USER_ROLE_TITLE = "Deputy Head of the Brussels Office"
USER_COUNTRY = "ES"
USER_LANGUAGE = "ca"
USER_TIMEZONE = "Europe/Brussels"
POLICY_INTERESTS = [
    "Cohesion",
    "Affordable Housing",
    "Local Government",
    "Energy",
    "Digital",
    "Migration",
]
PRIVATE_GUIDE_SLUG = "acm-catalonia"

# Expiry: 21 June 2026 23:59:59 UTC. After this, run
# scripts/downgrade_expired_subscriptions.py (or set up a cron) to flip
# subscription_tier to 'white' automatically.
SUBSCRIPTION_TIER = "blue"
SUBSCRIPTION_EXPIRES_AT = datetime(2026, 6, 21, 23, 59, 59, tzinfo=timezone.utc)


# Legislative carriages to attach to My Files (probed from prod DB 21 May 2026).
CARRIAGE_IDS = [
    "58d04f72-eu-affordable-housing-plan",  # COM(2025)1025 - placeholder, look up real UUID
    "4225c61e-housing-crisis-resolution",
    "62d0985e-mff-2028-2034-interim",
    "f4c25c94-cohesion-driving-force-cities",
    "3825f225-esf-plus",
    "e7995162-epbd-revision",
    "fc5fac1e-accelerate-eu-energy-union",
]

# At runtime we resolve these by partial UUID match (first 8 chars are the
# canonical short id; the rest after the hyphen is just a human label).
CARRIAGE_SHORT_IDS = [c.split("-", 1)[0] for c in CARRIAGE_IDS]

ADOPTED_TEXT_SHORT_IDS = [
    "30dd2808",  # P10_TA(2026)0064 - Housing crisis resolution
]


# Six MEUB Documents pre-loaded into Joan's Documents tab. Each one has real,
# substantive draft content so Brubru chat can quote from them.
DOCUMENTS = [
    {
        "title": "ACM Position on the European Affordable Housing Plan (DRAFT)",
        "document_type": "analysis",
        "policy_areas": ["Affordable Housing", "Cohesion"],
        "tags": ["acm-position", "housing", "eahp", "draft"],
        "celex_number": None,
        "procedure_reference": "COM(2025)1025",
        "include_in_ai_context": True,
        "executive_summary": (
            "ACM welcomes the European Affordable Housing Plan as the first comprehensive EU "
            "framework for housing policy and calls on the Commission to translate the December "
            "2025 communication into a binding instrument by Q1 2027. Catalan municipalities, "
            "with the AMB metropolitan housing operator and the Catalan Energy Pact, are ready to "
            "be implementation partners provided three conditions are met: (a) cohesion-fund "
            "delivery channels remain open directly to municipalities, (b) State-aid rules treat "
            "affordable housing as long-term investment under the modernised fiscal framework, "
            "and (c) planning, land-use and short-term-rental regulation remain in local hands."
        ),
        "content": (
            "## ACM Position on the European Affordable Housing Plan\n\n"
            "**Draft for internal review - not for distribution. Updated 21 May 2026.**\n\n"
            "### 1. Executive summary\n\n"
            "The European Affordable Housing Plan (EAHP), presented by the Commission as "
            "COM(2025) 1025 final on 16 December 2025 under Commissioner Dan Jorgensen, is the "
            "first EU strategy that treats housing as a shared responsibility across governance "
            "levels. The Associació Catalana de Municipis (ACM), representing over 1,000 Catalan "
            "local entities, welcomes the plan and calls for its rapid translation into binding "
            "instruments by the first quarter of 2027.\n\n"
            "Catalan municipalities are already operating at the frontier of European housing "
            "policy. The Àrea Metropolitana de Barcelona has launched a public housing operator "
            "(Habitatge Metròpolis Barcelona). The Catalan Energy Pact integrates housing "
            "renovation, energy poverty and local renewable production. The Generalitat has "
            "designated stressed-rental zones under Spanish Law 12/2023.\n\n"
            "These instruments work, but they remain capped by three EU-level constraints. ACM "
            "wants the EAHP follow-up to address all three.\n\n"
            "### 2. Three priority asks\n\n"
            "**Ask 1 - Direct municipal access to cohesion-fund housing finance.** The post-2027 "
            "Multiannual Financial Framework (file 2025/0571R(APP)) and the ERDF Regulation "
            "successor (currently 32021R1058) should preserve direct programming routes to "
            "municipalities, with at least a 15 percent of the urban envelope earmarked for "
            "affordable housing operations. The cohesion-policy-as-driving-force report (EP "
            "2026/2027(INI)) is the right vehicle for this earmark.\n\n"
            "**Ask 2 - State-aid modernisation for Services of General Economic Interest.** The "
            "2012 SGEI Decision (32012D0021) treats social housing as a narrow category limited "
            "to disadvantaged citizens. The EAHP follow-up should broaden the SGEI definition to "
            "match the demographic reality of housing stress in mid-income urban Europe, and the "
            "modernised fiscal rules should treat affordable-housing investment as long-term "
            "capital expenditure rather than ordinary expenditure.\n\n"
            "**Ask 3 - Preserve municipal planning competence.** Land-use, urban planning and "
            "short-term-rental regulation are constitutionally local matters in Spain and "
            "Catalonia. EU action should focus on financing, framework standards and skills, not "
            "on harmonising planning procedures.\n\n"
            "### 3. Catalan delivery examples ACM offers as implementation partners\n\n"
            "- Habitatge Metròpolis Barcelona - metropolitan public housing operator with a "
            "20-year programme to build and operate 4,500 social rental units.\n"
            "- The AMB land-bank - over 35 hectares of municipal land mobilised for affordable "
            "housing through public-private development partnerships.\n"
            "- La Garriga Energy Community (in the home town of ACM President Meritxell Budó) - "
            "small-municipality model for renewable energy communities under Directive (EU) "
            "2023/2413.\n"
            "- The Catalan Energy Pact - multi-level governance framework integrating Generalitat, "
            "AMB, ACM members and Catalan utilities on renovation and energy poverty.\n\n"
            "### 4. Procedural calendar\n\n"
            "- EP HOUS committee report (A10-0025/2026) adopted 10 March 2026, plenary vote 367 / "
            "166 / 84, recorded as P10_TA(2026)0064.\n"
            "- CEMR position paper 'A local plan for housing', published 10 March 2026.\n"
            "- Commission legislative follow-up package expected Q4 2026 - Q1 2027.\n"
            "- Council formal conclusions expected late 2026 under the Belgian and Polish "
            "presidencies.\n\n"
            "### 5. Recommended ACM action over the next 90 days\n\n"
            "1. Joint paper with CEMR, AER and Eurocities to harmonise the local-authority "
            "position before the legislative follow-up package.\n"
            "2. Bilateral meeting requests with DG REGIO Unit B.1, DG ENER Housing Task Force, "
            "Commissioner Jorgensen's cabinet, and the EP HOUS committee secretariat.\n"
            "3. CoR opinion on the EAHP - push for a Catalan rapporteur via the ES delegation.\n"
            "4. ACM Brussels Office launch event Q3 2026, ideally tied to the EU City Lab on "
            "Housing (Brussels, 15-16 October 2026).\n"
        ),
    },
    {
        "title": "Written question to the Commission - Direct municipal access to EU housing finance (DRAFT)",
        "document_type": "note",
        "policy_areas": ["Affordable Housing", "Cohesion"],
        "tags": ["written-question", "housing", "draft", "regi"],
        "celex_number": None,
        "procedure_reference": "COM(2025)1025",
        "include_in_ai_context": True,
        "content": (
            "## Question for written answer P-XXXXX/2026 - to the Commission\n\n"
            "**Draft to be tabled by a Catalan MEP on the REGI or EMPL committee.**\n\n"
            "**Subject**: Direct municipal access to EU housing finance under the post-2027 "
            "cohesion architecture.\n\n"
            "**Rule 138 of the Rules of Procedure**\n\n"
            "On 16 December 2025 the Commission presented the European Affordable Housing Plan "
            "(COM(2025) 1025 final), the first comprehensive EU strategy on housing. On 10 March "
            "2026 the European Parliament adopted, by 367 votes to 166, resolution "
            "P10_TA(2026)0064 calling for an EU-level intervention on housing supply, finance and "
            "skills, with explicit references to the role of local and regional authorities as "
            "primary implementers.\n\n"
            "In Catalonia, the over 1,000 municipalities represented by the Associació Catalana "
            "de Municipis (ACM) are the operational owners of social-housing land-banks, "
            "metropolitan housing operators (Habitatge Metròpolis Barcelona) and energy-renovation "
            "one-stop shops under Directive (EU) 2024/1275. Their capacity to deliver, however, "
            "depends on whether the post-2027 Multiannual Financial Framework (file "
            "2025/0571R(APP)) and the successor to the ERDF Regulation (currently Regulation (EU) "
            "2021/1058) preserve direct programming routes to municipal authorities.\n\n"
            "Can the Commission therefore answer:\n\n"
            "1. Will the housing-finance follow-up legislative package planned for Q4 2026 - Q1 "
            "2027 include a dedicated cohesion-policy strand earmarked for housing operations "
            "delivered by local authorities, and at what indicative share of the urban envelope?\n\n"
            "2. Will the Commission revise Decision 2012/21/EU on Services of General Economic "
            "Interest to broaden the eligibility of affordable housing operations beyond the "
            "narrow category of disadvantaged citizens, in line with the demographic reality of "
            "housing stress in mid-income urban Europe?\n\n"
            "3. Under the modernised fiscal rules adopted in 2024, will affordable-housing "
            "investment by local authorities be treated as long-term capital expenditure rather "
            "than ordinary expenditure for the purpose of the national net-expenditure path "
            "calculation?\n\n"
            "4. Does the Commission intend to consult formally with the European associations of "
            "local authorities (CEMR, AER, Eurocities) and with national associations such as the "
            "Associació Catalana de Municipis during the preparation of the follow-up package?\n"
        ),
    },
    {
        "title": "Motion for a CEMR Policy Committee resolution - A local plan for affordable housing in Catalonia (DRAFT)",
        "document_type": "strategy",
        "policy_areas": ["Affordable Housing", "Cohesion", "Local Government"],
        "tags": ["resolution", "cemr", "housing", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "include_in_ai_context": True,
        "objectives": (
            "Position the Associació Catalana de Municipis as a substantive contributor to CEMR's "
            "housing-policy work, anchor the CEMR 10 March 2026 position paper 'A local plan for "
            "housing' with Catalan operational examples, and obtain a CoR rapporteur slot for the "
            "Affordable Housing Plan opinion."
        ),
        "action_plan": (
            "1. Table the motion at the next CEMR Policy Committee meeting.\n"
            "2. Secure co-signatories from at least three large CEMR member federations.\n"
            "3. Brief Catalan CoR members on the motion ahead of the next CoR ECON commission.\n"
            "4. Coordinate with FEMP (Spanish federation) so the Catalan and Spanish lines align."
        ),
        "timeline": "Submitted to CEMR secretariat: 30 June 2026. Policy Committee vote: Q3 2026.",
        "stakeholders": [
            "CEMR Policy Committee",
            "FEMP (Federación Española de Municipios y Provincias)",
            "Committee of the Regions - ECON commission",
            "Eurocities housing forum",
            "AER housing working group",
        ],
        "content": (
            "## Motion for a CEMR Policy Committee resolution\n\n"
            "**A local plan for affordable housing in Catalonia - building on the CEMR 10 March "
            "2026 position paper.**\n\n"
            "Tabled by the Associació Catalana de Municipis (ACM) through its member "
            "representatives. Draft for review by the CEMR Policy Committee.\n\n"
            "### Recital\n\n"
            "The CEMR Policy Committee, having regard to its position paper 'A local plan for "
            "housing' of 10 March 2026, the European Affordable Housing Plan (COM(2025) 1025 "
            "final) of 16 December 2025, the European Parliament resolution P10_TA(2026)0064 of "
            "10 March 2026, and the European Charter of Local Self-Government (Council of Europe, "
            "ETS 122),\n\n"
            "### Considerations\n\n"
            "A. whereas Catalonia operates Habitatge Metròpolis Barcelona, a metropolitan housing "
            "operator backed by the over-1,000-member Associació Catalana de Municipis, with a "
            "20-year programme to deliver 4,500 social rental units;\n\n"
            "B. whereas the Catalan Energy Pact integrates housing renovation, energy poverty "
            "mitigation and local renewable production in a multi-level governance framework that "
            "includes the Generalitat, the Àrea Metropolitana de Barcelona, ACM members and "
            "Catalan utilities;\n\n"
            "C. whereas Spanish Law 12/2023 has empowered Catalan municipalities to designate "
            "stressed-rental zones, demonstrating that local-level rental regulation can complement "
            "EU-level financial instruments;\n\n"
            "D. whereas the post-2027 cohesion architecture and the modernised State-aid framework "
            "must be designed in dialogue with the local level if they are to deliver housing on "
            "the ground;\n\n"
            "### The CEMR Policy Committee:\n\n"
            "1. Endorses the operational examples set out by the Associació Catalana de Municipis "
            "and invites CEMR member federations to share comparable national experiences ahead of "
            "the Commission's legislative follow-up package;\n\n"
            "2. Calls on the Commission to ringfence at least 15 percent of the post-2027 urban "
            "ERDF envelope for affordable-housing operations delivered by local authorities;\n\n"
            "3. Calls on the Commission to revise Decision 2012/21/EU on Services of General "
            "Economic Interest to broaden the eligibility of affordable housing operations;\n\n"
            "4. Calls on the Council to treat affordable-housing investment as long-term capital "
            "expenditure under the modernised fiscal rules;\n\n"
            "5. Requests that the Committee of the Regions appoint a rapporteur from a Catalan "
            "municipality for its opinion on the European Affordable Housing Plan;\n\n"
            "6. Instructs the CEMR Secretary General to transmit this resolution to the Commission, "
            "the Parliament, the Council and the Committee of the Regions.\n"
        ),
    },
    {
        "title": "Email to Dragos Benea (REGI Chair) - request for an introductory meeting (DRAFT)",
        "document_type": "note",
        "policy_areas": ["Cohesion", "Local Government"],
        "tags": ["email-draft", "regi", "outreach", "draft"],
        "celex_number": None,
        "procedure_reference": "2026/2027(INI)",
        "include_in_ai_context": True,
        "content": (
            "## Email draft - to Mr Dragos Benea MEP, REGI Chair\n\n"
            "**To**: dragos.benea@europarl.europa.eu (also CC: REGI secretariat regi-secretariat@europarl.europa.eu)\n"
            "**From**: jmp@acm.cat (Joan Maria Piqué, Deputy Head, ACM Brussels Office)\n"
            "**Subject**: Introducing the ACM Brussels Office and request for an introductory meeting\n\n"
            "Dear Mr Benea,\n\n"
            "I am writing to introduce the new Brussels Office of the Associació Catalana de "
            "Municipis (ACM), which I joined as Deputy Head on 21 May 2026 under the direction of "
            "Mr Jordi Solé, former Member of this House. ACM represents over 1,000 Catalan local "
            "entities and is opening its Brussels office in 2026 at the European House of "
            "Municipalities, with the mission of bringing Catalonia's municipal voice closer to "
            "the EU institutions.\n\n"
            "Our priority files for 2026 align directly with the REGI committee's work programme. "
            "We are following with particular attention:\n\n"
            "1. The post-2027 Multiannual Financial Framework negotiations (file "
            "2025/0571R(APP)) and the future of cohesion policy delivery routes for "
            "municipalities.\n\n"
            "2. The own-initiative report 2026/2027(INI) - Cohesion policy as the driving force "
            "in implementing the EU agenda for cities, which is of direct interest to our member "
            "municipalities.\n\n"
            "3. The legislative follow-up to the European Affordable Housing Plan (COM(2025) 1025 "
            "final), where local-authority delivery channels will be decisive.\n\n"
            "I would be grateful for the opportunity to meet you, even briefly, in the coming "
            "weeks so I can introduce ACM's positions and listen to your views on the REGI "
            "agenda. I would be happy to come to your office in Brussels or Strasbourg at your "
            "convenience.\n\n"
            "Allow me also to thank you for the leadership you have shown in chairing REGI during "
            "the current legislative session, and to express ACM's appreciation for your "
            "consistent attention to the role of local authorities in EU cohesion policy.\n\n"
            "Yours sincerely,\n\n"
            "Joan Maria Piqué\n"
            "Deputy Head of the Brussels Office\n"
            "Associació Catalana de Municipis (ACM)\n"
            "of.europa@acm.cat - +34 932 886 097\n"
        ),
    },
    {
        "title": "Talking points - first meeting with DG REGIO Unit B.1 Urban Policy (DRAFT)",
        "document_type": "strategy",
        "policy_areas": ["Cohesion", "Local Government", "Affordable Housing"],
        "tags": ["talking-points", "dg-regio", "urban-policy", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "include_in_ai_context": True,
        "objectives": (
            "Open a working channel between ACM and DG REGIO Unit B.1 (Urban Policy). Position "
            "ACM as the preferred Catalan interlocutor on the urban agenda, the Affordable "
            "Housing Plan and the cohesion-policy delivery question."
        ),
        "action_plan": (
            "1. Open with ACM identity (1 minute).\n"
            "2. Present three policy points (5 minutes total).\n"
            "3. Listen - capture DG REGIO's reading of the Q3-Q4 calendar.\n"
            "4. Offer Catalan operational examples for case-study programming.\n"
            "5. Agree on a follow-up touchpoint."
        ),
        "timeline": "Meeting to be scheduled in June 2026.",
        "stakeholders": ["DG REGIO Unit B.1", "ACM Brussels Office", "ACM Presidency"],
        "content": (
            "## Talking points - first meeting with DG REGIO Unit B.1 (Urban Policy)\n\n"
            "**One-pager for Joan ahead of the June 2026 meeting. Brief in Catalan with English "
            "summary for note-takers.**\n\n"
            "### 1. Who we are (60 seconds)\n\n"
            "ACM is the largest Catalan local-government association, founded 1981, representing "
            "over 1,000 municipalities, comarques and mancomunitats. Our Brussels office, opened "
            "in 2026 at the European House of Municipalities, is directed by Jordi Solé (former "
            "MEP) and deputy-directed by Joan Maria Piqué. Our president is Meritxell Budó, mayor "
            "of La Garriga and former Catalan Minister.\n\n"
            "### 2. Three policy points\n\n"
            "**Point 1 - Cohesion policy delivery to municipalities.** ACM members care above all "
            "else that the post-2027 cohesion architecture preserves direct programming routes to "
            "the local level. Our concrete ask: a ringfence of at least 15 percent of the urban "
            "ERDF envelope for affordable-housing operations delivered by local authorities, with "
            "a managing-authority structure that does not concentrate decision-making at "
            "Member-State level. This dovetails with the EP own-initiative report 2026/2027(INI).\n\n"
            "**Point 2 - The European Affordable Housing Plan implementation.** The "
            "December 2025 Communication is welcome. The follow-up package expected Q4 2026 - Q1 "
            "2027 should: (a) broaden the SGEI definition for housing under Decision 2012/21/EU, "
            "(b) treat affordable-housing investment as long-term capital expenditure under the "
            "modernised fiscal rules, and (c) protect municipal planning competence. ACM brings "
            "operational examples: Habitatge Metròpolis Barcelona, the AMB land-bank, the Catalan "
            "Energy Pact.\n\n"
            "**Point 3 - Urban Agenda for the EU partnerships.** ACM is interested in joining or "
            "co-leading the next thematic partnership on housing or energy poverty under the "
            "Ljubljana Agreement framework. We can offer a Catalan participating city (Barcelona "
            "AMB or a representative medium-sized member like Terrassa, Sabadell, Lleida or "
            "Tarragona).\n\n"
            "### 3. What we offer DG REGIO\n\n"
            "- Case-study programming material from Catalan delivery examples.\n"
            "- Direct line into the over-1,000 municipality membership for consultation rounds.\n"
            "- Joint events in Brussels and Barcelona during the second half of 2026.\n\n"
            "### 4. Listening - what we want to hear\n\n"
            "- DG REGIO's reading of the legislative follow-up calendar for the Affordable "
            "Housing Plan.\n"
            "- The state of play on the urban dimension of the post-2027 cohesion architecture.\n"
            "- Which Member State delegations are most active or most resistant on the local "
            "delivery question.\n\n"
            "### 5. Close\n\n"
            "Agree on a follow-up touchpoint (quarterly meeting, joint event, written exchange). "
            "Offer to send the ACM Position on the European Affordable Housing Plan as a follow-up.\n"
        ),
    },
    {
        "title": "Briefing note - What Catalan municipalities can apply for in 2026 (DRAFT)",
        "document_type": "analysis",
        "policy_areas": ["Cohesion", "Affordable Housing", "Energy", "Digital", "Migration"],
        "tags": ["briefing", "funding", "tenderator", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "include_in_ai_context": True,
        "executive_summary": (
            "Tenderator-style listing of open and forthcoming EU funding calls for which Catalan "
            "municipalities are directly eligible or routinely partner. Coverage: ERDF urban "
            "windows, Cohesion Fund where applicable, AMIF (limited to Member-State channel), "
            "CEF Energy, LIFE, Horizon Europe Cluster 5, Interreg POCTEFA, URBACT, European "
            "Urban Initiative, New European Bauhaus Facility."
        ),
        "content": (
            "## Briefing note - What Catalan municipalities can apply for in 2026\n\n"
            "**Drafted for ACM members. Updated 21 May 2026. For full and current call detail, "
            "Brubru chat can answer specific questions against the live Tenderator dataset.**\n\n"
            "### Open in 2026 - direct municipal eligibility\n\n"
            "**ERDF programmes 2021-2027 (Catalonia OP and Spain Pluriregional OP)**. Live through "
            "the Generalitat managing authority. Mid-period reprogramming under way in 2026 - ACM "
            "members can still influence the rebalanced priorities.\n\n"
            "**European Urban Initiative (EUI) - Innovative Actions strand**. Calls on housing, "
            "climate transition, urban mobility, digital. Open in 2026 with deadlines in Q3 and "
            "Q4. Single-municipality eligible. Average grant 5 million EUR.\n\n"
            "**URBACT IV networks**. Knowledge-exchange networks on city policy themes. Joining "
            "the 2026 call as Lead Partner or Project Partner is light-touch and reputation-building.\n\n"
            "**CEF Energy 2026 calls**. Cross-border energy infrastructure. Catalan municipalities "
            "on the FR border (Cerdanya, Vallespir municipalities) are eligible for cross-border "
            "renewable-energy community proposals.\n\n"
            "**LIFE Programme - Climate Action and Clean Energy Transition strands**. Annual call "
            "open March-September. Municipalities lead or partner. Strong fit for water "
            "management, biodiversity, energy poverty.\n\n"
            "**Horizon Europe Cluster 5 (Climate, Energy, Mobility) and Cluster 4 (Digital)**. "
            "Municipalities participate as consortium partners or pilot sites. ACM Brussels Office "
            "can co-broker partner search through ERRIN.\n\n"
            "**Interreg POCTEFA (Spain-France-Andorra)**. 2021-2027 programme - calls roll out "
            "through 2026 on cross-border services, mobility, environment.\n\n"
            "**New European Bauhaus Facility (NEB)**. Calls on built environment, circularity, "
            "social inclusion. Open to municipalities as lead applicants.\n\n"
            "### Forthcoming in 2026 - likely to open\n\n"
            "**Social Climate Fund national plans (Spain - under preparation)**. The Fund itself "
            "runs from 2026 onwards under Regulation (EU) 2023/955; municipalities will receive "
            "pass-through funding through national mechanisms.\n\n"
            "**Recovery and Resilience Plan - revised Spanish milestones**. Commission proposal "
            "COM(2026) 0257 will reshape the calendar of measures Catalan municipalities can "
            "execute.\n\n"
            "**Affordable Housing legislative package (Q4 2026 - Q1 2027)**. Not yet a funding "
            "call - but the financing instrument it creates will be the most important post-2027 "
            "housing tool.\n\n"
            "### Indirect - Member-State channels\n\n"
            "**AMIF (Asylum, Migration and Integration Fund) - Regulation (EU) 2021/1147**. "
            "Routed via Member State; municipalities can sub-contract through Spanish national "
            "operator. ACM is pushing for a direct municipal window in the post-2027 architecture.\n\n"
            "**ESF+ - Regulation (EU) 2021/1057**. Catalan municipalities receive funding through "
            "the Generalitat managing authority and Spanish national OP.\n\n"
            "### How Brubru can help\n\n"
            "Ask Brubru questions like:\n\n"
            "- 'Which 2026 calls under LIFE are open to municipalities of fewer than 5,000 inhabitants?'\n"
            "- 'What is the application deadline for the European Urban Initiative Innovative "
            "Actions strand for housing?'\n"
            "- 'Show me Horizon Europe Cluster 5 calls where a Catalan municipality could be a "
            "pilot site.'\n\n"
            "Brubru will route those to the live Tenderator dataset and return current call detail.\n"
        ),
    },
]


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def upsert_user(db, apply: bool) -> str:
    """Create or update the Joan Maria Piqué user. Return the user UUID."""
    existing = db.execute(
        text("SELECT id::text, subscription_tier FROM users WHERE email = :e"),
        {"e": USER_EMAIL},
    ).first()
    if existing:
        logger.info(f"  [user] exists: {USER_EMAIL} (id={existing.id[:8]}, tier={existing.subscription_tier})")
        if apply:
            db.execute(
                text(
                    """
                    UPDATE users SET
                        full_name = :full_name,
                        first_name = :first_name,
                        preferred_name = :preferred_name,
                        organization = :org,
                        role_title = :role_title,
                        country = :country,
                        language = :language,
                        timezone = :tz,
                        policy_interests = CAST(:interests AS JSONB),
                        subscription_tier = :tier,
                        subscription_expires_at = :expires_at,
                        is_active = true,
                        is_verified = true,
                        updated_at = NOW()
                    WHERE email = :email
                    """
                ),
                {
                    "full_name": USER_FULL_NAME,
                    "first_name": USER_FIRST_NAME,
                    "preferred_name": USER_PREFERRED_NAME,
                    "org": USER_ORG,
                    "role_title": USER_ROLE_TITLE,
                    "country": USER_COUNTRY,
                    "language": USER_LANGUAGE,
                    "tz": USER_TIMEZONE,
                    "interests": '["' + '","'.join(POLICY_INTERESTS) + '"]',
                    "tier": SUBSCRIPTION_TIER,
                    "expires_at": SUBSCRIPTION_EXPIRES_AT,
                    "email": USER_EMAIL,
                },
            )
            logger.info("  [user] updated metadata + tier")
        return existing.id

    new_id = str(uuid.uuid4())
    if apply:
        db.execute(
            text(
                """
                INSERT INTO users (
                    id, email, password_hash, full_name, first_name, preferred_name,
                    organization, role, role_title, country, language, timezone,
                    policy_interests, subscription_tier, subscription_expires_at,
                    is_active, is_verified, created_at, updated_at
                ) VALUES (
                    :id, :email, :pw, :full_name, :first_name, :preferred_name,
                    :org, 'user', :role_title, :country, :language, :tz,
                    CAST(:interests AS JSONB), :tier, :expires_at,
                    true, true, NOW(), NOW()
                )
                """
            ),
            {
                "id": new_id,
                "email": USER_EMAIL,
                "pw": get_password_hash(USER_PASSWORD),
                "full_name": USER_FULL_NAME,
                "first_name": USER_FIRST_NAME,
                "preferred_name": USER_PREFERRED_NAME,
                "org": USER_ORG,
                "role_title": USER_ROLE_TITLE,
                "country": USER_COUNTRY,
                "language": USER_LANGUAGE,
                "tz": USER_TIMEZONE,
                "interests": '["' + '","'.join(POLICY_INTERESTS) + '"]',
                "tier": SUBSCRIPTION_TIER,
                "expires_at": SUBSCRIPTION_EXPIRES_AT,
            },
        )
        logger.info(f"  [user] CREATED: {USER_EMAIL} (id={new_id[:8]}, tier={SUBSCRIPTION_TIER}, expires={SUBSCRIPTION_EXPIRES_AT.date()})")
    else:
        logger.info(f"  [user] WOULD CREATE: {USER_EMAIL} (tier={SUBSCRIPTION_TIER}, expires={SUBSCRIPTION_EXPIRES_AT.date()})")
    return new_id


def resolve_full_uuids(db, short_ids: list[str], table: str) -> dict[str, str]:
    """Resolve 8-char short IDs to full UUIDs in the given table."""
    out = {}
    for s in short_ids:
        row = db.execute(
            text(f"SELECT id::text FROM {table} WHERE id::text LIKE :p LIMIT 1"),
            {"p": s + "%"},
        ).first()
        if row:
            out[s] = row.id
        else:
            logger.warning(f"  [WARN] no {table} row found for short id {s}")
    return out


def seed_carriage_tracks(db, user_id: str, apply: bool):
    full = resolve_full_uuids(db, CARRIAGE_SHORT_IDS, "legislative_carriages")
    for short, uid in full.items():
        exists = db.execute(
            text("SELECT 1 FROM user_carriage_tracks WHERE user_id = :u AND carriage_id = :c"),
            {"u": user_id, "c": uid},
        ).first()
        if exists:
            logger.info(f"  [track] SKIP carriage {short} (already tracked)")
            continue
        if apply:
            db.execute(
                text(
                    """
                    INSERT INTO user_carriage_tracks (
                        id, user_id, carriage_id,
                        notify_on_status_change, notify_on_blocking, notify_on_new_documents,
                        tracked_since
                    ) VALUES (
                        :id, :u, :c, true, true, true, NOW()
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), "u": user_id, "c": uid},
            )
            logger.info(f"  [track] CREATE carriage {short}")
        else:
            logger.info(f"  [track] WOULD CREATE carriage {short}")


def seed_adopted_tracks(db, user_id: str, apply: bool):
    full = resolve_full_uuids(db, ADOPTED_TEXT_SHORT_IDS, "texts_adopted")
    for short, uid in full.items():
        exists = db.execute(
            text("SELECT 1 FROM user_text_adopted_tracks WHERE user_id = :u AND text_adopted_id = :t"),
            {"u": user_id, "t": uid},
        ).first()
        if exists:
            logger.info(f"  [adopted] SKIP {short} (already tracked)")
            continue
        if apply:
            db.execute(
                text(
                    """
                    INSERT INTO user_text_adopted_tracks (
                        id, user_id, text_adopted_id, tracked_since
                    ) VALUES (
                        :id, :u, :t, NOW()
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), "u": user_id, "t": uid},
            )
            logger.info(f"  [adopted] CREATE {short}")
        else:
            logger.info(f"  [adopted] WOULD CREATE {short}")


def seed_documents(db, user_id: str, apply: bool):
    for d in DOCUMENTS:
        exists = db.execute(
            text("SELECT 1 FROM user_documents WHERE user_id = :u AND title = :t"),
            {"u": user_id, "t": d["title"]},
        ).first()
        if exists:
            logger.info(f"  [doc] SKIP '{d['title'][:60]}...' (already seeded)")
            continue
        if apply:
            db.execute(
                text(
                    """
                    INSERT INTO user_documents (
                        id, user_id, document_type, title, content,
                        celex_number, procedure_reference,
                        policy_areas, tags,
                        executive_summary, objectives, action_plan, timeline, stakeholders,
                        include_in_ai_context, is_private,
                        version, view_count, is_featured,
                        created_at, updated_at
                    ) VALUES (
                        :id, :u, :type, :title, :content,
                        :celex, :proc,
                        :areas, :tags,
                        :exec_sum, :objectives, :action_plan, :timeline, :stakeholders,
                        true, true,
                        1, 0, false,
                        NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "u": user_id,
                    "type": d["document_type"],
                    "title": d["title"],
                    "content": d.get("content"),
                    "celex": d.get("celex_number"),
                    "proc": d.get("procedure_reference"),
                    "areas": d.get("policy_areas"),
                    "tags": d.get("tags"),
                    "exec_sum": d.get("executive_summary"),
                    "objectives": d.get("objectives"),
                    "action_plan": d.get("action_plan"),
                    "timeline": d.get("timeline"),
                    "stakeholders": d.get("stakeholders"),
                },
            )
            logger.info(f"  [doc] CREATE '{d['title'][:60]}...'")
        else:
            logger.info(f"  [doc] WOULD CREATE '{d['title'][:60]}...'")


def flip_private_guide_pointer(db, apply: bool):
    if apply:
        db.execute(
            text(
                """
                UPDATE users
                SET private_guide_slug = :slug,
                    private_guide_status = 'ready',
                    private_guide_updated_at = NOW()
                WHERE email = :e
                """
            ),
            {"slug": PRIVATE_GUIDE_SLUG, "e": USER_EMAIL},
        )
        logger.info(f"  [guide] users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}', status = 'ready'")
    else:
        logger.info(f"  [guide] WOULD set users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    args = ap.parse_args()

    apply = args.apply
    logger.info("=" * 78)
    logger.info(f"Seed JMP / ACM Brussels Office - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = upsert_user(db, apply)
        seed_carriage_tracks(db, user_id, apply)
        seed_adopted_tracks(db, user_id, apply)
        seed_documents(db, user_id, apply)
        flip_private_guide_pointer(db, apply)
        # Pydantic round-trip smoke test BEFORE commit. If any inserted row
        # would 500 /api/documents, fail loudly instead of shipping a
        # white-screen to the user. See memory/feedback_raw_insert_orm_defaults.md.
        if apply:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, user_id)
            logger.info(f"  [validate] {n} user_documents rows round-trip cleanly")
        if apply:
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run only. Re-run with --apply to commit.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
