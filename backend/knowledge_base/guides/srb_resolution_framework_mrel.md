# Single Resolution Board and MREL: Resolution Planning under SRMR/BRRD

## QUICK FACTS
- Body: Single Resolution Board (SRB) -- the central resolution authority of the Banking Union
- Seat: Brussels (Treurenberg 22, 1049 Brussels)
- Chair: Dominique Laboureix (since January 2023, succeeded Elke Koenig)
- Scope: 21 Banking Union Member States (euro area plus Bulgaria under close cooperation since 1 January 2024)
- Pillar role: Resolution is the 2nd pillar of the Banking Union (1st = ECB/SSM prudential supervision, 3rd = deposit insurance/EDIS, still not established)
- Legal basis: Single Resolution Mechanism Regulation (SRMR), Regulation (EU) No 806/2014, CELEX 32014R0806
- Works alongside: Bank Recovery and Resolution Directive (BRRD), Directive 2014/59/EU, CELEX 32014L0059
- BRRD2: Directive (EU) 2019/879, CELEX 32019L0879 -- transposed the FSB TLAC standard into EU law and reshaped MREL
- Daisy Chains Directive: Directive (EU) 2024/1174, CELEX 32024L1174 -- applicable from 14 November 2024, amends Article 12d SRMR, gives flexibility on internal MREL in multi-layered resolution groups and simplifies treatment of liquidation entities
- CMDI reform (adopted 2026): SRMR3 = Regulation (EU) 2026/808; BRRD3 = Directive (EU) 2026/806; DGSD2 = Directive (EU) 2026/804. Signed 30 March 2026, entered into force 20 days after OJ publication (OJ L, 20.4.2026). SRM/SRB institutional provisions apply from 11 June 2026; most other provisions (including the recalibrated Public Interest Assessment) apply from 11 May 2028. See `banking_union_reform` for the full CMDI package
- MREL = Minimum Requirement for own funds and Eligible Liabilities -- the loss-absorbing and recapitalisation buffer every bank must hold
- MREL calibration: Loss Absorption Amount (LAA) + Recapitalisation Amount (RCA), expressed against risk-weighted assets/TREA and against the leverage ratio exposure (LRE); a Market Confidence Charge (MCC) is added on top of the RCA for resolution entities
- Current MREL policy: SRB MREL Policy 2024 (published May 2024), reflecting the Daisy Chains Directive changes
- Resolution tools (BRRD Article 37): bail-in, sale of business, bridge institution, asset separation
- Public Interest Assessment (PIA): decides whether a failing bank goes into resolution or normal national insolvency proceedings
- Single Resolution Fund (SRF): target level of at least 1% of covered deposits in Banking Union Member States; reached target circa 2024 at EUR 80 billion; stood at over EUR 81 billion at 31 December 2025; no additional bank levies needed for 2025 or 2026
- ESM common backstop: ESM Treaty amendment signed 27 January 2021 by all euro area states, would roughly double SRF firepower via an ESM credit line; ratification still incomplete as of mid-2026 (Italy and Czechia are the outstanding states among IGA-ratifying countries); not yet operational
- Governing bodies: Plenary Session (Chair, Vice-Chair, 4 full-time Board Members, 21 national resolution authority representatives, European Commission and ECB as permanent observers) and Executive Session (Chair, Vice-Chair non-voting, 4 full-time Board Members, extended to relevant NRA members when deliberating on a specific bank)

Verify SRF exact euro figure, CMDI application dates and ESM backstop ratification count against the live SRB/ESM pages before quoting in time-sensitive material -- all three move.

## What the SRB Does

The Single Resolution Board is the EU body responsible for planning and, if necessary, executing the orderly resolution of failing banks in the Banking Union, with the aim of protecting depositors, critical functions and financial stability without resorting to taxpayer-funded bail-outs. It is distinct from -- and works alongside -- the European Central Bank's Single Supervisory Mechanism (SSM), which handles day-to-day prudential supervision. The SRB is the resolution authority for the largest and most significant banks directly, and oversees national resolution authorities (NRAs) for smaller institutions under the Single Resolution Mechanism (SRM).

