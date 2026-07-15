# EMIR: Derivatives Clearing, Margins, and Central Counterparties (EMIR 3.0)

## QUICK FACTS

- Short name: EMIR (European Market Infrastructure Regulation)
- Full title: Regulation (EU) No 648/2012 on OTC derivatives, central counterparties and trade repositories
- CELEX: 32012R0648. OJ L 201, 27.7.2012, p. 1
- EUR-Lex URL: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32012R0648
- Legal basis: Article 114 TFEU. Entry into force: 16 August 2012
- Supervisor: ESMA -- technical standards, CCP supervisory colleges, trade repository registration, third-country CCP recognition. Responsible DG: DG FISMA. EP lead committee: ECON
- **Three pillars:** (1) clearing obligation for standardised OTC derivatives; (2) risk-mitigation techniques for non-centrally-cleared OTC derivatives (confirmation, reconciliation, compression, dispute resolution, margining); (3) trade reporting to a registered trade repository
- **EMIR 3.0 reform package:** Regulation (EU) 2024/2987 (amends EMIR, CRR and the Money Market Funds Regulation) plus Directive (EU) 2024/2994 (amends UCITS Directive 2009/65/EC, CRD 2013/36/EU, IFD (EU) 2019/2034)
- EMIR 3.0 published in OJ 4 December 2024, **in force 24 December 2024**. Directive transposition deadline: **25 June 2026**
- **Active Account Requirement (AAR), new Article 7a -- the headline change:** in-scope EU counterparties above the clearing threshold in specified systemic products must hold an active account at an EU-authorised CCP for those products, to cut reliance on UK CCPs (mainly LCH Ltd SwapClear, ICE Clear Europe)
- AAR product scope: OTC interest rate derivatives (IRD) in euro or Polish zloty, and OTC short-term interest rate derivatives (STIR) in euro
- AAR account-opening deadline: **24-25 June 2025** (6 months from entry into force); representativeness RTS effective **26 February 2026** (verify live, dates can shift with scrutiny periods)
- AAR representativeness test: at least 5 trades in each of the 5 most relevant subcategories per contract class, annual average, with proportionate exemptions for smaller clearing volumes (full detail below)
- UK CCP equivalence: extended by the Commission to **30 June 2028** (decision January 2025) to give EU clearing capacity time to build under EMIR 3.0
- Clearing thresholds (Delegated Reg (EU) No 149/2013, pending EMIR 3.0 recalibration): EUR 1bn gross notional each for credit and equity derivatives; EUR 3bn each for interest rate and FX derivatives; EUR 4bn for commodity and other derivatives
- Non-financial counterparties: **NFC+** (above threshold, subject to clearing) vs **NFC-** (below threshold, exempt from clearing, still subject to risk-mitigation rules)
- Trade reporting: **EMIR Refit** ISO 20022 XML reporting standards applicable **29 April 2024** (Unique Product Identifiers, around 203 reportable fields)
- CCP recovery and resolution: **Regulation (EU) 2021/23**, applicable from 12 August 2022 -- recovery plans, resolution authorities, resolution toolkit for EU CCPs
- **Brubru deep-dive explainer:** none published yet -- do not fabricate a URL; use the EUR-Lex and ESMA sources listed below

## Overview

EMIR is the EU's post-2008 framework for derivatives markets. The G20 Pittsburgh commitment of September 2009 -- that all standardised OTC derivatives should be cleared through central counterparties, reported to trade repositories, and (where appropriate) traded on exchanges or electronic platforms -- was transposed into EU law through EMIR (2012) on the clearing/reporting/risk-mitigation side and MiFID II/MiFIR (2014) on the trading-obligation side. EMIR pre-dates MiFID II and was itself amended by MiFID II/MiFIR for definitional consistency.

EMIR sits alongside two closely linked instruments that this guide treats as companions rather than duplicating in full: the **CCP Recovery and Resolution Regulation (EU) 2021/23**, which handles what happens if an EU CCP itself gets into difficulty, and **MiFIR's derivatives trading obligation**, which mandates on-venue trading for certain cleared derivatives. Both are cross-referenced below.

