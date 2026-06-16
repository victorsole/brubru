# Solvency II Directive

<!-- QUICK FACTS
instrument: Directive 2009/138/EC — Solvency II
celex: 32009L0138
oj: OJ L 335, 17.12.2009, p. 1
legal_base: Articles 47(2) and 55 EC Treaty (now Articles 53(1) and 62 TFEU)
type: Directive (recast)
adopter: European Parliament and Council
adopted: 25 November 2009
transposition_original: 31 October 2012
transposition_omnibus_ii: 31 March 2015 (Directive 2014/51/EU)
application_date: 1 January 2016
scope: all EU insurance and reinsurance undertakings (except grandfathered small undertakings and statutory social security schemes)
pillar_1: Quantitative requirements -- technical provisions, own funds, SCR, MCR, investment rules
pillar_2: Governance and supervisory requirements -- system of governance, ORSA, fit-and-proper, supervisory review
pillar_3: Transparency and reporting -- SFCR (public annual report) and RSR (supervisory reporting)
scr: Solvency Capital Requirement -- 99.5% Value-at-Risk over one-year period (Article 101(3))
mcr: Minimum Capital Requirement -- 85% VaR one-year; linear function; must stay between 25% and 45% of SCR
own_funds_tiering: Tier 1 (permanent + subordinate) must exceed 1/3 of SCR own funds and 1/2 of MCR own funds; Tier 3 capped at 1/3
orsa: Own Risk and Solvency Assessment -- undertaking's own prospective assessment of overall solvency needs (Article 45)
sfcr: Solvency and Financial Condition Report -- public annual disclosure (Article 51)
eiopa: European Insurance and Occupational Pensions Authority (successor to CEIOPS)
group_supervision: college of supervisors; group supervisor; Method 1 (consolidation) or Method 2 (deduction-aggregation)
recast: replaces 13 directives repealed by Article 310 plus Directive 64/225/EEC on reinsurance freedom of establishment
deep_dive_url: https://brubru.beresol.eu/eucanon/2009-138_solvency2/
-->

## Context

Solvency II is the EU's fundamental prudential supervisory framework for insurance and reinsurance. It replaced a patchwork of 14 earlier directives with a single, economic, risk-based regime. The stated main objective is the protection of policyholders and beneficiaries (Article 27). Financial stability and fair markets are secondary objectives and may not override policyholder protection.

The 2009 text set a transposition deadline of 31 October 2012. Directive 2014/51/EU (Omnibus II) subsequently amended Solvency II in several respects, including extending the transposition deadline to 31 March 2015 and setting 1 January 2016 as the application date. This guide describes the 2009 text.

---

## Structure: 312 Articles, 7 Annexes, 6 Titles

- **Title I** (Articles 1-311 range): General rules on taking-up and pursuit of business
  - Chapter I: Subject matter, scope, and definitions
  - Chapter II: Taking-up of business (authorisation)
  - Chapter III: Supervisory authorities and general rules
  - Chapter IV: Conditions governing business (governance, disclosure, qualifying holdings)
  - Chapter V: Pursuit of life and non-life simultaneously (composite prohibition)
  - Chapter VI: Quantitative requirements (technical provisions, own funds, SCR, MCR, investments)
  - Chapter VII: Undertakings in difficulty (intervention ladder)
  - Chapter VIII: Freedom of establishment and freedom to provide services
- **Title II** (Articles 178-211): Specific provisions for insurance and reinsurance (co-insurance, assistance, legal expenses, health, life, reinsurance, SPVs)
- **Title III** (Articles 212-266): Group supervision
- **Title IV** (Articles 267-296): Reorganisation and winding-up
- **Title V** (Articles 297-304): Other provisions (HICP revision of amounts, committee procedure, duration-based equity sub-module)
- **Title VI** (Articles 305-312): Transitional and final provisions
- **Annexes I-VII**: Insurance classes, legal forms, Standard formula structure, correlation table, repealed directives

---

## The Three Pillars

### Pillar 1: Quantitative Requirements

**Technical Provisions (Articles 76-86)**

Technical provisions equal the sum of the best estimate and the risk margin (Article 77).

