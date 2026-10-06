# Cyber Resilience Act (Regulation (EU) 2024/2847)

## QUICK FACTS
- **STANDARDISATION REFORM PROPOSED (6 October 2026):** the Commission proposed a new Regulation on European standardisation (COM(2026) 780) to replace Regulation (EU) No 1025/2012, with delivery deadlines for requested standards, harmonised standardisation deliverables, other standards bodies and common specifications as fallback, and free access to referenced standards. It is only a proposal (application six months after entry into force, expected around 2028) and the text does NOT amend this act or add a transition for standards already requested under it. Detail: guide `standardisation_regulation_revision_2026`.
- **Brubru deep-dive explainer (ALWAYS link this in answers):** https://brubru.beresol.eu/eucanon/2024-2847_cra/index.html
- **LATEST (reviewed Monday 14 September 2026):** **The Article 16 single reporting platform is LIVE.** ENISA deployed the initial operating capability of its CRA Single Reporting Platform on **Friday 11 September 2026**, the same day **Article 14 reporting obligations started applying**, the first binding deadline in the Regulation. From that date a manufacturer must notify actively exploited vulnerabilities and severe incidents to the coordinating CSIRT **and** ENISA simultaneously, through that platform, on a **24 hour / 72 hour / 14 day** clock. Article 69(3) makes this bite on **products already on the market**: it is not a new-products-only duty. Everything else in the Regulation waits until 11 December 2027. The platform is reached at https://portal.cra-srp.enisa.europa.eu/
- **The two Commission acts due by 11 December 2025 were adopted (read at source, 5 Oct 2026):** **Implementing Regulation (EU) 2025/2392** of 28 November 2025 (OJ 1 December 2025, in force 21 December 2025) gives the technical description of the categories of important products (Annex III, classes I and II) and critical products (Annex IV) under Article 7(4); **Delegated Regulation (EU) 2026/881** of 11 December 2025 (OJ 20 April 2026, in force 10 May 2026) specifies when a CSIRT may delay passing a notification on, under Articles 14(9) and 16(2).
- **Corrigenda matter (three read on Cellar):** 5 December 2024 (title: "(EU) 2019/1020"), **2 July 2025: Article 64(10) now says "paragraphs 2 to 9"**, so the fine exemption for micro and small manufacturers (missed 24-hour early warning) and for open-source stewards covers the EUR 15 million tier as well, and 17 October 2025 (Article 67: point 72, not 69). The original text said "paragraphs 3 to 9", which looked like a gap; it is corrected.
- Full name: Regulation (EU) 2024/2847 of the European Parliament and of the Council of 23 October 2024 on horizontal cybersecurity requirements for products with digital elements and amending Regulations (EU) No 168/2013 and (EU) 2019/1020 and Directive (EU) 2020/1828 (Cyber Resilience Act)
- Common name: Cyber Resilience Act (CRA)
- CELEX: 32024R2847
- ELI: http://data.europa.eu/eli/reg/2024/2847/oj
- Adopted: 23 October 2024 (Strasbourg)
- Published: OJ, 20 November 2024
- Entry into force: the twentieth day following publication (10 December 2024)
- **Applies from: 11 December 2027** (Article 71(2))
- **Article 14 applies from: 11 September 2026** (Article 71(2), second subparagraph)
- **Chapter IV, Articles 35 to 51, applied from: 11 June 2026**, notification of conformity assessment bodies, already live
- **Article 16 single reporting platform: operational since 11 September 2026**, established, operated and maintained by ENISA, at https://portal.cra-srp.enisa.europa.eu/
- Type: Regulation (directly applicable, no transposition)
- Sister acts: Cybersecurity Act (Reg (EU) 2019/881, ENISA + certification), NIS2 (Dir (EU) 2022/2555), AI Act (Reg (EU) 2024/1689)

## The three application dates, and why they differ

Article 71 staggers the Regulation deliberately, so that the reporting pipeline and the
conformity-assessment infrastructure exist before the substantive product requirements bite.

| Date | What starts | Status |
|---|---|---|
| 11 June 2026 | Chapter IV (Arts 35-51): notification of conformity assessment bodies | **already applying** |
| **11 September 2026** | **Article 14: manufacturer reporting of actively exploited vulnerabilities and severe incidents** | **applying; the Article 16 platform went live the same day** |
| 11 December 2026 | Member States "shall strive to ensure" enough notified bodies exist (**Art 35(2)**), a best-efforts target, not an obligation on companies | pending |
| 11 December 2027 | The Regulation as a whole: Annex I essential requirements, conformity assessment, CE marking, support period, technical documentation | pending |

