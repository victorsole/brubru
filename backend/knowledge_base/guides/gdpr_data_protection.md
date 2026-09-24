# General Data Protection Regulation (GDPR)

## QUICK FACTS
- **EDPB (21 Sep 2026):** fining guidelines adopted (five-step method; minor infringement generally a reprimand, otherwise a strong presumption of a fine), **consultation until 13 November 2026**; final DSA-GDPR guidelines adopted. Detail below.
- **LATEST (final decision 21 September 2026): the Irish Data Protection Commission (DPC) fined Google EUR 403 million over location data.** A NATIONAL decision by the Irish supervisory authority acting as **lead supervisory authority** for Google Ireland Limited under the one-stop-shop, NOT a European Commission fine and NOT an EDPB decision (the EDPB only published it on 23 September 2026). Decided by Commissioners Des Hogan, Dale Sunderland and Niamh Sweeney.
  - **Scope:** three features, **Web & App Activity**, **Location History** and **Location Accuracy** (Android), from **25 May 2018 to 4 February 2020**. Own-volition inquiry opened **February 2020** after complaints from consumer organisations including **BEUC**.
  - **Infringements:** (1) lawfulness and fairness of location processing in Web & App Activity and Location History; (2) accountability, as Google could not demonstrate compliance for Location Accuracy; (3) transparency for all three features; (4) retention of location data longer than necessary. **Legal references: Articles 5, 6, 12 and 13, listed TOGETHER. The DPC does NOT assign each finding to an article, so NEVER tabulate finding-by-article, and add no finding it did not make (e.g. purpose limitation).**
  - **Sanction:** administrative fines **totalling EUR 403 million** plus an order to bring processing into compliance **within 6 months**. The DPC's release does not split the total by infringement, so never state a breakdown.
  - Sources: DPC release https://dataprotection.ie/en/news-media/latest-news/data-protection-commission-fines-google-eu403-million-following-inquiry-googles-processing-location ; EDPB summary, 23 Sep 2026.
