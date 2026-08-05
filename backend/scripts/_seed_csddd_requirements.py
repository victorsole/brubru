"""Seed the canonical headline obligations of Directive (EU) 2024/1760 (CSDDD) into
law_requirements.

Pre-curated from a sequential read of the Directive (Articles 1-39, Annex I) -
Brubru canon project, 5 August 2026.

Note on Omnibus (2025): Directive (EU) 2025/794 (Stop-the-clock) postponed the
transposition deadline from 26 July 2026 to 26 July 2027, and Wave 1 application
from 26 July 2027 to 26 July 2028. The substantive Omnibus I proposal (COM(2025)
81 final) is still under negotiation and may further narrow scope, delete
Article 29 civil liability harmonisation, and soften Article 22 - NOT reflected
here (the below reflects the current in-force text).

IDs after running create_law_clusters.py --package csddd_corporate_sustainability_due_diligence
followed by _ingest_csddd_oneshot.py:
  SELECT id, celex FROM eu_laws WHERE celex='32024L1760'; -> 18368
  SELECT id, name FROM law_clusters WHERE name LIKE 'CSDDD%'; -> 60
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from core.database import SessionLocal
from models.eu_law import LawRequirement

CSDDD_LAW_ID = 18368
CSDDD_CLUSTER_ID = 60

REQUIREMENTS = [
    {
        "article": "Art 2",
        "requirement_text": (
            "Scope: applies to EU companies with more than 1,000 employees AND net worldwide "
            "turnover above 450 million euros; to ultimate parents of groups meeting those "
            "thresholds; to franchising or licensing companies with royalties above 22.5 million "
            "euros in the Union AND net worldwide turnover above 80 million euros. Applies "
            "equally to third-country companies with net Union turnover above 450 million euros. "
            "Thresholds must be met for TWO consecutive financial years to trigger scope; scope "
            "drops after two consecutive years below. AIFs and UCITS excluded."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "large EU + third-country companies + group parents",
    },
    {
        "article": "Art 5",
        "requirement_text": (
            "Conduct risk-based human rights and environmental due diligence via the 8-step "
            "process: (1) integrate due diligence into policies and risk management (Art 7); "
            "(2) identify and assess actual and potential adverse impacts (Art 8); (3) prioritise "
            "where full simultaneous coverage is not feasible (Art 9); (4) prevent and mitigate "
            "potential adverse impacts (Art 10) and bring actual adverse impacts to an end or "
            "minimise their extent (Art 11); (5) provide remediation for actual adverse impacts "
            "(Art 12); (6) meaningful stakeholder engagement (Art 13); (7) notification mechanism "
            "and complaints procedure (Art 14); (8) monitor effectiveness (Art 15) and publicly "
            "communicate on due diligence (Art 16). Retain documentation at least 5 years."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 7",
        "requirement_text": (
            "Integrate due diligence into all corporate policies and risk management systems. "
            "Adopt a due diligence policy that includes a description of the company's long-term "
            "approach; a code of conduct for employees and subsidiaries; a description of the "
            "processes to integrate due diligence in operations, products and services and across "
            "business relationships. Policy updated without undue delay after a significant "
            "change and reviewed at least every 24 months."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 8",
        "requirement_text": (
            "Identify and assess actual and potential adverse impacts (human rights and "
            "environmental) arising from own operations, subsidiaries and business partners in "
            "the chain of activities. Map operations, subsidiaries and, where relevant, business "
            "relationships; then carry out in-depth assessment where indicators suggest likely "
            "risk. Article 8 is one of the four fully harmonised provisions (Article 4(1)) - "
            "Member States cannot deviate."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 10",
        "requirement_text": (
            "Prevent and adequately mitigate potential adverse impacts. Take appropriate measures: "
            "develop and implement a prevention action plan with time-bound targets; seek "
            "contractual assurances from direct business partners (with cascading assurances "
            "sought from indirect partners); make necessary investments in own or joint "
            "activities including supplier processes; provide targeted support to SME business "
            "partners; collaborate with other companies. Contract termination is a last resort "
            "after other measures fail. Article 10(1) is fully harmonised."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 11",
        "requirement_text": (
            "Bring actual adverse impacts to an end or, where not immediately possible, minimise "
            "their extent. Same toolkit as Article 10 (corrective action plan, contractual "
            "assurances, investment, SME support, collaboration). Business relationship "
            "termination is a last resort. Article 11(1) is fully harmonised."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 12",
        "requirement_text": (
            "Provide REMEDIATION for actual adverse impacts caused by the company or those to "
            "which it contributed. Remediation restores affected persons, communities or "
            "environment to a situation equivalent or as close as possible to the situation "
            "they would have been in had the adverse impact not occurred, in proportion to the "
            "company's implication. May include financial or non-financial compensation and "
            "reimbursement of public authorities' remedial costs."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies (contributing to adverse impact)",
    },
    {
        "article": "Art 13",
        "requirement_text": (
            "Carry out MEANINGFUL ENGAGEMENT with stakeholders (employees, workers of "
            "subsidiaries and value-chain partners, unions, consumers, affected communities, "
            "civil society organisations, national human rights and environmental institutions). "
            "Engagement must be substantive, provide relevant information, allow response, "
            "consider the position of vulnerable groups and the impacts covered by the specific "
            "step of the due-diligence process."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "high",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 14",
        "requirement_text": (
            "Establish a notification mechanism and complaints procedure available to any "
            "natural or legal person with legitimate concerns about actual or potential adverse "
            "impacts (workers, unions, individuals affected, human rights and environmental "
            "defenders, civil society organisations). Complainants entitled to a follow-up, "
            "meeting with the company at appropriate level, and reasoned reply. May be operated "
            "in collaboration with other companies or in an industry / multi-stakeholder scheme."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "high",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 15",
        "requirement_text": (
            "MONITOR the effectiveness of the due diligence policy and measures at least every "
            "12 months and after significant change. Assess whether adverse impacts are properly "
            "identified, prevented, mitigated, brought to an end and minimised, and whether "
            "remediation has been effective. Findings feed back into policy and risk management "
            "systems and update the prevention or corrective action plans."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "high",
        "applicable_entity": "in-scope companies",
    },
    {
        "article": "Art 16",
        "requirement_text": (
            "PUBLICLY COMMUNICATE on due diligence via an annual statement published on the "
            "company's website in a Union language widely used in international business, free "
            "of charge, by 30 April each year covering the previous financial year. Statement "
            "specifies content to be adopted by Commission delegated act. Undertakings that "
            "report under CSRD Article 19a/29a/40a of Directive 2013/34/EU are exempted from "
            "publishing a separate Article 16 statement (single-instrument reporting)."
        ),
        "deadline": date(2029, 4, 30),
        "criticality": "high",
        "applicable_entity": "in-scope companies not exempted under CSRD",
    },
    {
        "article": "Art 22",
        "requirement_text": (
            "Adopt AND PUT INTO EFFECT a climate change mitigation transition plan compatible "
            "with 1.5 degrees Celsius in line with the Paris Agreement and climate neutrality "
            "2050 (Regulation (EU) 2021/1119). Plan must contain: time-bound targets for 2030 "
            "and in five-year steps to 2050 for scope 1, scope 2 and where relevant scope 3 GHG "
            "emissions; decarbonisation levers and key actions; investment and funding "
            "quantification; and role of admin/management/supervisory bodies. Updated every 12 "
            "months. Companies reporting a transition plan under CSRD Article 19a/29a/40a are "
            "deemed to comply with the adopt-and-report component."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope EU and third-country companies (points a, b, c)",
    },
    {
        "article": "Art 23",
        "requirement_text": (
            "Third-country companies within Article 2(2) must designate an AUTHORISED "
            "REPRESENTATIVE established or domiciled in a Union Member State where they "
            "operate. Notify the representative's name, address, email and phone to the "
            "supervisory authority. Empower the representative to receive communications from "
            "supervisory authorities on all compliance and enforcement matters and provide the "
            "necessary powers and resources to cooperate."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "third-country companies in Union scope",
    },
    {
        "article": "Art 24",
        "requirement_text": (
            "Member States designate one or more supervisory authorities to supervise Articles "
            "7 to 16 and Article 22 obligations, and inform the Commission of names and "
            "contact details by 26 July 2026 (postponed to 26 July 2027 by Directive (EU) "
            "2025/794). Authorities must be independent, legally and functionally separate "
            "from supervised companies, staff free from conflicts of interest."
        ),
        "deadline": date(2027, 7, 26),
        "criticality": "critical",
        "applicable_entity": "Member States",
    },
    {
        "article": "Art 25",
        "requirement_text": (
            "Supervisory authorities have adequate powers and resources to require information, "
            "carry out investigations, order the company to cease infringements, refrain from "
            "repetition and provide remediation, impose penalties, and adopt interim measures "
            "in the event of an imminent risk of severe and irreparable harm. Grant the company "
            "an appropriate remediation period first; enforcement without prejudice to "
            "Article 27 penalties and Article 29 civil liability."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "high",
        "applicable_entity": "Member State supervisory authorities",
    },
    {
        "article": "Art 26",
        "requirement_text": (
            "Any natural or legal person entitled to submit SUBSTANTIATED CONCERNS through "
            "easily accessible channels to any supervisory authority. Authority must protect "
            "the identity and personal information of the submitter on request and assess the "
            "concern in an appropriate period of time."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "medium",
        "applicable_entity": "Member State supervisory authorities",
    },
    {
        "article": "Art 27",
        "requirement_text": (
            "PENALTIES for infringement must be effective, proportionate and dissuasive. "
            "Member States must provide AT LEAST: pecuniary penalties AND a public statement "
            "naming the company where a pecuniary penalty is not paid on time. Pecuniary "
            "penalties calculated on net worldwide turnover; the MAXIMUM LIMIT MUST NOT BE "
            "LESS THAN 5 PERCENT of the net worldwide turnover of the last financial year "
            "(consolidated turnover for group parents). Decisions published and kept available "
            "at least 5 years."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "Member States (in national transposition)",
    },
    {
        "article": "Art 29",
        "requirement_text": (
            "CIVIL LIABILITY: Member States must ensure a company can be held liable for damage "
            "where (a) it intentionally or negligently failed to comply with Articles 10 or 11 "
            "obligations aimed at protecting the person AND (b) that failure caused damage. "
            "Full compensation for the injured person; no punitive/multiple/other damages. "
            "Limitation period AT LEAST 5 YEARS, not starting until infringement ceases and "
            "claimant reasonably knows of harm and infringer. Trade unions, NGOs and national "
            "human rights institutions may bring representative actions. Costs must not be "
            "prohibitively expensive; injunctive relief and evidence-disclosure orders "
            "available. OVERRIDING MANDATORY APPLICATION - applies even where the applicable "
            "law is not that of a Member State (Rome II carve-out)."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "critical",
        "applicable_entity": "in-scope companies (potential defendants)",
    },
    {
        "article": "Art 37",
        "requirement_text": (
            "Transposition deadline (as postponed by Directive (EU) 2025/794): Member States "
            "must adopt and publish national transposing law BY 26 JULY 2027 and immediately "
            "communicate the text to the Commission. Application in three postponed waves: "
            "Wave 1 from 26 July 2028 for companies with more than 5,000 employees + net "
            "worldwide turnover above 1.5 billion euros (or third-country equivalent in "
            "Union turnover); Wave 2 from 26 July 2029 for more than 3,000 employees + 900 "
            "million euros; Wave 3 from 26 July 2030 for all other in-scope companies "
            "including franchising."
        ),
        "deadline": date(2027, 7, 26),
        "criticality": "critical",
        "applicable_entity": "Member States (national legislator)",
    },
    {
        "article": "Art 31",
        "requirement_text": (
            "PUBLIC SUPPORT, PUBLIC PROCUREMENT AND PUBLIC CONCESSIONS: Member States must "
            "ensure that compliance with CSDDD national transposition qualifies as an "
            "environmental or social aspect that contracting authorities may take into account "
            "under Directives 2014/23/EU, 2014/24/EU and 2014/25/EU (public procurement), as "
            "award criteria and as performance conditions for public and concession contracts."
        ),
        "deadline": date(2028, 7, 26),
        "criticality": "medium",
        "applicable_entity": "Member States + contracting authorities",
    },
]

db = SessionLocal()
try:
    from sqlalchemy import text as _text
    n_deleted = db.execute(_text("""
        DELETE FROM law_requirements
        WHERE law_id = :lid AND cluster_id = :cid
    """), {"lid": CSDDD_LAW_ID, "cid": CSDDD_CLUSTER_ID}).rowcount
    if n_deleted:
        print(f"[purge] removed {n_deleted} prior CSDDD requirements")

    for r in REQUIREMENTS:
        req = LawRequirement(
            law_id=CSDDD_LAW_ID,
            cluster_id=CSDDD_CLUSTER_ID,
            article=r["article"][:50],
            requirement_text=r["requirement_text"],
            deadline=r.get("deadline"),
            criticality=r["criticality"],
            applicable_entity=r["applicable_entity"][:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-05"},
        )
        db.add(req)
    db.commit()
    print(f"[seeded] {len(REQUIREMENTS)} CSDDD requirements into law_requirements")
finally:
    db.close()