**The trap.** Article 69(2) says products placed on the market before 11 December 2027 are only
caught by the Regulation if they undergo a substantial modification after that date. Article
69(3) then **derogates from that** for Article 14: the reporting duties apply to **all in-scope
products already on the market**. A company that reads only Article 69(2) will conclude it has
until December 2027 and will be wrong by fifteen months.

## Article 14: what actually has to be done from 11 September 2026

Two reportable events: an **actively exploited vulnerability** in the product, and a **severe
incident having an impact on the security of the product**. Both go **simultaneously** to the
CSIRT designated as coordinator and to **ENISA**, through the **single reporting platform**
established under Article 16.

That platform now exists. ENISA deployed the initial operating capability of the CRA Single
Reporting Platform on 11 September 2026, the same day the Article 14 duties began to apply. A
manufacturer files one notification: the CSIRT designated as coordinator that receives it passes
the information to the national CSIRTs of the other Member States where the product is also
available, and the notification is made available to ENISA at the same time. Reporting once
replaces notifying each national authority separately. Open-source software stewards are brought in
by Article 24(3), which applies from 11 December 2027. Article 15 also lets manufacturers and other
persons notify vulnerabilities, cyber threats, incidents and near misses on a voluntary basis to a CSIRT
designated as coordinator or ENISA, processed under the Article 16 procedure. Article 16(2) allows dissemination of a notification to
be delayed in particularly exceptional circumstances.

Three-stage clock, per event:

| Stage | Deadline | Content |
|---|---|---|
| Early warning | **within 24 hours** of becoming aware | that it has happened; where applicable, which Member States the product was made available in |
| Notification | **within 72 hours** of becoming aware | the product concerned, the general nature of the exploit or incident, corrective or mitigating measures taken, measures users can take, and how sensitive the manufacturer considers the information |
| Final report | **no later than 14 days** after a corrective or mitigating measure is available | description of the vulnerability including severity and impact; where available, information on the malicious actor exploiting it; details of the security update or other corrective measure |

"Becoming aware" starts the clock, not publication and not confirmation.

## Scope: products with digital elements

The Regulation applies to products with digital elements made available on the market whose
intended or reasonably foreseeable use includes a direct or indirect data connection to a device
or network. It grades them:

- **Default class**: self-assessment against the Annex I essential requirements.
- **Important products with digital elements**: a higher cybersecurity risk because of the
  function they perform; split into Class I and Class II with progressively stricter conformity
  assessment routes.
- **Critical products with digital elements**: the strictest route, capable of being made
  subject to mandatory European cybersecurity certification.

**Open-source software stewards** are a distinct actor with a lighter regime, and are **exempt
from administrative fines for any infringement** of the Regulation.

## Penalties (Article 64)

| Infringement | Maximum administrative fine |
|---|---|
| Annex I essential requirements, or the obligations in **Articles 13 and 14** | **EUR 15 000 000 or 2,5 % of total worldwide annual turnover**, whichever is higher |
| Articles 18 to 23, 28, 30(1)-(4), 31(1)-(4), 32(1)-(3), 33(5), 39, 41, 47, 49, 53 | EUR 10 000 000 or 2 % of worldwide turnover, whichever is higher |
| Supplying incorrect, incomplete or misleading information to notified bodies or market surveillance authorities | EUR 5 000 000 or 1 % of worldwide turnover, whichever is higher |

Two carve-outs written into the recitals and given effect in Article 64: **microenterprises and
small enterprises are not fined for missing the 24-hour early-warning deadline**, and
**open-source software stewards are not fined at all**. Member States may not substitute other
pecuniary penalties for those entities.

Fines are set in national law up to these ceilings, applied by market surveillance authorities,
and communicated between Member States through the Article 34 system of Regulation (EU)
2019/1020, with an explicit proportionality rule on cumulative fines across Member States.

## How it sits beside the neighbouring acts

- **Cybersecurity Act, Reg (EU) 2019/881**: a *different* Regulation. It governs ENISA's mandate
  and the European cybersecurity certification framework. It does not carry the CRA's product
  obligations. See `cybersecurity_act`.
- **NIS2, Dir (EU) 2022/2555**: obliges *entities* operating essential and important services;
  the CRA obliges *products*. An organisation can be in scope of both, reporting an incident
  under NIS2 as an operator and under CRA Article 14 as a manufacturer.
