# DORA — Digital Operational Resilience Act (Regulation (EU) 2022/2554)

## QUICK FACTS
- Short name: DORA (Digital Operational Resilience Act)
- Full title: Regulation (EU) 2022/2554 of the European Parliament and of the Council of 14 December 2022 on digital operational resilience for the financial sector and amending Regulations (EC) No 1060/2009, (EU) No 648/2012, (EU) No 600/2014, (EU) No 909/2014 and (EU) 2016/1011
- CELEX: 32022R2554
- OJ reference: OJ L 333/1 of 27 December 2022 (79 pages)
- EUR-Lex URL: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554
- **Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2022-2554_dora/index.html — plain-language DORA explainer with article-by-article walk-through, glossary, the 5 pillars, the Oversight Framework, and links to all official sources
- Legal basis: Article 114 TFEU (internal market)
- Entry into force: 16 January 2023 (20 days after OJ publication)
- **Date of application: 17 January 2025** (2-year transition window)
- Companion act: **Directive (EU) 2022/2556** — amends 8 financial-sector directives (UCITS, Solvency II, AIFMD, CRD IV, BRRD, MiFID II, PSD2, IORP II) to align with DORA
- Lex specialis vs: **NIS 2 Directive (EU) 2022/2555** (recital 16)
- Amends 5 regulations: CRA Regulation (1060/2009), EMIR (648/2012), MiFIR (600/2014), CSDR (909/2014), BMR (2016/1011)
- Responsible DG: DG FISMA
- EP lead committee: ECON
- Authorities: EBA, ESMA, EIOPA (the three ESAs), through their Joint Committee
- Scope: **9 Chapters, 64 articles, 106 recitals**; 65 definitions in Article 3
- **In-scope universe: 21 categories of financial entities + ICT third-party service providers** (Art 2). Around 22,000 EU financial entities per recital 3.
- **The 5 pillars (covered below):** ICT risk management; ICT-related incident reporting; digital operational resilience testing; ICT third-party risk management; information-sharing arrangements
- **Plus the Oversight Framework** (Chapter V Section II) — EU-level oversight of designated **critical ICT third-party service providers (CTPPs)** by a Lead Overseer drawn from EBA / ESMA / EIOPA
- **TLPT (threat-led penetration testing) — every 3 years** for systemically-important entities; based on TIBER-EU framework (Art 26)
- **Periodic penalty payment on a CTPP:** up to **1% of average daily worldwide turnover** in the preceding business year, daily, max 6 months (Art 35(8))
- **Third-country CTPPs:** must establish a Union subsidiary within **12 months** of designation (Art 31(12))
- **Microenterprise threshold:** <10 employees AND turnover/balance ≤ €2 million (Art 3(60))
- **Reporting cadence on a major ICT-related incident:** initial notification → intermediate report(s) → final report after root-cause analysis (Art 19(4))
- Review: by **17 January 2028** (Art 58)

## Overview

DORA is the EU's first horizontal cybersecurity Regulation for the financial sector. It consolidates and upgrades ICT risk requirements that had been scattered across CRD IV, MiFID II, Solvency II, UCITS, AIFMD, PSD2, EMIR, CSDR, CRA Regulation, BMR and elsewhere, and brings them under a single Single-Rulebook-style act.

DORA is **directly applicable** (a Regulation, not a Directive — no national transposition) precisely because uneven national approaches to ICT risk had been fragmenting the Single Market for cross-border financial entities (recitals 9-14).

It covers **five core areas** (Article 1):
1. **ICT risk management** — governance, identification, protection, detection, response/recovery, learning, communication
2. **Reporting of major ICT-related incidents** — and voluntary notification of significant cyber threats — to competent authorities
3. **Digital operational resilience testing** — basic testing yearly; advanced threat-led penetration testing (TLPT) every 3 years for systemic entities
4. **Management of ICT third-party risk** — register of information, exit strategies, mandatory contractual clauses
5. **Information-sharing arrangements** — voluntary cyber-threat-intelligence exchange in trusted communities

Plus a **sixth, sui generis** building block: a **Union-level Oversight Framework** for **critical ICT third-party service providers** (Chapter V, Section II) — the first time the EU directly oversees non-financial service providers (cloud, software, data-centre, data-analytics) at Union level, on the basis that the financial system's resilience now depends on a small number of them.