- **CASE-LAW WATCH (17 September 2026): Advocate General's OPINION, NOT a judgment, Case C-317/25 Groupe Canal+** (AG Dean Spielmann): consent to direct marketing by an undertaking's unnamed "partners" is valid **only if the partners' identity is known**; otherwise fresh consent is needed before the first message, and an unsubscribe option does not cure it. The judgment is pending; never state this as the Court's ruling. Detail under Recent Developments.
- **Adjacent ruling (3 September 2026):** **Case C-798/24 [Jautiva]** -- Articles 5 and 6 read with Charter Articles 7 and 8 preclude national law making all shareholders' personal data publicly available where access carries no condition such as a demonstrated legitimate interest. See `eu_company_law_shareholder_disclosure`.
- **Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2016-679_gdpr/
- **National enforcement example (decision 21 July 2026):** the French CNIL fined **EXTIA** **EUR 300 000** under Articles 12 and 17 (erasure requests from job candidates left unanswered). Detail under Recent Developments.
- **EARLIER (Monday 8 June 2026, EDPB CHAIR PRESENTS 2025 ANNUAL REPORT TO LIBE):** EDPB Chair **Anu Talus** presented the **European Data Protection Board 2025 Annual Report** to the European Parliament's Committee on Civil Liberties, Justice and Home Affairs (LIBE). Headline figures from the report: national data protection authorities issued **EUR 1.1 billion in fines in 2025** and handled **572 cross-border decisions**; the EDPB and the DPAs are preparing to apply the new **GDPR Procedural Regulation**, since adopted as **Regulation (EU) 2025/2518** (in force 1 January 2026, applicable from 2 April 2027), which harmonises cross-border procedure and the one-stop-shop; see `edpb_consistency_one_stop_shop_gdpr_arts_60_to_66` for the full mechanism. On the digital-rulebook interplay, the EDPB **endorsed joint DMA-GDPR guidelines** with the Commission, **published DSA-GDPR guidelines**, and is working on **joint AI Act-GDPR guidance**. On simplification (Digital Omnibus / AI Omnibus), the Board supports cutting red tape "but not at any cost": it backs higher data-protection-certification thresholds, common data-breach and DPIA templates, a biometric-authentication derogation where the verification means are under the individual's sole control, a remedy for cookie-banner consent fatigue, harmonising the notion of scientific research, and exempting SMEs from record-keeping (except high-risk cases), but **firmly opposes the proposed change to the definition of personal data**, arguing that practical EDPB guidance on the CJEU case law brings more legal certainty than rewriting the GDPR. Under its **Helsinki Statement (2025)** the EDPB is issuing templates (legitimate-interest assessment, records of processing, privacy notice, DPIA, breach notification), accessible guideline summaries, and forthcoming **anonymisation guidelines**, all under the existing framework. Source: EP LIBE committee meeting, 8 June 2026 (webstream). Cross-link: `digital_omnibus_package`, `ai_act_regulation`.
- Full name: Regulation (EU) 2016/679 of the European Parliament and of the Council on the protection of natural persons with regard to the processing of personal data and on the free movement of such data
- CELEX: 32016R0679
- Adopted: 27 April 2016
- Published: OJ L 119, 4 May 2016
- Entry into force: 24 May 2016
- Applies from: 25 May 2018 (two-year implementation period)
- Legal basis: Article 16 TFEU (data protection), Article 8 Charter of Fundamental Rights
- Type: Regulation (directly applicable in all Member States)
- Responsible DG: DG JUST (Justice and Consumers)
- Responsible Commissioner: Michael McGrath (Democracy, Justice, Rule of Law)
- EP lead committee: LIBE (Civil Liberties, Justice and Home Affairs)
- Replaces: Data Protection Directive 95/46/EC (CELEX 31995L0046), repealed 25 May 2018
- Complemented by: Law Enforcement Directive (EU) 2016/680 (CELEX 32016L0680) for police/criminal justice
- Supervisory framework: 27 national Data Protection Authorities (DPAs) + European Data Protection Board (EDPB)
- Administrative fines (Tier 1, Art 83(4)): up to EUR 10 million or 2% of total worldwide annual turnover, whichever is higher, for controller/processor obligations
- Administrative fines (Tier 2, Art 83(5)): up to EUR 20 million or 4% of total worldwide annual turnover, whichever is higher, for basic principles, consent conditions, data subject rights and international transfers
- Structure: 11 chapters, 99 articles, 173 recitals
- EDPB established: 25 May 2018 (replaces Article 29 Working Party)

## Overview

The GDPR is the cornerstone of EU data protection law and the most widely referenced data regulation globally. It applies to any organisation processing personal data of EU residents, regardless of where the organisation is established. The regulation establishes a risk-based framework: controllers and processors must implement technical and organisational measures proportionate to the risk their processing poses to individuals.

The GDPR replaced the patchwork created by national implementations of Directive 95/46/EC with a directly applicable regulation, eliminating fragmentation while preserving limited Member State flexibility through approximately 50 opening clauses.

## Key Provisions

### Data Subject Rights
- **Right of access** (Article 15): copy of data held + supplementary information; free within one month
- **Right to rectification** (Article 16): correction of inaccurate personal data without undue delay
- **Right to erasure / "right to be forgotten"** (Article 17): deletion where data no longer necessary, consent withdrawn, or unlawful processing
- **Right to restriction** (Article 18): temporary halt to processing during contests of accuracy or legitimacy
- **Right to data portability** (Article 20): receive data in structured, commonly used, machine-readable format; direct transfer to another controller where technically feasible
- **Right to object** (Article 21): object to processing based on legitimate interests or for direct marketing; direct marketing objections must always be honoured
- Rights in automated decision-making (Article 22): not to be subject to solely automated decisions with significant effects, including profiling

### Lawful Bases for Processing (Article 6)
Six lawful bases: (1) consent, (2) contract performance, (3) legal obligation, (4) vital interests, (5) public task, (6) legitimate interests. Consent must be freely given, specific, informed, and unambiguous (Article 7). Special category data (health, biometric, genetic, racial/ethnic origin, political opinions, religious beliefs, trade union membership, sexual orientation) requires an additional condition under Article 9.

### Data Protection Officer (DPO)
Mandatory for: (a) public authorities, (b) controllers/processors whose core activities require large-scale systematic monitoring of individuals, (c) large-scale processing of special category data. DPO must be provided with resources, access to data, and independence. Contact details must be published and notified to the DPA.

