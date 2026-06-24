"""Seed the canonical headline obligations of Reg (EU) 2022/2554 (DORA) into law_requirements.

Pre-curated from a full sequential read of the Regulation (106 recitals, 64 articles, 9 chapters)
- Brubru canon project, 24 June 2026. Pre-seeding guarantees EU Law Comply can produce a complete
compliance report for any in-scope financial entity even when the AI extractor cannot parse the
Formex source cleanly.

IDs verified after running create_law_clusters.py --package dora_digital_operational_resilience:
  SELECT id, celex FROM eu_laws WHERE celex='32022R2554';                              -> 1532
  SELECT id, name FROM law_clusters WHERE name LIKE 'DORA%';                           -> 55
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.core.database import SessionLocal
from backend.models.eu_law import LawRequirement

DORA_LAW_ID = 1532
DORA_CLUSTER_ID = 55

REQUIREMENTS = [
    {
        "article": "Article 5",
        "requirement_text": (
            "The management body of the financial entity shall define, approve, oversee and bear "
            "ultimate responsibility for the ICT risk management framework. It must set the digital "
            "operational resilience strategy and the risk tolerance for ICT risk, approve and "
            "periodically review the ICT business continuity policy and ICT response and recovery "
            "plans, approve internal audit plans for ICT, allocate the ICT budget (including for "
            "ICT security awareness training), and put in place reporting channels covering ICT "
            "third-party arrangements and major ICT-related incidents. Members of the management "
            "body must keep their ICT-risk knowledge actively up to date through regular training."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) - all except those under Art 16 simplified framework",
    },
    {
        "article": "Article 6",
        "requirement_text": (
            "Establish and maintain a sound, comprehensive and well-documented ICT risk management "
            "framework as part of the overall risk management system. The framework must be reviewed "
            "at least once a year (periodically for microenterprises), upon any major ICT-related "
            "incident and following supervisory instructions. It must be subject to internal audit "
            "on a regular basis (for non-microenterprises), include a digital operational resilience "
            "strategy with explicit ICT risk tolerance and security objectives, and follow a three "
            "lines of defence model with an independent ICT risk control function."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) - not in Art 16 simplified scope",
    },
    {
        "article": "Article 8",
        "requirement_text": (
            "Identify, classify and document all ICT-supported business functions, roles and "
            "responsibilities, information assets and ICT assets and their dependencies. Identify "
            "all sources of ICT risk on a continuous basis. Perform an ICT risk assessment upon "
            "every major change in network and information system infrastructure. Map all "
            "information and ICT assets including those at remote sites. Maintain inventories and "
            "update them with every major change. Run a specific ICT risk assessment on legacy ICT "
            "systems at least yearly and before and after any new technology is connected."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 9",
        "requirement_text": (
            "Continuously monitor and control the security and functioning of ICT systems. Design "
            "and implement ICT security policies, procedures, protocols and tools covering data at "
            "rest, in use and in transit. Implement information security policy, sound network and "
            "infrastructure management (with the capability to instantaneously sever or segment the "
            "network in the event of a cyber-attack), strong authentication, cryptographic key "
            "management, ICT change management, and documented patch / update policies. Limit "
            "physical and logical access to information and ICT assets to what is required for "
            "approved functions only."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 10",
        "requirement_text": (
            "Put in place detection mechanisms to promptly identify anomalous activities, ICT "
            "network performance issues and ICT-related incidents, and to identify potential "
            "material single points of failure. Detection mechanisms must enable multiple layers "
            "of control, define alert thresholds, trigger ICT-related incident response processes "
            "including automatic alerts to relevant staff, and be regularly tested under Article 25. "
            "Data reporting service providers must additionally have systems that check trade "
            "reports for completeness and identify omissions / obvious errors."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 11",
        "requirement_text": (
            "Put in place a comprehensive ICT business continuity policy covering critical or "
            "important functions, with documented response and recovery plans. Conduct a business "
            "impact analysis (BIA) using quantitative and qualitative criteria. Maintain redundant "
            "ICT capacities (non-microenterprises). Test the business continuity and response and "
            "recovery plans at least yearly and after any substantive change to ICT systems "
            "supporting critical or important functions; include cyber-attack scenarios and "
            "primary-to-redundant switchover scenarios. Maintain a crisis management function. "
            "Keep readily accessible records of activities before and during disruption events."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 12",
        "requirement_text": (
            "Develop and document backup policies and procedures (specifying scope and minimum "
            "frequency) plus restoration and recovery procedures. Backup systems must be activatable "
            "without jeopardising the security of network and information systems or the "
            "availability / authenticity / integrity / confidentiality of data. Restore using ICT "
            "systems physically and logically segregated from the source system. Central securities "
            "depositories must maintain at least one secondary processing site at a geographical "
            "distance from the primary site, with full continuity capability and immediate "
            "accessibility for staff. Determine recovery time and recovery point objectives taking "
            "into account criticality and potential impact on market efficiency."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)); central securities depositories: additional secondary-site requirement",
    },
    {
        "article": "Article 13",
        "requirement_text": (
            "Gather information on vulnerabilities, cyber threats and ICT-related incidents and "
            "analyse impact. Conduct post-incident reviews after any major ICT-related incident "
            "and report changes implemented to competent authorities on request. Incorporate "
            "lessons learned into the ICT risk assessment process. Senior ICT staff must report "
            "at least yearly to the management body. Develop ICT security awareness programmes "
            "and digital operational resilience training as compulsory modules applicable to all "
            "employees and senior management."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 16",
        "requirement_text": (
            "Small and non-interconnected investment firms, payment institutions exempted under "
            "PSD2, electronic money institutions exempted under Directive 2009/110/EC, institutions "
            "exempted under CRD IV where Member States have not exercised the Article 2(4) option, "
            "and small institutions for occupational retirement provision are subject to a "
            "simplified ICT risk management framework: a documented framework, continuous "
            "monitoring of ICT systems, identification of key TPP dependencies, business continuity "
            "and back-up / restoration measures, regular testing, and incorporation of test and "
            "post-incident conclusions into the risk assessment. Articles 5 to 15 do not apply."
        ),
        "criticality": "important",
        "applicable_entity": "small and non-interconnected investment firm; exempted payment institution; exempted EMI; small IORP; CRD IV exempted institution (where MS option not exercised)",
    },
    {
        "article": "Article 17",
        "requirement_text": (
            "Define, establish and implement an ICT-related incident management process that "
            "detects, manages and notifies ICT-related incidents. Record all ICT-related incidents "
            "and significant cyber threats. Identify and address root causes. The process must "
            "include early warning indicators, procedures to identify / track / log / categorise / "
            "classify incidents by priority and severity in line with Article 18 criteria, assign "
            "roles for different incident types and scenarios, plan communications, and ensure "
            "that at least major ICT-related incidents are escalated to senior management and the "
            "management body."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 18",
        "requirement_text": (
            "Classify ICT-related incidents and determine their impact on the basis of six "
            "criteria: number and relevance of clients or counterparts affected (and transactions "
            "/ reputational impact); duration and downtime; geographical spread (in particular if "
            "affecting more than two Member States); data losses (availability, authenticity, "
            "integrity, confidentiality); criticality of services affected; economic impact (direct "
            "and indirect, absolute and relative). Classify cyber threats as significant on the "
            "basis of criticality of services at risk, number / relevance of clients targeted and "
            "geographical spread."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 19",
        "requirement_text": (
            "Report major ICT-related incidents to the relevant competent authority via initial "
            "notification, followed by intermediate report(s) whenever the status changes "
            "significantly, and a final report once the root-cause analysis has been completed and "
            "actual impact figures replace estimates. Templates set by RTS / ITS (Art 20). "
            "Significant credit institutions report to the national competent authority, which "
            "immediately transmits to the ECB. Significant cyber threats may be notified "
            "voluntarily. Where the incident has impact on the financial interests of clients, "
            "inform affected clients without undue delay about the incident and mitigation "
            "measures taken. Reporting may be outsourced but the financial entity remains fully "
            "responsible."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 23",
        "requirement_text": (
            "Credit institutions, payment institutions, account information service providers and "
            "electronic money institutions shall report under DORA the operational or security "
            "payment-related incidents previously reported under PSD2 Article 96, including major "
            "operational or security payment-related incidents, irrespective of whether the "
            "incident is ICT-related."
        ),
        "criticality": "important",
        "applicable_entity": "credit institution; payment institution; account information service provider; electronic money institution",
    },
    {
        "article": "Article 24",
        "requirement_text": (
            "Establish, maintain and review a sound and comprehensive digital operational "
            "resilience testing programme as an integral part of the ICT risk management framework "
            "(non-microenterprises). The programme must follow a risk-based approach, ensure "
            "independent testing parties (internal or external) with conflict-of-interest controls, "
            "include procedures to prioritise / classify / remedy all issues revealed by tests, and "
            "ensure that at least yearly tests are conducted on all ICT systems and applications "
            "supporting critical or important functions."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) - not microenterprises",
    },
    {
        "article": "Article 25",
        "requirement_text": (
            "The testing programme must provide for the execution of an appropriate menu of tests: "
            "vulnerability assessments and scans, open-source analyses, network security "
            "assessments, gap analyses, physical security reviews, questionnaires and scanning "
            "software solutions, source code reviews where feasible, scenario-based tests, "
            "compatibility testing, performance testing, end-to-end testing and penetration "
            "testing. Central securities depositories and central counterparties must perform "
            "vulnerability assessments before any deployment or redeployment of new or existing "
            "applications and infrastructure components."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)); CSDs and CCPs subject to additional pre-deployment requirement",
    },
    {
        "article": "Article 26",
        "requirement_text": (
            "Carry out advanced testing through threat-led penetration testing (TLPT) at least "
            "every 3 years, where identified by the competent authority on the basis of impact on "
            "the financial sector, systemic character, ICT risk profile and ICT maturity. Each TLPT "
            "must cover several or all critical or important functions and be performed on live "
            "production systems. The scope must include the financial entity's ICT third-party "
            "service providers that support critical or important functions. Pooled testing is "
            "permitted under conditions in Article 26(4). Internal testers allowed under "
            "supervisory approval with external-tester rotation every 3 tests; significant credit "
            "institutions (SSM) must use external testers only. Aligned with the TIBER-EU framework."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity identified by competent authority as required to perform TLPT (Art 26(8)); excludes Art 16 simplified-framework entities and microenterprises",
    },
    {
        "article": "Article 27",
        "requirement_text": (
            "TLPT must only be carried out by testers of the highest suitability and reputability, "
            "with demonstrated expertise in threat intelligence, penetration testing and red team "
            "testing, certified by a Member State accreditation body or adhering to formal codes "
            "of conduct, providing audited assurance on risk management, and fully covered by "
            "professional indemnity insurance. Where internal testers are used, the threat "
            "intelligence provider must be external to the financial entity."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity required to perform TLPT (Art 26)",
    },
    {
        "article": "Article 28",
        "requirement_text": (
            "Manage ICT third-party risk as an integral component of the ICT risk management "
            "framework. Adopt and regularly review a strategy on ICT third-party risk, including a "
            "policy on the use of ICT services supporting critical or important functions. Maintain "
            "and update at entity, sub-consolidated and consolidated levels a register of "
            "information of all contractual arrangements on the use of ICT services, distinguishing "
            "those supporting critical or important functions from those that do not. Report at "
            "least yearly to the competent authority. Inform the competent authority in a timely "
            "manner of any planned contractual arrangement on ICT services supporting critical or "
            "important functions, and whenever a function becomes critical or important. Pre-"
            "contractual due diligence is mandatory; put in place exit strategies for ICT services "
            "supporting critical or important functions."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
    {
        "article": "Article 29",
        "requirement_text": (
            "Assess whether the envisaged ICT services contract leads to dependence on a TPP that "
            "is not easily substitutable, or to multiple critical-function contracts with the same "
            "TPP or closely connected TPPs. Where subcontracting of critical or important services "
            "is involved, weigh benefits and risks - in particular for ICT subcontractors "
            "established in a third country, considering insolvency law, data-protection "
            "enforcement and effective access to data and the length / complexity of subcontracting "
            "chains."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) entering ICT contracts supporting critical or important functions",
    },
    {
        "article": "Article 30",
        "requirement_text": (
            "Every contract for ICT services must include in writing at least: a clear description "
            "of all functions and services; locations of processing and storage; availability / "
            "authenticity / integrity / confidentiality provisions; data access, recovery and "
            "return on TPP insolvency / resolution / discontinuation; service level descriptions; "
            "TPP assistance during ICT incidents at no additional cost or at an ex-ante cost; full "
            "TPP cooperation with competent and resolution authorities; termination rights and "
            "notice periods; conditions for TPP participation in the financial entity's ICT "
            "security awareness training. For ICT services supporting critical or important "
            "functions, additionally: precise quantitative and qualitative SLA targets; notice "
            "and reporting on material changes affecting the TPP's ability to deliver; testing of "
            "the TPP's contingency plans; TPP participation in TLPT; unrestricted rights of "
            "access, inspection and audit by the financial entity, the competent authority and the "
            "Lead Overseer; adequate exit-strategy transition periods."
        ),
        "criticality": "critical",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) and its ICT third-party service providers",
    },
    {
        "article": "Article 45",
        "requirement_text": (
            "Where the financial entity participates in voluntary information-sharing arrangements "
            "on cyber threat information and intelligence (indicators of compromise, tactics, "
            "techniques, procedures, alerts, configuration tools), participation must take place "
            "within trusted communities, the arrangements must protect the sensitive nature of the "
            "shared information and comply with GDPR and competition law. Notify the competent "
            "authority of participation upon validation of membership, and of cessation of "
            "membership once it takes effect."
        ),
        "criticality": "informational",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t)) participating in voluntary information-sharing arrangements",
    },
    {
        "article": "Article 14",
        "requirement_text": (
            "Establish crisis communication plans enabling responsible disclosure of at least major "
            "ICT-related incidents or vulnerabilities to clients and counterparts, and to the "
            "public as appropriate. Implement separate communication policies for internal staff "
            "and for external stakeholders. Designate at least one person responsible for "
            "implementing the communication strategy for ICT-related incidents and for the public "
            "and media function."
        ),
        "criticality": "important",
        "applicable_entity": "financial entity (Art 2(1)(a)-(t))",
    },
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(LawRequirement).filter(LawRequirement.law_id == DORA_LAW_ID).count()
        if existing:
            print(f"DORA already has {existing} requirements seeded - skipping insertion")
            return
        inserted = 0
        for r in REQUIREMENTS:
            req = LawRequirement(
                law_id=DORA_LAW_ID,
                cluster_id=DORA_CLUSTER_ID,
                article=r["article"][:50],
                requirement_text=r["requirement_text"],
                criticality=r["criticality"],
                applicable_entity=r["applicable_entity"][:100],
            )
            db.add(req)
            inserted += 1
        db.commit()
        print(f"inserted {inserted} DORA requirements into law_requirements (law_id={DORA_LAW_ID}, cluster_id={DORA_CLUSTER_ID})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
