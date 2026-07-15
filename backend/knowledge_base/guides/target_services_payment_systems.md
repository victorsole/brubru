# Eurosystem Market Infrastructure: T2, TIPS, T2S and TARGET Services

## QUICK FACTS
- Topic: TARGET Services -- the Eurosystem's market infrastructure for payments, securities settlement, instant payments and collateral management
- Operator: The Eurosystem (European Central Bank + national central banks of the 20 euro-area member states)
- **T2**: Real-time gross settlement (RTGS) system for large-value payments in central bank money. Live since 20 March 2023, when the "T2-T2S consolidation" retired the original TARGET2 (launched 2007) and merged its payments and liquidity-management functions into a single new platform, T2.
- **T2S (TARGET2-Securities)**: Pan-European securities settlement platform, settling securities transactions in central bank money. Started operations 22 June 2015, migrated in five waves through September 2017. Around 20 central securities depositories (CSDs) connect to it.
- **TIPS (TARGET Instant Payment Settlement)**: 24/7/365 real-time settlement of instant credit transfers, in seconds, any day of the year. Launched 30 November 2018. Settles in euro, Swedish krona and Danish krone; Norwegian krone and Icelandic krona extensions planned.
- **ECMS (Eurosystem Collateral Management System)**: Harmonised system for managing collateral pledged for Eurosystem credit operations. Went live 16 June 2025, after being rescheduled twice (from November 2024).
- **Pontes**: The Eurosystem's new distributed ledger technology (DLT) interoperability link, connecting market DLT platforms to TARGET Services. Governing Council approved eligibility criteria and use cases on 4 December 2025; initial offering foreseen to go live in Q3 2026, with further functionality added step by step.
- **Instant Payments Regulation (Regulation (EU) 2024/886)**: amends the SEPA Regulation (260/2012) and the Cross-Border Payments Regulation (924/2009). Euro-area payment service providers (PSPs) had to be reachable to RECEIVE instant credit transfers from 9 January 2025, and had to be able to SEND instant transfers -- at no higher a price than an equivalent standard credit transfer -- plus offer mandatory Verification of Payee (VoP), all from 9 October 2025. Non-euro-area PSPs get later deadlines: receiving by 9 January 2027, sending and VoP by 9 July 2027 (non-bank PSPs: 9 April 2027 for both).
- Verify current milestone status live: implementation deadlines above have already passed for euro-area PSPs as of this guide's last verification; treat as historical fact, not upcoming.
- Related: EU securities settlement is moving from T+2 to T+1 under a targeted CSDR amendment, published in the Official Journal 14 October 2025, applying from 11 October 2027 (phased implementation from December 2026).

TARGET Services are the plumbing underneath every euro payment and euro-denominated securities transaction: the wholesale settlement layer that retail instant payments, card schemes, securities trades and central bank operations all ultimately clear through in central bank money.

## What TARGET Services Are

"TARGET" originally stood for Trans-European Automated Real-time Gross settlement Express Transfer system. Today "TARGET Services" is the Eurosystem's umbrella term for the family of market infrastructure platforms it operates for the euro area (and, for some services, non-euro EU currencies on an opt-in basis): T2, T2S, TIPS, ECMS and, as of 2026, Pontes. They share common technical and governance features ("shared features") but serve distinct functions:

| Service | What it settles | Launched | Key users |
|---------|------------------|----------|-----------|
| T2 | Large-value payments (RTGS) | 20 March 2023 (replacing TARGET2, 2007) | Central banks, commercial banks, ancillary systems |
| T2S | Securities transactions | 22 June 2015 | Central securities depositories (CSDs), custodian banks |
| TIPS | Instant credit transfers | 30 November 2018 | PSPs offering SEPA Instant Credit Transfer |
| ECMS | Collateral for Eurosystem credit operations | 16 June 2025 | Counterparties in Eurosystem monetary policy operations |
| Pontes | DLT-market-platform interoperability | Initial offering Q3 2026 | Market DLT platforms, tokenised-asset participants |

## T2 (RTGS)

T2 settles large-value and time-critical payments -- interbank transfers, the cash leg of securities transactions, monetary policy operations -- individually and in real time, in central bank money, removing settlement risk. It replaced TARGET2 in the March 2023 "T2-T2S consolidation," which combined payments settlement with a shared, more efficient liquidity-management layer across T2 and T2S. The ECB ran a public consultation in 2025-2026 on extending T2 operating hours to support cross-time-zone and DLT-related settlement needs.

## T2S (Securities Settlement)

T2S is the single pan-European platform for settling securities transactions in central bank money, regardless of the currency or the CSD involved. It removed the fragmentation of national securities settlement systems, cutting cross-border settlement costs and enabling same technical processing across markets. Migration ran in five waves (June 2015 to September 2017); nearly all euro-area CSDs, plus some outside the euro area (Denmark), now settle through it.

## TIPS (Instant Payments)

TIPS settles SEPA Instant Credit Transfers in under ten seconds, 24 hours a day, 365 days a year, in central bank money. It is the settlement rail behind the EU's instant-payments push and behind the Instant Payments Regulation's reachability requirements below. TIPS started in euro and has since added Swedish krona and Danish krone as settlement currencies (both non-euro EU currencies participating on an opt-in basis), with Norwegian krone and Icelandic krona extensions in the pipeline.

## ECMS (Collateral Management)