The best estimate is the probability-weighted average of future cash flows discounted at the risk-free interest rate term structure. It is a gross-of-reinsurance figure; reinsurance recoverables are calculated separately and adjusted for counterparty default risk (Article 81).

The risk margin uses the Cost-of-Capital approach: the additional capital an acquirer would need to hold to support the obligations over their lifetime, multiplied by the cost-of-capital rate.

Where future cash flows can be reliably replicated using financial instruments with observable market values, the market value of those instruments may be used without a separate best-estimate/risk-margin split (Article 77(4)).

**Own Funds and Tiering (Articles 87-99)**

Basic own funds = excess of assets over liabilities (valued at fair value) plus subordinated liabilities (Article 88).

Ancillary own funds are items callable to absorb losses that are not basic own funds (unpaid share capital, letters of credit, guarantees). They require prior supervisory approval (Article 90).

Own-fund items are classified into three tiers (Articles 93-96):

- **Tier 1**: Permanent availability and full subordination on winding-up. The most loss-absorbing.
- **Tier 2**: Subordination but not necessarily full permanence.
- **Tier 3**: Items meeting neither criterion fully.

Eligibility limits (Article 98):
- For SCR coverage: Tier 1 must exceed one-third of total eligible own funds; Tier 3 must be less than one-third.
- For MCR coverage: Tier 1 must exceed one-half of total eligible basic own funds.

Surplus funds (accumulated profits not available for distribution) qualify as Tier 1 where they meet the permanence criteria (Articles 91 and 96).

**Solvency Capital Requirement (Articles 100-127)**

The SCR is the principal capital requirement. Eligible own funds must cover it at all times.

**Article 101(3) (confirmed verbatim):** "It shall correspond to the Value-at-Risk of the basic own funds of an insurance or reinsurance undertaking subject to a confidence level of 99,5 % over a one-year period." Recital 64 describes this as ruin occurring no more than once in every 200 cases.

The SCR covers at least: non-life underwriting risk, life underwriting risk, health underwriting risk, market risk, credit risk, and operational risk (which includes legal risk but excludes strategic and reputational risk) (Article 101(4)).

**Standard Formula (Articles 103-111):**

SCR = Basic SCR + operational risk capital charge + adjustment for loss-absorbing capacity of technical provisions and deferred taxes.

The Basic SCR (Article 104) aggregates five risk modules, each calibrated at 99.5% VaR one-year (Article 104(4)):
1. Non-life underwriting risk (premium/reserve risk + catastrophe sub-modules)
2. Life underwriting risk (mortality, longevity, disability/morbidity, expense, revision, lapse, life catastrophe)
3. Health underwriting risk (expense, claims, epidemic/catastrophe)
4. Market risk (interest rate, equity, property, spread, currency, concentration)
5. Counterparty default risk (reinsurance, derivatives, intermediary receivables)

Key calibration constraints:
- Operational risk capped at 30% of Basic SCR for non-life business (Article 107(3))
- Equity sub-module symmetric adjustment: deviation from standard charge capped at plus or minus 10 percentage points (Article 106(3))

Undertakings may replace a subset of standard formula parameters with parameters derived from their own data (undertaking-specific parameters), subject to supervisory approval (Article 104(7)).

**Internal Models (Articles 112-127):**

Full or partial internal models may replace the standard formula after supervisory approval. Partial models may cover one or more modules or specific business units. Key approval standards:
- Use test: the model must be embedded in risk management and decision-making (Article 120).
- Statistical quality standards: methods actuarially and statistically sound; data updated at least annually (Article 121).
- Calibration: results must be equivalent to the 99.5% VaR one-year measure (Article 122).
- Validation: regular validation including statistical testing (Article 124).
- Documentation: full documentation of theory, assumptions, and limitations (Article 125).

**Capital Add-On (Article 37):**

Supervisors may impose a capital add-on following the supervisory review process in three exceptional circumstances: (a) the risk profile deviates significantly from standard formula assumptions and internal modelling is inappropriate or under development; (b) the risk profile deviates from internal model assumptions due to under-captured risks; (c) the system of governance deviates significantly from required standards. The add-on is a last resort and reviewed annually.

**Minimum Capital Requirement (Articles 128-131):**

The MCR is the absolute floor below which authorisation must be withdrawn. It is a simple, auditable linear function of technical provisions, written premiums, capital-at-risk, deferred taxes, and administrative expenses (Article 129(2)).

