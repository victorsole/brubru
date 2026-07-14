# EU Cybersecurity Certification Framework: EUCC, EUCS, EU5G

## QUICK FACTS
- Legal basis: Title III (Articles 46-65) of the Cybersecurity Act, Regulation (EU) 2019/881, CELEX 32019R0881
- Purpose: creates a single EU-wide system of cybersecurity certification schemes for ICT products, ICT services and ICT processes, replacing a patchwork of national schemes
- Three assurance levels apply across every scheme: **basic** (self-assessment possible), **substantial** (moderate assurance), **high** (certificate issued only via, or overseen by, a National Cybersecurity Certification Authority)
- **EUCC** (European Common Criteria-based cybersecurity certification scheme): for ICT products, hardware, software and components. Adopted via **Commission Implementing Regulation (EU) 2024/482** of 31 January 2024 (OJ L, 2024/482, published 7 February 2024), CELEX 32024R0482. **Applicable from 27 February 2025.** The first and, as of mid-2026, the only fully live scheme.
- EUCC assurance mapping: **substantial** corresponds to Common Criteria attack-potential resistance levels AVA_VAN 1-2; **high** corresponds to AVA_VAN 3-5. Built on the international Common Criteria standard (ISO/IEC 15408).
- **EUCS** (European Cybersecurity Certification Scheme for Cloud Services): candidate scheme, drafted by ENISA since 2019-2020, **stalled since 2022 over a sovereignty/data-localisation dispute**. The March 2024 draft dropped the strict EU-ownership requirement; Council urged acceleration in September 2024; work paused through 2025 and is described by the Commission as "expected to resume", tied to the Cybersecurity Act revision and the forthcoming Cloud and AI Development Act.
- **EU5G**: candidate scheme for 5G network equipment, requested by the Commission as a Council implementing act follow-up to the EU 5G Toolbox. ENISA's concrete 2024 deliverable was a set of certification specifications for the **embedded Universal Integrated Circuit Card (eUICC/eSIM)**, developed with an ENISA Ad Hoc Working Group and issued for certification under the EUCC framework (public consultation 26 June-5 September 2024, report published November 2024). The full standalone EU5G scheme has not been formally launched.
- Other schemes on ENISA's roadmap, all pre-candidate or in development: **EUDI Wallet** certification (linked to the eIDAS 2.0 Digital Identity Regulation, (EU) 2024/1183) and **EUMSS** (EU Managed Security Services, covering incident response, penetration testing, security audits and consultancy), whose legal hook was added by Regulation (EU) 2025/37 (applied 15 January 2025).
- Schemes are **voluntary by default** unless made mandatory by other EU law (for example the Cyber Resilience Act, Regulation (EU) 2024/2847, and the Radio Equipment Directive Delegated Regulation (EU) 2022/30 both build presumption-of-conformity links to EU certification).
- Key actors: **ENISA** prepares candidate schemes; the **ECCG** (Member State representatives) opines on drafts; the **SCCG** (industry/consumer/academic representatives) advises the Commission; **National Cybersecurity Certification Authorities (NCCAs)** enforce schemes domestically and authorise Certification Bodies (and, for EUCC "high", ITSEFs); the Commission adopts schemes via implementing act following the **Union Rolling Work Programme**.
- **Cybersecurity Act 2.0**: proposed 20 January 2026, COM(2026)11, procedure 2026/0011(COD), rapporteur Marketa Gregorova (Greens/EFA, Czechia), ITRE. Would repeal and replace Regulation (EU) 2019/881 with a "cyber-secure by design" simplified certification track (12-month default timeline). See `cybersecurity_act` guide for full revision detail.
- No certification scheme currently in force is mandatory for the private sector; EUCC is the only scheme companies can actually obtain a certificate under today.

## What the framework does

The European Cybersecurity Certification Framework (ECCF), set up under Title III of the Cybersecurity Act, does not itself certify anything. It is a **meta-framework**: a procedure for the Commission, acting on ENISA-prepared candidate schemes, to adopt EU-wide certification schemes by implementing act. Once adopted, a scheme becomes directly applicable across all Member States, replacing any equivalent national scheme for the products, services or processes it covers (Article 57 CSA). The goal is to stop the fragmentation of national cybersecurity labels (Germany's BSI, France's ANSSI/SecNumCloud, and others) that forced vendors to certify the same product multiple times to sell across the EU.

Every scheme, whatever it covers, must specify:
- the type of ICT product, service or process covered
- one or more assurance levels (basic, substantial, high)
- the specific security requirements, evaluation criteria and methods
- the validity period of certificates and any monitoring/vulnerability-disclosure obligations
- rules on who can issue certificates at each assurance level

## The three assurance levels

| Level | Meaning | Who can certify |
|-------|---------|------------------|
| Basic | Minimal risk of exploitation; self-assessment (EU statement of conformity) may be sufficient | Manufacturer/provider (self-assessment) or a Conformity Assessment Body |
| Substantial | Moderate risk; independent third-party evaluation required | Accredited Conformity Assessment Body |
| High | State-actor-level risk; most rigorous, resistance to skilled attackers with significant resources | Certificate issued (or its issuance authorised) by the National Cybersecurity Certification Authority, evaluation by an authorised laboratory |