ECMS harmonises how the Eurosystem manages assets pledged as collateral for monetary policy credit operations and intraday credit across all 20 national central banks, replacing 20 separate national collateral-management systems with a single platform and rulebook. Originally planned for November 2024, the launch slipped twice before going live on 16 June 2025; the Governing Council approved a further update to the project's internal governance agreement in November 2025 reflecting the delay.

## Pontes (DLT Interoperability)

Pontes is the newest addition to the TARGET Services family: a Eurosystem-built interoperability link connecting market-operated DLT (distributed ledger technology) platforms to TARGET Services, so tokenised-asset transactions can settle in central bank money without the DLT platform itself needing to touch T2 or T2S directly. It sits alongside "Appia," the Eurosystem's separate exploratory DLT work. The Governing Council approved the use cases, eligibility criteria for participants, market DLT operators and eligible assets on 4 December 2025, with the initial Pontes offering foreseen to go live in Q3 2026 and further functionality added incrementally afterwards. Pontes is a short-to-medium-term bridging solution; it does not replace or pre-empt the digital euro project, which is a separate, retail-facing initiative (see `digital_euro_project.md`).

## Instant Payments Regulation (Regulation (EU) 2024/886)

The Instant Payments Regulation entered into force in April 2024 and amends both the SEPA Regulation (260/2012) and the Cross-Border Payments Regulation (924/2009) to make instant euro payments the norm rather than a premium option. Core obligations for euro-area PSPs (banks, electronic money institutions, payment institutions):

- **Receive** instant credit transfers: mandatory from 9 January 2025.
- **Send** instant credit transfers, at no higher a price than the PSP's equivalent standard (non-instant) credit transfer: mandatory from 9 October 2025.
- **Verification of Payee (VoP)**: PSPs must offer payers a free check confirming that the name on an account matches the IBAN before a transfer is authorised, reducing "authorised push payment" fraud and misdirected transfers. Mandatory from 9 October 2025 for euro-area PSPs, applying to both instant and standard SEPA credit transfers.

Non-euro-area EU PSPs (banks in Member States outside the euro area) have longer deadlines: reachability to receive by 9 January 2027; sending and VoP by 9 July 2027 (non-bank PSPs such as EMIs and payment institutions: both obligations by 9 April 2027). A limited derogation, subject to national competent authority permission, allows some non-euro-area PSPs to delay full compliance for euro-denominated transfers above a threshold until 9 June 2028.

TIPS is the natural settlement rail for the instant transfers the Regulation mandates, though PSPs may also reach instant-payment reachability through other RT1-type instant payment schemes as long as they meet the Regulation's interoperability requirements.

## CSDR and the Move to T+1 Settlement

A related but distinct reform: the EU is shortening its standard securities settlement cycle from two business days after trade (T+2) to one (T+1), via a targeted amendment to the Central Securities Depositories Regulation (CSDR). The amending act was published in the Official Journal on 14 October 2025 and applies from 11 October 2027, with a phased implementation starting December 2026. T+1 does not change which platform settles the trades (T2S remains the securities settlement rail) but compresses the operational window for matching, funding and collateral movements that flow through T2, T2S and ECMS.

## Why This Matters for EU Policy Professionals

- **Financial-services and payments dossiers**: TARGET Services are the operational backbone referenced whenever EU legislation touches payments (Instant Payments Regulation, PSD3/PSR), securities settlement (CSDR, T+1), or collateral and monetary policy implementation.
- **Digital euro debate**: TARGET infrastructure, and now Pontes, are frequently cited by the ECB and Eurosystem as the "wholesale" and "interoperability" layer that would sit alongside a retail digital euro, distinguishing the two workstreams. See `digital_euro_project.md`.
- **Crypto-assets and tokenisation**: Pontes and the Eurosystem's exploratory DLT work (Appia) are the institutional response to market demand for settling tokenised securities and crypto-assets in central bank money, relevant to MiCA implementation debates. See `mica_crypto_assets_regulation.md`.
- **Banking union and financial stability**: TARGET balances and settlement risk are recurring indicators in ECB and Eurogroup financial-stability discussions. See `banking_union_reform.md` and `eurogroup_eurozone_finance_ministers.md`.
- **Monetary policy implementation**: ECMS collateral eligibility and valuation directly affect how Eurosystem counterparties access central bank credit operations. See `ecb_monetary_policy.md`.

## Key Resources

| Resource | URL | What it offers |
|----------|-----|-----------------|
| TARGET Services hub | ecb.europa.eu/paym/target/html/index.en.html | Overview of T2, T2S, TIPS, ECMS, Pontes, governance and documentation |
| TIPS overview | ecb.europa.eu/paym/target/tips/html/index.en.html | TIPS facts, figures, onboarding, cross-border payments |
| Instant Payments Regulation (Reg. 2024/886) | eur-lex.europa.eu, CELEX 32024R0886 | Full legal text and implementation deadlines |
| ECB Instant Payments Regulation explainer | ecb.europa.eu/paym/retail/instant_payments/html/instant_payments_regulation.en.html | Plain-language deadline summary |

## Cross-References

- `ecb_monetary_policy.md` -- monetary policy operations that ECMS collateral supports
- `digital_euro_project.md` -- the retail-facing digital euro, distinct from wholesale TARGET/Pontes infrastructure
- `mica_crypto_assets_regulation.md` -- crypto-asset regulation intersecting with Pontes/DLT settlement
- `banking_union_reform.md` -- financial stability and systemic-risk context for payment and settlement infrastructure
- `eurogroup_eurozone_finance_ministers.md` -- euro-area governance context