**Article 129(1)(c):** calibrated to 85% VaR over one year.

**MCR corridor (Article 129(3)):** The MCR must not fall below 25% nor exceed 45% of the SCR.

**MCR absolute floors (Article 129(1)(d)):**
- Non-life (standard): EUR 2,200,000
- Non-life (liability/credit/suretyship classes): EUR 3,200,000
- Life: EUR 3,200,000
- Reinsurance: EUR 3,200,000 (captive reinsurance: EUR 1,000,000)

**Investment: Prudent Person Principle (Article 132):**

All assets must be managed in accordance with the prudent person principle. No mandatory asset allocation; no prior approval of investment decisions required (Article 133). Assets covering technical provisions must be invested appropriately to the nature and duration of liabilities, in the best interest of policyholders. Derivatives permissible only to reduce risk or facilitate efficient portfolio management.

---

### Pillar 2: Governance and Supervisory Requirements

**System of Governance (Articles 41-50)**

Every undertaking must have an effective governance system providing for sound and prudent management (Article 41). Must include written policies on risk management, internal control, internal audit, and outsourcing, reviewed at least annually.

**Four mandatory governance functions:**

1. **Risk management function (Article 44):** Covers all material risk categories including underwriting/reserving, ALM, investment (including derivatives), liquidity and concentration risk, operational risk, and reinsurance. For internal model users, the function also oversees model design, testing, and documentation.

2. **Compliance function (Article 46):** Advises on legal and regulatory compliance; assesses impact of legal change.

3. **Internal audit function (Article 47):** Evaluates adequacy and effectiveness of internal controls and governance. Must be objective and independent from operational functions.

4. **Actuarial function (Article 48):** Coordinates technical provisions calculation; ensures appropriateness of methods and assumptions; opines on underwriting policy and reinsurance arrangements.

Multiple functions may be combined in smaller undertakings, except the internal audit function, which must remain independent (Recital 32).

**Fit and Proper (Article 42):**

All persons who effectively run the undertaking or hold other key functions must at all times be professionally qualified, knowledgeable, and experienced (fit) and of good repute and integrity (proper). Changes to key function holders must be notified to the supervisory authority.

**Own Risk and Solvency Assessment (ORSA) (Article 45):**

Every undertaking must conduct its own risk and solvency assessment covering:
(a) Overall solvency needs with respect to its specific risk profile and business strategy.
(b) Continuous compliance with SCR, MCR, and technical provision requirements.
(c) The degree to which the undertaking's risk profile deviates from the SCR assumptions.

The ORSA must be conducted regularly and following any significant change in risk profile. Results are reported to supervisors as part of supervisory reporting. The ORSA does not serve to set a capital requirement different from the SCR or MCR (Article 45(7)).

**Supervisory Review Process (Articles 36-38):**

Home Member State bears exclusive financial supervision responsibility for the undertaking's entire business including cross-border branches and services (Article 30). Supervisors must review strategies, processes, and reporting procedures using a prospective, risk-based, proportionate approach (Articles 29 and 36). Capital add-ons may be imposed following this process (Article 37).

**Outsourcing (Article 49):**

Undertakings remain fully responsible for all obligations when outsourcing. Supervisors must be notified prior to outsourcing critical or important functions.

---

### Pillar 3: Transparency and Reporting

**Solvency and Financial Condition Report (SFCR) (Articles 51-56):**

Annual public disclosure containing:
(a) Business description and performance.
(b) System of governance and assessment of its adequacy.
(c) Risk exposure, concentration, mitigation, and sensitivity.
(d) Valuation bases for assets, technical provisions, and liabilities with explanation of differences from financial statements.
(e) Capital management: structure and amount of own funds; SCR and MCR amounts; SCR calculation method used; significant deviations from standard formula or internal model; any MCR non-compliance or significant SCR non-compliance.

Supervisors may permit non-disclosure where information would give competitors significant undue advantage or is confidential, but never for capital management information (Article 53(4)).

Material developments (MCR breach, significant SCR breach) trigger additional immediate disclosure (Article 54).

**Regular Supervisory Reporting (RSR) (Article 35):**