## EUCC: the live scheme

EUCC (European Common Criteria-based cybersecurity certification scheme) is the framework's proof of concept and, as of mid-2026, its only scheme actually issuing certificates.

- **Legal basis:** Commission Implementing Regulation (EU) 2024/482 of 31 January 2024, CELEX 32024R0482, OJ L, 2024/482, 7 February 2024. Applicable from 27 February 2025.
- **Scope:** ICT products, their documentation, and protection profiles submitted for certification, including semiconductors, smart cards, hardware security modules and secure elements, and increasingly software components.
- **Standard:** built on Common Criteria (ISO/IEC 15408), already the international benchmark, so EUCC certificates are designed to be broadly recognised outside the EU too (mutual recognition arrangements with the international Common Criteria Recognition Arrangement, CCRA).
- **Assurance levels:** substantial (AVA_VAN 1-2) and high (AVA_VAN 3-5); EUCC does not use "basic" for products.
- **Who issues certificates:** accredited Certification Bodies, based on evaluation by accredited (and, for "high", NCCA-authorised) ITSEFs (IT Security Evaluation Facilities).
- **National authorities' role:** each Member State's NCCA authorises Certification Bodies and ITSEFs to operate at "high" assurance, and runs an oversight/peer-review process so private certification bodies remain internationally recognised.
- **Lifecycle obligations:** certified products remain subject to ongoing monitoring, vulnerability management and disclosure procedures for the life of the certificate, not just at the point of issue.
- **Practical effect:** EUCC formally replaces the earlier informal "SOG-IS" mutual recognition arrangement among a subset of Member States, extending Common-Criteria-based mutual recognition to the whole EU.

## EUCS: the stalled cloud scheme

EUCS (European Cybersecurity Certification Scheme for Cloud Services) is the framework's most politically contentious file, and remains a candidate scheme rather than an adopted one.

- **What it would cover:** cloud infrastructure and service providers (IaaS/PaaS/SaaS), across the same three assurance levels.
- **The sovereignty dispute:** at the request of some Member States, the Commission asked ENISA to add a clause at the "high" assurance level requiring that data not fall under non-EU legal jurisdiction: in practice, that cloud providers offering "high"-level certified services be headquartered in the EU and majority EU-owned, not merely host and process data on EU soil.
- **Opposing coalition:** a July 2022 non-paper signed by Denmark, Estonia, Greece, Ireland, the Netherlands, Poland and Sweden argued the clause introduced "political criteria into what was intended to be a technical certification scheme" and would exclude too many providers, including US hyperscalers (Microsoft, Amazon, Google) operating EU subsidiaries. Opposition later grew to around twelve Member States, led by the Netherlands.
- **Supporting coalition:** France, Italy, Spain and Germany backed the sovereignty clause, echoing France's national SecNumCloud scheme; several European cloud providers lobbied ENISA not to drop it.
- **Where it landed:** the March 2024 draft removed the EU-ownership/sovereignty requirement altogether, leaving jurisdictional risk to be addressed by national regulators rather than the EU scheme itself, a compromise that left some stakeholders worried about "certification shopping" across Member States.
- **Current status:** the Council urged acceleration in September 2024, but formal adoption has not followed. Work is officially paused; the Commission describes EUCS as "expected to resume", now folded into the wider Cybersecurity Act revision (COM(2026)11, January 2026) and expected to be complemented by the forthcoming Cloud and AI Development Act, which would address sovereignty and non-technical risk outside the certification scheme itself.

## EU5G: the 5G scheme, folded into EUCC for now

EU5G is the framework's response to the 2019 EU 5G Toolbox, which flagged the need for a coordinated, harmonised certification approach to 5G network equipment across Member States (rather than each running its own security review of vendors such as Huawei, ZTE, Nokia and Ericsson).

- **Status:** candidate scheme, not formally adopted; work has not fully resumed as a standalone EU5G scheme.
- **What ENISA has actually delivered:** rather than wait for full EU5G adoption, ENISA developed technical specifications for certifying the **embedded Universal Integrated Circuit Card (eUICC)** (the secure element behind eSIM) as a protection profile evaluable under the already-live EUCC scheme. Public consultation ran 26 June to 5 September 2024, with ENISA's consultation report published November 2024. The eUICC also has read-across to EU Digital Identity Wallets (Regulation (EU) 2024/1183), since a Wallet can rely on the same secure-element architecture.
- **Practical read:** in the near term, buyers and vendors evaluating 5G secure-element components should look to EUCC certificates covering eUICC specifications, not to a separate "EU5G certificate": that label does not yet exist operationally.

## Other schemes on the roadmap

