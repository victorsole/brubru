# European Single Access Point (ESAP): the EU's public disclosure hub

## QUICK FACTS
- **What it is**: The European Single Access Point (ESAP) is a single, free, EU-wide, machine-readable access point for public financial, capital-markets and sustainability-related information about EU entities and their financial products and services. It is often described as the EU's "Bloomberg of disclosures": one portal replacing dozens of fragmented national registers.
- **Establishing legislation (three-instrument package)**: **Regulation (EU) 2023/2859** (CELEX 32023R2859) establishing ESAP itself, adopted 13 December 2023; the **ESAP Omnibus Directive (EU) 2023/2864** amending sectoral directives (including the Transparency Directive) to feed data into ESAP; and the **ESAP Omnibus Regulation (EU) 2023/2869** amending sectoral regulations (including the Prospectus Regulation and Short Selling Regulation) for the same purpose. Together the three instruments amend more than 30 pieces of EU financial-services and sustainability legislation to route their public disclosures through ESAP.
- **Operator**: **ESMA** (European Securities and Markets Authority, Paris) is mandated to establish and operate the ESAP portal.
- **Two-tier submission model**: reporting entities (issuers, financial firms) submit information to a national or EU **"Collection Body"** (typically the national competent authority, a national business/company register, or an EU body such as one of the three ESAs); the Collection Body then forwards the data to ESAP in a **machine-readable format** (principally **XBRL** where the underlying legislation already requires it, e.g. ESEF annual financial reports) with structured **metadata** (entity identifiers such as LEI, document type, language, reporting period) so users can search and filter across the whole EU.
- **Phased go-live (dates fixed in the Regulation)**:
  - **Phase 1**: data collection begins **10 July 2026**; the public portal itself must be made available by ESMA by **10 July 2027**. Phase 1 scope covers the **Transparency Directive**, the **Prospectus Regulation** and the **Short Selling Regulation** (issuer disclosures, prospectuses, net short-position notifications).
  - **Phase 2**: collection and public access begin simultaneously from **10 January 2028**, widening the scope to further sectoral acts (market-industry sources describe an intermediate "phase 2bis" tranche from January 2029, though this sub-phase is not a defined term in the Regulation text itself: treat as a monitoring note, not a legal deadline).
  - **Phase 3**: from **10 January 2030**, the remaining identified perimeter comes online: market commentary puts this at roughly 8 further regulations and 12 further directives, completing coverage of the 30+ sectoral acts amended by the Omnibus package (including CSRD/ESRS sustainability reporting, MiFID II, EMIR, CRR/CRD, Solvency II strands as they are phased in).
- **Coverage once complete**: prospectuses, periodic and ongoing issuer disclosures (Transparency Directive), short-selling notifications, sustainability reporting under CSRD/ESRS, credit ratings, securitisation disclosures, and other public financial-services filings currently scattered across ~30 national and EU registers.
- **Users**: institutional and retail investors, financial analysts, data vendors, national and EU supervisors, researchers and civil society: all get one free search interface instead of navigating 27 national systems in as many formats and languages.
- **Strategic role**: ESAP is a foundational data-infrastructure enabler for the **Savings and Investment Union (SIU)**: cheap, comparable, machine-readable disclosure data is a precondition for cross-border retail investment, EU green bond pricing, and supervisory convergence at ESMA. Verify phase dates and the "phase 2bis" terminology against the Regulation text and ESMA's implementation pages before citing in time-sensitive material, as market commentary sometimes uses informal sub-phase labels not present in the legal text.

## Why ESAP exists

EU financial and sustainability disclosures have historically been scattered across national company registers, national competent authority (NCA) websites, stock exchange filing systems and sector-specific EU registers: in different formats, different languages and with inconsistent machine-readability. An investor wanting to compare disclosures across, say, a German issuer, a Polish issuer and an Irish fund had to navigate three different national systems with three different search interfaces. This fragmentation was repeatedly flagged as a barrier to a genuine EU single market for capital, both in the original Capital Markets Union (CMU) agenda and in the Letta and Draghi reports that fed into the Savings and Investment Union rebrand in 2025.