It does NOT cover: prudential capital requirements (those stay in CRR / Solvency II), market conduct, or the substantive financial-services authorisation regimes (those stay in their sectoral acts).

## Structure — 9 Chapters

| Chapter | Articles | Subject |
|---|---|---|
| I | 1-4 | General provisions (subject matter, scope, definitions, proportionality) |
| II | 5-16 | ICT risk management framework + simplified regime |
| III | 17-23 | ICT-related incident management, classification and reporting |
| IV | 24-27 | Digital operational resilience testing (including TLPT) |
| V Section I | 28-30 | Managing ICT third-party risk — key principles |
| V Section II | 31-44 | **Oversight Framework** for critical ICT third-party service providers |
| VI | 45 | Information-sharing arrangements |
| VII | 46-56 | Competent authorities |
| VIII | 57 | Delegated acts |
| IX | 58-64 | Review clause + amendments to 5 regulations + entry into force |

## Scope — 21 categories of financial entities

Article 2(1) brings into scope, regardless of size unless explicitly carved out:
(a) credit institutions; (b) payment institutions (including PSD2-exempt); (c) account information service providers; (d) electronic money institutions (including 2009/110/EC-exempt); (e) investment firms; (f) crypto-asset service providers and issuers of asset-referenced tokens (MiCA); (g) central securities depositories (CSDR); (h) central counterparties (EMIR); (i) trading venues (MiFID II); (j) trade repositories; (k) managers of alternative investment funds (AIFMD); (l) UCITS management companies; (m) data reporting service providers (MiFIR APAs/CTPs/ARMs); (n) insurance and reinsurance undertakings; (o) insurance / reinsurance / ancillary insurance intermediaries; (p) institutions for occupational retirement provision (IORPs); (q) credit rating agencies; (r) administrators of critical benchmarks; (s) crowdfunding service providers (Reg 2020/1503); (t) securitisation repositories; (u) **ICT third-party service providers** (only for the Oversight Framework).

Entities (a) to (t) are collectively "financial entities".

Carve-outs (Art 2(3)): small AIFMs (Art 3(2) AIFMD), small insurers (Art 4 Solvency II), IORPs with ≤15 members, MiFID Art 2/3 exempt persons, microenterprise insurance/reinsurance/ancillary insurance intermediaries, post-office giro institutions.

Member States *may* additionally exempt entities listed in Art 2(5) points (4)-(23) of CRD IV.

## Pillar 1 — ICT Risk Management (Chapter II, Articles 5-16)

### Governance (Art 5)
The **management body bears ultimate responsibility** for ICT risk. It must define, approve and oversee the ICT risk management framework, set the risk tolerance, approve the ICT business continuity policy + response and recovery plans, allocate the ICT budget, approve the ICT third-party policy, and keep itself trained on ICT risk (Art 5(4)).

Financial entities (other than microenterprises) must establish a dedicated **role to monitor ICT third-party arrangements**, or designate a member of senior management responsible for that exposure (Art 5(3)).

### ICT risk management framework (Art 6)
Must be sound, comprehensive and well-documented. Reviewed at least yearly, plus after every major ICT-related incident or supervisory finding. Subject to internal audit (Art 6(6)). Must include a **digital operational resilience strategy** (Art 6(8)) covering risk tolerance, security objectives, ICT reference architecture, detection mechanisms, current resilience status, testing plan, communication strategy.

Microenterprises and small/non-interconnected entities follow a **simplified framework (Art 16)** — Articles 5 to 15 do not apply; instead a leaner list of 8 obligations.

### ICT systems, protocols and tools (Art 7)
Reliable, scalable to peak loads, technologically resilient.

### Identification (Art 8)
Map all ICT-supported business functions, classify information assets and ICT assets, identify all ICT third-party dependencies, run risk assessment on every major change, conduct yearly ICT risk assessments on legacy systems.

### Protection and prevention (Art 9)
Information security policy, network/infrastructure management, access control, strong authentication, cryptography, ICT change management, patch management. Networks must be designed to be **instantaneously severable or segmentable** to prevent contagion.

### Detection (Art 10)
Mechanisms to detect anomalous activities, multi-layer controls, alert thresholds, automatic escalation.

### Response and recovery (Art 11)
ICT business continuity policy, response and recovery plans, **business impact analysis (BIA)**, redundant ICT capacities, testing at least yearly (including cyber-attack scenarios and primary↔redundant switchovers for non-microenterprises), crisis management function.

