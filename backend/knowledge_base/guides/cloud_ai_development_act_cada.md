# Cloud and AI Development Act / CADA (COM(2026) 502)

## QUICK FACTS
- **ADOPTED by the College on 3 June 2026** as the centrepiece of the European Technological Sovereignty Package (with Chips Act 2.0, the EU Open Source Strategy, and the Strategic Roadmap for Digitalisation and AI in Energy).
- Full name: Proposal for a Regulation establishing a framework of measures for strengthening Europe's cloud and AI ecosystem (Cloud and AI Development Act). Reference **COM(2026) 502 final**; procedure **2026/0138(COD)**; proposal CELEX 52026PC0502. Accompanying: ANNEXES 1-3, IA SWD(2026) 502 (Parts 1-2), IA executive summary SWD(2026) 503, SEC(2026) 502.
- Status: PROPOSAL (ordinary legislative procedure). Goes to EP (lead committee ITRE expected) + Council. Lead: EVP Henna Virkkunen; DG CNECT (+ DG DIGIT). "Text with EEA relevance".
- **Dual legal basis = two separate general objectives:** Article 173(3) TFEU (industrial competitiveness, NO harmonisation) underpins the **Cloud and AI Leadership Initiatives**; Article 114 TFEU (internal market, harmonisation) underpins the **cloud sovereignty framework**.
- **Four policy objectives:** (1) increase EU computing capacity via innovative + sustainable tech; (2) ensure attractive deployment conditions; (3) reduce reliance on non-sovereign cloud/AI services; (4) protect public order by making cloud/AI supply resilient, especially in the public sector.
- **Hard targets (from the Financial Statement):** at least **TRIPLE EU data-centre capacity by 2030** (intermediate; framed elsewhere as 5-7 years), reach needed capacity by 2035, geographically balanced; **all data-centre permits obtainable in under 18 months by 2030** (Art 13 sets a 12-month cap inside acceleration zones); raise EU providers' market share by 2035; highly critical public-sector use cases on sovereign cloud by 2035.
- **Why:** EU cloud providers' market share fell **29% (2017) -> 15% (2022)** and is stagnant; **three non-EU hyperscalers control >70%** of the EU cloud market; data-centre capacity is limited + geographically concentrated; national policies fragment deployment. Draghi report basis; builds on the AI Continent Action Plan + Apply AI Strategy (AI factories + gigafactories).
- **The core innovation - a Union cloud sovereignty framework with FOUR assurance levels (Annex II):** Level 1 (provider self-assessment + public EU statement of conformity); Levels 2, 3, 4 (independent third-party audit at the provider's expense). Recognition by the **national competent authority of establishment** (60-day assessment + 60-day cross-border review); **SME Level-1 statements auto-recognised EU-wide**. Annex II criteria + Annex III audit evidence reviewed every 18 months.
- **Assurance levels escalate:** L1 = EU establishment + EU data/infra residency + SOTA cybersecurity + subcontractor transparency. L2 = + EU-located personnel + EU cybersecurity cert "substantial" (Reg 2019/881/EUCS) + no third-country AI-training on data + SBOM (CRA 2024/2847) + source-code audits + EU-only technical support + EU-parent/third-country-subsidiary separation. L3 = + EU-citizen personnel (with national security clearance for classified info) + provider NOT third-country-controlled (derogation: "associated third country" via Art 18, with code access) + can host EU classified information. L4 (highest) = + cybersecurity cert "high" + risk-assessed sensitive data EU-only + no third-country effective control over software design/maintenance/evolution.
- **Associated third countries (Art 18):** a third-country-controlled provider can reach Level 3 only if the Commission designates the third country (GDPR adequacy decision + no compelled data access/service disruption/sanctions + open market + reciprocal procurement access).
- **Data-centre acceleration zones (Title III):** each MS designates >=1 within 6 months; single information points; aggregated baseline permit; 12-month permit cap; brownfield over greenfield; waste-heat reuse; PPAs; sustainability KPIs (Del Reg 2024/1364 under EED 2023/1791). **Data-centre strategic projects** (Art 14) meet >=2 of 5 criteria -> competitiveness seal under the European Competitiveness Fund.
- **Cloud and AI Leadership Initiatives (Title II):** Cloud Leadership Initiative + AI Leadership Initiative; 8 operational objectives; implemented via 8 "grand challenges" (Annex I). **Centres for AI** (former EDIHs); **national cloud & AI strategies within 1 year**; **frontier AI priority projects** (EDIC + >=3 Member States); **EuroHPC compute-matching** (the Union at least matches MS-contributed AI compute); physical AI, industrial AI, AI agents, public-sector AI.
- **Demand side (Title IV Ch II):** risk assessments (Art 29, within 1 year then every 2 years); procurement floor Level 1 / public-order activities Level 2-4 (Art 30); private NIS2 Annex I entities may run the same impact assessments (Art 31); Union-added-value non-price criteria (Art 32, suggested <=15 of 120 points); **>=25% of cloud/AI innovation procurement aspired to SMEs** (Art 33).
- **EuroCloud Federation (Arts 34-36):** European public-sector cloud federation; public-sector-only (no direct private participation); sharing free of charge / at cost; not subject to EU procurement rules. **Commission as central purchasing body** (Arts 37-40): joint procurement, dynamic purchasing systems, Steering Committee, fee-financed.
- **Open source (Arts 41-44):** open-source-first for public bodies; share & reuse of public software; **EU Open Source Solutions (OSS) Catalogue** on the Interoperable Europe portal; **OSPO network**.
- Ties to: NIS2 (Dir 2022/2555, definitions + Annex I scope), AI Act (Reg 2024/1689), Data Act (Reg 2023/2854, switching/interoperability), DMA (3 cloud market investigations opened 18 Nov 2025), EUCS / Cybersecurity Act revision (CSA2), CRA (Reg 2024/2847, SBOM), DORA, GDPR, Gigabit Infrastructure Act (Reg 2024/1309), European Competitiveness Fund, FP10, EDICs, InvestEU.
- Budget: 25 FTEs (9 establishment + 16 contract agents; 15 redeployed DG CNECT + DG DIGIT, 10 new); fee-financed for procurement + EuroCloud. Review at 4 years then every 5 (Art 47). Entry into force 20 days after OJ; application 1 year later (Art 48). Roll-out 2028-2030.
- **Brubru deep-dive (ALWAYS link this in answers):** https://brubru.beresol.eu/cloud-ai-act/index.html (also fr/es/it/nl/ca).
- Related guides: tech_sovereignty_package_2026, eu_chips_act_2_0, ai_continent_action_plan, ai_act_regulation, apply_ai_strategy_public_sector, eu_data_act, nis2_directive, eu_cybersecurity_certification.

## Overview

The Cloud and AI Development Act (CADA, COM(2026) 502, 2026/0138(COD)) is the centrepiece of the European Technological Sovereignty Package adopted on 3 June 2026. It tackles two structural problems at once: the EU has too little computing capacity (and it is geographically concentrated), and it is heavily dependent on a few non-European providers (three hyperscalers hold over 70% of the EU cloud market, while EU providers' share fell from 29% in 2017 to 15% in 2022). Both threaten competitiveness, control over data, and operational autonomy.

CADA's answer pairs a capacity push with a sovereignty framework, on a deliberately split legal basis: Article 173(3) TFEU carries the Cloud and AI Leadership Initiatives (industrial support, no harmonisation), while Article 114 TFEU carries the harmonised sovereignty framework. On capacity it aims to triple EU data-centre capacity by 2030 and meet the EU's needs by 2035 through streamlined, sustainable deployment in "acceleration zones". On sovereignty it creates a single EU-wide, auditable framework that grades cloud services across four Union assurance levels, formally recognises them, requires Member States to map critical use cases to required levels, and sets up coordinated procurement plus a public-sector federation (EuroCloud). A single EU-wide audit is designed to end "sovereign-washing".

The Act builds on the AI Continent Action Plan and the Apply AI Strategy (AI factories and gigafactories) and dovetails with the Data Act, the DMA, NIS2, the EUCS cloud certification scheme, the Cyber Resilience Act and the EU Open Source Strategy. Its mandatory measures reach the public sector and private essential entities in the NIS2 Annex I sectors.

## Complete Article-by-Article Overview

### Title I - General provisions
- **Art 1 Subject matter:** five measures (Cloud + AI Leadership Initiatives; accelerated data-centre deployment; a sovereign cloud/AI offer to safeguard public order; reducing dependencies on critical technologies; fostering public-sector cloud adoption). Two general objectives (competitiveness/innovation; single-market resilience + strategic autonomy).
- **Art 2 Definitions:** "cloud computing service" = NIS2 Art 6(30); "AI system" = AI Act Art 3(1); frontier AI; AI agent; data centre; software/hardware/component/manufacturer = CRA (Reg 2024/2847); auditing organisation; audit criteria/evidence; control = Reg 2021/697; etc.

### Title II - Cloud and AI Leadership Initiatives (Art 173(3) TFEU)
- **Art 3 General objective** + **Art 4 eight operational objectives:** (1) energy/resource-efficient data-centre tech; (2) autonomous cloud stacks; (3) frontier AI; (4) physical AI; (5) industrial AI; (6) AI-agent platforms; (7) public-sector AI; (8) regional/local AI adoption + uptake of European cloud services.
- **Art 5 Experience and Acceleration Centres for AI ("Centres for AI"):** each MS establishes them, building on the former European Digital Innovation Hubs (EDIHs).
- **Art 6 Implementation:** via large-scale cross-sectoral "grand challenges" (Annex I); may be entrusted to joint undertakings (Smart Networks & Services JU, EuroHPC JU); funded via Horizon Europe / Digital Europe.
- **Art 7 National cloud and AI strategies:** each MS adopts one within 1 year (AI-first principle; aligned to Digital Decade targets), notifies within 3 months, reviews every 3 years.
- **Art 8 Frontier AI priority projects:** Commission may recognise projects (open calls) supporting grand challenge 3, run by an EDIC or eligible entity with >=3 Member States pooling compute.
- **Art 9 Computing support:** the Union at least matches MS-contributed AI compute to frontier AI priority projects within EuroHPC access time; also supports industrial/physical/public-sector AI.

### Title III - Data centre capacities (Art 114 TFEU)
- **Art 10 Data centre acceleration zones:** each MS designates >=1 within 6 months (grid capacity, connectivity, copper phase-out, waste-heat reuse, brownfield preference, sustainability); energy-needs analysis feeds national grid planning.
- **Art 11 Conditions:** sustainability KPIs from Del Reg 2024/1364; fair, non-discriminatory access, no speculative reservation.
- **Art 12 Single information points:** assist operators across permits (may reuse Gigabit Infrastructure Act single points).
- **Art 13 Facilitated permitting:** zones treated as strategic under the environmental-assessment speed-up regulation; aggregated baseline permit; **permit-granting <=12 months**; highest national significance where it exists.
- **Art 14 Data centre strategic projects:** Commission designates projects meeting >=2 of 5 criteria (support essential public-sector functions; highly sustainable/innovative; grid stability/clean-energy colocation; integrate EU-made chips/processors/quantum; address a compute shortage). Get the competitiveness seal under the ECF.
- **Art 15 Monitoring the capacity gap:** Commission tracks available compute, demand, and the gap.

### Title IV - Autonomy
**Chapter I - cloud sovereignty framework.** Art 16 four Union assurance levels (criteria in Annex II; review every 18 months). Art 17 recognition by the national competent authority of establishment (60-day assessment; cross-border 60-day review; Commission binding decision on disputes; SME Level-1 auto-recognition). Art 18 associated third countries (Level 3 derogation). Art 19 Level 1 conformity self-assessment + public EU statement of conformity. Art 20 independent third-party audit for Levels 2-4 (auditor independence: no non-audit services 12 months before/after, no audit services in prior 10 years, no contingent fees; annual review). Art 21 audit evidence (Annex III). Art 22 central public repository (revocations stay 5 years). Art 23 transparency obligations. Art 24 penalties + compensation. Art 25-26 national competent authorities + powers. Art 27-28 mutual assistance + cross-border cooperation.
**Chapter II - demand-side.** Art 29 risk assessments (within 1 year, then every 2 years) mapping public-order activities to Levels 2-4. Art 30 procurement: non-public-order bodies use Level 1; public-order activities (NIS2 Annex I/II + national security, defence, justice, law enforcement, border management) use Levels 2-4; narrow derogations. Art 31 private NIS2 Annex I entities may run similar impact assessments. Art 32 Union added value (non-price criteria; suggested <=15/120 points). Art 33 monitoring innovation procurement; aspire to >=25% to innovative SMEs.
**Chapter III - EuroCloud Federation.** Art 34 establishes the European public-sector cloud federation (voluntary, public-sector only). Art 35 sharing conditions (sharing entity owns the hardware/controls the intermediate entity). Art 36 cost-recovery fees.
**Chapter IV - Commission procurement.** Art 37 Commission as central purchasing body for Union entities + MS contracting authorities + selected partner organisations. Art 38 agreement + Steering Committee (>=2 MS to start; EFTA + candidate countries can join). Art 39 applicable procurement framework. Art 40 fees.
**Chapter V - Open source.** Art 41 open-source-first; Art 42 share & reuse of public software via the OSS Catalogue; Art 43 EU OSS Catalogue (on the Interoperable Europe portal); Art 44 OSPO network.

### Title V - Final provisions
Delegated acts (Art 6(4), 16(2), 20(9), 21(1), 31(3)); committee procedure (Reg 182/2011); review at 4 years then every 5 (Art 47); entry into force 20 days after OJ, application 1 year later (Art 48).

## Annex I - The 8 Grand Challenges
1. **Environmental sustainability, performance & security of EU data centres** - target average **PUE 1.15** across the Union; raise server utilisation toward **50%**; integrate EU semiconductors/quantum; harden security.
2. **Cloud stacks** - end-to-end EU hardware + software cloud stacks (AI servers on EU semiconductors/quantum).
3. **Frontier AI** - next-generation multimodal frontier models/systems.
4. **Physical AI** - autonomous robots, industrial systems, drones in unstructured environments.
5. **Industrial AI** - sector-specific industrial AI (automotive, manufacturing, healthcare, energy, agri-food, defence).
6. **Cooperative European Industrial Models** - confidentiality-preserving collaboration (federated/distributed training, secure execution).
7. **AI Agents Platform** - a European AI-agent orchestration framework / middleware.
8. **Public Sector AI** - models on high-quality public-sector data (health, public administration, law, crisis management).

## Annex II - Criteria for the four Union assurance levels (cumulative, escalating)
| Level | Audit | Key criteria (on top of lower levels) |
|---|---|---|
| **Level 1** | Self-assessment + public EU statement of conformity | EU establishment; EU data/infra residency (unless customer requires otherwise); SOTA cybersecurity; full subcontractor transparency; no third-country law compelling pre-disclosure of vulnerabilities. SME statements auto-recognised EU-wide. |
| **Level 2** | Independent third-party audit | EU-located personnel; EU cybersecurity cert "substantial" (Reg 2019/881/EUCS, national scheme until then); data not used to train/fine-tune third-country AI + never leaves EU; third-country-control safeguards; EU-only technical support; **SBOM** (CRA) + source-code audits + migration plans for third-country components; effective EU-parent / third-country-subsidiary separation. |
| **Level 3** | Independent third-party audit | Personnel are **EU citizens** (+ national security clearance for classified info); provider **NOT subject to third-country control** (derogation only via an Art 18 associated-third-country implementing act, with reasonable code access); EU-resident support only; may host **EU classified information**. |
| **Level 4** (highest) | Independent third-party audit | Cybersecurity cert **"high"**; risk-assessed sensitive data EU-only; **no third-country effective control** over the design/maintenance/evolution of software components; strictest separation. |

## Annex III - Audit evidence (11 criteria)
A Union establishment; B location of infrastructure/assets/personnel; C data localisation in the EU; D Union citizenship; E EU cybersecurity certification (Reg 2019/881; CEN/TS 18026:2024 + CEN/CLC/TS 18072:2025 in the interim); F no third-country AI training on data; G absence of third-country control (5% ownership/voting test up to ultimate owners, cap table, governance, commercial/financial links); H no technical/operational support outside the EU (help desk, SOC/NOC, privileged access, backup, disaster recovery EU-only); I software-supply-chain transparency (SBOM, dependency list, source-code audit rights, switchover plans); J open-source software (no tamper/disrupt remote features; maintenance/alternatives); K global services & third-country subsidiaries (legal/operational separation; foreign-government requests redirected to the competent Union entity).

## Impact Assessment Key Figures (SWD(2026) 502 / 503)
- 3 non-EU hyperscalers >70% of the EU cloud market; EU providers 29% (2017) -> 15% (2022).
- Triple EU data-centre capacity by 2030; full needed capacity by 2035; permits <18 months by 2030; PUE 1.15 + ~50% utilisation (Annex I).
- Six policy options assessed (PO1-A/B/C capacity; PO2-A/B/C dependence); preferred = PO1-B + PO2-C + PM8/PM9.
- 436 public-consultation responses; >100 bilateral meetings; positive Regulatory Scrutiny Board opinion (8 May 2026).

## Legislative Procedure Next Steps
| Stage | Status |
|---|---|
| Commission adoption (College) | Done, 3 June 2026 |
| EP committee (ITRE expected) + Council | Pending (2026/0138(COD)) |
| Trilogues | Pending |
| Entry into force / application | 20 days after OJ; application 1 year later |
| Review | 4 years after entry into force, then every 5 |

## Official Sources
- Proposal page (DG CNECT): https://digital-strategy.ec.europa.eu/en/library/proposal-cloud-and-ai-development-act-cada
- COM(2026) 502 final + ANNEXES 1-3; SWD(2026) 502 (IA Parts 1-2); SWD(2026) 503 (IA executive summary).
- Press: IP/26/1187; Q&A QANDA/26/1188 + QANDA/26/1185.

## Related Brubru Guides
- tech_sovereignty_package_2026 (umbrella package)
- eu_chips_act_2_0 (companion act)
- ai_continent_action_plan, apply_ai_strategy_public_sector, ai_act_regulation
- eu_data_act, nis2_directive, eu_cybersecurity_certification
