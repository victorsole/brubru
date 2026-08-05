# One Substance, One Assessment (OSOA): The EU Chemicals Assessment Reform

## QUICK FACTS

- **What it is**: "One Substance, One Assessment" (OSOA) is the EU's reform of how chemical safety data is generated, shared and assessed across the whole chemicals acquis (REACH, CLP, biocides, food, water, medical devices, RoHS and around 70 pieces of chemicals-related law), so that a given substance is assessed once rather than separately, and sometimes inconsistently, by different agencies for different sectoral laws.
- **Legal basis**: three linked acts, all of the European Parliament and of the Council, signed 26 November 2025, published in the Official Journal on 12 December 2025, in force since **1 January 2026**:
  1. **Regulation (EU) 2025/2455** (CELEX `32025R2455`) establishing a common data platform on chemicals (the Common Data Platform on Chemicals, CDPC) and a monitoring and outlook framework.
  2. **Regulation (EU) 2025/2457** (CELEX `32025R2457`) on the reattribution of scientific and technical tasks and improving cooperation among Union agencies in the area of chemicals; amends Regulation (EC) No 178/2002 (General Food Law/EFSA), Regulation (EC) No 401/2009 (EEA), Regulation (EU) 2017/745 (Medical Devices Regulation) and Regulation (EU) 2019/1021 (POPs Regulation).
  3. **Directive (EU) 2025/2456** (CELEX `32025L2456`) amending Directive 2011/65/EU (RoHS) as regards the reattribution of scientific and technical tasks to the European Chemicals Agency.
- **Origin**: Commission legislative package proposed 7 December 2023 (COM(2023) 779, COM(2023) 751 and COM(2023) 752), lead procedure **2023/0453(COD)**, under the 2020 Chemicals Strategy for Sustainability (COM(2020) 667), part of the European Green Deal's zero-pollution ambition.
- **Legislative path**: EP first-reading position 1 April 2025; Council-Parliament provisional political agreement 12 June 2025; EP final vote on all three files 21 October 2025; Council final adoption (green light) 13 November 2025; signature 26 November 2025; OJ publication 12 December 2025; entry into force 1 January 2026.
- **Who runs it**: the **European Chemicals Agency (ECHA)**, based in Helsinki, hosts and operates the CDPC and gains new scientific and technical tasks under the reattribution acts, working alongside the European Food Safety Authority (EFSA), the European Medicines Agency (EMA), the European Environment Agency (EEA), the EU Agency for Safety and Health at Work (EU-OSHA), the European Commission (including the Joint Research Centre) and Member State authorities.
- **Key forward dates**: joint agency implementation plan due mid-2026; Article 26 study-notification obligations (economic operators must notify ECHA of commissioned chemical studies) apply from **2 November 2027**; first annual monitoring-and-outlook report on emerging chemical risks expected around 2 July 2027; core platform services targeted operational roughly three years after entry into force (around 2029); full historical-data integration targeted around ten years after entry into force (around 2036). Treat post-2026 dates as indicative pending the Commission's published implementation roadmap.
- **Official sources**: EUR-Lex `https://eur-lex.europa.eu/eli/reg/2025/2455/oj/eng` (CDPC Regulation), `https://eur-lex.europa.eu/eli/reg/2025/2457/oj/eng` (reattribution Regulation), `https://eur-lex.europa.eu/eli/dir/2025/2456/oj/eng` (RoHS/ECHA Directive), OEIL procedure file `https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2023/0453(COD)`, ECHA `https://echa.europa.eu/`.

This guide is the entry point for the whole OSOA reform. For the deep technical detail of the data platform itself (what it pools, FAIR access rules, IPCheM absorption, human biomonitoring), see the companion guide `eu_chemicals_common_data_platform_cdpc`.

## The problem OSOA is solving