The SRM has three pillars:
1. **Prudential supervision** -- ECB/SSM (see `ecb_monetary_policy`, `financial_supervision_eba`)
2. **Resolution** -- SRB and national resolution authorities (this guide)
3. **Deposit insurance** -- national Deposit Guarantee Schemes under the DGSD, with a full European Deposit Insurance Scheme (EDIS) still politically blocked

## MREL: Minimum Requirement for Own Funds and Eligible Liabilities

MREL is the bank-specific buffer of capital and bail-inable liabilities that every institution in scope must hold so that, if it fails, losses can be absorbed and the bank recapitalised without public money. It is the EU's implementation of the FSB's Total Loss-Absorbing Capacity (TLAC) standard for global systemically important banks, extended to a wider population of EU banks.

**Calibration formula:**
- **Loss Absorption Amount (LAA):** broadly mirrors the bank's own funds requirements (Pillar 1 + Pillar 2 + combined buffer), reflecting the losses the bank should be able to absorb before resolution
- **Recapitalisation Amount (RCA):** the amount of loss-absorbing capacity needed to recapitalise the bank post-resolution so it can regain market confidence and meet authorisation conditions, generally mirroring the same capital requirements post-resolution
- **Market Confidence Charge (MCC):** an additional buffer added to the RCA for resolution entities, calibrated only against MREL-TREA (total risk exposure amount); the SRB's 2024 policy allows resolution authorities to reduce the MCC where resolvability progress justifies it
- MREL is expressed both as a percentage of total risk exposure amount (TREA, i.e. risk-weighted assets) and as a percentage of the leverage ratio exposure (LRE)

**External vs internal MREL:** external MREL applies at the resolution entity level (the entity that would actually be resolved); internal MREL applies to subsidiaries within a resolution group, ensuring losses can be passed up the chain to the resolution entity. The 2024 Daisy Chains Directive (Directive (EU) 2024/1174) specifically targets internal MREL in multi-layered ("daisy chain") group structures, giving resolution authorities more flexibility in setting internal MREL and simplifying the treatment of liquidation entities (the SRB will generally not set internal MREL above the amount sufficient to absorb losses for pure liquidation entities).

**Eligible liabilities:** must be subordinated (in most cases), have a remaining maturity of at least one year, not be funded directly or indirectly by the bank itself, and not be derivatives or deposits excluded by law. Senior non-preferred debt is the most common MREL-eligible instrument issued by EU banks.

**Resolution tools available once MREL is triggered (BRRD Article 37):**
- **Bail-in:** write-down or conversion into equity of eligible liabilities, following the statutory creditor hierarchy (CET1 first, then AT1, Tier 2, subordinated debt, senior non-preferred, senior unsecured, with certain liabilities such as covered deposits and secured liabilities excluded)
- **Sale of business:** transfer of shares or assets to a private purchaser without shareholder consent
- **Bridge institution:** transfer of critical functions to a temporary publicly controlled entity pending sale
- **Asset separation:** transfer of impaired assets to an asset management vehicle, always used alongside another tool, never alone

## Public Interest Assessment (PIA) and Resolvability

The **Public Interest Assessment** is the gatekeeping test the SRB runs when a bank is failing or likely to fail: does resolution action serve the public interest (financial stability, protection of depositors, protection of public funds, continuity of critical functions), or would normal national insolvency proceedings achieve those objectives equally well or better? A positive PIA sends the bank into resolution; a negative PIA sends it into national insolvency (winding-up), where covered deposits are paid out by the national Deposit Guarantee Scheme.

The CMDI reform (SRMR3/BRRD3/DGSD2, adopted 2026, most provisions applying from 11 May 2028) recalibrates the PIA test: under the new framework insolvency must be demonstrably *more* effective than resolution to defeat a positive PIA, rather than merely equally effective as under the old wording. The practical effect is to widen the population of banks for which resolution -- rather than national insolvency -- becomes the default expectation, extending the toolkit to smaller and mid-sized, predominantly deposit-funded institutions that previously fell outside the SRB's direct resolution planning focus. See `banking_union_reform` for the full legislative detail (procedures 2023/0111(COD), 2023/0112(COD), 2023/0113(COD); rapporteurs Tinagli, Niedermayer, Peter-Hansen).

