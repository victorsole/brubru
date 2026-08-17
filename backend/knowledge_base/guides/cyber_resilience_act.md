# Cyber Resilience Act (Regulation (EU) 2024/2847)

## QUICK FACTS
- **LATEST (Monday 17 August 2026 — 25 DAYS TO THE FIRST BINDING DEADLINE):** **Article 14 reporting obligations start applying on 11 September 2026.** From that date a manufacturer must notify actively exploited vulnerabilities and severe incidents to the coordinating CSIRT **and** ENISA simultaneously, via the single reporting platform in Article 16, on a **24 hour / 72 hour / 14 day** clock. Article 69(3) makes this bite on **products already on the market** — it is not a new-products-only duty. Everything else in the Regulation waits until 11 December 2027.
- Full name: Regulation (EU) 2024/2847 of the European Parliament and of the Council of 23 October 2024 on horizontal cybersecurity requirements for products with digital elements and amending Regulations (EU) No 168/2013 and (EU) 2019/1020 and Directive (EU) 2020/1828 (Cyber Resilience Act)
- Common name: Cyber Resilience Act (CRA)
- CELEX: 32024R2847
- ELI: http://data.europa.eu/eli/reg/2024/2847/oj
- Adopted: 23 October 2024 (Strasbourg)
- Published: OJ, 20 November 2024
- Entry into force: the twentieth day following publication (10 December 2024)
- **Applies from: 11 December 2027** (Article 71(2))
- **Article 14 applies from: 11 September 2026** (Article 71(2), second subparagraph)
- **Chapter IV, Articles 35 to 51, applied from: 11 June 2026** — notification of conformity assessment bodies, already live
- Type: Regulation (directly applicable, no transposition)
- Sister acts: Cybersecurity Act (Reg (EU) 2019/881, ENISA + certification), NIS2 (Dir (EU) 2022/2555), AI Act (Reg (EU) 2024/1689)

## The three application dates, and why they differ

Article 71 staggers the Regulation deliberately, so that the reporting pipeline and the
conformity-assessment infrastructure exist before the substantive product requirements bite.

| Date | What starts | Status today (17 Aug 2026) |
|---|---|---|
| 11 June 2026 | Chapter IV (Arts 35-51): notification of conformity assessment bodies | **already applying** |
| **11 September 2026** | **Article 14: manufacturer reporting of actively exploited vulnerabilities and severe incidents** | **25 days away** |
| 11 December 2026 | Member States "shall strive to ensure" enough notified bodies exist (Art 43(2)) — a best-efforts target, not an obligation on companies | pending |
| 11 December 2027 | The Regulation as a whole: Annex I essential requirements, conformity assessment, CE marking, support period, technical documentation | pending |

**The trap.** Article 69(2) says products placed on the market before 11 December 2027 are only
caught by the Regulation if they undergo a substantial modification after that date. Article
69(3) then **derogates from that** for Article 14: the reporting duties apply to **all in-scope
products already on the market**. A company that reads only Article 69(2) will conclude it has
until December 2027 and will be wrong by fifteen months.

## Article 14 — what actually has to be done from 11 September 2026

Two reportable events: an **actively exploited vulnerability** in the product, and a **severe
incident having an impact on the security of the product**. Both go **simultaneously** to the
CSIRT designated as coordinator and to **ENISA**, through the **single reporting platform**
established under Article 16.

Three-stage clock, per event:

| Stage | Deadline | Content |
|---|---|---|
| Early warning | **within 24 hours** of becoming aware | that it has happened; where applicable, which Member States the product was made available in |
| Notification | **within 72 hours** of becoming aware | the product concerned, the general nature of the exploit or incident, corrective or mitigating measures taken, measures users can take, and how sensitive the manufacturer considers the information |
| Final report | **no later than 14 days** after a corrective or mitigating measure is available | description of the vulnerability including severity and impact; where available, information on the malicious actor exploiting it; details of the security update or other corrective measure |

"Becoming aware" starts the clock, not publication and not confirmation.

## Scope — products with digital elements

The Regulation applies to products with digital elements made available on the market whose
intended or reasonably foreseeable use includes a direct or indirect data connection to a device
or network. It grades them:

- **Default class** — self-assessment against the Annex I essential requirements.
- **Important products with digital elements** — a higher cybersecurity risk because of the
  function they perform; split into Class I and Class II with progressively stricter conformity
  assessment routes.
- **Critical products with digital elements** — the strictest route, capable of being made
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

- **Cybersecurity Act, Reg (EU) 2019/881** — a *different* Regulation. It governs ENISA's mandate
  and the European cybersecurity certification framework. It does not carry the CRA's product
  obligations. See `cybersecurity_act`.
- **NIS2, Dir (EU) 2022/2555** — obliges *entities* operating essential and important services;
  the CRA obliges *products*. An organisation can be in scope of both, reporting an incident
  under NIS2 as an operator and under CRA Article 14 as a manufacturer.
- **AI Act, Reg (EU) 2024/1689** — Article 15 cybersecurity requirements for high-risk AI systems
  interact with the CRA where the AI system is itself a product with digital elements.
- **Directive (EU) 2020/1828** (representative actions) is amended by the CRA; collective redress
  for CRA infringements starts 11 December 2027.

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

## Related Brubru guides

`cybersecurity_act`, `nis2_directive`, `ai_act_regulation`, `enisa_european_cybersecurity_agency`,
`ai_agents_compliance_architecture_eu`, `eu_legislation_milestones_aug_sep_2026`