### Backup, restoration and recovery (Art 12)
Backup systems segregated physically and logically from source ICT systems. **CSDs must maintain at least one secondary processing site** at a geographical distance from the primary, with full continuity capability (Art 12(5)).

### Learning and evolving (Art 13)
Post-incident reviews, lessons-learned feedback into the framework, **ICT security awareness programmes and digital operational resilience training as compulsory staff modules** (Art 13(6)) covering all employees and senior management.

### Communication (Art 14)
Crisis communication plans for responsible disclosure of major incidents or vulnerabilities. At least one person responsible for the public/media function.

### RTS (Art 15)
ESAs to develop common draft regulatory technical standards specifying ICT risk-management policies, access management, detection mechanisms, business-continuity policy components, testing, response/recovery, and the framework-review report — submitted to the Commission by **17 January 2024**.

## Pillar 2 — ICT-related Incident Reporting (Chapter III, Articles 17-23)

### Incident management process (Art 17)
Detect, manage, notify. Record all ICT-related incidents and significant cyber threats. Root-cause identification. Early warning indicators. Major incidents escalated to senior management and management body.

### Classification (Art 18)
Six criteria for determining incident impact:
1. Number / relevance of clients or financial counterparts affected, transactions affected, reputational impact
2. Duration and downtime
3. Geographical spread (especially if affecting >2 Member States)
4. Data losses (availability, authenticity, integrity, confidentiality)
5. Criticality of services affected
6. Economic impact (direct + indirect, absolute + relative)

A **major ICT-related incident** has a "high adverse impact" on systems supporting critical or important functions. A **significant cyber threat** has the technical characteristics that could result in a major incident.

### Reporting (Art 19)
Mandatory reporting of major incidents to the competent authority (a single national authority designated if the entity has multiple supervisors). **Three-stage reporting**:
- **Initial notification** — as soon as the materiality thresholds are met
- **Intermediate report(s)** — whenever status changes significantly
- **Final report** — after root-cause analysis, with actual impact figures

Significant cyber threats may be notified **voluntarily**. Cross-border impacts go through EBA/ESMA/EIOPA → notification to relevant Member States. Significant credit institutions (under SSM): report to NCA, which immediately transmits to ECB.

Materiality thresholds, time limits and templates set by RTS + ITS (Art 20), submitted to the Commission by **17 July 2024**.

### EU Hub feasibility study (Art 21)
ESAs to assess by **17 January 2025** whether a single EU Hub for major ICT-related incident reporting is feasible.

### Payment-related incidents (Art 23)
Credit institutions, payment institutions, account information service providers and electronic money institutions report under DORA the operational/security payment-related incidents previously reported under PSD2 Art 96 — irrespective of whether ICT-related.

## Pillar 3 — Digital Operational Resilience Testing (Chapter IV, Articles 24-27)

### General testing (Arts 24-25)
A **comprehensive testing programme** as integral part of the ICT risk management framework. Risk-based. Tests performed by independent parties (internal or external). Wide menu of tools: vulnerability assessments and scans, open-source analyses, network security assessments, gap analyses, physical security reviews, questionnaires, scanning software, source-code reviews where feasible, scenario-based tests, compatibility testing, performance testing, end-to-end testing, penetration testing. **At least yearly** tests on all ICT systems and applications supporting critical or important functions.

CSDs and CCPs must perform vulnerability assessments before any deployment or redeployment of new or existing applications and infrastructure components.

### Advanced testing — TLPT (Art 26)
**Threat-led penetration testing** — a framework that mimics the tactics, techniques and procedures of real-life threat actors, delivering a controlled, bespoke, intelligence-led (red team) test of the financial entity's **critical live production systems**.

- Performed **at least every 3 years** (frequency may be adjusted by the competent authority)
- Required only of financial entities **identified** by the competent authority based on (Art 26(8)): impact on the financial sector, possible financial-stability concerns including systemic character, specific ICT risk profile and ICT maturity
- Must cover several or all critical or important functions
- Pooled TLPT permitted (Art 26(4)) where ICT third-party participation could adversely impact other customers — coordinated by one designated financial entity
- Internal testers allowed with prior supervisory approval, no conflict of interest, periodic rotation (external testers every 3 tests, Art 26(8))
- **Significant credit institutions (SSM): external testers only**
- Attestation provided by the authority for mutual recognition across the EU; the financial entity retains full responsibility
- Aligned with the **TIBER-EU** framework
- RTS (Art 26(11)) submitted to the Commission by **17 July 2024**