ESAP addresses this directly: it does not create new disclosure obligations on companies (the underlying reporting duties already exist under sectoral EU law), it creates a **single retrieval layer** on top of existing disclosures, enforced by requiring the data be submitted in structured, machine-readable form with common metadata so it can be indexed, searched and compared centrally.

## Legal architecture: three linked instruments

ESAP was adopted as a package of three linked instruments on 13 December 2023, all published in the same Official Journal batch:

1. **Regulation (EU) 2023/2859**: the "ESAP Regulation" itself. Establishes ESAP, mandates ESMA to build and operate it, defines the two-tier Collection Body model, sets governance and funding arrangements, and fixes the phased implementation dates.
2. **Directive (EU) 2023/2864**: the "ESAP Omnibus Directive". Amends the directives that need to be changed to route their disclosures into ESAP (notably the Transparency Directive 2004/109/EC and other directives requiring member state transposition).
3. **Regulation (EU) 2023/2869**: the "ESAP Omnibus Regulation". Amends the directly-applicable EU regulations that need to be changed for the same purpose (notably the Prospectus Regulation (EU) 2017/1129 and the Short Selling Regulation (EU) 236/2012, with later phases reaching further into EMIR, CRR and other sectoral regulations).

This "one Regulation establishing the infrastructure + two Omnibus instruments amending the feeder legislation" pattern is the same drafting technique used elsewhere in EU financial-services law when a new cross-cutting mechanism has to plug into dozens of pre-existing sectoral acts without rewriting each one from scratch.

## The two-tier Collection Body model

ESAP does not collect information directly from companies. Instead:

1. **Reporting entities** (issuers, investment firms, funds, credit institutions, etc.) continue to file their disclosures exactly as sectoral law already requires: to their NCA, to a national company register, to a stock exchange, or to an EU body such as one of the European Supervisory Authorities (ESMA, EBA, EIOPA).
2. That recipient acts as the **"Collection Body"** for ESAP purposes. Collection Bodies are responsible for checking the machine-readability of what they receive and forwarding it, together with structured metadata, to ESAP.
3. **ESMA**, as ESAP operator, ingests the feed from all Collection Bodies across the EU and exposes it through a single public search portal, free of charge.

This means the practical burden of the ESAP transition falls largely on national registers and NCAs (which must upgrade their submission pipelines to produce ESAP-compliant machine-readable files with the right metadata), rather than on ESMA rebuilding disclosure collection from scratch, and rather than on reporting companies filing twice.

## Format requirements: machine-readability and XBRL

Where the underlying sectoral legislation already mandates a machine-readable format: most notably the **European Single Electronic Format (ESEF)**, which requires XBRL tagging of annual financial reports under the Transparency Directive: ESAP simply re-uses that existing structured data. Where sectoral legislation does not yet mandate a machine-readable format, the ESAP Omnibus instruments introduce phased machine-readability requirements so that, over time, all information flowing into ESAP carries consistent structured tagging and metadata (entity identifier, document type, reporting period, language, home member state).

## Phased implementation

The Regulation sets binding dates for ESMA to make the ESAP platform operational, with the reporting perimeter widening in stages so that Collection Bodies and reporting entities are not all forced to upgrade simultaneously:

| Phase | Collection starts | Public access | Scope |
|---|---|---|---|
| Phase 1 | 10 July 2026 | 10 July 2027 | Transparency Directive, Prospectus Regulation, Short Selling Regulation |
| Phase 2 | 10 January 2028 | 10 January 2028 (simultaneous) | Widened sectoral scope (market commentary describes an intermediate "2bis" sub-tranche from January 2029: not a defined legal term, verify before citing) |
| Phase 3 | 10 January 2030 | 10 January 2030 (simultaneous) | Remaining perimeter: the balance of the 30+ sectoral acts amended by the Omnibus package, expected to include CSRD/ESRS sustainability reporting and further prudential/market-structure disclosures |

The 10 July 2027 date for public launch of the portal is the headline figure most commonly cited; the 10 July 2026 date is when Collection Bodies must begin submitting data to ESMA so the portal has content ready for the public launch a year later.

## Relationship to other EU financial-data initiatives