### Data Protection by Design and by Default (Article 25)
Technical and organisational measures must embed data protection principles into processing systems from the design stage and ensure that only data necessary for each purpose is processed by default.

### Data Breach Notification (Articles 33-34)
Breaches likely to risk individuals' rights must be notified to the supervisory authority within 72 hours of becoming aware. Where breach likely results in high risk, affected data subjects must also be informed without undue delay.

### International Transfers (Chapter V)
Transfers to third countries permitted only where: (a) Commission adequacy decision in force, (b) appropriate safeguards in place (standard contractual clauses, binding corporate rules, approved codes of conduct), or (c) specific derogations apply. Adequacy decisions in force include the EU-US Data Privacy Framework (adopted July 2023, replacing Privacy Shield invalidated by Schrems II in 2020), and decisions for the UK, Switzerland, Japan, South Korea, and others.

## Enforcement

### National Data Protection Authorities
Each Member State maintains an independent DPA with powers to investigate, correct, ban processing, and impose administrative fines. Lead DPA for cross-border cases is determined by the establishment of the controller's EU main establishment (one-stop-shop mechanism, Article 56).

### One-Stop-Shop (OSS) Mechanism
For controllers with establishments in multiple Member States, the DPA of the main establishment acts as lead supervisory authority. Concerned DPAs participate in the case. Disputes resolved through the consistency mechanism and, if necessary, binding decisions from the EDPB (Article 65).

### European Data Protection Board (EDPB)
Independent body comprising heads of all 27 national DPAs and the European Data Protection Supervisor (EDPS). Issues binding decisions in OSS disputes, guidelines, recommendations, and opinions. Key guidelines include: Guidelines 05/2020 on consent, Guidelines 01/2022 on data subject rights, and Guidelines 02/2023 on technical scope of Article 3 (territorial scope).

### Fines
Two tiers: (a) up to EUR 10 million or 2% global turnover for procedural infringements (data breach notification, DPO obligations, records of processing); (b) up to EUR 20 million or 4% global turnover for substantive violations (lawful basis, data subject rights, international transfers). Largest fines to date: Meta EUR 1.2 billion (Ireland DPA, May 2023, SCCs/US transfers), Meta EUR 390 million (January 2023, consent for behavioural advertising), Amazon EUR 746 million (Luxembourg CNPD, 2021).

## Recent Developments (2025-2026)

- **EDPB plenary, 21 September 2026 (detail):** guidelines on imposing administrative fines alongside other corrective powers. Five steps: a legal basis for a fine; who is liable (controller or processor, by who is bound by the provision); intent or negligence (a culpable infringement is required); aggravating and mitigating factors; effective, proportionate and dissuasive. 14 worked examples; corrective measures range from warnings and reprimands to orders, bans and withdrawal of certification. Also the final DSA-GDPR interplay guidelines. https://www.edpb.europa.eu/news/edpb-harmonises-fining-methodology-and-adopts-final-dsa-gdpr-guidelines_en

- **AG opinion, Case C-317/25 Groupe Canal+ (17 September 2026), full detail** (read from press release No 130/26, 22 September 2026):
  - **This is an ADVOCATE GENERAL'S OPINION, not a judgment.** Advocate General **Dean Spielmann**. The Court usually follows an opinion but is not bound by it, and the judgment is still to come. **Never state this as the Court's ruling**; say what the Advocate General proposed and that the judgment is pending.
  - **What he proposes:** consent given to an undertaking for "its partners" to use personal data for **direct marketing** is valid **only if the identity of those partners is known**. Consent must be freely given, specific, sufficiently informed and unambiguous, and to be informed it must let the data subject know **the identity of the controller**.
  - So having data used by an internet service provider's "partners" does **not** mean the person consented to marketing from any company in that category. Where the identity of the controller doing the marketing was not known when consent was taken, **fresh consent must be obtained before the marketing, at the latest at the time of the first communication**.
  - **An unsubscribe option does not cure it.** The possibility of unsubscribing on receipt of the first message arises after the campaign has begun and cannot replace prior consent.
  - **The facts:** in 2021 Groupe Canal+ commissioned electronic direct-marketing campaigns targeting about **3.9 million people**, using data collected by two internet service providers whose subscribers had consented to marketing by unidentified "partners". The French data protection authority (**CNIL**) found the consent invalid and fined Groupe Canal+ **EUR 600,000**. Groupe Canal+ challenged that before the Conseil d'Etat, which referred the question.
  - Press release: https://curia.europa.eu/site/upload/docs/application/pdf/2026-09/cp260130en.pdf