The regulation has been amended twice at meaningful scale: **EMIR Refit** (Regulation (EU) 2019/834, 2019) simplified reporting obligations for smaller counterparties and introduced single-sided reporting for some transaction types, and **EMIR 3.0** (Regulation (EU) 2024/2987 plus Directive (EU) 2024/2994, in force December 2024) is the current live reform, centred on the Active Account Requirement.

## The Clearing Obligation

Article 4 requires that OTC derivative contracts belonging to a class that ESMA has declared subject to the clearing obligation must be cleared through an authorised or recognised CCP. ESMA runs a bottom-up (CCP already clears the class, ESMA proposes extending the obligation) and top-down (ESMA identifies systemically relevant uncleared classes) determination process under Article 5. Classes currently subject to the obligation include specified interest rate swap classes (EUR, USD, GBP, JPY) and index credit default swap classes.

Frontloading (contracts entered into after determination but before the obligation formally applies) and backloading provisions govern the transition window once a class is designated. Counterparties must classify themselves correctly (financial counterparty, NFC+, NFC-, or a third-country equivalent) because the clearing obligation, margining rules and reporting granularity all depend on that classification.

## Central Counterparties (CCPs)

**Authorisation (Title III, Articles 14-21).** An EU CCP must be authorised by its national competent authority in coordination with a supervisory college that includes ESMA, the relevant central bank of issue, and other Member State authorities. Authorisation is service- and product-specific; a CCP must apply separately (via a streamlined fast-track procedure under EMIR 3.0) to extend into new services or products, which was previously slow enough to push EU clearing business toward faster-moving UK CCPs.

**Prudential requirements (Title IV).** Capital requirements, organisational requirements (independent risk committee with clearing member and client representation), conduct of business rules, and default fund/skin-in-the-game requirements ensure a CCP can absorb the default of its largest two clearing members (the "cover 2" standard) through its default waterfall: defaulter's margin, defaulter's default-fund contribution, CCP's own capital ("skin in the game"), non-defaulting members' default-fund contributions, further assessments.

**Recovery and resolution.** Regulation (EU) 2021/23 requires every EU CCP to draw up a recovery plan and gives resolution authorities pre-emptive resolution-planning powers and a resolution toolkit (write-down of variation margin gains, partial tear-up of contracts, forced allocation of positions, government stabilisation tools as a last resort) modelled on the bank BRRD regime but adapted to CCP loss-allocation mechanics.

**Third-country CCPs.** Article 25 requires ESMA recognition, contingent on a Commission equivalence decision for the third country's regime. Recognised third-country CCPs are tiered: **Tier 1** (not systemically important, lighter-touch recognition) and **Tier 2** (substantially systemically important, subject to EU-comparable prudential requirements and ESMA on-site inspection powers). The three UK CCPs (ICE Clear Europe, LCH Ltd, LME Clear Ltd) are recognised under this regime, with LCH Ltd designated Tier 2. The UK equivalence decision underpinning this recognition has been repeatedly time-limited and was most recently extended to 30 June 2028.

## The Active Account Requirement (EMIR 3.0, Article 7a)

The AAR is the centrepiece of EMIR 3.0 and the main reason for this reform. Roughly 90% of euro-denominated interest rate derivatives clearing has historically taken place at LCH Ltd in London, a concentration the EU considers a systemic financial-stability risk it cannot supervise directly post-Brexit.

**Who is in scope.** EU counterparties (financial counterparties and NFC+ non-financial counterparties) that are subject to the clearing obligation and whose cleared volumes in the in-scope product categories exceed specified thresholds.

**In-scope products.** OTC interest rate derivatives denominated in euro, OTC interest rate derivatives denominated in Polish zloty, and OTC short-term interest rate derivatives denominated in euro -- the three product categories ESMA identified as most concentrated in third-country (UK) CCPs and most systemically significant for the EU.

