# DORA: The Digital Operational Resilience Act and Its Impact on the Financial Sector

**Analysis of ICT Risk Management, Incident Reporting, Resilience Testing, and the Oversight Framework for Critical ICT Third-Party Providers**

**Author:** Victor Sole Ferioli, Founder & Director, Beresol

**Date:** February 2026

**Location:** Brussels, Belgium

---

## Executive Summary

The Digital Operational Resilience Act (Regulation (EU) 2022/2554), known as DORA, is a landmark EU regulation that harmonises digital operational resilience requirements across the entire financial sector. Published in the Official Journal on 27 December 2022 and fully applicable since **17 January 2025**, DORA establishes a comprehensive framework covering ICT risk management, incident reporting, resilience testing, third-party risk management, and -- most innovatively -- direct EU-level oversight of critical ICT third-party service providers.

**Key Findings:**

- **Scope:** DORA applies to 21 categories of financial entities (from banks and insurers to crypto-asset service providers) plus ICT third-party providers
- **Five pillars:** ICT risk management, incident reporting, resilience testing, third-party risk management, and information sharing
- **Oversight Framework:** For the first time, the EU can directly oversee critical ICT providers (cloud, SaaS, etc.) serving the financial sector, with penalties of up to 1% of daily worldwide turnover
- **13 technical standards:** The European Supervisory Authorities (EBA, ESMA, EIOPA) have developed 13 RTS/ITS in two batches
- **Lex specialis:** DORA takes precedence over NIS 2 for financial sector entities, creating a sector-specific cybersecurity regime

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Legal Framework and Identification](#2-legal-framework-and-identification)
3. [Scope: Who Must Comply](#3-scope-who-must-comply)
4. [The Five Pillars of DORA](#4-the-five-pillars-of-dora)
5. [Delegated and Implementing Acts](#5-delegated-and-implementing-acts)
6. [The Oversight Framework for Critical ICT Providers](#6-the-oversight-framework-for-critical-ict-providers)
7. [Penalties and Enforcement](#7-penalties-and-enforcement)
8. [Implementation Timeline](#8-implementation-timeline)
9. [Amendments to Other EU Regulations](#9-amendments-to-other-eu-regulations)
10. [Practical Implications for Financial Institutions](#10-practical-implications-for-financial-institutions)
11. [Conclusions](#11-conclusions)
12. [References](#12-references)

---

## 1. Introduction

### 1.1 Context

The financial sector's increasing dependence on information and communication technology (ICT) -- from cloud computing and SaaS platforms to algorithmic trading systems and mobile banking -- has created systemic vulnerabilities that transcend national borders. Before DORA, ICT risk management in finance was addressed through a patchwork of sector-specific rules in directives like CRD IV, Solvency II, MiFID II, and PSD2, leading to fragmentation, gaps, and inconsistent supervisory approaches across Member States.

DORA was proposed by the European Commission in September 2020 as part of the Digital Finance Package, alongside MiCA (Markets in Crypto-Assets Regulation) and a pilot regime for DLT market infrastructures. After two years of negotiation, it was adopted in November 2022 and published in the Official Journal on 27 December 2022.

### 1.2 What DORA Changes

DORA introduces a **single, harmonised framework** for digital operational resilience across the entire EU financial sector. Its five pillars -- ICT risk management, incident management and reporting, digital operational resilience testing, ICT third-party risk management, and information sharing -- replace the fragmented national approaches with uniform EU-level requirements.

Most significantly, DORA establishes the first **EU-level oversight framework** for critical ICT third-party service providers (CTPPs), giving the European Supervisory Authorities direct supervisory powers over technology companies that are systemically important to finance.

---

## 2. Legal Framework and Identification

| Field | Value |
|-------|-------|
| **Full title** | Regulation (EU) 2022/2554 of the European Parliament and of the Council of 14 December 2022 on digital operational resilience for the financial sector |
| **Short name** | DORA (Digital Operational Resilience Act) |
| **CELEX number** | 32022R2554 |
| **OJ reference** | OJ L 333, 27.12.2022, p. 1-79 |
| **Legal basis** | Article 114 TFEU (internal market harmonisation) |
| **Procedure** | 2020/0266(COD) |
| **Entry into force** | 16 January 2023 |
| **Application date** | 17 January 2025 |

**Companion Directive:** Directive (EU) 2022/2556 (CELEX: 32022L2556) amends eight existing directives to align them with DORA, including UCITS, Solvency II, AIFMD, CRD IV, BRRD, MiFID II, PSD2, and IORP II.

---

## 3. Scope: Who Must Comply

### 3.1 Financial Entities (Article 2(1)(a)-(t))

DORA applies to **21 categories** of entities:

| Category | Entity Type |
|----------|-------------|
| (a) | Credit institutions |
| (b) | Payment institutions (including PSD2-exempted) |
| (c) | Account information service providers |
| (d) | Electronic money institutions (including EMD2-exempted) |
| (e) | Investment firms |
| (f) | Crypto-asset service providers and issuers of asset-referenced tokens (under MiCA) |
| (g) | Central securities depositories |
| (h) | Central counterparties |
| (i) | Trading venues |
| (j) | Trade repositories |
| (k) | Managers of alternative investment funds (AIFMs) |
| (l) | Management companies (UCITS) |
| (m) | Data reporting service providers |
| (n) | Insurance and reinsurance undertakings |
| (o) | Insurance intermediaries and ancillary insurance intermediaries |
| (p) | Institutions for occupational retirement provision (IORPs) |
| (q) | Credit rating agencies |
| (r) | Administrators of critical benchmarks |
| (s) | Crowdfunding service providers |
| (t) | Securitisation repositories |
| (u) | ICT third-party service providers (subject to Oversight Framework when designated as critical) |

### 3.2 Exclusions (Article 2(3))

- Small AIFMs (Article 3(2) of AIFMD)
- Small insurance/reinsurance undertakings (Article 4 of Solvency II)
- IORPs with 15 or fewer members
- Certain MiFID II-exempted persons
- Post office giro institutions (Member State option)

### 3.3 Proportionality (Article 4)

Simplified requirements apply to small and non-interconnected investment firms, small IORPs (up to 100 members), and microenterprises. These entities benefit from a simplified ICT risk management framework (Article 16) with reduced documentation and reporting obligations.

---

## 4. The Five Pillars of DORA

### 4.1 ICT Risk Management (Chapter II, Articles 5-16)

The management body bears **ultimate responsibility** for ICT risk management (Article 5). Financial entities must:

- Establish a comprehensive ICT risk management framework reviewed annually (Article 6)
- Identify all ICT-supported business functions, information assets, and dependencies (Article 8)
- Implement protection and prevention measures including cybersecurity policies, access controls, and encryption (Article 9)
- Deploy detection mechanisms for anomalous activities (Article 10)
- Maintain response and recovery plans, including business continuity and disaster recovery (Article 11)
- Establish backup and restoration policies (Article 12)
- Learn from incidents and update risk assessments accordingly (Article 13)
- Maintain communication plans for ICT-related incidents (Article 14)

A **simplified framework** (Article 16) is available for qualifying smaller entities.

### 4.2 ICT-Related Incident Management and Reporting (Chapter III, Articles 17-23)

Financial entities must establish an incident management process and report major ICT-related incidents to competent authorities through a three-stage process:

1. **Initial notification** -- within 4 hours of classification (or 24 hours of awareness)
2. **Intermediate report** -- within 72 hours of initial notification
3. **Final report** -- within 1 month of the intermediate report

Incidents are classified using criteria including: clients affected, data losses, duration, geographical spread, and criticality of services (Article 18). Voluntary notification of significant cyber threats is also encouraged (Article 19(2)).

Article 21 mandates a feasibility study for establishing a **single EU Hub** for major ICT-related incident reporting, which could centralise the currently distributed reporting process.

### 4.3 Digital Operational Resilience Testing (Chapter IV, Articles 24-27)

Financial entities must maintain a testing programme that includes:

- Testing of **all critical ICT systems** at least annually (Article 25)
- **Threat-led penetration testing (TLPT)** at least every 3 years for significant entities (Article 26), carried out in accordance with the TIBER-EU framework
- Clear requirements for both internal and external testers (Article 27)

### 4.4 Managing ICT Third-Party Risk (Chapter V, Articles 28-44)

This is DORA's most innovative pillar, comprising:

**Section I -- Key Principles (Articles 28-30):**
- Governance frameworks for ICT outsourcing (Article 28)
- Mandatory **register of information** on all ICT third-party contractual arrangements (Article 28(3))
- Preliminary ICT concentration risk assessment (Article 29)
- **Key contractual provisions** required in all ICT service agreements (Article 30): service level descriptions, data location, audit rights, exit strategies, termination rights, and sub-outsourcing conditions

**Section II -- Oversight Framework (Articles 31-44):** See Section 6 below.

### 4.5 Information Sharing (Chapter VI, Article 45)

Financial entities may exchange cyber threat intelligence among themselves, provided they:
- Notify competent authorities of participation in sharing arrangements
- Protect shared information (confidentiality, data protection)
- Operate within trusted communities

---

## 5. Delegated and Implementing Acts

DORA mandates **13 regulatory and implementing technical standards** developed jointly by the three ESAs, published in two batches.

### Batch 1 (in force 15 July 2024)

| Type | Subject | DORA Article | Implementing Act |
|------|---------|--------------|-----------------|
| RTS | ICT risk management framework | Art. 15 | Delegated Reg. (EU) 2024/1774 |
| RTS | Simplified ICT risk management framework | Art. 16(3) | Delegated Reg. (EU) 2024/1774 |
| RTS | Classification of ICT-related incidents and cyber threats | Art. 18(3) | Delegated Reg. (EU) 2024/1772 |
| RTS | Policy on ICT services supporting critical/important functions | Art. 28(10) | Delegated Reg. (EU) 2024/1773 |

### Batch 2 (adopted late 2024 - early 2025)

| Type | Subject | DORA Article | Implementing Act |
|------|---------|--------------|-----------------|
| RTS | Content/timelines for incident reporting | Art. 20(a) | Delegated Reg. (EU) 2025/301 |
| ITS | Standard forms/templates for incident reporting | Art. 20(b) | Implementing Reg. (EU) 2025/302 |
| RTS | Threat-led penetration testing (TLPT) | Art. 26(11) | Pending final publication |
| RTS | Harmonisation of oversight monitoring activities | Art. 41 | Delegated Reg. (EU) 2025/295 |
| ITS | Standard templates for the register of information | Art. 28(9) | Revised ITS adopted |
| RTS | Elements for subcontracting critical ICT services | Art. 30(5) | Delegated Reg. (EU) 2025/532 |
| RTS | Criteria for joint examination teams | Art. 32 | Delegated Reg. (EU) 2025/420 |
| RTS | Estimation of aggregated costs/losses from major ICT incidents | Art. 11(10) | Pending |
| Guidelines | Cooperation between ESAs and competent authorities | Art. 32(7) | Joint Guidelines published |

---

## 6. The Oversight Framework for Critical ICT Providers

### 6.1 Designation of Critical Providers (Article 31)

The ESAs, through the Joint Committee, designate ICT third-party service providers as **critical (CTPPs)** based on:
- Systemic impact on financial services if the provider experiences operational failure
- Systemic character or importance of the financial entities relying on the provider
- Degree of substitutability (lack of alternatives)
- Number of Member States where associated financial entities operate
- Degree of reliance of financial entities on the provider's services

The first round of designations occurred in 2025.

### 6.2 Oversight Structure (Article 32)

The Oversight Framework consists of four pillars:

- **Lead Overseer:** One of the three ESAs assigned to each CTPP, determined by the proportion of financial entity clients across sectors (EBA for banking-heavy, ESMA for capital markets-heavy, EIOPA for insurance-heavy)
- **Joint Oversight Network (JON):** Coordination body across ESAs
- **Oversight Forum:** Advisory body with ESA and national authority representatives, Commission, ESRB, ECB, and ENISA as observers
- **Joint Examination Teams:** Operational teams including staff from all three ESAs and relevant national competent authorities

### 6.3 Lead Overseer Powers (Article 35)

The Lead Overseer can:
- Request all relevant information and documentation
- Conduct general investigations (interviews, document production, on-site data collection)
- Conduct **on-site inspections** at any CTPP premises, including data centres
- Issue **recommendations** regarding ICT security, service quality, governance, and sub-outsourcing
- Conduct an annual **Oversight Risk Assessment Process (ORAP)**

### 6.4 Extra-EU Providers (Article 36)

CTPPs established outside the EU must **establish a subsidiary within the EU** within 12 months of designation, or the oversight may be exercised through agreements with non-EU authorities.

### 6.5 Compliance Mechanism

CTPPs operate under a "comply or explain" regime. If a CTPP fails to follow recommendations or provide adequate justification, the Lead Overseer may **publicly disclose** the non-compliance and issue opinions to competent authorities for supervisory follow-up actions.

---

## 7. Penalties and Enforcement

### 7.1 Administrative Penalties for Financial Entities (Articles 50-52)

DORA does not prescribe specific penalty amounts at EU level for financial entities. Member States determine penalties through national law, but competent authorities must have the power to impose:
- Orders to cease and desist
- Temporary prohibition of activities
- Requirements for remedial measures
- Public statements identifying the entity and the breach
- Administrative financial penalties

Penalties must be **effective, proportionate, and dissuasive**.

### 7.2 Periodic Penalty Payments for CTPPs (Article 35(6)-(8))

This is the only direct EU-level financial sanction in DORA:
- **Rate:** Up to 1% of the CTPP's average daily worldwide turnover in the preceding business year
- **Duration:** Accrued daily for a maximum of 6 months
- **Trigger:** Non-compliance with Lead Overseer's information requests, investigations, or inspection requirements

For a large cloud provider with EUR 50 billion annual revenue, this translates to approximately EUR 1.37 million per day, or up to EUR 250 million over 6 months.

---

## 8. Implementation Timeline

| Milestone | Date |
|-----------|------|
| Published in OJ | 27 December 2022 |
| Entry into force | 16 January 2023 |
| Batch 1 RTS/ITS in force | 15 July 2024 |
| **Full application date** | **17 January 2025** |
| Batch 2 RTS/ITS adopted | October 2024 - March 2025 |
| First designation of CTPPs | 2025 |
| Commencement of CTPP oversight | End 2025 |
| First TLPT cycle deadline | January 2028 |
| Commission review report | By 17 January 2028 (Article 58) |

---

## 9. Amendments to Other EU Regulations

DORA directly amends **five existing EU regulations**:

| Regulation Amended | Key Amendment |
|-------------------|---------------|
| Regulation (EC) No 1060/2009 (Credit Rating Agencies) | Adds ICT risk management and digital resilience requirements for CRAs |
| Regulation (EU) No 648/2012 (EMIR -- CCPs, trade repositories) | Integrates DORA ICT requirements for CCPs and trade repositories |
| Regulation (EU) No 600/2014 (MiFIR -- trading venues, data reporting) | Aligns ICT resilience for trading venues and data reporting service providers |
| Regulation (EU) No 909/2014 (CSDR -- central securities depositories) | Adds DORA-aligned ICT risk management for CSDs |
| Regulation (EU) 2016/1011 (Benchmarks Regulation) | Incorporates ICT resilience for administrators of critical benchmarks |

The companion **Directive (EU) 2022/2556** amends eight existing directives: UCITS, Solvency II, AIFMD, CRD IV, BRRD, MiFID II, PSD2, and IORP II.

---

## 10. Practical Implications for Financial Institutions

### 10.1 For Banks and Investment Firms

- Full ICT risk management framework aligned with DORA Articles 5-15
- Register of all ICT third-party contractual arrangements
- Incident reporting within the tight 4-hour/72-hour/1-month timeline
- Annual resilience testing, with TLPT every 3 years for significant institutions
- Review and renegotiation of all ICT vendor contracts to include Article 30 mandatory provisions

### 10.2 For Asset Managers and Fund Managers

- AIFMs and UCITS management companies are in scope
- Proportionality principle allows simplified framework for smaller managers
- Must assess ICT concentration risk before entering outsourcing arrangements
- Key concern: dependence on a small number of cloud/SaaS providers for portfolio management, NAV calculation, and reporting

### 10.3 For Insurance and Pension Funds

- Insurance undertakings, reinsurance undertakings, and IORPs must comply
- EIOPA coordinates the oversight for CTPPs primarily serving this sector
- Particular focus on legacy IT systems common in the insurance industry

### 10.4 For ICT Service Providers

- Must support financial entity clients with incident reporting and audit requirements
- Critical providers face direct EU oversight with potential penalties
- Non-EU providers may need to establish EU subsidiaries
- Sub-outsourcing arrangements require explicit contractual provisions

---

## 11. Conclusions

DORA represents a paradigm shift in how the EU regulates technology risk in the financial sector. By replacing fragmented national rules with a single harmonised framework, and by introducing direct oversight of critical technology providers, DORA creates a comprehensive approach to digital operational resilience that reflects the reality of modern financial services.

The regulation's impact extends well beyond traditional financial entities: it fundamentally reshapes the relationship between the financial sector and its technology providers, introducing EU-level accountability for systemic technology risks. As oversight of critical ICT third-party providers commences in late 2025, the full implications of this framework will become clear.

For EU policy professionals and financial institutions alike, DORA is now the central reference point for digital resilience -- and its influence on future regulatory frameworks, both in the EU and globally, is already visible in the approach taken by other jurisdictions looking to address technology concentration risk in finance.

---

## 12. References

- Regulation (EU) 2022/2554 -- EUR-Lex: https://eur-lex.europa.eu/eli/reg/2022/2554/oj
- Directive (EU) 2022/2556 (companion directive)
- EIOPA DORA page: https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en
- Delegated Regulations (EU) 2024/1772, 2024/1773, 2024/1774 (Batch 1 RTS)
- Delegated Regulations (EU) 2025/295, 2025/301, 2025/420, 2025/532 (Batch 2 RTS)
- Implementing Regulation (EU) 2025/302 (incident reporting templates)
- DORA full article text: https://www.digital-operational-resilience-act.com/DORA_Articles.html