- **CNIL / EXTIA, full detail (decision 21 July 2026, reported by the EDPB on 11 September 2026):** the French supervisory authority **CNIL** fined **EXTIA**, an IT and engineering consultancy that recruits consultants for client projects, **EUR 300 000** for failing to respect the rights of individuals. The articles engaged were **Article 12** (transparent information and the modalities for exercising data-subject rights) and **Article 17** (right to erasure). Of 265 erasure requests received in 2024, mostly from job candidates and occasionally from former employees, more than three quarters had not been dealt with or had not been dealt with satisfactorily: 12 were never processed, 166 requesters were never informed of the action taken, and 27 were informed late, outside the one-month deadline. The CNIL's restricted committee, the body that imposes sanctions, weighed the number of people affected and the fact that the company had already been reminded of its obligations twice. The case arose from individual complaints and from the EDPB Coordinated Enforcement Framework action on the right to erasure launched in 2025. Treat this as one national fine decided on its own facts: it binds no other authority and changes no rule. Its practical reading is narrow, that automatic deletion of a candidate's data does not relieve the controller of the separate duty to tell the requester what was done. Decision: Délibération de la formation restreinte SAN-2026-010. Sources: https://www.cnil.fr/en/sanction-failure-rights-individuals-extia and https://www.edpb.europa.eu/news/failure-to-respect-the-rights-of-individuals-the-cnil-fined-extia-300-000-eur_en

### GDPR and AI Act Interplay
The AI Act (Regulation (EU) 2024/1689, CELEX 32024R1689, applicable from August 2026 for most provisions) and GDPR interact extensively. AI systems processing personal data must comply with both frameworks simultaneously. The EDPB issued Opinion 28/2024 on the interplay, clarifying that AI model training does not automatically confer anonymisation. Legitimate interest (Article 6(1)(f) GDPR) cannot be invoked to override GDPR obligations for high-risk AI systems. The Commission's guidelines on AI and data protection (December 2025) address data minimisation obligations for training datasets and purpose limitation when deploying AI models.

### DMA-GDPR Interplay Guidelines
The Digital Markets Act (Regulation (EU) 2022/1925, CELEX 32022R1925) and GDPR overlap significantly for gatekeepers. The EDPB and the Commission published joint guidance in October 2025 clarifying: (a) gatekeepers cannot rely on consent as the lawful basis for combining personal data across services where the DMA prohibits such combination without consent (Article 5(2) DMA), meaning freely-given consent under GDPR and DMA prohibition interact; (b) data portability rights under Article 20 GDPR and DMA porting obligations are complementary but legally distinct; (c) the DMA prohibition on tracking end users for targeted advertising outside the gatekeeper's core service applies regardless of the GDPR lawful basis invoked. Meta's AdFree subscription model has been challenged under both frameworks by the Austrian and German DPAs.

### European Health Data Space (EHDS)
Regulation (EU) 2025/327 (CELEX 32025R0327), the European Health Data Space, entered into force in March 2025. The EHDS creates a lex specialis relationship with GDPR: it builds on GDPR as the foundation but introduces specific rules for health data primary use (patient access, care continuity) and secondary use (research, public health). EHDS Article 33 opens a specific lawful basis for secondary use of electronic health data for approved purposes, operating alongside GDPR Article 9(2)(j) (scientific research). EHDS national digital health authorities oversee primary use; health data access bodies oversee secondary use. Full secondary use provisions apply from March 2027.

### 2026 Enforcement Highlights