### Tester requirements (Art 27)
Highest suitability and reputability, demonstrable expertise in threat intelligence + penetration testing + red team testing, certified by a Member State accreditation body or adhering to formal codes of conduct, audited assurance on risk management, professional indemnity insurance.

## Pillar 4 — ICT Third-Party Risk Management (Chapter V Section I, Articles 28-30)

### Principles (Art 28)
The financial entity **at all times remains fully responsible** for compliance — outsourcing does not transfer obligations.

Mandatory artefacts:
- **Strategy on ICT third-party risk**, reviewed regularly by the management body
- **Register of information** of all contractual arrangements on the use of ICT services, distinguishing those that support critical or important functions from those that do not. Reportable yearly to the competent authority; full register or sections produced on request (Art 28(3))
- Pre-contracting due diligence: criticality assessment, supervisory conditions, ICT concentration risk analysis, due diligence on the prospective TPP, conflict-of-interest screening (Art 28(4))
- Termination triggers (Art 28(7)): significant breach by the TPP, material changes affecting performance, evidenced ICT risk-management weaknesses, where the competent authority can no longer effectively supervise the financial entity
- **Exit strategies** for ICT services supporting critical or important functions (Art 28(8)) — comprehensive, documented, sufficiently tested

### Concentration risk (Art 29)
Pre-contracting analysis: would the contract result in dependence on a TPP that is not easily substitutable, or in multiple critical-function contracts with the same TPP / closely connected TPPs? Subcontracting analysis especially where the subcontractor is in a third country: insolvency law of that third country, data-protection enforcement, length / complexity of subcontracting chains.

### Key contractual provisions (Art 30)
Every contract for ICT services must include at least: full description of functions/services; locations of processing and storage; availability/authenticity/integrity/confidentiality provisions; data-access, recovery and return on insolvency or termination; service-level descriptions; TPP assistance during ICT incidents; full cooperation with competent and resolution authorities; termination rights with minimum notice; conditions for TPP participation in the financial entity's training programmes.

**For ICT services supporting critical or important functions**, additionally: precise quantitative + qualitative SLA performance targets; notice periods and reporting obligations on developments materially impacting service delivery; requirement to implement and test business contingency plans; participation in the financial entity's TLPT; **unrestricted rights of access, inspection and audit** by the financial entity, the competent authority and the Lead Overseer (with right to take copies on site); **adequate transition periods** in exit strategies.

Microenterprises may delegate audit rights to an independent third party appointed by the TPP (Art 30(3) last subparagraph).

## The Oversight Framework — critical ICT third-party service providers (Chapter V Section II, Articles 31-44)

The most innovative part of DORA. The EU directly oversees, at Union level, the cloud / software / data-centre / data-analytics providers on whose continued availability the financial system depends.

### Designation (Art 31)
The three ESAs through their Joint Committee, on recommendation from the Oversight Forum (Art 32), designate an ICT third-party service provider as **critical** ("CTPP") based on:
1. **Systemic impact** on the stability, continuity or quality of financial services if the provider fails
2. **Systemic character** of the financial entities relying on it (G-SIIs, O-SIIs and their interdependencies)
3. **Reliance** of financial entities on its services for critical or important functions
4. **Degree of substitutability** — limited alternatives, market share, technical complexity, migration cost and risk

The list of CTPPs is published yearly. ICT TPPs not automatically designated **may opt in** by application (Art 31(11)).

**Third-country CTPPs must establish an EU subsidiary within 12 months of designation** (Art 31(12)) and may continue providing services from outside the Union, but oversight presence in the EU is mandatory.

Carved out (Art 31(8)): financial entities providing ICT services to other financial entities, providers already under ESCB oversight (TARGET, T2S etc.), intra-group providers, and providers active only in one Member State serving entities active only in that Member State.

### Structure (Art 32)
- **Joint Committee** (ESAs) — cross-sector coordination
- **Oversight Forum** — sub-committee, prepares joint positions, includes Chairs of the ESAs, one high-level NCA representative per Member State, ECB / ESRB / ENISA / Commission as observers
- **Joint Oversight Network (JON, Art 34)** — coordinates the three Lead Overseers

