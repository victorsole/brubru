# SREP: Supervisory Review and Evaluation Process (ECB Banking Supervision)

## QUICK FACTS
- **What it is:** SREP (Supervisory Review and Evaluation Process) is the annual assessment ECB Banking Supervision (the Single Supervisory Mechanism, SSM) runs on every "significant institution" (large euro-area bank it supervises directly) to decide how much capital and liquidity that specific bank needs above the legal minimum.
- **Legal basis:** Articles 97-101 of Directive 2013/36/EU (CRD, as amended by CRD VI) require competent authorities to run SREP; Regulation (EU) No 1024/2013 (the SSM Regulation) gives the ECB the power to do it directly for significant institutions; the European Banking Authority (EBA) issues SREP Guidelines that harmonise the methodology across the EU.
- **Who is assessed:** ECB-supervised "significant institutions" (roughly 105-113 banking groups as of the 2025 cycle, representing about 80% of euro-area banking assets). Less significant institutions are SREP-assessed by their national competent authority under the same EBA Guidelines.
- **Four assessment elements, each scored 1 (low risk) to 4 (high risk):** (1) business-model viability and profitability; (2) internal governance and risk management; (3) risks to capital (credit risk, market risk, interest-rate risk in the banking book (IRRBB), operational risk); (4) risks to liquidity and funding. The four scores feed an overall SREP score.
- **Two capital outputs:**
  - **Pillar 2 Requirement (P2R):** a legally BINDING add-on above the Pillar 1 minimum (CET1 4.5% / Tier 1 6% / Total capital 8%, set by the CRR) plus the combined buffer requirement. It covers risks that Pillar 1 under-captures or excludes (e.g. IRRBB, concentration risk, governance weaknesses). At least 56.25% of P2R must be met with CET1 capital and at least 75% with Tier 1 capital.
  - **Pillar 2 Guidance (P2G):** a NON-binding supervisory expectation, informed mainly by the outcome of the EU-wide stress test, sitting above the P2R and the combined buffer. Breaching P2G does not trigger automatic restrictions, but persistent or unaddressed breaches invite supervisory scrutiny.
- **2026-applicable results (latest cycle, published 18 November 2025):** average overall CET1 capital requirement and guidance for significant institutions held broadly stable at **11.2% of risk-weighted assets**; average P2R stayed broadly stable at **1.2% CET1** (about 2.1% in total-capital terms); average P2G fell from 1.3% to **1.1% CET1**, reflecting stronger 2025 EU-wide stress-test results (higher loss-absorption capacity from higher bank profitability). Source: ECB press release 18 November 2025 and "Aggregated results of the 2025 SREP."
- **Maximum Distributable Amount (MDA) trigger:** if a bank's CET1 capital falls below the sum of Pillar 1 (4.5%) + P2R (CET1 portion) + the combined buffer requirement (capital conservation buffer + countercyclical buffer + systemic buffers), the bank must automatically restrict dividends, share buybacks, variable remuneration (bonuses) and AT1 coupon payments. P2G sits ABOVE the MDA trigger and is not itself part of it, but repeated P2G breaches are a strong forward signal that the MDA threshold is being approached.
- **Multi-year, risk-based SREP reform (decided 2024, phased in, fully applied from the 2026 cycle):** the ECB moved from a full annual deep-dive on every bank to a multi-year approach: Joint Supervisory Teams (JSTs, combining ECB staff and national supervisors) focus each year on the risks that matter most for a given bank and revisit the rest in more depth over a multi-year horizon; banks with a stable risk profile get their SREP decision updated only every two years unless a material change occurs. Goal: a shorter, simpler, more risk-based and judgement-driven process ("SREP of tomorrow"). Verify the current-cycle wording against `bankingsupervision.europa.eu/activities/srep` before quoting specifics, as the reform continues to be refined.
- **Interaction with the EU-wide stress test:** the biennial EU-wide stress test (run by the EBA in cooperation with the ECB, national authorities and the ESRB) is a key input to P2G: the size of the projected CET1 capital depletion under the adverse scenario feeds directly into how much P2G a bank is set.
- **Not the same as MREL:** SREP and its P2R/P2G outputs are a going-concern PRUDENTIAL supervision tool (ECB, under CRD/CRR). The Minimum Requirement for own funds and Eligible Liabilities (MREL) is a RESOLUTION tool set by the Single Resolution Board (SRB) to ensure a bank can be recapitalised in resolution. See `srb_resolution_framework_mrel.md` for MREL.