**Three layered obligations.**
1. **Account opening (operational condition):** open and maintain an active, operational account at an EU-authorised CCP for the in-scope product categories. Deadline: within six months of entry into force, i.e. by 24-25 June 2025.
2. **Representativeness condition:** clear a minimum representative volume of in-scope trades through the EU account, calibrated as at least 5 trades in each of the 5 most relevant subcategories per contract class on an annual average basis, with proportionate longer reference periods for smaller clearing volumes and a full exemption below a low-volume threshold.
3. **Reporting condition:** in-scope counterparties must report to their competent authority (and ESMA aggregates EU-wide) on their EU versus non-EU clearing volumes, to let supervisors monitor whether the requirement is shifting activity as intended.

**Timeline.** The Regulation entered into force with the account-opening obligation live from 24 December 2024 (six-month grace period to 24-25 June 2025). The representativeness and reporting technical detail followed via ESMA's regulatory technical standards, finalised in ESMA's June 2025 report and taking effect 26 February 2026. Verify the current in-force date of the RTS live, since Commission endorsement and Parliament/Council scrutiny periods can shift the effective date by weeks.

**Why it matters for advocacy.** Buy-side and sell-side firms with material euro/PLN interest-rate derivative books face real operational cost (new CCP membership, collateral segregation, basis risk between EU and UK cleared books) to comply. EU CCPs (Eurex Clearing being the principal beneficiary) are the commercial winners. The measure is contested: industry associations (ISDA, FIA) have raised concerns about fragmenting liquidity and increasing costs without proportionate systemic-risk benefit, while EU institutions frame it as a Capital Markets Union and open strategic autonomy priority.

## Risk-Mitigation Techniques for Non-Centrally-Cleared OTC Derivatives (Article 11)

For OTC derivative contracts not subject to the clearing obligation (either because the class is not yet designated, or because the counterparty is an NFC- below threshold), EMIR still imposes:

- **Timely confirmation:** electronic confirmation of trade terms within tight deadlines (same or next business day for most counterparty types)
- **Portfolio reconciliation:** periodic reconciliation of outstanding contract terms between counterparties, frequency scaled to portfolio size
- **Portfolio compression:** analysis and, where appropriate, execution of portfolio compression exercises for larger uncleared portfolios
- **Dispute resolution:** documented procedures to identify, record and resolve disputes over contract valuation or margin calls within defined timeframes
- **Margining (the bilateral margin rules):** exchange of variation margin daily and, above a phased-in notional threshold, initial margin, calculated under standardised or approved internal models, segregated from the posting counterparty's own assets. This is the bilateral counterpart to CCP-side margining and follows the BCBS-IOSCO global framework for uncleared margin.

## Trade Reporting (Article 9)

All derivative contracts -- OTC and exchange-traded -- must be reported to a trade repository registered or recognised by ESMA, by both counterparties (or, for some transaction types after EMIR Refit, by only one side, e.g. the financial counterparty reporting on behalf of an NFC-). The **EMIR Refit reporting overhaul** (Delegated/Implementing Regulations amending Commission Regulations 148/2013 and 1247/2012) became applicable on 29 April 2024, replacing the legacy format with ISO 20022 XML messaging, mandatory Unique Product Identifiers (UPI) sourced from the Derivatives Service Bureau, and a substantially expanded field set (around 203 total reportable fields). ESMA-registered trade repositories currently include DTCC, Regis-TR and UnaVista.

## Key Numbers