### Lead Overseer (Art 31(1)(b), Art 33)
For each CTPP, the Lead Overseer is the ESA (EBA, ESMA or EIOPA) responsible for the financial-entity sub-sector whose entities together hold the largest share of total assets among the financial entities using that CTPP. The Lead Overseer is the **primary point of contact** for the CTPP and conducts the assessment of governance, ICT risk management, business continuity, physical security, incident management, data portability, testing, audits and standards.

The Lead Overseer adopts a yearly **individual oversight plan** per CTPP (Art 33(4)); the CTPP may submit a reasoned statement within 15 calendar days before adoption.

### Powers of the Lead Overseer (Art 35)
- Request all relevant information and documentation (Art 37)
- General investigations (Art 38) — examine records, take copies, summon representatives, interview, request data-traffic records
- On-site and off-site inspections (Art 39) — enter business premises, seal premises/books/records during inspection
- Issue **recommendations** on ICT security standards, service terms preventing single points of failure or amplification of systemic impact, **planned subcontracting** including with subcontractors in third countries, and (most powerful) **require the CTPP to refrain from a further subcontracting arrangement** where it would be in a third country, concern a critical/important function, and the Lead Overseer deems it poses a clear and serious risk to Union financial stability
- **Periodic penalty payments** to compel compliance: up to **1% of average daily worldwide turnover**, imposed on a daily basis until compliance, max 6 months (Art 35(8))

The Lead Overseer can exercise these powers outside the Union (Art 36) if the CTPP consents and the relevant third-country authority does not object, subject to administrative cooperation arrangements between the ESAs and that authority.

### Follow-up (Art 42)
Within 60 calendar days, the CTPP either notifies that it will follow the recommendation, or provides a reasoned explanation for not following. If the explanation is insufficient or no notification is provided, the Lead Overseer publicly discloses the non-compliance.

Competent authorities — as a measure of last resort, after notification + (voluntary) consultation with NIS 2 authorities — may take a decision (Art 42(6)) **requiring financial entities to temporarily suspend, in part or completely, the use of a service** provided by the CTPP, or to terminate the relevant contractual arrangements, until the identified risks are addressed.

### Oversight fees (Art 43)
Lead Overseer expenditure is fully fee-funded by CTPPs, proportionate to turnover. The amount + payment mechanism set by delegated act by 17 July 2024.

### International cooperation (Art 44)
EBA, ESMA and EIOPA may conclude administrative arrangements with third-country regulatory and supervisory authorities to share best practices on ICT-third-party risk review. Five-yearly confidential report to the EP, Council and Commission.

## Pillar 5 — Information-Sharing Arrangements (Chapter VI, Article 45)

Financial entities may **voluntarily** exchange cyber threat information and intelligence (indicators of compromise, tactics, techniques, procedures, alerts, configuration tools) within **trusted communities**, governed by rules of conduct that respect business confidentiality, GDPR and competition law. Participation must be notified to the competent authority.

## Competent authorities and penalties (Chapter VII, Articles 46-56)

### Competent authorities (Art 46)
DORA does not create new national supervisors — it routes compliance through the existing sectoral competent authorities (CRD IV for credit institutions, PSD2 for payment institutions, IFD/MiFID II for investment firms, MiCA for crypto-asset service providers, CSDR for CSDs, EMIR for CCPs and trade repositories, MiFID II / MiFIR for trading venues and data reporting service providers, AIFMD for AIFMs, UCITS for management companies, Solvency II for insurers/reinsurers, IDD for insurance intermediaries, IORP II for pension funds, CRA Regulation for credit rating agencies, BMR for critical benchmarks, Reg 2020/1503 for crowdfunding, Reg 2017/2402 for securitisation repositories). The ECB supervises significant credit institutions under the SSM.

### Administrative penalties and remedial measures (Art 50)
Member States lay down rules that are effective, proportionate and dissuasive. Powers include: cease-and-desist orders, temporary/permanent cessation of practices, pecuniary measures, data-traffic record requests (where permitted nationally), public notices identifying the person and the breach.

### Criminal penalties (Art 52)
Member States may apply criminal penalties instead of administrative ones; if so, coordination duties with judicial authorities apply.

### Notification duty (Art 53)
Member States must notify implementing laws to the Commission, ESMA, EBA and EIOPA by **17 January 2025**.

### Publication (Art 54)
Competent authorities publish administrative penalty decisions on their website without undue delay (with anonymisation / deferral / non-publication safety valves).