- French CNIL fined EXTIA EUR 300 000 by a decision of 21 July 2026, published by the CNIL on 9 September 2026 and carried by the EDPB national news page on 11 September 2026, for breaches of Articles 12 and 17 in handling erasure requests. An audit in April 2025 followed complaints from former employees and candidates and formed part of the EDPB Coordinated Enforcement Framework action on the right to erasure. The restricted committee found that 12 of the 265 erasure requests received in 2024 had gone unprocessed, that 166 requesters had never been told what action was taken, and that 27 had been told outside the one-month deadline, with delays of up to several months. The company argued that many requests concerned candidates whose data were deleted automatically; the restricted committee held that automatic deletion does not exempt a controller from informing the person of the outcome. Remedial steps taken during the procedure, and valid reasons for a residual number of requests such as an inability to identify the person, were taken into account in the company's favour. The aggravating factors were the infringement of essential principles on the rights of individuals, the number of people concerned, and two prior reminders of the company's obligations. This is a national decision on its own facts and sets no precedent beyond them, but it is a useful illustration that Article 12 imposes a duty to respond that is distinct from the substantive erasure duty in Article 17.

### 2025 Enforcement Highlights
- Irish DPA finalised 14 binding decisions under OSS mechanism in 2025, including EUR 251 million fine against Meta for data breach notification failures (November 2024 decision)
- French CNIL fined a health data processor EUR 3.5 million for inadequate security measures (January 2025)
- Italian Garante issued provisional measures against DeepSeek (January 2025) ordering suspension of processing of Italian users' data pending investigation
- EDPB adopted Guidelines 01/2025 on processing of personal data through blockchain technologies

## Related Legislation

| Instrument | CELEX | Relationship |
|---|---|---|
| Law Enforcement Directive (EU) 2016/680 | 32016L0680 | Governs police/criminal justice processing; lex specialis to GDPR |
| ePrivacy Directive 2002/58/EC | 32002L0058 | Lex specialis for electronic communications; cookies, confidentiality |
| AI Act (EU) 2024/1689 | 32024R1689 | Intersects on AI training, automated decisions; EDPB Opinion 28/2024 |
| Digital Markets Act (EU) 2022/1925 | 32022R1925 | DMA-GDPR interplay on gatekeeper data combination and portability |
| Digital Services Act (EU) 2022/2065 | 32022R2065 | DSA profiling restrictions for minors; ad targeting transparency |
| European Health Data Space (EU) 2025/327 | 32025R0327 | Lex specialis for health data; secondary use framework |
| Data Act (EU) 2023/2854 | 32023R2854 | IoT data access rules; GDPR applies where personal data involved |
| NIS2 Directive (EU) 2022/2555 | 32022L2555 | Cybersecurity obligations intersect with GDPR breach notification |
| Data Governance Act (EU) 2022/868 | 32022R0868 | Trusted data intermediaries; public sector data re-use |

## Institutional Landscape

| Institution / Body | Role |
|---|---|
| European Commission (DG JUST) | Legislative guardian; GDPR review (Article 97); adequacy decisions |
| European Data Protection Board (EDPB) | Binding dispute resolution; guidelines; consistency mechanism |
| European Data Protection Supervisor (EDPS) | Oversees EU institutions' own processing; member of EDPB |
| National DPAs (27) | Investigations, fines, authorisations; lead DPA under OSS |
| Court of Justice of the EU (CJEU) | Authoritative interpretation (Schrems I/II, Google Spain, etc.) |
| EP LIBE Committee | Legislative co-decision; EDPB rapporteur; scrutiny of adequacy decisions |

## Sources
- Regulation (EU) 2016/679: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679
- EDPB guidelines and opinions: https://www.edpb.europa.eu/our-work-tools/general-guidance/guidelines-recommendations-best-practices_en
- EDPB binding decisions: https://www.edpb.europa.eu/our-work-tools/binding-decisions_en
- GDPR enforcement tracker: https://www.enforcementtracker.com/

## Related Brubru Guides
- `ai_act_regulation` -- AI Act interaction with GDPR on training data and automated decisions
- `digital_markets_act` -- DMA-GDPR interplay on gatekeeper data combination
- `digital_services_act` -- DSA profiling restrictions and ad transparency
- `data_governance_act` -- Trusted intermediaries and public sector data re-use
- `eu_health_data_space` -- EHDS lex specialis rules for health data
- `eu_cybersecurity_nis2` -- NIS2 security obligations and breach notification overlap
- `eu_equality_antidiscrimination` -- Special category data (health, biometric, ethnicity)