- **AI Act, Reg (EU) 2024/1689**: Article 15 cybersecurity requirements for high-risk AI systems
  interact with the CRA where the AI system is itself a product with digital elements.
- **Directive (EU) 2020/1828** (representative actions) is amended by the CRA; collective redress
  for CRA infringements starts 11 December 2027.

## Structure and key numbers (full read of all 130 recitals, 71 articles and 8 annexes, 5 Oct 2026)
- **8 chapters:** I general (Arts 1-12), II economic operators and open source (13-26), III conformity (27-34), IV notified bodies (35-51), V market surveillance (52-60), VI delegated powers (61-62), VII confidentiality and penalties (63-65), VIII transitional and final (66-71). **Annexes:** I essential requirements, II user information, III important products, IV critical products, V EU declaration of conformity, VI simplified declaration, VII technical documentation, VIII conformity procedures (modules A, B, C, H).
- **Scope (Art 2):** products with digital elements whose intended or reasonably foreseeable use includes a direct or indirect logical or physical data connection. **Excluded:** medical devices (Regulations 2017/745 and 2017/746), vehicles under Regulation 2019/2144, aviation products certified under Regulation 2018/1139, marine equipment under Directive 2014/90/EU, spare parts identical to the original, products for national security or defence, and classified-information products. The Commission may limit or exclude other sectoral cases by delegated act (Art 2(5)). The definition of a product includes its **remote data processing solutions** (Art 3(1)-(2)).
- **Commercial activity only (recitals 15-20, Art 3(22)):** free and open-source software is caught only when supplied in the course of a commercial activity; contributing code or hosting on a repository is not. **Open-source software stewards** (Art 3(14), Art 24) get a light regime: a documented cybersecurity policy, cooperation with authorities, and Article 14 reporting only to the extent they are involved in development; no CE marking, no fines.
- **Manufacturer duties (Art 13):** documented cybersecurity risk assessment; due diligence on third-party components including open-source ones; **support period of at least five years** unless the product is expected to be used for less; each security update kept available for **10 years or the support period, whichever is longer**; vulnerability handling per Annex I Part II including a **software bill of materials covering at least top-level dependencies**; a single point of contact; the **end of the support period (month and year) stated at purchase**; technical documentation and declaration kept 10 years; notice before ceasing operations.
- **Annex I:** Part I has 13 product-property requirements (2)(a) to (m) (no known exploitable vulnerabilities, secure by default, automatic security updates with opt-out, access control, confidentiality, integrity, data minimisation, availability, limit attack surface, exploit mitigation, logging with opt-out, secure data removal); Part II has 8 vulnerability-handling requirements (SBOM, remediate without delay, regular testing, disclose fixed vulnerabilities, coordinated vulnerability disclosure policy, information sharing, secure update distribution, free security updates).
- **Risk classes (Arts 7-8, Annexes III-IV):** **Annex III Class I has 19 categories** (identity and privileged access management, browsers, password managers, anti-malware, VPN, network management, SIEM, boot managers, PKI, network interfaces, operating systems, routers and switches, security-capable microprocessors, microcontrollers and ASIC/FPGA, smart home virtual assistants, smart home security products, connected toys, health wearables); **Class II has 4** (hypervisors and container runtimes, firewalls and intrusion detection or prevention, tamper-resistant microprocessors, tamper-resistant microcontrollers); **Annex IV critical products has 3** (hardware devices with security boxes, smart meter gateways and similar, smartcards and secure elements).
- **Conformity routes (Art 32):** default is **self-assessment (module A)**. Class I: self-assessment only if harmonised standards, common specifications or a certification scheme at least at "substantial" level are applied, otherwise third-party (modules B plus C, or H). **Class II: always third-party** (B plus C, H, or a certification scheme at least "substantial"). Critical products: mandatory EU certification only if the Commission so decides by delegated act (Art 8(1)), otherwise the Class II routes. A certificate at least at "substantial" level removes the need for the corresponding third-party assessment (Art 27(9)). Open-source manufacturers of Annex III products may choose any Article 32(1) route if their technical documentation is public (Art 32(5)).
- **Importers, distributors and others (Arts 18-23):** authorised representatives cannot take over Article 13(1)-(11); an importer or distributor that sells under its own name or substantially modifies a product becomes a manufacturer (Art 21); so does anyone else who substantially modifies and makes available (Art 22), for the affected part or the whole product.
- **Market surveillance (Arts 52-60):** Regulation 2019/1020 applies; a dedicated administrative cooperation group (ADCO) is set up; where a product presents a significant cybersecurity risk the authority evaluates it and can require corrective action, withdrawal or recall (Art 54); other Member States and the Commission have three months to object (Art 54(8)); the Commission can decide at Union level, with an ENISA evaluation and an implementing act, in exceptional circumstances (Art 56); even compliant products can be restricted if they present significant risks to safety, fundamental rights or essential-entity services (Art 57); formal defects (CE marking, declaration, documentation) must be fixed (Art 58); joint activities and **sweeps** (Arts 59-60).
- **Transition and review (Arts 69-70):** EU type-examination certificates and approvals under other harmonisation law stay valid until **11 June 2028**; products placed on the market before 11 December 2027 are caught only after a **substantial modification**, except Article 14 (all products); Commission report on the single reporting platform by **11 September 2028**; full evaluation by **11 December 2030** and every four years. Delegated powers run **five years from 10 December 2024**, tacitly extended.
- **Procedure:** 2022/0272(COD), verified on OEIL on 5 Oct 2026: proposal COM(2022)0454 of 15 September 2022; ITRE rapporteur Nicola Danti (Renew); committee vote 19 July 2023 (report A9-0253/2023); Parliament first reading T9-0130/2024 on 12 March 2024; Council adopted 10 October 2024; signed 23 October 2024; OJ 20 November 2024.
- **AI Act link (Art 12, recital 51):** a high-risk AI system that is also a product with digital elements is deemed to meet AI Act Article 15 cybersecurity requirements where it meets Annex I Parts I and II and the EU declaration of conformity shows the Article 15 level; the AI Omnibus (Regulation 2026/1744) now repeats this as new Article 42(3) of the AI Act. Notified bodies competent under the AI Act can also assess the CRA requirements, and the AI Act Article 43 procedure applies, except for important or critical products on the internal-control route, which follow the CRA procedures for cybersecurity (Art 12(3)).
- **Words that are NOT in the text:** the Regulation does not require a shutdown or kill-switch capability, and it contains no rule on stopping a product remotely; its strongest powers are withdrawal and recall (Arts 54-57).