Undertakings submit to supervisors all information necessary for supervision including governance assessment, valuation principles, risk exposures, risk management systems, and capital structure. Requested at predefined periods, on predefined events, or during enquiries.

---

## Substantive Provisions: Key Articles

| Topic | Articles | Key content |
|---|---|---|
| Scope and exclusions | 2-12 | Exclusion: GWP < EUR 5m, TPs < EUR 25m, no liability/credit/suretyship (Art. 4) |
| Definitions (39 terms) | 13 | Qualifying holding = 10%; participation = 20%; risk types |
| Authorisation conditions | 14-25 | Single EU passport; scheme of operations required |
| Supervision objectives | 27-28 | Policyholder protection primary; financial stability secondary |
| Home state supervision | 30 | Exclusive financial supervision of entire business |
| Capital add-on | 37 | Three grounds; exceptional tool; annual review |
| Governance system | 41-50 | Four functions; written policies; proportionality |
| Fit and proper | 42 | All key function holders; ongoing requirement |
| ORSA | 45 | Prospective; not a capital requirement; reported to supervisor |
| Compliance function | 46 | Advises management body |
| Internal audit | 47 | Independent from operations |
| Actuarial function | 48 | Opinions on TPs, UW policy, reinsurance |
| Outsourcing | 49 | Prior notification for critical functions |
| SFCR | 51-55 | Annual public disclosure |
| Qualifying holdings | 57-63 | 60 working-day assessment; three notification thresholds |
| Auditor duties | 72 | Mandatory reporting of MCR/SCR breaches to supervisor |
| Composite undertakings | 74 | Notional MCR per activity; separate financing |
| Asset valuation | 75 | Fair value; liabilities at fair transfer value |
| Technical provisions | 76-86 | Best estimate + risk margin; market-consistent |
| Best estimate | 77(2) | Probability-weighted discounted cash flows |
| Risk margin | 77(3) | Cost-of-Capital method |
| Replicating portfolio | 77(4) | Market value where reliable replication possible |
| Reinsurance recoverables | 81 | Calculated gross; adjusted for counterparty default |
| Basic own funds | 87-88 | Excess of assets over liabilities + subordinated liabilities |
| Ancillary own funds | 89-90 | Callable items; prior supervisory approval required |
| Tiering criteria | 93 | Permanence + subordination determine tier |
| Eligibility limits | 98 | Tier 1 > 1/3 (SCR); Tier 1 > 1/2 (MCR); Tier 3 < 1/3 |
| SCR calibration | 101(3) | 99.5% VaR one-year |
| SCR risk coverage | 101(4) | Six risk categories including operational risk |
| Standard formula structure | 103-111 | BSCR + OpRisk + loss-absorbing adjustment |
| BSCR modules | 104-105 | Five modules; each calibrated 99.5% VaR one-year |
| Equity symmetric adjustment | 106 | Maximum ± 10pp from standard charge |
| OpRisk cap | 107(3) | 30% of BSCR for non-life |
| Internal model approval | 112 | Full or partial; supervisory approval required |
| Use test | 120 | Embedded in risk management and decision-making |
| MCR calibration | 129(1)(c) | 85% VaR one-year |
| MCR corridor | 129(3) | 25%-45% of SCR |
| MCR absolute floors | 129(1)(d) | EUR 1m-3.2m depending on class |
| Prudent person principle | 132 | All assets; no mandatory allocation; no prior approval |
| SCR non-compliance | 138 | 6-month recovery (extendable); immediate notification |
| MCR non-compliance | 139 | 3-month restoration; withdrawal on failure (Art. 144) |
| Group scope | 213 | In addition to solo supervision |
| Group SCR | 218 | Eligible own funds >= group SCR at all times |
| Method 1 | 230-232 | Accounting consolidation; group SCR >= sum of solo MCRs |
| Method 2 | 233-234 | Deduction and aggregation; sum of solo SCRs at proportional shares |
| Group supervisor | 247 | Designated from Member State supervisors |
| College of supervisors | 248 | Established for every group; chaired by group supervisor |
| Third-country equivalence | 260 | Commission may assess equivalence; reliance if equivalent |
| Reorganisation | 269 | Home state exclusive; automatically effective throughout EU |
| Winding-up | 273 | Home state exclusive |
| Insurance claims priority | 275 | Precedence over other claims; two implementation options |
| Repeal of predecessors | 310 | 13 predecessor directives repealed effective 1 November 2012 |
| Transposition | 309 | Original deadline 31 October 2012 (Omnibus II: 31 March 2015) |

