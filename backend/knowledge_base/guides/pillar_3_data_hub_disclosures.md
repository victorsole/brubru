# EBA Pillar 3 Data Hub: Centralised Prudential Disclosures

## QUICK FACTS
- **What it is**: The **Pillar 3 Data Hub (P3DH)** is a centralised EBA platform that receives, publishes and lets the public search bank prudential ("Pillar 3") disclosures for all EEA institutions on a single, harmonised digital portal, replacing the old model where each bank published its own Pillar 3 report on its own website in its own format.
- **Legal basis**: mandated by the 2024 EU Banking Package implementing Basel III (Basel IV) finalisation: **CRR3** (Regulation (EU) 2024/1623, CELEX **32024R1623**, amending the Capital Requirements Regulation (EU) No 575/2013) together with its twin directive **CRD VI**. CRR3 moved the detailed Pillar 3 disclosure obligations of CRR Part Eight (Articles 431-455) toward centralised EBA submission and publication instead of purely bank-run websites, and mandated the EBA to build the technical infrastructure.
- **Operator**: **EBA** (European Banking Authority, Paris).
- **Portal**: `https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub` (the older `/legacy/` path for this page is dead: use this URL).
- **Timeline**: large and other institutions began **submitting** disclosures to the EBA from **26 January 2026**; the public-facing hub with visualisation and bulk-download tools **went live on 28 January 2026**. First reference dates covered: **June, September and December 2025** (backfilled), with the full dataset expected to be complete by **June 2026**. **Small and non-complex institutions (SNCIs)** are being phased in separately and later: as of mid-2026 the EBA was still consulting on the SNCI onboarding process (Discussion Paper open **8 June to 20 July 2026**): a firm SNCI go-live date was not yet fixed at the time of writing; verify before citing a specific SNCI date.
- **Who submits**: EU/EEA credit institutions and investment firms in scope of CRR Pillar 3 (Part Eight), tiered by size/complexity (large institutions and other institutions first; SNCIs later, likely on a lighter/simplified track consistent with the existing CRR SNCI disclosure waivers).
- **What is disclosed**: the same substantive content as CRR Part Eight always required, own funds and capital ratios (CET1/Tier 1/Total), risk-weighted exposure amounts by risk type, leverage ratio, liquidity (LCR and NSFR), large exposures, asset encumbrance, remuneration policy (including staff earning ≥ EUR 1 million), ESG/climate risk disclosures, and (going forward) the phase-in of the Basel III output floor (72.5% of standardised RWAs, transitional). The Hub does not add new disclosure content on its own: it changes **where** and **how** the existing CRR Part Eight content is submitted and accessed.
- **Format**: structured, machine-readable submission by institutions (XBRL-CSV and data-extractable PDF formats referenced in EBA implementing technical standards), republished by the EBA "as submitted" with a visualisation tool and bulk-download files.
- **Purpose**: market discipline (the classic Basel "Pillar 3" rationale), comparability across institutions and Member States, and a single access point instead of 27+ national/bank-level silos: the banking-sector counterpart to the securities-and-sustainability-disclosure logic of the **European Single Access Point (ESAP)**.
- **Responsible DG / EU body**: EBA (not a Commission DG); underlying legislative file steered by DG FISMA and EP ECON as co-legislators of the CRR3/CRD VI Banking Package.

## Why it exists

Pillar 3 of the Basel framework (market discipline, alongside Pillar 1 minimum capital and Pillar 2 supervisory review) has always required EU banks to publish detailed prudential disclosures under CRR Part Eight (Articles 431-455): own funds, risk exposures, leverage, liquidity, remuneration and more. Historically, each institution published its own Pillar 3 report as a PDF on its own website, on its own schedule, in its own layout. That made cross-bank and cross-border comparison slow and labour-intensive for supervisors, analysts, investors and civil society: exactly the kind of fragmentation the EU's wider disclosure-infrastructure agenda (also visible in ESAP for securities and sustainability data) has been dismantling since 2023.

The 2024 Banking Package (CRR3/CRD VI), the EU's implementation of the final Basel III ("Basel IV") reforms, addressed this specifically for banks: instead of leaving Pillar 3 publication to each institution, CRR3 requires large and other institutions to submit their Pillar 3 data directly to the EBA in structured format, and mandates the EBA to build and operate a **Pillar 3 Data Hub** that republishes the data, unchanged, through one free public portal with search, comparison and bulk-download tools.

## What changed for institutions

- **Before**: each institution designed its own Pillar 3 report (PDF, often annual or semi-annual), published on its own website; disclosure content was governed by CRR Part Eight but presentation and access were not standardised.
- **After (P3DH)**: in-scope institutions submit prescribed Pillar 3 templates directly to the EBA in machine-readable formats (XBRL-CSV / data-extractable PDF) on a defined reporting calendar; the EBA republishes the submitted data on the Hub "as submitted" (no EBA editing of content), with a visualisation tool for cross-institution and cross-period comparison and options to download the underlying data in bulk.
- **Institutions still hold the legal disclosure obligation** under CRR Part Eight; the Hub changes the delivery and access channel, not who is legally responsible for the accuracy of the disclosed figures.