### Data protection (Art 56)
Personal data retention up to **15 years** (except where pending court proceedings require longer).

## Definitions (Article 3) — the load-bearing 18

The full Article 3 has 65 definitions. The ones that drive the rest of the Regulation:

| # | Term | Captures |
|---|---|---|
| 1 | digital operational resilience | The financial entity's ability to ensure continued provision of financial services through ICT disruptions |
| 5 | ICT risk | Reasonably identifiable circumstance that could compromise security of network/information systems |
| 8 | ICT-related incident | Unplanned event(s) compromising security of N&IS or adversely affecting availability/authenticity/integrity/confidentiality of data or services |
| 10 | major ICT-related incident | ICT-related incident with high adverse impact on systems supporting critical or important functions |
| 13 | significant cyber threat | Cyber threat that could result in a major ICT-related incident |
| 17 | threat-led penetration testing (TLPT) | Intelligence-led red team test of live production systems |
| 18 | ICT third-party risk | Risk arising from the use of ICT services provided by third parties (incl. subcontractors) |
| 19 | ICT third-party service provider | Undertaking providing ICT services |
| 20 | ICT intra-group service provider | Undertaking part of a financial group providing predominantly ICT services within that group |
| 21 | ICT services | Digital and data services provided through ICT systems on an ongoing basis, hardware-as-a-service included; analogue telephony excluded |
| 22 | critical or important function | Function whose disruption would materially impair financial performance, soundness or continuity, or compliance with authorisation conditions |
| 23 | critical ICT third-party service provider | TPP designated as critical under Article 31 |
| 29 | ICT concentration risk | Exposure to one or related critical TPPs creating a dependency that could endanger critical/important functions or Union financial stability |
| 60 | microenterprise | <10 persons AND turnover/balance ≤ €2 million |
| 61 | Lead Overseer | ESA appointed under Art 31(1)(b) |
| 63 | small enterprise | 10-49 persons, turnover/balance > €2M but ≤ €10M |
| 64 | medium-sized enterprise | <250 persons, turnover ≤ €50M or balance ≤ €43M |
| 65 | public authority | Government or other public administration, including national central banks |

## Headline numbers and dates

| Item | Value | Source |
|---|---|---|
| Application date | **17 January 2025** | Art 64 |
| Entry into force | 16 January 2023 | Art 64 |
| RTS submission deadline (most) | 17 January 2024 | Arts 15, 16, 18, 28, 41 |
| RTS / ITS / delegated-act deadline (rest) | 17 July 2024 | Arts 20, 26, 30, 31, 43 |
| EU Hub feasibility report deadline | 17 January 2025 | Art 21 |
| Member State notification of implementing law | 17 January 2025 | Art 53 |
| Auditor / audit-firm review report | 17 January 2026 | Art 58(3) |
| Full DORA review report | 17 January 2028 | Art 58(1) |
| TLPT frequency | every 3 years | Art 26(1) |
| External tester rotation | every 3 tests if using internal | Art 26(8) |
| Periodic penalty payment cap on CTPP | 1% average daily worldwide turnover | Art 35(8) |
| Max penalty-payment duration | 6 months | Art 35(7) |
| Third-country CTPP subsidiary deadline | 12 months from designation | Art 31(12) |
| Reasoned-statement window after designation | 6 weeks | Art 31(5) |
| Microenterprise threshold | <10 people AND ≤ €2M | Art 3(60) |
| Small / non-interconnected investment firm threshold | Art 12(1) IFR | via Art 3(34) |
| IORP carve-out | ≤15 members total | Art 2(3)(c) |
| Personal data retention | max 15 years | Art 56(2) |
| Financial entities in scope | ~22,000 (recital 3 estimate) | recital 3 |
| Lead Overseer turnover threshold for fee | proportionate (delegated act) | Art 43 |

## Lineage and Family Tree