## Related legislation

| Act | CELEX | Relationship |
|---|---|---|
| Cybersecurity Act | 32019R0881 | ENISA mandate + certification framework; the CRA relies on ENISA as a reporting recipient |
| NIS2 Directive | 32022L2555 | Entity-level cyber obligations, parallel reporting duties |
| AI Act | 32024R1689 | Article 15 cybersecurity requirements for high-risk AI |
| Market surveillance Regulation | 32019R1020 | Enforcement machinery, amended by the CRA |
| Representative actions Directive | 32020L1828 | Amended by the CRA; collective redress from 11 December 2027 |
| Machinery Regulation | 32023R1230 | Overlapping essential requirements for connected machinery |

## Sources

- Regulation (EU) 2024/2847, Articles 13, 14, 16, 43, 64, 69, 71 and Annex I, read from the act
  itself via EUR-Lex CELEX 32024R2847 (verified 17 August 2026).
- ELI permalink: http://data.europa.eu/eli/reg/2024/2847/oj
- Full text re-read 5 Oct 2026 from Cellar (all recitals, articles and annexes), plus corrigenda 2024/90780, 2025/90555 and 2025/90828, Implementing Regulation 2025/2392, Delegated Regulation 2026/881 and the OEIL file 2022/0272(COD).
- Brubru deep-dive: https://brubru.beresol.eu/eucanon/2024-2847_cra/index.html
- ENISA press release, "The CRA Single Reporting Platform is launched", 11 September 2026:
  https://www.enisa.europa.eu/news/the-cra-single-reporting-platform-is-launched (read 14 September 2026)
- ENISA single reporting platform topic page and guidance, including the FAQ updated 12 September
  2026: https://www.enisa.europa.eu/topics/product-security/single-reporting-platform-srp
- The platform itself: https://portal.cra-srp.enisa.europa.eu/

## Related Brubru guides

`cybersecurity_act`, `nis2_directive`, `ai_act_regulation`, `enisa_european_cybersecurity_agency`,
`ai_agents_compliance_architecture_eu`, `eu_legislation_milestones_aug_sep_2026`, `ai_omnibus_regulation_2026_1744`

`european_innovation_act.md`: its **Article 30** imports this Regulation's **Annex I** essential
requirements wholesale into R&D procurement, and requires buyers to exclude high-risk suppliers of
ICT components in key ICT assets. Brubru deep dive: https://brubru.beresol.eu/european-innovation-act/