- **Savings and Investment Union (SIU)**: ESAP is core data infrastructure for the SIU's push toward a genuine single market for retail savings and investment: comparable, centrally searchable disclosure data lowers the cost for retail investors and cross-border funds to evaluate EU issuers. See `savings_and_investment_union`.
- **CSRD / ESRS sustainability reporting**: Corporate sustainability reporting under the Corporate Sustainability Reporting Directive, tagged to the European Sustainability Reporting Standards, is one of the disclosure streams intended to flow into ESAP once the relevant phase covers it. See `corporate_sustainability_due_diligence`.
- **EU Taxonomy**: Taxonomy-alignment disclosures published under sustainability reporting obligations become centrally searchable via ESAP once in scope. See `eu_taxonomy_sustainable_finance`.
- **MiFID II**: market and investment-firm disclosures under MiFID II are among the sectoral acts amended by the Omnibus package to eventually feed ESAP. See `mifid_ii_directive`.
- **data.europa.eu**: ESAP is a sector-specific, ESMA-run counterpart to the EU's general open-data portal; the two are complementary but ESAP is scoped specifically to financial-services and sustainability disclosures with a regulatory Collection Body pipeline, not a general open-data catalogue. See `data_europa_eu_open_data_portal`.
- **ESMA's supervisory mandate**: operating ESAP sits alongside ESMA's broader supervisory-convergence role under the SIU package (see the planned sibling guide on ESMA's expanding direct-supervision mandate).
- **Listing Act**: the EU's 2024 Listing Act package (simplifying prospectus and listing rules) is one of the upstream simplification efforts whose resulting disclosures will also route through ESAP once Phase 1 is live (see the planned sibling guide on the Listing Act).
- **EBA Pillar 3 data hub**: the EBA is separately developing a centralised hub for banks' Pillar 3 prudential disclosures; this is a parallel, sector-specific initiative distinct from ESAP, though conceptually aligned with the same "centralise scattered disclosures" logic (see the planned sibling guide, when created).

## Why it matters for EU policy and market professionals

For anyone tracking EU capital-markets integration, ESAP is the plumbing that makes several other flagship initiatives usable in practice: CSRD/ESRS sustainability data is only valuable at scale if it can be retrieved and compared across thousands of companies without visiting each national register; EU Green Bond pricing depends on investors being able to verify issuer disclosures quickly and cheaply; and the Savings and Investment Union's ambition to mobilise part of the EU's roughly EUR 35 trillion in household financial savings into cross-border investment depends on lowering the information-search cost that currently deters retail and even institutional cross-border investment. ESAP is therefore best understood not as a standalone transparency initiative but as foundational data infrastructure underpinning the EU's wider capital-markets and sustainable-finance agenda.

## Verify before citing

- The Regulation itself: EUR-Lex CELEX **32023R2859**: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R2859`.
- ESMA's ESAP implementation page (the correct current URL is `https://www.esma.europa.eu/esmas-activities/data/european-single-access-point-esap`: the `/digital-finance-and-innovation/` path in older references now 404s).
- The European Commission's finance.ec.europa.eu ESAP landing page: verify the current URL at time of use; the previously bookmarked `financial-data-and-transparency/european-single-access-point-esap_en` path returned a 404 during this guide's research and should be re-checked before use in outward-facing material.
- The informal "phase 2bis" label (January 2029) appears in market/industry commentary (e.g. regulatory-technology vendors) but is not confirmed as a defined term in the Regulation's own text: treat as a monitoring note pending direct verification against the Regulation's phasing annex.

## Cross-links

- `savings_and_investment_union`: the SIU package ESAP underpins as core data infrastructure
- `esma_supervisory_oversight_mandates` (planned sibling guide): ESMA's broader supervisory-convergence role alongside operating ESAP
- `listing_act_eu_capital_markets` (planned sibling guide): upstream prospectus/listing simplification whose disclosures route through ESAP
- `eu_taxonomy_sustainable_finance`: taxonomy-alignment disclosures in scope for later ESAP phases
- `corporate_sustainability_due_diligence`: CSRD/ESRS sustainability reporting feeding into ESAP
- `data_europa_eu_open_data_portal`: the EU's general open-data counterpart to ESAP's sector-specific hub
- `mifid_ii_directive`: one of the 30+ sectoral acts amended to feed ESAP
- `pillar_3_data_hub_disclosures` (planned sibling guide): EBA's parallel prudential-disclosure hub for banks