**Resolvability assessment:** the SRB annually assesses whether banks under its remit are "resolvable" against its published Expectations for Banks (EfB), covering governance, loss-absorbing capacity, liquidity and funding in resolution, operational continuity, information systems, communication and separability. Banks with unresolved resolvability deficiencies can be required to take remedial action, and the SRB can restrict distributions (the Maximum Distributable Amount related to MREL, M-MDA) if a bank breaches its combined buffer requirement on top of MREL.

## Single Resolution Fund (SRF) and the Common Backstop

The **Single Resolution Fund** is an ex-ante fund built from annual contributions levied on banks across the 21 Banking Union Member States, available to support resolution actions (for example financing a bridge institution or covering losses not absorbed by bail-in, subject to the 8% total-liabilities bail-in threshold before SRF money can be used). Its target level is at least 1% of covered deposits held in Banking Union Member States, verified annually. The Fund reached its target level around 2024 (approximately EUR 80 billion) and stood at over EUR 81 billion at 31 December 2025; the SRB has not needed to raise additional annual contributions for 2025 or 2026.

The **ESM common backstop** is a credit line from the European Stability Mechanism intended to roughly double the SRF's effective firepower in a systemic crisis, repayable by the banking sector over time so it remains fiscally neutral in the medium term. The backstop was agreed by Eurogroup in 2020 and the underlying ESM Treaty amendment was signed by all euro area states on 27 January 2021, but it only becomes operational once every euro area Member State has ratified the amendment. As of mid-2026 ratification remains incomplete, with Italy and Czechia the outstanding states among those that have ratified the underlying SRM intergovernmental agreement -- the backstop is therefore agreed in principle but not yet live.

## Governance

- **Plenary Session:** Chair, Vice-Chair, 4 full-time Board Members, plus one representative from each of the 21 participating national resolution authorities; the European Commission and the ECB sit as permanent observers. Decides on the SRF, general methodology and matters affecting more than one participating Member State.
- **Executive Session:** Chair, Vice-Chair (non-voting), 4 full-time Board Members. Prepares resolution plans, sets MREL and takes resolution decisions for banks under direct SRB remit; extended to include the relevant NRA member(s) when deliberating on a specific bank ("extended" Executive Session).
- The SRB works closely with the European Commission, the ECB/SSM, the European Banking Authority (technical standards, stress tests) and national resolution authorities.

## Timeline

| Date | Event |
|------|-------|
| 2014 | SRMR (Reg 806/2014) and BRRD (Dir 2014/59) adopted, establishing the SRM and the SRB |
| 1 January 2016 | SRB becomes fully operational; SRF established |
| 2019 | BRRD2 (Dir (EU) 2019/879) transposes FSB TLAC into EU MREL framework |
| 11 April 2024 | Daisy Chains Directive (Dir (EU) 2024/1174) adopted |
| 14 November 2024 | Daisy Chains Directive changes to Article 12d SRMR become applicable |
| May 2024 | SRB publishes MREL Policy 2024 |
| 31 December 2024 | SRF reaches approximately EUR 80 billion, above the 1% covered-deposits target |
| 25-26 March 2026 | EP adopts CMDI package (SRMR3, BRRD3, DGSD2) at second reading |
| 30 March 2026 | CMDI package signed |
| 11 June 2026 | SRM/SRB institutional provisions of CMDI package become applicable |
| 31 December 2025 | SRF stands at over EUR 81 billion |
| 11 May 2028 | Most CMDI provisions, including the recalibrated PIA, become applicable; Member States must transpose BRRD3 |

## Related Brubru Guides
- `banking_union_reform` -- the CMDI legislative package (SRMR3/BRRD3/DGSD2) in full
- `crr_capital_requirements_regulation` -- own funds requirements that underpin the LAA/RCA calculation
- `ecb_monetary_policy` -- ECB/SSM prudential supervision, the 1st pillar of the Banking Union
- `financial_supervision_eba` -- European Banking Authority, technical standards and stress tests
- `esrb_macroprudential_framework` -- systemic risk oversight alongside resolution
- `eu_anti_money_laundering` -- AML obligations that interact with bank authorisation and resolution