## Timeline

| Date | Milestone |
|---|---|
| 2024 | CRR3 (Regulation (EU) 2024/1623) adopted, mandating the EBA to build a centralised Pillar 3 disclosure hub |
| 23 January 2026 | EBA publishes the Pillar 3 Data Hub user guide (large and other institutions) |
| 26 January 2026 | Large and other institutions begin submitting Pillar 3 disclosures directly to the EBA |
| 28 January 2026 | Public Pillar 3 Data Hub portal goes live (visualisation + bulk download) |
| June, September, December 2025 | First reference dates covered by the backfilled dataset available on the Hub |
| By June 2026 | Full dataset (large and other institutions) expected to be complete |
| 8 June - 20 July 2026 | EBA Discussion Paper open for consultation on the Pillar 3 Data Hub onboarding process for small and non-complex institutions (SNCIs) |
| TBC | Confirmed SNCI go-live date not yet fixed at time of writing: verify against the EBA's Transparency and Pillar 3 regulatory-activities page before citing |

## Scope: who is in and who is not (yet)

- **In from launch**: large institutions and "other institutions" as defined in CRR (the standard CRR size/complexity tiering, distinct from SNCIs).
- **Phased in later**: small and non-complex institutions (SNCIs), which already benefit from simplified/waived Pillar 3 disclosure obligations under CRR Part Eight; the EBA is consulting on how (and by implication, roughly when) SNCIs will be onboarded to the Hub, rather than requiring the same submission process as large institutions from day one.
- **Not covered by the Hub itself**: Pillar 2 supervisory review outcomes (SREP), which remain confidential supervisor-to-institution communication and are not part of the public Pillar 3 disclosure regime.

## Relationship to other EU disclosure infrastructure

- **CRR Part Eight (Articles 431-455)** remains the substantive legal source of what must be disclosed; the Hub is the delivery/access layer built on top of it. See `crr_capital_requirements_regulation` for the full CRR structure, including the pre-existing Pillar 3 article list.
- **EBA's Single Rulebook role**: the EBA already writes the binding technical standards (RTS/ITS) that define CRR's harmonised rulebook; building and operating the Hub extends that role from rule-setting into direct data infrastructure. See `financial_supervision_eba`.
- **ESAP (European Single Access Point)**: ESAP is the wider, cross-sectoral EU single-access-point project (securities, prospectuses, sustainability reporting, operated by ESMA, phased in from 2026-2030) covering issuers and financial products generally. The Pillar 3 Data Hub is the banking-prudential-specific analogue, run by the EBA rather than ESMA, and focused on CRR Pillar 3 content rather than the broader ESAP perimeter. The two are complementary, not the same platform: do not conflate P3DH submissions with ESAP submissions. See `esap_european_single_access_point`.
- **Banking Union / resolution disclosures**: Pillar 3 covers going-concern prudential disclosure; resolution-related disclosures (MREL, resolvability) sit closer to the Banking Union's resolution framework. See `banking_union_reform`.
- **ESG/climate disclosures**: CRR Part Eight already requires ESG risk disclosures from large listed institutions; these flow through the same Hub submission channel. See `eu_taxonomy_sustainable_finance` for the broader sustainable-finance disclosure architecture (CSRD/ESRS/EU Taxonomy) that supplies much of the underlying ESG data.

## Useful References

- EBA Pillar 3 Data Hub (portal): https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub
- EBA press release, Hub goes live: https://www.eba.europa.eu/publications-and-media/press-releases/eba-pillar-3-data-hub-goes-live
- EBA Discussion Paper, Pillar 3 Data Hub process for SNCIs: https://www.eba.europa.eu/publications-and-media/press-releases/eba-launches-discussion-paper-pillar-3-data-hub-small-banks
- EBA Transparency and Pillar 3 regulatory activities: https://www.eba.europa.eu/regulation-and-policy/transparency-and-pillar-3
- EBA homepage: https://www.eba.europa.eu/
- CRR3 (Regulation (EU) 2024/1623) on EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1623
- CRR (Regulation (EU) No 575/2013), Part Eight disclosure articles: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0575

## Related Brubru Guides

- `crr_capital_requirements_regulation`: the underlying CRR/CRR3 Pillar 3 disclosure obligations (Articles 431-455) that the Hub now centralises
- `financial_supervision_eba`: the EBA's Single Rulebook and supervisory-convergence role, of which the Hub is an extension
- `esap_european_single_access_point`: the wider, ESMA-run cross-sectoral EU single-access-point project for securities and sustainability disclosures
- `banking_union_reform`: the Banking Union's resolution-side disclosure and reform framework
- `eu_taxonomy_sustainable_finance`: the ESG/sustainability disclosure architecture feeding into CRR Pillar 3 ESG risk content