## What SREP does

Every significant institution supervised directly by the ECB goes through SREP. The Joint Supervisory Team responsible for that bank pulls together on-site inspection findings, off-site monitoring, internal model outcomes, stress-test results and the bank's own ICAAP (Internal Capital Adequacy Assessment Process) and ILAAP (Internal Liquidity Adequacy Assessment Process) submissions, then produces:

1. A score (1-4) for each of the four elements (business model, governance, capital risks, liquidity risks) and an overall score.
2. A Pillar 2 Requirement (P2R), which becomes legally binding once the ECB issues its SREP decision to the bank.
3. A Pillar 2 Guidance (P2G), a supervisory expectation rather than a legal requirement.
4. Qualitative measures: supervisory recommendations, remediation deadlines, sometimes additional own-funds requirements tied to specific findings (e.g. governance weaknesses, model deficiencies).

The bank then has to hold, on top of the P2R and P2G:
- The Pillar 1 minimum (CET1 4.5%, Tier 1 6%, Total 8% of risk-weighted assets, from the CRR).
- The combined buffer requirement: capital conservation buffer (2.5%), institution-specific countercyclical capital buffer, and where applicable a G-SII/O-SII buffer or systemic risk buffer.

Stack these together and you get the bank's total overall capital requirement and guidance, published each November/December for application the following year.

## Why the P2R differs bank to bank

P2R is bank-specific by design. A bank with concentrated commercial real estate exposure, weak governance, or a fragile IRRBB profile will typically carry a higher P2R than a peer with a diversified, well-managed balance sheet. This is the standard answer to "why is my P2R 1.75%" (or any other figure): it reflects the ECB's assessment of THAT bank's idiosyncratic risks not already captured by Pillar 1, not a sector-wide default. There is no published formula; it is a supervisory judgement documented in the bank's individual SREP decision letter, which is confidential to the bank (only the aggregated, anonymised averages are published).

## What to watch each cycle

- **November:** the ECB publishes aggregated SREP results (averages, distributions, score trends) for the cycle applicable the following calendar year.
- Banks disclose their own P2R (Pillar 3 / investor disclosures require it) but not the full SREP decision letter or the individual element scores.
- Any material downgrade in SREP score, a rising P2R trend, or a P2G breach are standard "watch" signals for bank equity and credit analysts, and for the bank's own board risk committee.

## Related Brubru resources

- `crr_capital_requirements_regulation.md`: the Pillar 1 minimum capital ratios, own-funds definitions and buffers that SREP sits on top of (CRR explicitly excludes Pillar 2/supervisory review, which is what this guide covers).
- `banking_union_reform.md`: the wider Banking Union architecture (SSM + Single Resolution Mechanism + the still-incomplete European Deposit Insurance Scheme) that SREP operates within.
- `srb_resolution_framework_mrel.md`: MREL and the resolution-side capital/liabilities requirement, distinct from SREP's going-concern P2R/P2G.
- `financial_supervision_eba.md`: the EBA's role in issuing the SREP Guidelines that harmonise methodology across the EU, including for less significant institutions supervised nationally.
- `ecb_monetary_policy.md`: background on the ECB's dual role (monetary policy and, since 2014, banking supervision via the SSM, kept operationally separate).
- `esrb_macroprudential_framework.md`: the European Systemic Risk Board's role in macroprudential oversight, which feeds into systemic buffer settings that sit alongside P2R/P2G in the overall capital stack.

## Key sources

- ECB Banking Supervision, SREP overview: https://www.bankingsupervision.europa.eu/activities/srep/html/index.en.html
- ECB Banking Supervision, news and publications hub: https://www.bankingsupervision.europa.eu/press/publications/html/index.en.html
- ECB press release, "ECB keeps capital requirements broadly stable for 2026 amid persisting global challenges," 18 November 2025: https://www.bankingsupervision.europa.eu/press/pr/date/2025/html/ssm.pr251118~fb9a8367f3.en.html
- ECB, "Aggregated results of the 2025 SREP": https://www.bankingsupervision.europa.eu/activities/srep/2025/html/ssm.srep202511_aggregatedresults2025.en.html
- ECB, FAQ on the SREP reform ("SREP of tomorrow"): https://www.bankingsupervision.europa.eu/press/other-publications/publications/html/ssm.faq_srep~e7acf21c24.en.html
- Directive 2013/36/EU (CRD), Articles 97-101: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013L0036
- Regulation (EU) No 1024/2013 (SSM Regulation): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R1024
