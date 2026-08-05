# BEFIT: Business in Europe -- Framework for Income Taxation

## QUICK FACTS
- **Proposal**: Commission proposal for a Council Directive on Business in Europe: Framework for Income Taxation ("BEFIT"), COM(2023) 532, presented **12 September 2023**. CELEX **52023PC0532** (EUR-Lex frequently WAF-gates automated fetches of this page; verify directly in a browser if a fetch fails).
- **What it is**: a proposal for a **common set of rules to compute the corporate tax base** of large groups operating across the EU -- successor in spirit to the earlier CCCTB/CCTB (Common Consolidated/Common Corporate Tax Base) proposals, which the Commission formally withdrew.
- **Scope, mandatory tier**: groups (EU-headquartered or with EU operations) with **annual combined revenue of at least EUR 750 million** in at least two of the last four fiscal years -- the same threshold used by the Pillar Two minimum-tax Directive and by Country-by-Country Reporting (DAC4). Third-country-headquartered groups fall in scope if their EU members have combined revenue of at least EUR 50 million in at least two of the last four years, or at least 5% of the group's total worldwide revenue.
- **Scope, optional tier**: smaller groups below the threshold may opt in if they prepare consolidated financial statements.
- **Three-step mechanic**:
  1. **Compute**: each group member calculates a preliminary tax result under common BEFIT rules, bridging from its financial accounting figures (IFRS or a Member State's national GAAP) rather than replacing national accounting.
  2. **Aggregate**: all members' preliminary results are summed into a single **BEFIT tax base** for the group, with automatic cross-border loss offsetting within the group during a transitional period.
  3. **Allocate**: the aggregated base is reallocated to each Member State by a **transitional formula** based on each member's average share of the group's taxable results over the preceding three years. Member States then apply **their own national corporate tax rate** to their allocated share -- BEFIT harmonises the base, not the rate.
- **Governance**: a "BEFIT team" of representatives from the tax administrations where group members are established reviews the group's BEFIT Information Return, intended to reduce duplicated compliance and disputes across jurisdictions.
- **Companion proposal**: a **Transfer Pricing Directive**, COM(2023) 529, presented the same day, would codify the OECD arm's-length principle and common transfer-pricing rules directly into EU law -- reducing scope for transfer-pricing disputes both inside and outside the BEFIT population.
- **Status**: stalled in Council on **unanimity grounds** (Article 115 TFEU, direct taxation affecting the internal market). As of the EP ECON own-initiative stocktaking in 2026, blockers include Estonia, Hungary and Ireland, reflecting the same tax-sovereignty resistance that slowed CCCTB for over a decade. Verify the live negotiation status before asserting a timeline -- this file moves slowly and unpredictably.
- **Adjacent to Pillar Two**: BEFIT uses the identical EUR 750 million threshold as the OECD/EU Pillar Two 15% global minimum tax (Directive (EU) 2022/2523) but is a **separate, additional layer** -- a common tax *base* and allocation mechanism, not a minimum *rate*. Critics (echoed in the Kollár ECON report) argue BEFIT plus Pillar Two risks a double compliance burden on the same population of large groups; supporters argue BEFIT reduces the 27-jurisdiction base-computation patchwork that groups still face even after Pillar Two harmonised the rate floor.
- **Lead DG**: DG TAXUD (Taxation and Customs Union). Responsible Commissioners on the corporate-tax dossier: **Wopke Hoekstra** (Climate, Net Zero and Clean Growth) and **Maria Luís Albuquerque** (Financial Services).
- **Council configuration**: ECOFIN (Economic and Financial Affairs), unanimity required under Article 115 TFEU.
- **Related SME-facing proposal**: the Commission's parallel **Head Office Tax (HOT) system for SMEs**, COM(2023) 528, would let qualifying SMEs with permanent establishments abroad compute tax under their head office's home-country rules rather than BEFIT's group-level mechanism -- a lighter-touch alternative for smaller cross-border businesses. Verify HOT's own status separately; it is not part of the BEFIT text.

## Why BEFIT Exists

The EU has tried to harmonise the corporate tax base twice before: the 2011 CCTB/CCCTB proposals and a 2016 relaunch, both of which stalled indefinitely on Council unanimity. BEFIT is the Commission's third attempt, relaunched in the post-Pillar Two environment on the theory that agreeing a global 15% minimum rate makes it more politically feasible to also agree a common EU base -- since Member States can no longer compete purely on rate below the 15% floor, the argument runs that a common base reduces compliance costs without further eroding a Member State's ability to compete on rate above 15%. The proposal explicitly targets compliance-cost reduction for groups currently filing under up to 27 different national base-computation regimes, while preserving each Member State's sovereign right to set its own headline rate.

## How the BEFIT Base and Allocation Work

1. **Preliminary tax result**: each BEFIT group member starts from its financial accounting net income or loss and applies a common, limited set of adjustments (defined by the Directive) to compute a preliminary tax result -- this does not require a full parallel set of books, only accounting-to-tax bridging adjustments.
2. **Aggregation into one base**: the preliminary results of every member of the BEFIT group across the EU are summed. Losses of one member automatically offset profits of another during a transitional period, addressing a long-standing complaint that groups cannot offset losses across Member State borders under national rules alone.
3. **Transitional allocation formula**: rather than a permanent formulary-apportionment key (which BEFIT does not yet fix), the aggregated base is allocated to each Member State based on that member's average percentage share of the group's total taxable result over the preceding three fiscal years -- a baseline formula intended to be replaced by a permanent allocation method after a review period.
4. **National application**: once a Member State receives its allocated share, it applies its own corporate tax rate and any national adjustments (incentives, deductions the Directive does not harmonise) to determine the actual tax due in that jurisdiction.
5. **One-stop compliance filing**: the BEFIT group files a single, standardised BEFIT Information Return with a designated filing entity, replacing (for participating groups) a set of separately formatted national base computations -- while national tax payment and rate-setting remain fully domestic.

## Interaction With Adjacent EU Tax Files

- **Pillar Two Directive (EU) 2022/2523**: same EUR 750 million threshold population; BEFIT is a base-harmonisation layer on top of, not a substitute for, the 15% minimum-rate floor. See `eu_pillar_two_minimum_tax_15` for the Pillar Two mechanics.
- **Transfer Pricing Directive, COM(2023) 529**: presented alongside BEFIT the same day, harmonising the arm's-length principle EU-wide -- relevant both to BEFIT-scope groups and to the wider transfer-pricing population.
- **DAC (Directive on Administrative Cooperation)**: the DAC framework's automatic-exchange machinery (most recently DAC9 for Pillar Two GloBE returns) is the likely template for how BEFIT Information Returns would eventually be exchanged between Member State tax administrations, though BEFIT itself is not yet a DAC amendment. See `eu_dac_administrative_cooperation_tax`.
- **CCCTB/CCTB (withdrawn)**: BEFIT is explicitly positioned by the Commission as replacing, not reviving, the earlier common consolidated base proposals, which were formally withdrawn from the legislative pipeline.
- **Head Office Tax (HOT) system for SMEs, COM(2023) 528**: a lighter, opt-in alternative for SMEs with cross-border permanent establishments, filed the same day as BEFIT but a separate legal instrument with its own (also unanimity-blocked) negotiation track.
- **ECON own-initiative report (Kollár, PE781.467)**: the European Parliament's 2026 stocktaking of Pillar Two implementation, BEFIT's stalled status and US tax-policy divergence gives the fullest current political read on where BEFIT sits in the EP/Council pipeline -- see `eu_corporate_tax_policy_2026` for that detail rather than duplicating it here.

## Brubru Users

- Tax directors and in-house tax counsel at multinationals above the EUR 750 million threshold tracking whether BEFIT will apply on top of their existing Pillar Two compliance
- Big Four and boutique tax advisory firms modelling the compliance-cost impact of a single BEFIT Information Return versus 27 separate national base computations
- Trade associations (BusinessEurope, AmCham EU, Digital Europe) monitoring the Council unanimity blockers and lobbying on the transitional allocation formula
- DG TAXUD stakeholders and Member State Finance Ministry attachés following the Article 115 TFEU negotiation
- SME advisers assessing whether the Head Office Tax alternative is a better fit than BEFIT's group-level mechanism

## Status and Verification Notes

BEFIT has no adopted text and no transposition deadline -- it remains a Commission proposal awaiting Council unanimity. Facts requiring live re-verification before external use: (1) the current list of Member States blocking or resisting BEFIT in Council (Estonia, Hungary, Ireland were named in the 2026 EP ECON stocktaking; this can shift); (2) whether the Commission has revised or withdrawn any element of COM(2023) 532 or COM(2023) 529 since publication; (3) the status of the parallel Head Office Tax (HOT) proposal, COM(2023) 528. Verify against `https://taxation-customs.ec.europa.eu/taxation/business-taxation/business-europe-framework-income-taxation-befit_en` directly rather than relying on secondary press coverage. The EUR-Lex CELEX page for 52023PC0532 returned an empty/gated response on automated fetch (HTTP 202, consistent with EUR-Lex's known JS-rendered anti-bot behaviour) -- open it in a browser to confirm the text directly if needed.

## Cross-Links

- `eu_corporate_tax_policy_2026` -- EP ECON own-initiative report (Kollár), the political framing around Pillar Two review, BEFIT's stalled status, and US tax divergence
- `eu_pillar_two_minimum_tax_15` -- the 15% global minimum tax Directive sharing BEFIT's EUR 750 million threshold
- `eu_dac_administrative_cooperation_tax` -- DAC1-DAC9 information-exchange framework, the likely template for future BEFIT return exchange
- `vat_in_the_digital_age_2026` -- separate indirect-tax digitalisation file, same DG TAXUD lead
- `single_market_programme` -- internal market context for cross-border compliance-cost reduction
