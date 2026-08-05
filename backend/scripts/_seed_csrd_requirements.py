"""Seed the canonical headline obligations of Directive (EU) 2022/2464 (CSRD) into law_requirements.

Pre-curated from a sequential read of the Directive (recitals 1-72; Articles 1-8; new Articles
19a, 29a, 29b, 29c, 29d, 40a-40d inserted into Directive 2013/34/EU) - Brubru canon project,
5 August 2026. Pre-seeding guarantees EU Law Comply can produce a complete compliance report for
any large undertaking, listed SME, group parent or third-country undertaking with EU operations
even when the AI extractor cannot parse the Formex source cleanly.

Note on Omnibus (2025): Directive (EU) 2025/794 (Stop-the-clock) postponed Wave 2 (FY2025 -> FY2027)
and Wave 3 (FY2026 -> FY2028). Wave 1 (large PIEs >500 employees, already reporting since FY2024)
is unchanged. Substantive Omnibus proposal narrowing scope to ~7,000 firms is still under
negotiation as of Aug 2026 and NOT reflected here.

IDs after running create_law_clusters.py --package csrd_corporate_sustainability_reporting
followed by _ingest_csrd_oneshot.py:
  SELECT id, celex FROM eu_laws WHERE celex='32022L2464'; -> 10087
  SELECT id, name FROM law_clusters WHERE name = 'CSRD - Corporate Sustainability Reporting Directive'; -> 59
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

CSRD_LAW_ID = 10087
CSRD_CLUSTER_ID = 59

REQUIREMENTS = [
    {
        "article": "Art 19a(1)",
        "requirement_text": (
            "Include sustainability information in the management report as a clearly identifiable "
            "dedicated section. The information must cover both the undertaking's impacts on "
            "sustainability matters (impact materiality) AND how sustainability matters affect the "
            "undertaking's development, performance and position (financial materiality). The "
            "double materiality principle is mandatory: an undertaking must consider each "
            "perspective on its own and disclose information material from either or both."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "large undertakings and listed SMEs (except micro)",
    },
    {
        "article": "Art 19a(2)(a)",
        "requirement_text": (
            "Disclose the business model and strategy including: resilience to sustainability "
            "risks; sustainability opportunities; the transition plan (including implementing "
            "actions and financial/investment plans) to make the business model and strategy "
            "compatible with the 1.5 degrees Celsius target of the Paris Agreement and the 2050 "
            "climate neutrality objective of Regulation (EU) 2021/1119 (European Climate Law); "
            "exposure to coal-, oil- and gas-related activities where relevant; how the strategy "
            "takes account of stakeholders' interests and impacts on sustainability."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(2)(b)",
        "requirement_text": (
            "Disclose time-bound sustainability targets set by the undertaking, including at "
            "minimum ABSOLUTE greenhouse-gas emission reduction targets for 2030 AND 2050. Report "
            "progress made towards achieving those targets and state whether the environmental "
            "targets are based on conclusive scientific evidence (IPCC + European Scientific "
            "Advisory Board on Climate Change)."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(2)(c)-(e)",
        "requirement_text": (
            "Disclose the role of administrative, management and supervisory bodies with regard "
            "to sustainability matters and their expertise/skills; the undertaking's sustainability "
            "policies; the existence of incentive schemes linked to sustainability matters offered "
            "to members of those bodies."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "high",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(2)(f)",
        "requirement_text": (
            "Disclose the due diligence process implemented for sustainability matters; the "
            "principal actual or potential adverse impacts connected with the undertaking's own "
            "operations AND value chain (including products, services, business relationships and "
            "supply chain); actions taken to identify and monitor those impacts; and actions taken "
            "to prevent, mitigate, remediate or bring an end to actual or potential adverse "
            "impacts, together with the result of such actions."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(2)(g)-(h)",
        "requirement_text": (
            "Disclose the principal risks to the undertaking related to sustainability matters, "
            "including its principal dependencies on those matters, and how it manages those "
            "risks. Disclose indicators relevant to the qualitative and quantitative disclosures "
            "in points (a) to (g). Report the process used to identify the information reported."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "high",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(3)",
        "requirement_text": (
            "Where applicable, sustainability information must contain information about the "
            "undertaking's own operations AND its value chain (products, services, business "
            "relationships, supply chain). For the first three years of application, where not all "
            "necessary value-chain information is available, explain the efforts made, the reasons "
            "for gaps, and the plan to obtain that information in future. After year 3, the grace "
            "period ends."
        ),
        "deadline": date(2027, 12, 31),
        "criticality": "high",
        "applicable_entity": "reporting undertakings with value chains",
    },
    {
        "article": "Art 19a(4)",
        "requirement_text": (
            "Report sustainability information IN ACCORDANCE WITH the European Sustainability "
            "Reporting Standards (ESRS) adopted by the Commission under Article 29b. First set "
            "adopted by Delegated Regulation (EU) 2023/2772 (12 standards: ESRS 1, ESRS 2, E1-E5, "
            "S1-S4, G1). Sector-specific ESRS due 30 June 2026. Non-compliance with the ESRS is a "
            "breach of the reporting obligation itself."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 19a(5)",
        "requirement_text": (
            "Inform workers' representatives at the appropriate level of the sustainability "
            "information and the means of obtaining and verifying it, and discuss it with them. "
            "The workers' representatives' opinion must be communicated, where applicable, to the "
            "administrative, management or supervisory bodies."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "medium",
        "applicable_entity": "reporting undertakings with workers' representation",
    },
    {
        "article": "Art 29a",
        "requirement_text": (
            "Parent undertakings of a large group must prepare CONSOLIDATED sustainability "
            "reporting at group level covering the parent and its subsidiaries. Subsidiary "
            "undertakings whose information is included in a parent's consolidated report are "
            "exempted from single-undertaking Article 19a reporting, subject to publicity "
            "conditions (name and registered office of parent; weblinks to consolidated report; "
            "exemption statement). Large listed subsidiaries are NOT exempted."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "critical",
        "applicable_entity": "parent undertakings of large groups",
    },
    {
        "article": "Art 29b",
        "requirement_text": (
            "The Commission adopts European Sustainability Reporting Standards (ESRS) by delegated "
            "acts, based on technical advice from EFRAG, after consulting the Member State Expert "
            "Group on Sustainable Finance, the Accounting Regulatory Committee, ESMA/EBA/EIOPA "
            "(2-month opinion), EEA, FRA, ECB, CEAOB and the Platform on Sustainable Finance. First "
            "set adopted 31 July 2023 by Delegated Regulation (EU) 2023/2772."
        ),
        "deadline": date(2023, 7, 31),
        "criticality": "high",
        "applicable_entity": "European Commission",
    },
    {
        "article": "Art 29d",
        "requirement_text": (
            "Prepare the management report (including the sustainability section) in the single "
            "electronic reporting format (ESEF) laid down in Commission Delegated Regulation (EU) "
            "2019/815. Mark up (tag) sustainability information according to the digital "
            "sustainability taxonomy to be adopted by the Commission by delegated act. Applies "
            "from financial years starting on or after 1 January 2026 (Article 5(2), point (14) "
            "derogation)."
        ),
        "deadline": date(2027, 12, 31),
        "criticality": "high",
        "applicable_entity": "reporting undertakings",
    },
    {
        "article": "Art 34 (assurance)",
        "requirement_text": (
            "Obtain an assurance opinion on sustainability reporting. LIMITED ASSURANCE is required "
            "from the first year of application. The Commission may adopt limited-assurance "
            "standards by 1 October 2026 and reasonable-assurance standards by 1 October 2028 by "
            "delegated act, in which case reasonable assurance may become mandatory. Assurance is "
            "performed by the statutory auditor by default, or by an independent assurance "
            "services provider (IASP) accredited under Regulation (EC) No 765/2008 where the "
            "Member State opens the market to IASPs."
        ),
        "deadline": date(2025, 12, 31),
        "criticality": "critical",
        "applicable_entity": "reporting undertakings and their statutory auditors",
    },
    {
        "article": "Art 40a-40d",
        "requirement_text": (
            "Third-country undertakings with net EU turnover above 150 million euros in each of "
            "the last two consecutive financial years, and having at least one EU subsidiary that "
            "is a large or listed undertaking (except micro) or an EU branch with net turnover "
            "above 40 million euros, must publish a sustainability report through that subsidiary "
            "or branch. Report standards to be adopted by delegated act by 30 June 2024. Applies "
            "from financial years starting on or after 1 January 2028 (Wave 4)."
        ),
        "deadline": date(2028, 12, 31),
        "criticality": "critical",
        "applicable_entity": "EU subsidiary/branch of large third-country undertakings",
    },
    {
        "article": "Art 5(1)",
        "requirement_text": (
            "Member States must bring into force the laws, regulations and administrative "
            "provisions necessary to comply with Articles 1 to 3 of the Directive by 6 July 2024, "
            "and immediately communicate the text to the Commission. Failure to transpose triggers "
            "Commission infringement proceedings (Article 258 TFEU) - opened for multiple Member "
            "States in autumn 2024."
        ),
        "deadline": date(2024, 7, 6),
        "criticality": "critical",
        "applicable_entity": "Member States (national legislator)",
    },
    {
        "article": "Art 5(2)(a) Wave 1",
        "requirement_text": (
            "Wave 1: financial years starting on or after 1 January 2024. Applies to large "
            "undertakings that are public-interest entities exceeding an average of 500 employees "
            "during the financial year, and to PIEs that are parent undertakings of a large group "
            "on a consolidated basis exceeding 500 employees. First reports published in 2025. "
            "This wave is UNCHANGED by Directive (EU) 2025/794 (Stop-the-clock)."
        ),
        "deadline": date(2024, 1, 1),
        "criticality": "critical",
        "applicable_entity": "large PIEs above 500 employees (former NFRD scope)",
    },
    {
        "article": "Art 5(2)(b) Wave 2",
        "requirement_text": (
            "Wave 2 (original): financial years starting on or after 1 January 2025. Applies to "
            "all other large undertakings and to parent undertakings of a large group. "
            "POSTPONED BY TWO YEARS by Directive (EU) 2025/794 (Stop-the-clock) to financial "
            "years starting on or after 1 January 2027, first reports in 2028."
        ),
        "deadline": date(2027, 1, 1),
        "criticality": "critical",
        "applicable_entity": "large non-PIE undertakings meeting 2 of 3 size thresholds",
    },
    {
        "article": "Art 5(2)(c) Wave 3",
        "requirement_text": (
            "Wave 3 (original): financial years starting on or after 1 January 2026. Applies to "
            "listed SMEs (except micro), small non-complex credit institutions, and captive (re)"
            "insurance undertakings meeting the size criteria. POSTPONED BY TWO YEARS by Directive "
            "(EU) 2025/794 to financial years starting on or after 1 January 2028. Listed SMEs may "
            "additionally opt out with a management-report explanation for financial years starting "
            "before 1 January 2028."
        ),
        "deadline": date(2028, 1, 1),
        "criticality": "high",
        "applicable_entity": "listed SMEs (except micro) + captive (re)insurers",
    },
    {
        "article": "Art 20",
        "requirement_text": (
            "Corporate governance statement (in the management report) must describe the diversity "
            "policy applied to administrative, management and supervisory bodies with regard to "
            "gender AND other aspects (age, disabilities, educational and professional background), "
            "the objectives of that policy, how it has been implemented, and the results. If no "
            "policy is applied, explain why. Undertakings reporting under Article 19a may present "
            "this alongside sustainability information with a cross-reference."
        ),
        "deadline": date(2024, 12, 31),
        "criticality": "medium",
        "applicable_entity": "listed undertakings within CSRD scope",
    },
    {
        "article": "Art 51 (Dir 2013/34)",
        "requirement_text": (
            "Member States must lay down effective, proportionate and dissuasive SANCTIONS for "
            "infringements of the national provisions adopted pursuant to CSRD (Article 51 of "
            "Directive 2013/34/EU as amended). Sanctions must apply to failures to publish "
            "sustainability information, failures to comply with ESRS, missing assurance opinions, "
            "and false declarations. Enforcement lies with national competent authorities under "
            "Directive 2004/109/EC for listed issuers and under national company law for others."
        ),
        "deadline": date(2024, 7, 6),
        "criticality": "high",
        "applicable_entity": "Member States (national legislator + supervisory authorities)",
    },
]

db = SessionLocal()
try:
    # Idempotent: purge any existing CSRD requirements first (matches by law_id + cluster_id).
    from sqlalchemy import text as _text
    n_deleted = db.execute(_text("""
        DELETE FROM law_requirements
        WHERE law_id = :lid AND cluster_id = :cid
    """), {"lid": CSRD_LAW_ID, "cid": CSRD_CLUSTER_ID}).rowcount
    if n_deleted:
        print(f"[purge] removed {n_deleted} prior CSRD requirements")

    for r in REQUIREMENTS:
        req = LawRequirement(
            law_id=CSRD_LAW_ID,
            cluster_id=CSRD_CLUSTER_ID,
            article=r["article"][:50],
            requirement_text=r["requirement_text"],
            deadline=r.get("deadline"),
            criticality=r["criticality"],
            applicable_entity=r["applicable_entity"][:100],
            extra_metadata={"source": "canon_curated_seed", "seeded_at": "2026-08-05"},
        )
        db.add(req)
    db.commit()
    print(f"[seeded] {len(REQUIREMENTS)} CSRD requirements into law_requirements")
finally:
    db.close()