| Year | Step | Significance |
|---|---|---|
| 2016 | NIS Directive (EU) 2016/1148 | First horizontal EU cybersecurity instrument; only certain credit institutions, trading venues and CCPs identified at MS level |
| 2018 | Commission FinTech Action Plan (8 March) | Identifies need for sector-specific ICT resilience instrument |
| 2019 | Joint ESA technical advice (April) | EBA/EIOPA/ESMA call for coherent EU approach to ICT risk in finance |
| Sept 2020 | DORA proposal (COM/2020/595) | Part of the Digital Finance Package, alongside MiCA |
| 14 Dec 2022 | DORA adopted | Regulation (EU) 2022/2554 + Directive (EU) 2022/2556 published together (OJ L 333) |
| 14 Dec 2022 | NIS 2 adopted (same day) | Directive (EU) 2022/2555 — DORA is **lex specialis** vs NIS 2 |
| 16 Jan 2023 | Entry into force | Day 20 after OJ |
| 17 Jan 2024 | First-batch RTS deadline | ICT risk management, simplified framework, incident classification, ICT third-party policy, register of information |
| 17 July 2024 | Second-batch RTS / ITS / delegated act deadline | Incident reporting templates, TLPT, subcontracting, CTPP designation criteria, oversight fees |
| **17 Jan 2025** | **DORA applies in full** | Compliance enforced from this date |
| 17 Jan 2026 | Auditor review report (Art 58(3)) | Whether to extend DORA to statutory auditors / audit firms |
| 17 Jan 2028 | Full review report (Art 58(1)) | Designation criteria, voluntary cyber-threat notification, third-country regime, JON effectiveness |

## Companion act — Directive (EU) 2022/2556

The DORA Directive (32022L2556) amends **8 financial-sector Directives** to align them with DORA, by replacing or narrowing their pre-existing operational-risk / ICT-risk provisions and inserting a cross-reference to DORA:
- Directive 2009/65/EC (UCITS)
- Directive 2009/138/EC (Solvency II)
- Directive 2011/61/EU (AIFMD)
- Directive 2013/36/EU (CRD IV)
- Directive 2014/59/EU (BRRD)
- Directive 2014/65/EU (MiFID II)
- Directive (EU) 2015/2366 (PSD2)
- Directive (EU) 2016/2341 (IORP II)

Plus DORA itself amends **5 Regulations** (Arts 59-63): CRA Regulation (1060/2009), EMIR (648/2012), MiFIR (600/2014), CSDR (909/2014), BMR (2016/1011) — same logic: narrow or replace their ICT-related provisions and route them through DORA.

## What DORA does NOT do

- It does not set **capital requirements** for ICT risk — that is a deliberate departure from the traditional "set a capital number" approach to operational risk (recital 12). DORA is a **qualitative** instrument: protect, detect, contain, recover, learn.
- It does not impose **data localisation** — Recital 82 is explicit: DORA does not require data storage or processing to be undertaken in the Union, even for CTPPs.
- It does not create new sectoral competent authorities — it routes through the existing CRD IV, MiFID II, Solvency II, PSD2 etc. authorities (Art 46).
- It does not replace **NIS 2** — financial entities remain part of the NIS 2 ecosystem (Cooperation Group, CSIRTs) for cross-sector learning, but for the substantive ICT-risk + incident-reporting obligations DORA is lex specialis (recital 16).
- It does not regulate the **financial-services aspect** of any product. The substantive sectoral acts (CRR, MiFID II, MiCA, AIFMD, UCITS, Solvency II, PSD2 etc.) continue to apply unchanged for everything other than ICT risk.

## Useful References

- **Official text**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554
- **DORA Directive (companion)**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2556
- **OJ L 333, 27 December 2022**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L:2022:333:TOC
- **NIS 2 Directive (related)**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2555
- **TIBER-EU framework** (ECB): https://www.ecb.europa.eu/paym/cyber-resilience/tiber-eu/html/index.en.html
- **ESA Joint Committee on DORA**: https://www.eba.europa.eu / https://www.esma.europa.eu / https://www.eiopa.europa.eu
- **ENISA**: https://www.enisa.europa.eu
- **Commission Digital Finance Strategy**: https://finance.ec.europa.eu/digital-finance_en

## Related Brubru Guides

- `crr_capital_requirements_regulation.md` — the prudential capital framework (separate axis; DORA does not set capital)
- `gdpr_data_protection.md` — interaction via Art 9 (data protection), Art 30 (data return on TPP insolvency), Art 56 (personal data retention)
- `mica_markets_in_crypto_assets.md` (if present) — crypto-asset service providers and asset-referenced token issuers are in scope of DORA via Art 2(1)(f)
- `nis2_directive.md` (if present) — DORA is lex specialis vs NIS 2 for financial entities
- `dsa_enforcement.md` — cross-Union oversight architecture precedent
