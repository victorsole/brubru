# Spain's AI Governance Bill (Proyecto de Ley Orgánica para el buen uso y la gobernanza de la IA) and AESIA, compared with the EU AI Act

## QUICK FACTS
- **The bill**: *Proyecto de Ley Orgánica para el buen uso y la gobernanza de la inteligencia artificial*, sent by the Spanish Government to the Congreso de los Diputados. Published in the **Boletín Oficial de las Cortes Generales, Congreso, Serie A, núm. 97-1, 12 June 2026**, file 121/000096. Amendment deadline **30 June 2026**. **Still a bill** (in parliamentary procedure as of 15 September 2026); do not describe it as law.
- **What it does**: it is Spain's **implementing law for the EU AI Act** (Regulation (EU) 2024/1689). It **creates no new obligations for companies**: it designates authorities, sets the national sanctions regime and procedure, runs the national AI sandbox, and adds rules for the Spanish central State's own use of AI.
- **Structure**: **41 articles in 5 chapters**, 2 additional provisions, 1 repealing provision, 8 final provisions. Only Articles 21.3 and 28 (biometric identification offences) and Final Provision 3 (electoral law) have **organic-law** rank; the rest is ordinary law.
- **Drafted before the Digital Omnibus on AI**: Regulation (EU) 2026/1744 (adopted 8 July 2026, OJ 24 July 2026, **in force 27 July 2026**) amended the AI Act after the bill was tabled. The bill does **not** reflect it (see "Omnibus gaps" below).
- **Late**: the AI Act required Member States to designate authorities and notify penalty rules **by 2 August 2025** (Articles 70(2) and 99(2)).
- **AESIA** (Agencia Española de Supervisión de Inteligencia Artificial, based in A Coruña, statute Royal Decree 729/2023 of 22 August 2023) becomes the **single point of contact**, the **default market surveillance authority** for anything not assigned elsewhere, runs the **national sandbox**, hosts a **single complaints window**, and must become an **independent public-law entity within 6 months** of the law entering into force (Additional Provision 2).
- **Notifying authority**: the **Dirección General de Inteligencia Artificial** (Secretaría de Estado de Digitalización e Inteligencia Artificial), supported by **ENAC**, for Annex III systems; sectoral notifying authorities stay in place for Annex I products (Article 4).
- **Fine ceilings (Article 30)**: very serious, prohibited practices **EUR 35 million or 7%** of worldwide turnover; very serious, failure to report a **serious incident EUR 15 million or 3%**; serious **EUR 7.5 million or 1%**; minor **EUR 500,000 or 0.5%**. SMEs and start-ups pay the **lower** of amount and percentage (Article 30.8).
- **Softer than the EU ceiling**: most high-risk and transparency breaches are "serious" (EUR 7.5M / 1%) in Spain, whereas AI Act Article 99(4) allows up to **EUR 15M / 3%**. Prohibited practices keep the EU maximum.
- **Public sector is not fined**: public bodies receive a declaration of infringement, a warning and corrective orders, plus possible disciplinary liability (Article 39), as AI Act Article 99(8) allows.
- **Other procedural rules**: limitation 1 / 3 / 5 years (Article 32); decision within 9 months (minor) or 18 months (serious and very serious) (Article 35.4); **25% reduction for admitting liability plus 25% for voluntary early payment** (Article 40); periodic penalty payments up to 10% of the fine (Article 30.4); AESIA publishes all sanctions within 15 working days (Article 34).

## Who supervises what (Article 5)

| AI use | Spanish market surveillance authority |
|---|---|
| Prohibited practices (a) manipulation, (b) exploiting vulnerabilities, (c) social scoring, (f) emotion recognition at work or school | AESIA |
| Prohibited practices (e) untargeted facial scraping, (g) biometric categorisation by sensitive traits | AEPD (Spanish Data Protection Agency) and regional data protection authorities |
| Prohibited practices (d) individual crime-risk prediction, (h) real-time remote biometric identification by police | CGPJ (General Council of the Judiciary) |
| Annex III.1 biometrics (outside law enforcement, justice, democratic processes) and III.1(c) in migration; III.7 migration, asylum, border control | AEPD and regional DPAs |
| Annex III.1 biometrics for law enforcement or justice; III.6 law enforcement; III.8(a) administration of justice | CGPJ |
| Annex III.1(c) emotion recognition (outside migration and justice), III.2 critical infrastructure, III.3 education, III.4 employment, III.5 essential services (except b and c) | AESIA |
| Annex III.5(b) creditworthiness | Banco de España (supervised institutions) or CNMV (supervised operators) |
| Annex III.5(c) life and health insurance pricing | DGSFP (Dirección General de Seguros y Fondos de Pensiones) |
| Annex III.8(b) influencing elections | AESIA, **only once it is an independent entity** (Final Provision 3 amending the electoral law, LOREG) |
| Article 50 transparency (chatbots, synthetic content marking, deepfakes) | AESIA |
| Annex I products (toys, lifts, medical devices, etc.) | The existing sectoral authority; AESIA steps in temporarily if it lacks resources |
| Annex I radio equipment | AESIA |
| Anything not assigned, and new prohibitions or high-risk categories | AESIA by default until the Council of Ministers designates another authority (Article 5.9) |