| Item | Value |
|---|---|
| Original EMIR entry into force | 16 August 2012 |
| EMIR 3.0 Regulation + Directive in force | 24 December 2024 |
| Directive (EU) 2024/2994 transposition deadline | 25 June 2026 |
| AAR account-opening deadline | 24-25 June 2025 (6 months from entry into force) |
| AAR representativeness RTS effective | 26 February 2026 |
| AAR representativeness minimum | 5 trades in each of 5 most relevant subcategories, annual average |
| UK CCP equivalence extension | to 30 June 2028 |
| EMIR Refit reporting (ISO 20022) applicable | 29 April 2024 |
| Clearing threshold, credit / equity derivatives | EUR 1 billion gross notional each |
| Clearing threshold, interest rate / FX derivatives | EUR 3 billion gross notional each |
| Clearing threshold, commodity and other derivatives | EUR 4 billion gross notional |
| CCP default waterfall standard | Cover 2 (largest two clearing member defaults) |
| CCP Recovery and Resolution Regulation applicable | 12 August 2022 |

## Lineage

**Regulation (EU) No 648/2012** (original EMIR) responded to the 2009 G20 Pittsburgh commitments on OTC derivatives reform. **EMIR Refit** (Regulation (EU) 2019/834, applicable mid-2019) simplified reporting for smaller counterparties, introduced single-sided reporting for NFC- and small AIFs/UCITS, and refined the clearing-threshold calculation methodology. The **EMIR Refit reporting technical standards** (2022, applicable 29 April 2024) delivered the operational ISO 20022 overhaul separately from the legislative Refit. **EMIR 3.0** (Regulation (EU) 2024/2987 and Directive (EU) 2024/2994, in force 24 December 2024) is the current reform wave, built around the Active Account Requirement, streamlined CCP product/service authorisation, and prudential adjustments (via the linked CRR and CRD/IFD amendments) that reduce the capital penalty for EU counterparties clearing at EU CCPs relative to third-country CCPs. EMIR is also cross-referenced and partially amended by DORA (Regulation (EU) 2022/2554), MiFID II/MiFIR, and the CCP Recovery and Resolution Regulation (EU) 2021/23.

## Useful References

- EUR-Lex, original EMIR (CELEX 32012R0648): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32012R0648
- EUR-Lex, EMIR 3.0 Regulation (CELEX 32024R2987): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2987
- ESMA post-trading / EMIR hub: https://www.esma.europa.eu/esmas-activities/markets-and-infrastructure/post-trading
- ESMA clearing obligation and risk-mitigation techniques page: https://www.esma.europa.eu/post-trading/clearing-obligation-and-risk-mitigation-techniques-under-emir
- ESMA clearing thresholds page: https://www.esma.europa.eu/post-trading/clearing-thresholds
- ESMA EMIR reporting hub: https://www.esma.europa.eu/data-reporting/emir-reporting
- ESMA final report on the Active Account Requirement RTS (June 2025): https://www.esma.europa.eu/sites/default/files/2025-06/ESMA91-1505572268-4201_Final_Report_on_EMIR_3_Active_Account_Requirement.pdf
- European Commission, extension of UK CCP equivalence: https://finance.ec.europa.eu/news/commission-extends-time-limited-equivalence-uk-central-counterparties-2025-01-31_en
- ESMA register of CCPs authorised under EMIR: https://www.esma.europa.eu/sites/default/files/library/ccps_authorised_under_emir.pdf

## Related Brubru Guides

- `esma_supervisory_oversight_mandates.md` -- ESMA's role as technical standard-setter, CCP supervisory-college participant, trade repository registrar and third-country recognition authority
- `mifid_ii_directive.md` -- companion trading-venue and derivatives-trading-obligation framework; EMIR clearing determinations feed the MiFIR trading obligation
- `eu_financial_markets_mifid.md` -- overview of the wider MiFID II/MiFIR advocacy context that EMIR's clearing obligation interacts with
- `savings_and_investment_union.md` -- Capital Markets Union / Savings and Investment Union initiative, within which EMIR 3.0 and the drive to deepen EU clearing capacity sit
- `listing_act_eu_capital_markets.md` -- adjacent Capital Markets Union file on primary-market access, part of the same competitiveness agenda as EMIR 3.0
- `dora_digital_operational_resilience.md` -- DORA amends EMIR (Regulation (EU) No 648/2012) for ICT third-party risk oversight of CCPs and trade repositories; read together on operational-resilience obligations for financial market infrastructure