Before this reform, the same chemical substance could be assessed multiple times by different EU bodies under different sectoral laws, using data that was not shared between them. Benzoic acid, for example, has historically undergone separate chemical safety assessments under six different regulatory frameworks (biocides, pesticides, food flavourings, food additives, food contact materials and cosmetics), each generating its own paperwork and sometimes its own new testing. ECHA runs REACH and CLP; EFSA covers pesticides, food additives and food contact materials; EMA covers medicines; the EEA and EU-OSHA hold environmental and occupational data; the Commission's Joint Research Centre runs chemical-monitoring tools such as IPCheM. None of these repositories talked to each other in a structured way.

The 2020 Chemicals Strategy for Sustainability set "one substance, one assessment" as an explicit political objective: pool the data once, assess it consistently, cut duplicate testing (including duplicate animal testing), and give regulators an earlier warning system for emerging chemical risks. OSOA is the legislative delivery of that objective, translated into three linked acts rather than one, because the reform needed both a new data infrastructure and a rewiring of which agency does which task under existing sectoral laws.

## The three OSOA instruments

| Act | CELEX | What it does | Amends / establishes |
|-----|-------|---------------|----------------------|
| Regulation (EU) 2025/2455 | `32025R2455` | Establishes the Common Data Platform on Chemicals (CDPC) and a monitoring and outlook framework for emerging chemical risks; creates the Article 26 obligation for economic operators and testing facilities to notify ECHA of chemical studies commissioned for authorisation, registration or safety-assessment purposes | New freestanding regulation; absorbs the JRC's IPCheM monitoring tool |
| Regulation (EU) 2025/2457 | `32025R2457` | Reattributes scientific and technical tasks between EU agencies and sets a formal procedure to reconcile diverging scientific opinions (for example between EFSA and ECHA) | Amends Regulation (EC) No 178/2002 (General Food Law/EFSA's founding regulation), Regulation (EC) No 401/2009 (EEA), Regulation (EU) 2017/745 (Medical Devices Regulation), Regulation (EU) 2019/1021 (POPs Regulation) |
| Directive (EU) 2025/2456 | `32025L2456` | Reattributes scientific and technical tasks under RoHS to ECHA, including assessment of RoHS exemption applications | Amends Directive 2011/65/EU (RoHS, restriction of hazardous substances in electrical and electronic equipment) |

The package works as a set: Regulation 2025/2455 builds the shared data infrastructure (the CDPC) and the mandatory study-notification system; Regulation 2025/2457 and Directive 2025/2456 redraw who does the underlying scientific and technical work, so that duplicated assessments (the same substance evaluated separately under REACH, food-contact rules and RoHS, for instance) can be consolidated in one agency's hands rather than repeated in several.

Read together with:
- `reach_chemicals_regulation` for the REACH registration and evaluation data that feeds the CDPC.
- `eu_clp_regulation_classification_labelling` for the classification and labelling data pooled alongside REACH data.
- `biocidal_products_regulation` for the Biocidal Products Regulation (BPR) data stream (guide pending; the BPR is explicitly listed among the acts whose data feeds the CDPC).

## Regulation (EU) 2025/2457: reattributing scientific and technical tasks

This is the "who does what" half of the package. It does not touch the data platform directly; it moves specific scientific and technical responsibilities between agencies so the same expertise is not duplicated across sectoral laws:

- Amends the **General Food Law framework** (Regulation (EC) No 178/2002, EFSA's founding regulation), including a revised Article 30 procedure to formally reconcile diverging scientific conclusions between EFSA and other scientific bodies such as ECHA, addressing a long-standing complaint that agencies could reach conflicting views on the same substance with no structured resolution mechanism.
- Amends the **EEA's founding regulation** (Regulation (EC) No 401/2009) to align the European Environment Agency's role in the new data and monitoring architecture.
- Amends the **Medical Devices Regulation** (Regulation (EU) 2017/745), clarifying interfaces between medical-device chemical safety assessment and the wider chemicals framework.
- Amends the **POPs Regulation** (Regulation (EU) 2019/1021, persistent organic pollutants), aligning POPs assessment tasks with the reattributed agency responsibilities.

## Directive (EU) 2025/2456: RoHS tasks move to ECHA

RoHS (Directive 2011/65/EU) restricts hazardous substances such as lead, mercury and certain phthalates in electrical and electronic equipment. Historically, scientific and technical assessment work under RoHS (notably assessing applications for exemptions from the restrictions) sat largely with the Commission's own technical assistance contractors. Directive 2025/2456 formally reattributes that scientific and technical work, including assessment of RoHS exemption applications, to ECHA, consistent with ECHA's expanding role as the EU's central chemicals-science agency, and gives the Commission a review clause to revisit the arrangement as ECHA's scientific-committee governance evolves.

## Regulation (EU) 2025/2455: the Common Data Platform on Chemicals

Regulation 2025/2455 is the flagship instrument of OSOA. It does three things:

1. Establishes the **Common Data Platform on Chemicals (CDPC)**, a single digital entry point pooling hazard, use, emission, exposure and human-biomonitoring data that already exists across REACH, CLP, biocides, plant protection products, food contact materials, cosmetics, the Drinking Water Directive, industrial emissions and occupational exposure legislation, drawing ultimately on around 70 pieces of EU chemicals-related law. It absorbs the Joint Research Centre's existing IPCheM monitoring tool and applies FAIR (Findable, Accessible, Interoperable, Reusable) principles to non-confidential data.
2. Creates a **monitoring and outlook framework** intended to give regulators earlier warning of emerging chemical risks, drawing on input from ECHA, EFSA, EMA and EU-OSHA, with a first annual report expected in the second half of 2027.
3. Introduces, under **Article 26**, a mandatory **study-notification obligation**: economic operators and testing facilities that commission studies generating chemical data (whether on single substances or on substances present in products) for the purposes of authorisation, registration or safety assessment under the sectoral laws listed in Annex I must notify ECHA's database. Both the commissioning party and the testing facility have independent notification duties (a "double-coverage" design so the obligation is not lost if one side fails to notify). Studies already reportable to EFSA are excluded from double notification. This obligation applies from **2 November 2027**, and is the nearest binding compliance date in the whole OSOA package for industry.

For the full technical detail of the CDPC (data categories, FAIR access rules, exclusions, the human-biomonitoring stream, the IPCheM transition, and the detailed implementation timeline), see `eu_chemicals_common_data_platform_cdpc`.

## ECHA's expanded role

Across all three acts, the direction of travel is the same: ECHA moves from being the agency that runs REACH and CLP registration/evaluation to becoming the EU's central, cross-cutting chemicals-science hub. It hosts and operates the CDPC; it gains new scientific and technical tasks reattributed from the Commission under RoHS (Directive 2025/2456); and it becomes one of the counterparties in the new EFSA-ECHA scientific-opinion reconciliation procedure under Regulation 2025/2457. This does not remove EFSA, EMA, the EEA or EU-OSHA from the chemicals landscape, each retains its own sectoral mandate and continues to feed data into the CDPC, but it does concentrate more of the EU's chemicals-science coordination function inside ECHA. For background on ECHA's existing mandate and structure, see `echa_agency_overview`; for EFSA's, see `efsa_agency_overview`.

## Timeline

| Milestone | Date | Status |
|-----------|------|--------|
| Commission legislative package (COM(2023) 779 + companions) | 7 December 2023 | Complete |
| Council general approach | 14 June 2024 | Complete |
| EP first-reading position | 1 April 2025 | Complete |
| Council-Parliament provisional political agreement (trilogue) | 12 June 2025 | Complete |
| EP final vote on all three files | 21 October 2025 | Complete |
| Council final adoption | 13 November 2025 | Complete |
| Signature | 26 November 2025 | Complete |
| Publication in Official Journal L | 12 December 2025 | Complete |
| Entry into force | 1 January 2026 | Complete |
| Joint agency implementation plan due | Mid-2026 (verify against Commission roadmap once published) | Upcoming |
| Article 26 study-notification obligation applies | 2 November 2027 | Upcoming |
| First annual monitoring/outlook report on emerging risks | Around 2 July 2027 (verify) | Upcoming |
| Core CDPC services targeted operational | Around 2029 (roughly 3 years post entry into force) | Upcoming |
| Full historical-data integration targeted | Around 2036 (roughly 10 years post entry into force) | Upcoming |

## Why it matters to policy professionals

- **Industry and regulatory affairs teams**: the Article 26 study-notification duty (from 2 November 2027) is the first hard compliance date most companies will face under OSOA, separate from and additional to existing REACH, CLP, BPR or sectoral reporting duties. It applies to studies commissioned for authorisation, registration or safety-assessment purposes, and duplicates onto both the commissioning company and the contracted testing facility.
- **Public affairs and Transparency Register strategists**: the reattribution acts (2025/2457 and 2025/2456) shift institutional weight further toward ECHA relative to EFSA, the EEA, EMA and EU-OSHA. Any engagement strategy on chemicals files should track ECHA's growing scientific-committee workload and the new EFSA-ECHA reconciliation procedure under the amended Article 30 of the General Food Law.
- **NGOs, researchers and public-health advocates**: the CDPC's FAIR-compliant public data access and the formalised human-biomonitoring stream materially expand what is independently verifiable about chemical exposure and hazard data across the EU, beyond what any single agency's own database previously offered.
- **Compliance teams**: OSOA is primarily a data-governance and institutional reform. It does not itself rewrite the substantive hazard classification, authorisation or restriction rules in REACH, CLP, the BPR or RoHS, those obligations still flow from the underlying instruments. What changes is where data must be reported, which agency assesses it, and how disagreements between agencies get resolved.

## Key documents and resources

| Resource | URL | What it offers |
|----------|-----|-----------------|
| Regulation (EU) 2025/2455 (CDPC) | https://eur-lex.europa.eu/eli/reg/2025/2455/oj/eng | Full text establishing the Common Data Platform on Chemicals |
| Regulation (EU) 2025/2457 (task reattribution) | https://eur-lex.europa.eu/eli/reg/2025/2457/oj/eng | Full text of the agency-task reattribution and cooperation Regulation |
| Directive (EU) 2025/2456 (RoHS/ECHA) | https://eur-lex.europa.eu/eli/dir/2025/2456/oj/eng | Full text amending RoHS to move scientific/technical tasks to ECHA |
| OEIL procedure file 2023/0453(COD) | https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2023/0453(COD) | Full legislative history: committee votes, rapporteur, plenary votes, trilogue timeline |
| ECHA homepage | https://echa.europa.eu/ | Agency portal; search "common data platform chemicals" for guidance pages |
| DG Environment, Chemicals Strategy for Sustainability | https://environment.ec.europa.eu/strategy/chemicals-strategy_en | Commission policy page for the 2020 strategy that OSOA implements |
| Council press release, final green light | https://www.consilium.europa.eu/en/press/press-releases/2025/11/13/chemicals-council-greenlights-legislative-package-to-streamline-chemical-safety-assessments | Council's own account of the final adoption step, 13 November 2025 |

## Related Brubru guides

- `eu_chemicals_common_data_platform_cdpc`: the detailed technical guide to the CDPC itself (data categories, FAIR rules, IPCheM, human biomonitoring, exclusions).
- `echa_agency_overview`: ECHA's mandate, structure and existing tasks, ahead of the OSOA reattribution.
- `reach_chemicals_regulation`: the REACH registration and evaluation framework whose data feeds the CDPC.
- `efsa_agency_overview`: EFSA's role in food and feed chemical safety, and its position in the new EFSA-ECHA reconciliation procedure.
- `eu_clp_regulation_classification_labelling`: the CLP classification and labelling framework, another major CDPC data source.
- `biocidal_products_regulation`: the Biocidal Products Regulation, whose data is explicitly in scope for the CDPC.