Coordination: a **joint collaboration commission** of market surveillance authorities, including regional ones, chaired by AESIA (Article 8), whose decisions do not bind the CGPJ or independent authorities. Mandatory reports between authorities within **10 working days**. Complaints go to AESIA's single window and are routed to the competent authority within **10 working days** (Article 9); lodging a complaint does not make the complainant a party. Whistleblowers are protected under Spain's Law 2/2023 (Article 10).

## Offences, mapped to the AI Act

- **Very serious (Article 14)**: placing on the market, putting into service or using a system under AI Act Article 5(1) points **(a) to (h)**, the eight original prohibitions only.
- **Very serious (Article 15)**: provider (or deployer failing that) not reporting a **serious incident** under Article 73. The AI Act sets no specific ceiling for Article 73 in Article 99(4), so this is a national choice.
- **Serious, any operator (Article 16)**: not registering (Article 49, including the national register for Annex III.2 critical infrastructure), obstructing inspections or powers (Articles 74, 79, 80), ignoring provisional or corrective measures (Articles 79(5), 80, 82), **misleading** information to authorities (Article 99(5)).
- **Serious, providers (Article 17)**: Article 50 transparency and synthetic content marking; Chapter III Section 2 requirements; Articles 17, 18, 19, 20, 22, 43 and others.
- **Serious, authorised representatives, importers, distributors, deployers, notified bodies (Articles 18 to 22)**: Articles 22.3, 23.1/2/6/7, 24.1/5/6, 26.1/2/4/5/6/9/11/12, 27 (fundamental rights impact assessment), 50.3 and 50.4, 31.4 to 31.9.
- **Serious, law enforcement deployers (Article 21.3)**: real-time remote biometric identification outside Article 5(1)(h), without prior authorisation, not requesting it within 24 hours in urgency, exceeding the authorisation's limits, not deleting data after refusal, not notifying each use (Articles 5(3) and 5(4)).
- **Minor (Articles 23 to 29)**: **inaccurate or incomplete** information; provider duties under Articles 16(b), 16(h) with 83, 16(k), 16(l), 47; Articles 22.4, 23.3 to 23.5, 24.3; **not requesting authorisation for post-remote biometric identification (Article 26(10))**; notified body duties under Articles 31, 33, 34, 36.3.

## Comparison with the EU AI Act as amended (verdicts)

| Topic | Verdict | Why |
|---|---|---|
| New prohibitions (Art 5(1) non-consensual intimate imagery and CSAM, applicable 2 December 2026) | **Missing** | Article 14 of the bill lists points (a) to (h) only; no offence and no authority |
| Real-time biometric identification national rules (AI Act Art 5(5)) | **Missing** | Art 5(5) requires national law setting the authorising body, permitted objectives and offences before any use can be authorised; the bill only sanctions. Without it, no use can lawfully be authorised in Spain |
| High-risk and transparency fines | **Softer** | EUR 7.5M / 1% versus EU ceiling EUR 15M / 3% (Art 99(4)) |
| Post-remote biometric identification without authorisation (Art 26(10)) | **Much softer** | Minor in Spain (EUR 500k / 0.5%) versus EU ceiling EUR 15M / 3% |
| Small mid-cap enterprises (Art 99(6a), added by the Omnibus) | **Missing** | Article 30.8 covers only SMEs and start-ups |
| Value-chain cooperation (Art 25(2) and (4), fineable under Art 99(4)(da) since the Omnibus) | **Missing** | Not typified |
| AI Office exclusive competence (Art 75(1) as amended) | **Missing** | Systems built on a GPAI model by the same provider or group, and AI systems integrated into VLOPs/VLOSEs, are now supervised by the AI Office; the bill's designations ignore this and Article 3.1(a) includes GPAI providers in scope without saying so |
| Real-world testing frameworks for Annex I Section B products (new Art 60a) | **Missing (optional)** | Not addressed |
| Synthetic content marking offence (Article 17.1(b)) | **Drafting error** | Cites Article 50(1) and (5); marking is Article 50(2) |
| "Ultrasuplantación" | **Drafting error** | The Spanish AI Act text says "ultrafalsificación" (deepfake) |
| Real-time RBI outside Art 5(1)(h) | **Double typification** | Very serious under Article 14 and serious under Article 21.3(a); Article 33.3 applies the gravest, but the overlap should go |
| National sandbox | Aligned | AESIA sandbox; repeals Royal Decree 817/2023; EU deadline now **2 August 2027** |
| Public sector fines | National option | Warnings, no fines (Art 99(8)) |
| State public sector AI inventory, AI delegate per entity (Article 12) | Added by Spain | Exclusions: defence, national security, critical infrastructure, cybersecurity, research, transparency-law limits, social security benefit fraud systems. Tax-fraud AI systems become confidential under the General Tax Law (Final Provision 1) |
| Workers (AI Act Art 2(11)) | Aligned | Labour obligations and Labour Inspectorate role preserved (Additional Provision 1) |
| Independence of CGPJ and AESIA for law enforcement and elections (Art 74(8)) | Open question | Needs explicit justification that they meet the Law Enforcement Directive independence conditions |