---

## Key Numbers

- **SCR**: 99.5% VaR, one-year horizon (Article 101(3))
- **MCR**: 85% VaR, one-year horizon (Article 129(1)(c))
- **MCR corridor**: 25%-45% of SCR (Article 129(3))
- **Tier 1 floor for SCR**: > one-third of eligible own funds (Article 98(1)(a))
- **Tier 3 ceiling for SCR**: < one-third of eligible own funds (Article 98(1)(b))
- **Tier 1 floor for MCR**: > one-half of eligible basic own funds (Article 98(2))
- **Operational risk cap**: 30% of Basic SCR (Article 107(3))
- **Equity symmetric adjustment**: maximum ± 10 percentage points (Article 106(3))
- **MCR absolute floor, non-life standard**: EUR 2,200,000
- **MCR absolute floor, non-life liability classes**: EUR 3,200,000
- **MCR absolute floor, life**: EUR 3,200,000
- **MCR absolute floor, reinsurance**: EUR 3,200,000; captive reinsurance: EUR 1,000,000
- **Small undertaking exclusion**: GWP < EUR 5,000,000 and TPs < EUR 25,000,000 (Article 4)
- **SCR recovery period**: 6 months, extendable to 9 months (Article 138(3)-(4))
- **MCR restoration period**: 3 months (Article 139(2))

---

## Lineage: The 14 Recast Instruments

Article 310 repeals 13 directives effective 1 November 2012. The user framing of "14 recast directives" also includes Directive 64/225/EEC:

1. Council Directive 64/225/EEC (reinsurance, freedom of establishment)
2. First Council Directive 73/239/EEC (non-life, taking-up and pursuit)
3. Council Directive 73/240/EEC (non-life, freedom of establishment)
4. Council Directive 76/580/EEC (amendment to 73/239)
5. Council Directive 78/473/EEC (community co-insurance)
6. Council Directive 84/641/EEC (tourist assistance)
7. Council Directive 87/344/EEC (legal expenses insurance)
8. Second Council Directive 88/357/EEC (non-life, freedom to provide services)
9. Council Directive 92/49/EEC (third non-life directive)
10. Directive 98/78/EC (supplementary supervision of groups)
11. Directive 2001/17/EC (reorganisation and winding-up)
12. Directive 2002/83/EC (life assurance)
13. Directive 2005/68/EC (reinsurance)

Omnibus II (Directive 2014/51/EU) is the principal post-2009 amendment, which also introduced a long-term guarantee package and transitional measures for equity risk and risk-free rates.

---

## EIOPA

Solvency II references CEIOPS (Committee of European Insurance and Occupational Pensions Supervisors) throughout. CEIOPS was replaced by EIOPA (European Insurance and Occupational Pensions Authority) as the competent Level 3 body under the European System of Financial Supervision, established by Regulation 1094/2010. EIOPA issues regulatory technical standards, implementing technical standards, and guidelines under the Solvency II framework. Level 2 is principally Commission Delegated Regulation (EU) 2015/35.

---

## Useful References

- Directive 2014/51/EU (Omnibus II): principal amendment; moved application date to 1 January 2016; long-term guarantee package
- Commission Delegated Regulation (EU) 2015/35: Level 2 implementing measures (technical provisions, SCR standard formula, own funds classification, internal models, groups)
- EIOPA website: regulatory technical standards, implementing technical standards, guidelines
- OJ L 335, 17.12.2009, p. 1: original publication
- CELEX 32009L0138: EUR-Lex full text
- Deep-dive: https://brubru.beresol.eu/eucanon/2009-138_solvency2/

---

## Related Brubru Guides

- EU Financial Supervision Architecture (EIOPA, EBA, ESMA)
- Insurance Distribution Directive (IDD, Directive 2016/97/EU)
- Capital Requirements Regulation (CRR) and Directive (CRD) -- banking parallel
- IORP II Directive (Directive 2016/2341/EU) -- occupational pensions
