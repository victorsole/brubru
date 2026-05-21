"""
Seed David Devant Cerezo (EFPIA) profile.

Updates the existing user (david.devantcerezo@efpia.eu) with EFPIA context,
attaches 7 priority legislative carriages to My Files, seeds 6 MEUB documents
under the canonical pattern (document_type='uploaded' with semantic type in
doc_metadata.original_document_type), points him at the david-devant-efpia
private guide bundle, and runs the Pydantic round-trip validator before
commit.

Pattern reference: memory/feedback_raw_insert_orm_defaults.md (esp. the
canonical `'uploaded' + doc_metadata.original_document_type` pattern).

Usage:
    cd backend && python3.12 scripts/seed_ddevant_efpia.py            # dry-run
    cd backend && python3.12 scripts/seed_ddevant_efpia.py --apply    # write DB

Idempotent: re-runs skip rows that already exist for this user.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru/backend")
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru")

from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv("/Users/victorsole/Documents/GitHub/brubru/.env")

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


USER_EMAIL = "david.devantcerezo@efpia.eu"
USER_FULL_NAME = "David Devant Cerezo"
USER_FIRST_NAME = "David"
USER_PREFERRED_NAME = "David"
USER_ORG = "EFPIA (European Federation of Pharmaceutical Industries and Associations)"
USER_ROLE_TITLE = "Junior Manager, Public Affairs"
USER_COUNTRY = "BE"
USER_LANGUAGE = "ca"
USER_TIMEZONE = "Europe/Brussels"
POLICY_INTERESTS = [
    "Pharmaceutical Legislation",
    "HTA",
    "Compulsory Licensing",
    "Trade and IP",
    "AMR",
    "Critical Medicines",
    "Pharma environment",
]
PRIVATE_GUIDE_SLUG = "david-devant-efpia"

SUBSCRIPTION_TIER = "blue"
SUBSCRIPTION_EXPIRES_AT = datetime(2026, 6, 21, 23, 59, 59, tzinfo=timezone.utc)


CARRIAGE_SHORT_IDS = [
    "e83253e6",  # 2023/0131(COD) Revision of EU pharmaceutical legislation (Regulation)
    "e17cfd3b",  # 2023/0132(COD) Pharma reform Directive
    "2bc872f5",  # 2023/0129(COD) Compulsory licensing of patents for crisis management
    "b8e889e9",  # COM(2026)0130 CETA: APIs
    "147fb074",  # 2017/0018(COD) HTA cooperation (parent Reg 2021/2282)
    "bc6394d6",  # 2026/2685(DEA) Variations to marketing authorisations
    "f9280cd1",  # 2023/0126(COD) Unitary SPC (plant-protection) - comparator pattern
]


DOCUMENTS = [
    {
        "title": "EFPIA Europe's Choice policy asks - one-page brief",
        "original_document_type": "policy_summary",
        "policy_areas": ["Pharmaceutical Legislation", "HTA"],
        "tags": ["efpia", "europes-choice", "policy-asks"],
        "executive_summary": (
            "EFPIA Europe's Choice frames Europe at a competitiveness crossroads against the US "
            "and Asia in life-sciences innovation. Five concrete policy asks: (1) expanding HTA "
            "to capture wider societal benefits, (2) speeding up pricing and reimbursement, "
            "(3) increasing investment in innovative medicines, (4) eliminating clawbacks, "
            "(5) revaluing innovation from cost-to-system to investment-in-healthier-future."
        ),
        "content": (
            "## EFPIA Europe's Choice - one-page policy brief\n\n"
            "**Internal brief drafted from EFPIA published positions. 21 May 2026.**\n\n"
            "### 1. The framing\n\n"
            "EFPIA Europe's Choice positions Europe at a crossroads. Mounting health-system "
            "pressures - ageing populations, chronic disease burden, competing budgetary demands - "
            "are forcing short-term cost-cutting at the expense of long-term innovation. "
            "Without deliberate policy choices, Europe will slip behind the US and Asia in "
            "research, development and production of new medicines.\n\n"
            "### 2. The five concrete policy asks\n\n"
            "**Ask 1 - Expand HTA to capture wider societal benefits.** Joint Clinical "
            "Assessments under Regulation (EU) 2021/2282 currently focus on clinical comparators. "
            "EFPIA wants HTA frameworks - both national and EU-level - to value broader societal "
            "outcomes (productivity, caregiver burden, equity).\n\n"
            "**Ask 2 - Speed up pricing and reimbursement procedures.** EFPIA's WAIT Report "
            "documents inequalities in patient access across Member States. The ask is for "
            "binding timelines and process discipline, not full price harmonisation.\n\n"
            "**Ask 3 - Increase investment in innovative medicines.** Public investment in "
            "innovation (IHI, Horizon Cluster 1 Health) plus structural-fund pass-through to "
            "industrial R&D. Counterweight to the cost-containment push at Member-State level.\n\n"
            "**Ask 4 - Eliminate clawbacks.** Rebate schemes (in DE, FR, ES, IT) that recoup "
            "spend post-launch undermine reinvestment in newer treatments. EFPIA's most "
            "Member-State-sensitive ask; pushed through Council Health Working Party rather than "
            "Commission-side.\n\n"
            "**Ask 5 - Revalue innovation as investment, not cost.** A reframing ask. Connects "
            "to the wider Clean Industrial Deal narrative on life sciences as a strategic sector.\n\n"
            "### 3. How David should use this brief\n\n"
            "- One-page version of Europe's Choice for any Public Affairs-induction conversation.\n"
            "- Reference when the Commission or EP raise Member-State-level pricing concerns.\n"
            "- Pair with the Cancer Comparator Report 2025 and the WAIT Report for evidence.\n"
        ),
    },
    {
        "title": "EFPIA position outline on EU Pharma Legislation revision (2023/0131-0132 COD) DRAFT",
        "original_document_type": "analysis",
        "policy_areas": ["Pharmaceutical Legislation"],
        "tags": ["efpia-position", "pharma-reform", "draft"],
        "celex_number": None,
        "procedure_reference": "2023/0131(COD)",
        "executive_summary": (
            "EFPIA's position on the EU pharma reform (2023/0131 Regulation + 2023/0132 "
            "Directive): the package as agreed in trilogue (11 Dec 2025) jeopardises Europe's "
            "ability to compete. Eight counter-proposals span regulatory optimisation, R&D "
            "incentives, evidence-based access, patient-centred unmet medical need, proportionate "
            "supply chain and environment requirements, meaningful AMR incentive, simplified "
            "orphan and paediatric incentives."
        ),
        "content": (
            "## EFPIA position outline - EU Pharma Legislation revision\n\n"
            "**Internal position outline drafted from EFPIA published recommendations. 21 May 2026.**\n\n"
            "### 1. Context\n\n"
            "Files: 2023/0131(COD) (Regulation replacing Reg 726/2004) + 2023/0132(COD) "
            "(Directive replacing Dir 2001/83/EC). Trilogue provisional agreement 11 December "
            "2025. Formal Council adoption expected autumn 2026. Applicable 2028.\n\n"
            "### 2. The bottom line\n\n"
            "EFPIA's headline: the package weakens IP and innovation incentives at exactly the "
            "moment Europe needs to defend its life-sciences industrial base. Specifically:\n\n"
            "- Regulatory data protection (RDP) reduced from 8 to 6 years, with a recovery "
            "mechanism contingent on launch in all Member States within a tight window. EFPIA "
            "opposes this as practically impossible to meet given national HTA and reimbursement "
            "timelines.\n\n"
            "- Orphan medicines exclusivity revised: extension to 11 years possible but with "
            "tighter criteria.\n\n"
            "- Paediatric incentive simplified but uncertain in net effect.\n\n"
            "### 3. The eight EFPIA counter-proposals\n\n"
            "1. Regulatory optimisation and expedited pathways. PRIME-like fast-track for "
            "high-unmet-need products; EMA capacity build-out.\n\n"
            "2. Strengthen (not cut) R&D baseline. Separate innovation incentives that do not "
            "depend on launch sequencing.\n\n"
            "3. Address access barriers through evidence-based approach. The launch-in-all-MS "
            "trigger is the wrong lever; binding HTA timelines (file 2017/0018 follow-up) are "
            "the right one.\n\n"
            "4. Patient-centred unmet medical need definition. Avoid bureaucratic UMN labels "
            "that can be litigated.\n\n"
            "5. Proportionate supply-chain requirements. Shortage notification is fine; the "
            "responsibility-shifting onto MAHs in the draft is not.\n\n"
            "6. Proportionate environmental requirements. Environmental risk assessment in line "
            "with established practice; no duplicative reporting alongside Urban Waste Water EPR.\n\n"
            "7. Meaningful AMR R&D incentive. The transferable exclusivity voucher (TEV) must be "
            "robust, transferable and economically viable. Sub-economic alternatives will not "
            "fix the AMR pipeline gap.\n\n"
            "8. Simplified orphan medicine and paediatric incentives. Keep the operational mix "
            "(market exclusivity + PIP) but reduce administrative burden.\n\n"
            "### 4. EFPIA next steps\n\n"
            "- Member coordination ahead of Council formal adoption (autumn 2026).\n"
            "- Engagement on the Commission delegated and implementing acts that will land "
            "across 2027.\n"
            "- WAIT Report 2026 publication timed to Council Health Working Party calendar.\n"
            "- Continued advocacy via Strategy for European Life Sciences and Europe's Choice "
            "narratives.\n"
        ),
    },
    {
        "title": "HTA Regulation 2021/2282 - first-year implementation review for EFPIA members (BRIEFING)",
        "original_document_type": "briefing_note",
        "policy_areas": ["HTA"],
        "tags": ["hta", "jca", "regulation-2021-2282", "implementation"],
        "celex_number": "32021R2282",
        "procedure_reference": "2017/0018(COD)",
        "content": (
            "## HTA Regulation 2021/2282 - first-year implementation review\n\n"
            "**EFPIA-internal briefing for member companies. 21 May 2026.**\n\n"
            "### 1. Where we are\n\n"
            "Regulation (EU) 2021/2282 entered application on 12 January 2025 for new oncology "
            "medicines and ATMPs. Joint Clinical Assessments (JCAs) are now running through the "
            "Member State Coordination Group (MSCG). After ~16 months of practical operation, "
            "EFPIA member companies have submitted multiple JCA filings.\n\n"
            "### 2. Operational reality for EFPIA members\n\n"
            "**The PICO question is everything.** Each JCA defines population, intervention, "
            "comparator and outcome (PICO). Member companies tell us PICOs are unrealistically "
            "wide in scope (often demanding comparisons against multiple Member-State-specific "
            "standards of care). This drives up evidence-package size and risks contradiction "
            "with subsequent national HTAs.\n\n"
            "**Timelines are tight.** 100-day window from start to draft JCA report. Member "
            "companies need EFPIA to coordinate informal feedback to MSCG on procedural "
            "improvements.\n\n"
            "**Confidentiality versus transparency tension.** Final JCA reports become public; "
            "interim documents are confidential. Member companies struggle with the friction.\n\n"
            "### 3. What is coming\n\n"
            "- 12 January 2028: scope expands to orphan medicines.\n"
            "- 12 January 2030: scope expands to all centrally authorised medicinal products and "
            "to high-risk medical devices + class D IVDs.\n"
            "- Brubru chat can answer per-JCA pipeline questions via the v1 API + the live HTA "
            "tracker if requested.\n\n"
            "### 4. EFPIA's three asks of MSCG (David should socialise these)\n\n"
            "1. Pragmatic PICO scoping aligned to evidence reality rather than maximal scope.\n"
            "2. Faster informal exchange between sponsor and MSCG during the 100-day window.\n"
            "3. Predictable timetable around expansion of scope to orphans + devices.\n"
        ),
    },
    {
        "title": "DG SANTE talking points - the pharma reform trilogue endgame (DRAFT)",
        "original_document_type": "talking_points",
        "policy_areas": ["Pharmaceutical Legislation"],
        "tags": ["dg-sante", "talking-points", "trilogue", "draft"],
        "celex_number": None,
        "procedure_reference": "2023/0131(COD)",
        "content": (
            "## DG SANTE talking points - pharma reform trilogue endgame\n\n"
            "**One-pager for David ahead of DG SANTE / Cabinet engagement. Draft.**\n\n"
            "### 1. Who EFPIA is (60 seconds)\n\n"
            "EFPIA represents 40 leading pharmaceutical companies and 33+ national associations, "
            "an industry that invests EUR 50+ billion per year in R&D in Europe. Together with "
            "specialised groups EBE (biotech) and Vaccines Europe, we speak for the research-"
            "based pharma sector in Brussels.\n\n"
            "### 2. Headline points (5 minutes total)\n\n"
            "**Point 1 - The package as agreed undermines Europe's competitiveness.** Six-year "
            "RDP with a launch-in-all-MS recovery is practically impossible to meet given "
            "national HTA timelines. EFPIA's analysis projects acceleration of investment to the "
            "US and Asia.\n\n"
            "**Point 2 - The Implementing Acts are the next battle.** EFPIA wants industry "
            "consulted seriously on the secondary legislation that will operationalise the new "
            "RDP framework, the unmet-medical-need definitional rules and the AMR TEV mechanics.\n\n"
            "**Point 3 - HTA implementation experience is feeding back the wrong lessons.** Tight "
            "PICOs and limited informal exchange under Reg 2021/2282 risk being replicated in the "
            "pharma reform's evidence-collection provisions. Avoid this loop.\n\n"
            "### 3. What EFPIA offers\n\n"
            "- Concrete data on member-company R&D location decisions.\n"
            "- Operational PICO experience from the first-year HTA implementation.\n"
            "- Direct line into the 40 leading manufacturers across the EU.\n"
            "- Joint events with EFPIA-managed groups (Vaccines Europe, EBE) and member "
            "associations (Farmaindustria, vfa, ABPI, Leem etc.).\n\n"
            "### 4. Listening agenda\n\n"
            "- DG SANTE's reading of the Council formal-adoption calendar (autumn 2026 still "
            "realistic?).\n"
            "- Cabinet's view on the AMR TEV economics.\n"
            "- Implementing Acts working schedule for 2027.\n"
            "- Whether DG SANTE sees an opening on the HTA Regulation procedural improvements "
            "without reopening the Regulation itself.\n"
        ),
    },
    {
        "title": "Compulsory licensing crisis tool (2023/0129 COD) - implementation watch (BRIEFING)",
        "original_document_type": "briefing_note",
        "policy_areas": ["Compulsory Licensing", "Trade and IP"],
        "tags": ["compulsory-licensing", "implementing-acts", "pandemic-treaty"],
        "celex_number": None,
        "procedure_reference": "2023/0129(COD)",
        "content": (
            "## Compulsory licensing crisis tool - implementation watch\n\n"
            "**EFPIA-internal briefing. 21 May 2026.**\n\n"
            "### 1. Where we are\n\n"
            "Regulation 2023/0129(COD) on compulsory licensing of patents for crisis management "
            "is adopted. The EU now has a single mechanism layered on top of Member-State "
            "compulsory-licensing regimes.\n\n"
            "### 2. EFPIA's settled position\n\n"
            "EFPIA opposed the original proposal as a deterrent to investment and as duplicative "
            "of robust national regimes. With the file now adopted, EFPIA's focus shifts to:\n\n"
            "1. Implementing acts that will define crisis triggers and royalty calculation.\n"
            "2. Avoiding scope creep beyond declared crises.\n"
            "3. WHO Pandemic Treaty interaction - the EU position in WHO must not "
            "instrumentalise the EU compulsory licensing tool against EU member companies' IP.\n\n"
            "### 3. Three watch items\n\n"
            "**Watch 1 - First implementing act on royalty calculation.** Expected Commission "
            "draft late-2026 / early-2027. EFPIA will provide industry input.\n\n"
            "**Watch 2 - First test case.** If a Member State triggers the mechanism for a "
            "specific medicine, EFPIA will need to be ready to brief members within 24 hours "
            "with the EFPIA-coordinated procedural and substantive lines.\n\n"
            "**Watch 3 - WHO Pandemic Treaty.** Negotiations continue. The IP-related provisions "
            "of any treaty must not extend EU compulsory licensing beyond the EU territorial "
            "scope through WHO commitments.\n\n"
            "### 4. EFPIA action\n\n"
            "- Coordinate position with EUROBIO and biotech-association allies (EBE, Vaccines "
            "Europe inside EFPIA).\n"
            "- Bilateral with DG GROW Cabinet on the implementing acts.\n"
            "- Joint advocacy with US/Japan industry counterparts on WHO Pandemic Treaty IP.\n"
        ),
    },
    {
        "title": "EU pharma calendar 2026 - EFPIA member opportunities (BRIEFING)",
        "original_document_type": "briefing_note",
        "policy_areas": ["Pharmaceutical Legislation", "AMR", "Critical Medicines"],
        "tags": ["calendar", "ihi", "horizon-europe", "funding"],
        "celex_number": None,
        "procedure_reference": None,
        "executive_summary": (
            "Tenderator-style listing of 2026 EU funding and engagement opportunities for EFPIA "
            "member companies. Covers IHI (Innovative Health Initiative), Horizon Europe Cluster "
            "1 Health, AMR partnership funding, Innovation Fund cross-applicable for pharma "
            "industrial decarbonisation, plus EMA fee waivers and EFPIA-led calls."
        ),
        "content": (
            "## EU pharma calendar 2026 - EFPIA member opportunities\n\n"
            "**Briefing note for member companies. Draft 21 May 2026. Live Tenderator data via "
            "Brubru chat for current call detail.**\n\n"
            "### 1. IHI - Innovative Health Initiative\n\n"
            "Joint Undertaking with EFPIA, EuropaBio, Vaccines Europe, COCIR and MedTech Europe. "
            "Annual call cycle. 2026 themes typically cover precision medicine, AMR, regulatory "
            "science, digital health, and rare disease.\n\n"
            "### 2. Horizon Europe Cluster 1 (Health)\n\n"
            "EUR 8 billion budget for 2021-2027 (final years now in execution). Open in 2026: "
            "mission-mode calls on cancer, mental health, age-related conditions, and "
            "Pandemic-preparedness. Member companies typically participate as consortium "
            "partners, sometimes as Lead Partner on large consortium-driven trials.\n\n"
            "### 3. AMR partnership funding\n\n"
            "Two complementary tracks: (a) the AMR Action plan implementation funding through "
            "Horizon Cluster 1, (b) the transferable exclusivity voucher (TEV) mechanism inside "
            "the upcoming pharma reform package once applicable. The TEV is the demand-side "
            "lever; the partnership funding is the supply-side R&D push.\n\n"
            "### 4. Innovation Fund (ETS) for pharma decarbonisation\n\n"
            "Not pharma-specific. Member companies investing in low-carbon manufacturing or "
            "process electrification can apply under the standard Innovation Fund track. "
            "Rounds 4-5 are active in 2026.\n\n"
            "### 5. EMA fee waivers and SME-track\n\n"
            "EMA SME definition + fee waivers apply to companies <250 employees. EFPIA members "
            "are generally larger, but spin-outs and EBE members qualify. Worth tracking.\n\n"
            "### 6. EFPIA-led member calls\n\n"
            "EFPIA periodically issues internal calls for member-funded studies, joint position "
            "papers, and industrial-policy white papers. David's onboarding window is the "
            "natural moment to ask what is in flight.\n\n"
            "### 7. How Brubru helps\n\n"
            "Ask Brubru questions like:\n\n"
            "- 'Which Horizon Cluster 1 Health calls are open in Q3 2026 and target oncology?'\n"
            "- 'What is the IHI 2026 call topic list as of today?'\n"
            "- 'Show me Innovation Fund Round 5 deadlines for the next 6 months.'\n\n"
            "Brubru will route those to the live Tenderator dataset.\n"
        ),
    },
]


def upsert_user(db, apply: bool) -> str:
    existing = db.execute(
        text("SELECT id::text, subscription_tier, role FROM users WHERE email = :e"),
        {"e": USER_EMAIL},
    ).first()
    if not existing:
        raise RuntimeError(f"User {USER_EMAIL} not found - expected to exist (already in DB).")
    logger.info(f"  [user] exists: {USER_EMAIL} (id={existing.id[:8]}, current tier={existing.subscription_tier}, role={existing.role})")
    if apply:
        db.execute(
            text("""
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
            """),
            {
                "full_name": USER_FULL_NAME,
                "first_name": USER_FIRST_NAME,
                "preferred_name": USER_PREFERRED_NAME,
                "org": USER_ORG,
                "role_title": USER_ROLE_TITLE,
                "country": USER_COUNTRY,
                "language": USER_LANGUAGE,
                "tz": USER_TIMEZONE,
                "interests": json.dumps(POLICY_INTERESTS),
                "tier": SUBSCRIPTION_TIER,
                "expires_at": SUBSCRIPTION_EXPIRES_AT,
                "email": USER_EMAIL,
            },
        )
        logger.info(f"  [user] updated metadata + tier={SUBSCRIPTION_TIER}, expires={SUBSCRIPTION_EXPIRES_AT.date()}")
    return existing.id


def resolve_carriage_uuids(db, short_ids: list[str]) -> dict[str, str]:
    out = {}
    for s in short_ids:
        row = db.execute(text("SELECT id::text FROM legislative_carriages WHERE id::text LIKE :p LIMIT 1"), {"p": s + "%"}).first()
        if row:
            out[s] = row.id
        else:
            logger.warning(f"  [WARN] no legislative_carriage row found for short id {s}")
    return out


def seed_carriage_tracks(db, user_id: str, apply: bool):
    resolved = resolve_carriage_uuids(db, CARRIAGE_SHORT_IDS)
    for short, uid in resolved.items():
        exists = db.execute(
            text("SELECT 1 FROM user_carriage_tracks WHERE user_id = :u AND carriage_id = :c"),
            {"u": user_id, "c": uid},
        ).first()
        if exists:
            logger.info(f"  [track] SKIP carriage {short}")
            continue
        if apply:
            db.execute(
                text("""
                    INSERT INTO user_carriage_tracks (
                        id, user_id, carriage_id,
                        notify_on_status_change, notify_on_blocking, notify_on_new_documents,
                        tracked_since
                    ) VALUES (
                        :id, :u, :c, true, true, true, NOW()
                    )
                """),
                {"id": str(uuid.uuid4()), "u": user_id, "c": uid},
            )
            logger.info(f"  [track] CREATE carriage {short}")
        else:
            logger.info(f"  [track] WOULD CREATE carriage {short}")


def seed_documents(db, user_id: str, apply: bool):
    for d in DOCUMENTS:
        exists = db.execute(
            text("SELECT 1 FROM user_documents WHERE user_id = :u AND title = :t"),
            {"u": user_id, "t": d["title"]},
        ).first()
        if exists:
            logger.info(f"  [doc] SKIP '{d['title'][:60]}'")
            continue

        meta = {"original_document_type": d.get("original_document_type", "uploaded")}

        if apply:
            db.execute(
                text("""
                    INSERT INTO user_documents (
                        id, user_id, document_type, title, content,
                        celex_number, procedure_reference,
                        policy_areas, tags,
                        executive_summary, objectives, action_plan, timeline, stakeholders,
                        doc_metadata,
                        include_in_ai_context, is_private,
                        version, view_count, is_featured,
                        created_at, updated_at
                    ) VALUES (
                        :id, :u, 'uploaded', :title, :content,
                        :celex, :proc,
                        :areas, :tags,
                        :exec_sum, :objectives, :action_plan, :timeline, :stakeholders,
                        CAST(:meta AS jsonb),
                        true, true,
                        1, 0, false,
                        NOW(), NOW()
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "u": user_id,
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
                    "meta": json.dumps(meta),
                },
            )
            logger.info(f"  [doc] CREATE [{d['original_document_type']:<18}] '{d['title'][:60]}'")
        else:
            logger.info(f"  [doc] WOULD CREATE [{d['original_document_type']:<18}] '{d['title'][:60]}'")


def flip_private_guide(db, apply: bool):
    if apply:
        db.execute(
            text("""
                UPDATE users
                SET private_guide_slug = :slug,
                    private_guide_status = 'ready',
                    private_guide_updated_at = NOW()
                WHERE email = :e
            """),
            {"slug": PRIVATE_GUIDE_SLUG, "e": USER_EMAIL},
        )
        logger.info(f"  [guide] users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}', status=ready")
    else:
        logger.info(f"  [guide] WOULD set users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    args = ap.parse_args()

    apply = args.apply
    logger.info("=" * 78)
    logger.info(f"Seed David Devant Cerezo / EFPIA - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = upsert_user(db, apply)
        seed_carriage_tracks(db, user_id, apply)
        seed_documents(db, user_id, apply)
        flip_private_guide(db, apply)

        if apply:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, user_id)
            logger.info(f"  [validate] {n} user_documents rows round-trip cleanly")
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