## Omnibus gaps: what an amendment should add
1. Very serious offences for the two new prohibitions (non-consensual intimate imagery of identifiable persons; child sexual abuse material), applicable **2 December 2026**, plus a designated authority.
2. Lower-of-two fine rule for **small mid-cap enterprises**.
3. Offences for **Article 25(2) and (4)** value-chain duties.
4. Alignment with the **AI Office's exclusive supervision** (Article 75(1)) and routing of its requests via AESIA as single point of contact.
5. Updated dates: high-risk obligations **2 December 2027** (Annex III) and **2 August 2028** (Annex I); national sandbox **2 August 2027**; Article 50(2) marking for systems placed on the market before 2 August 2026 by **2 December 2026**; public authorities' high-risk systems by **2 August 2030**.
6. Review of the radio equipment designation: products needing third-party assessment only for spectrum or interference aspects are no longer high-risk (Article 6(1c)).
7. Machinery moved to Annex I Section B.
8. Whether Spain creates national real-world testing frameworks under Article 60a.

## Timeline
- 22 Aug 2023: AESIA statute (Royal Decree 729/2023). 8 Nov 2023: first Spanish AI sandbox (Royal Decree 817/2023).
- 1 Aug 2024: AI Act in force. 2 Feb 2025: prohibitions and AI literacy apply. **2 Aug 2025**: governance, GPAI, penalties; deadline for authorities (missed by Spain).
- 12 Jun 2026: bill published in the Congreso. 30 Jun 2026: amendment deadline.
- 8 Jul 2026: Digital Omnibus on AI adopted; 27 Jul 2026 in force. 2 Aug 2026: general application of the AI Act except high-risk.
- 2 Dec 2026: new prohibitions apply. 2 Aug 2027: national sandboxes operational. 2 Dec 2027: Annex III high-risk. 2 Aug 2028: Annex I high-risk. 2 Aug 2030: public authorities' high-risk systems.
- The Spanish law enters into force the day after publication in the BOE, except the electoral designation of AESIA.

## How to answer common questions
- "Does Spain's AI law add obligations for companies?" No. Obligations come from the AI Act; the Spanish bill designates authorities and sets penalties.
- "Who supervises my credit-scoring AI in Spain?" Banco de España or the CNMV, depending on who supervises the firm, not AESIA.
- "Are Spanish AI fines the same as the EU's?" Only for prohibited practices. Most other breaches cap at EUR 7.5M or 1% in Spain against EUR 15M or 3% allowed by the AI Act.
- "Can Spanish police use live facial recognition?" Not lawfully until Spain adopts the national rules Article 5(5) requires; the bill sanctions misuse but does not provide them.
- "Is the Spanish AI law in force?" No, it is a bill in the Congreso (as of 15 September 2026). Check the Congreso file before asserting a later stage.

## Brubru resources
- In-depth Spanish-language comparison (internal, 15 Sep 2026): kept by Beresol, not public.
- Related guides: `ai_act_regulation`, `ai_act_amendments_2026` (Digital Omnibus on AI), `ai_act_harmonised_standards_m613`.
- Sources: AI Act consolidated text 27 July 2026 https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:02024R1689-20260727 ; Regulation (EU) 2026/1744 http://data.europa.eu/eli/reg/2026/1744/oj ; Congreso https://www.congreso.es (BOCG Serie A núm. 97-1).