| Scheme | Covers | Status (mid-2026) |
|--------|--------|--------------------|
| EUCC | ICT products, hardware, software, components | Live, applicable since 27 February 2025 |
| EUCS | Cloud services (IaaS/PaaS/SaaS) | Stalled since 2022; "expected to resume" |
| EU5G | 5G network equipment | Candidate; eUICC specifications live under EUCC |
| EUDI Wallet | EU Digital Identity Wallets (eIDAS 2.0) | Under development |
| EUMSS | Managed security services (incident response, pen-testing, audits, consultancy) | Under development; legal hook added by Reg (EU) 2025/37 |

The Commission sets priorities for future candidate schemes through the **Union Rolling Work Programme for European Cybersecurity Certification**, prepared with ENISA and the ECCG.

## Governance actors

- **ENISA** (EU Agency for Cybersecurity, Athens): prepares candidate schemes at the Commission's request, maintains the certification website (certification.enisa.europa.eu), runs public consultations and Ad Hoc Working Groups of technical experts.
- **European Cybersecurity Certification Group (ECCG)**: Member State representative body that must be consulted on, and largely agree with, ENISA's candidate schemes before Commission adoption.
- **Stakeholder Cybersecurity Certification Group (SCCG)**: advisory group of industry, consumer organisation and academic representatives, appointed by the Commission, advises on strategic issues and the rolling work programme.
- **National Cybersecurity Certification Authorities (NCCAs)**: one per Member State, supervise and enforce schemes domestically, authorise Conformity Assessment Bodies and (for EUCC) ITSEFs, handle complaints and market surveillance.
- **Conformity Assessment Bodies / Certification Bodies**: accredited private or public bodies that actually issue certificates at basic/substantial level (and high, once authorised by the relevant NCCA).

## Links to other EU cybersecurity law

- **Cyber Resilience Act** (Regulation (EU) 2024/2847): products meeting EUCC or another ECCF scheme's requirements can use that certification to demonstrate compliance with equivalent CRA essential requirements (presumption of conformity), reducing duplicate testing. Core CRA obligations apply from 11 December 2027.
- **Radio Equipment Directive Delegated Regulation (EU) 2022/30**: cybersecurity requirements for radio equipment (Article 3(3)(d)(e)(f) RED) can likewise be demonstrated via harmonised standards or ECCF certification.
- **NIS2 Directive** (Directive (EU) 2022/2555): does not itself require ECCF certification, but national authorities may reference certified products/services as evidence of an operator's risk-management measures.
- **Cybersecurity Act 2.0 proposal** (COM(2026)11, 20 January 2026, procedure 2026/0011(COD)): would streamline scheme adoption (12-month default development timeline) and formally position ECCF certification as a "compliance accelerator" reducing overlapping obligations across NIS2, the Cyber Resilience Act and the AI Act's cybersecurity-of-AI provisions. See the `cybersecurity_act` guide for full detail on the revision procedure, rapporteur and timeline.

## Key Documents

- [Regulation (EU) 2019/881: Cybersecurity Act, Title III (Articles 46-65)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019R0881)
- [Commission Implementing Regulation (EU) 2024/482: EUCC scheme](https://eur-lex.europa.eu/eli/reg_impl/2024/482/oj/eng)
- [ENISA: Cybersecurity Certification Framework](https://www.enisa.europa.eu/topics/product-security-and-certification/cybersecurity-certification-framework)
- [European Union Cybersecurity Certification website (schemes, documents, downloads)](https://certification.enisa.europa.eu/index_en)
- [EUCC scheme page](https://certification.enisa.europa.eu/browse-topic/eucc_en)
- [ENISA: EU5G eUICC public consultation](https://www.enisa.europa.eu/news/share-your-feedback-enisa-public-consultation-bolsters-eu5g-cybersecurity-certification)
- [Cybersecurity Act 2.0 proposal, COM(2026)11](https://digital-strategy.ec.europa.eu/en/library/proposal-regulation-eu-cybersecurity-act)

## Timeline

| Date | Event |
|------|-------|
| 2019-2020 | ENISA begins preparing EUCC and EUCS candidate schemes at Commission request |
| July 2022 | Seven Member States' non-paper opposes EUCS sovereignty clause |
| 31 January 2024 | Commission adopts Implementing Regulation (EU) 2024/482 (EUCC) |
| 7 February 2024 | EUCC regulation published in OJ L |
| March 2024 | EUCS draft drops EU-ownership sovereignty requirement |
| 26 June-5 September 2024 | ENISA public consultation on eUICC (EU5G) certification specifications |
| September 2024 | Council urges acceleration of EUCS |
| November 2024 | ENISA publishes eUICC consultation report |
| 15 January 2025 | Regulation (EU) 2025/37 applies (managed security services / EUMSS legal hook) |
| 27 February 2025 | EUCC becomes applicable; first EU certificates issuable |
| 20 January 2026 | Cybersecurity Act 2.0 proposed, COM(2026)11 |
| Mid-2026 | EUCS and EU5G remain candidate schemes; EUCC is the only live scheme |
