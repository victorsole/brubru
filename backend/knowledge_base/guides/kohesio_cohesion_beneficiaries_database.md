# Kohesio: the EU cohesion policy beneficiaries database

## QUICK FACTS
- **URL:** https://kohesio.ec.europa.eu/ (also aliased at https://kohesio.eu/)
- **Operator:** DG REGIO (Directorate-General for Regional and Urban Policy), European Commission
- **What it is:** the single public, project-level database of Cohesion Policy beneficiaries and the projects they run, built to make "who got EU cohesion money, for what, and where" transparent and searchable.
- **Launch:** 17 March 2022, unveiled at the start of the 8th Cohesion Forum.
- **Coverage (funds):** European Regional Development Fund (ERDF), European Social Fund / European Social Fund Plus (ESF/ESF+), Cohesion Fund, Just Transition Fund (JTF). Interreg (cross-border, transnational, interregional cooperation) projects are ERDF-funded and appear in Kohesio's project data as a distinct programme category.
- **Timeframe:** built first for the 2014-2020 programming period; DG REGIO is progressively enriching it with 2021-2027 projects and beneficiaries in cooperation with Member States and programme authorities. Coverage is therefore uneven across periods and countries, not a complete real-time mirror of current spending.
- **Scale (reported, evolving, verify before citing a precise figure):** at launch (March 2022) the platform held data on "over 1.5 million projects" across all 27 Member States. A subsequent data.europa.eu profile put the count at "more than 1.7 million projects and approximately 500,000 beneficiaries." Other secondary sources cite figures as high as 1.8 million projects and roughly 600,000 direct beneficiaries. **Do not assert a single fixed project count or a cumulative EUR total as current fact**: the dataset grows continuously as new operations lists are ingested, and no verified single "cumulative EUR" figure for Kohesio itself was found; the often-cited EUR 392 billion is the 2021-2027 Cohesion Policy *budget envelope* (ERDF + Cohesion Fund + ESF+ + JTF), not a Kohesio-reported cumulative disbursement total. Always re-check the live platform or its FAQ/statistics page before quoting a number.
- **Data model:** built on Wikibase (the open-source semantic-data software from Wikimedia Deutschland, the same technology stack that underpins Wikidata) and W3C semantic web / linked-open-data (LOD) standards. Projects and beneficiaries are entities with stable Q-identifiers (e.g. a beneficiary page at `/en/beneficiaries/Q4868`), feeding into what the Commission calls the "EU Knowledge Graph."
- **How to search:** an interactive map on the homepage, dedicated project and beneficiary search pages, AI-assisted "smart search" for terms and related concepts, and standard/advanced filters by Member State, region, theme, funding programme, and investment/intervention category.
- **Data access:** bulk downloads by country in CSV/XLSX format, plus RDF for linked-data reuse, via the platform's Services/Data pages (`kohesio.ec.europa.eu/en/services`, `kohesio.ec.europa.eu/data`). No publicly documented stable REST or SPARQL endpoint was confirmed at time of writing: treat "API access" claims about Kohesio as unverified until a documented endpoint is found; the safe access pattern to cite is bulk CSV/XLSX/RDF download, not a live query API.
- **Legal basis for the underlying beneficiary lists:** Regulation (EU) No 1303/2013, Annex XII (2014-2020 communication/transparency obligation) and Regulation (EU) 2021/1060, Article 49 (2021-2027 CPR). Managing authorities in each Member State must publish lists of operations and beneficiaries; Kohesio aggregates, cleans, machine-translates, and geolocates that raw data rather than being a primary source itself.
- **Complementary platform:** cohesiondata.ec.europa.eu (the "Cohesion Open Data Platform," also DG REGIO) is the programme/finance-level counterpart: it visualises planned versus implemented finances, EU payments to Member States, and agreed targets for hundreds of national, regional, and interregional programmes (reported at over EUR 110 billion across 150 adopted 2021-2027 programmes, out of a EUR 308 billion Investment for Jobs and Growth envelope from 22 adopted Partnership Agreements). Kohesio is project/beneficiary-granular; cohesiondata is programme/finance-aggregated. Both sit under the same DG REGIO transparency mandate but are separate systems with separate data models.
- **Not the same system as the RRF Scoreboard:** the Recovery and Resilience Facility (RRF, Regulation (EU) 2021/241) is *not* Cohesion Policy: it is a separate, one-off Next Generation EU instrument managed by DG ECFIN, not DG REGIO. Its transparency counterpart is the **Recovery and Resilience Scoreboard** (`reforms-investments.ec.europa.eu` / `ec.europa.eu/economy_finance/recovery-and-resilience-scoreboard`), which tracks milestones, targets, and disbursements per national plan. No functional data link between Kohesio and the RRF Scoreboard was found; treat them as parallel EU transparency platforms covering different funding instruments, not an integrated pair.
- **Caveats:** data completeness and update frequency vary significantly by Member State (dependent on how promptly each managing authority publishes its operations list); beneficiary name strings are not standardised across countries, which makes cross-border entity resolution (matching "the same company" across national lists) genuinely hard; 2021-2027 coverage lags 2014-2020 coverage; project titles/descriptions are machine-translated, which can introduce translation artefacts.

Guide for anyone tracing EU cohesion funding to a named beneficiary: NGOs and journalists doing "follow the money" investigations, funds and advisers doing portfolio-company due diligence, and public-affairs professionals checking whether a client or competitor has received Cohesion Policy support.

## What Kohesio is

Kohesio is the European Commission's public platform for discovering, at project level, what EU Cohesion Policy funds have paid for and who received the money. It was launched by DG REGIO on 17 March 2022, at the opening of the 8th Cohesion Forum, explicitly framed as a transparency and accountability tool: rather than leaving beneficiary disclosure scattered across dozens of national managing-authority websites in inconsistent formats, Kohesio centralises, standardises, machine-translates, and geolocates that data into one searchable, mappable, multilingual resource.

It answers a narrow but high-value question that no other single EU database answers cleanly: "did organisation X receive EU cohesion money, for which project, under which fund, and how much?" Kohesio complements (it does not replace) the national managing-authority disclosure pages that remain the legal originals of the data.

## Coverage: funds and timeframe

Kohesio covers the four shared-management funds that make up EU Cohesion Policy under the Common Provisions Regulation umbrella:

- **European Regional Development Fund (ERDF)**, including Interreg cross-border, transnational, and interregional cooperation programmes, which are ERDF-funded and appear as a distinct Kohesio programme category.
- **European Social Fund (ESF)** for 2014-2020, succeeded by **European Social Fund Plus (ESF+)** for 2021-2027.
- **Cohesion Fund** (Member States with GNI below 90% of the EU average).
- **Just Transition Fund (JTF)**, the newest of the four, introduced for the 2021-2027 period to support regions transitioning away from carbon-intensive industries.

The platform's data backbone was built first for the **2014-2020 programming period**, where coverage is now broad and mature. DG REGIO is progressively adding **2021-2027** projects and beneficiaries as Member States and programme authorities publish and transmit their operations lists. This means 2021-2027 coverage is materially thinner and less complete than 2014-2020 coverage, and will keep growing rather than existing as a static snapshot.

Kohesio does **not** cover the Recovery and Resilience Facility (Next Generation EU / RRF), the European Maritime, Fisheries and Aquaculture Fund (EMFAF), the Asylum, Migration and Integration Fund (AMIF), the Internal Security Fund (ISF), or the Border Management and Visa Instrument (BMVI), even though several of those funds share the Common Provisions Regulation's audit and control architecture (see `cohesion_policy_audit.md`). Users asking about RRF-funded projects should be pointed to the separate Recovery and Resilience Scoreboard, not to Kohesio.

## Data model: Wikibase, Q-identifiers, and the EU Knowledge Graph

Kohesio is built on **Wikibase**, the open-source semantic-database software developed by Wikimedia Deutschland (the same software that underpins Wikidata), combined with W3C semantic web / linked-open-data (LOD) standards. This is an unusual technical choice for an EU Commission platform and is worth knowing because it shapes how the data can be queried and reused.

In practice this means:

- Every **beneficiary** and every **project** is modelled as an **entity** with a stable identifier of the Wikidata-style form `Qnnnnnnn` (for example, a regional-authority beneficiary page is reachable at `kohesio.ec.europa.eu/en/beneficiaries/Q4868`).
- Entities carry structured properties (location, fund, programme, EU contribution amount, dates, thematic classification) rather than free text, which is what makes filtering and aggregation possible.
- Kohesio's entities feed into what the Commission calls the **EU Knowledge Graph**, a broader linked-data initiative connecting Kohesio with other EU open-data resources so that identifiers can, in principle, be reused and cross-referenced outside the platform itself.
- Source data arrives as heterogeneous national "lists of operations" published under transparency obligations (see Legal basis below); a Kohesio pipeline ingests, standardises, geocodes, and machine-translates these lists into the entity model. The underlying national lists remain the legally authoritative source; Kohesio is a derived, standardised layer on top of them.

## How to search Kohesio

- **Interactive map** on the homepage, letting users browse projects geographically down to regional and local level.
- **Dedicated search pages** for projects and for beneficiaries, each returning entity pages with structured metadata.
- **AI-assisted "smart search"**, which the platform's own documentation describes as allowing search by term or related concept rather than exact string match.
- **Filters**: Member State, region (down to NUTS-level granularity in many cases), thematic priority/policy objective, funding programme, and investment/intervention category.
- **Bulk download**: country-by-country CSV/XLSX exports and RDF linked-data exports via the Services/Data pages, for anyone who wants the raw dataset rather than the web interface.

No publicly documented, stable REST or SPARQL query endpoint for Kohesio was confirmed during research for this guide. Bulk CSV/XLSX/RDF download is the verified access pattern; anything beyond that (a live queryable API) should be checked against the current Services page before being cited to a user as fact.

## Relationship to cohesiondata.ec.europa.eu and the RRF Scoreboard

Kohesio is one of two DG REGIO transparency platforms and should not be confused with the other:

| Platform | Granularity | What it shows | Operator |
|---|---|---|---|
| **Kohesio** (`kohesio.ec.europa.eu`) | Project and beneficiary level | Individual funded projects, who ran them, EU contribution per project | DG REGIO |
| **Cohesion Open Data Platform** (`cohesiondata.ec.europa.eu`) | Programme and finance level | Planned versus implemented finances, EU payments to Member States, agreed targets, across hundreds of national/regional/interregional programmes | DG REGIO |

The Cohesion Open Data Platform has reported, for the 2021-2027 period, data on over EUR 110 billion in EU financing across 150 adopted programmes, and an interactive presentation of the EUR 308 billion made available under the Investment for Jobs and Growth goal from 22 adopted Partnership Agreements. Use cohesiondata for "how much has this Member State's programme received/spent so far" questions, and Kohesio for "which specific organisation received money for which project" questions.

The **Recovery and Resilience Facility (RRF)** is a separate, one-off instrument under Next Generation EU (Regulation (EU) 2021/241), managed by DG ECFIN rather than DG REGIO, and is **not** part of Cohesion Policy despite sharing some policy objectives. Its transparency counterpart is the **Recovery and Resilience Scoreboard**. Research for this guide found no functional integration or shared identifier system linking Kohesio to the RRF Scoreboard: they are parallel platforms for different funding instruments. Do not describe them to a user as linked or interoperable without further verification.

## Relevance to the Brubru financial-data spine

Kohesio is one of the most directly usable "follow the EU money" surfaces available for the financial/corporate-intelligence vertical sketched in `data/financial_data.md` (entity spine + monitoring/auditing/screening product shapes):

- **Beneficiary trail**: for a named company, NGO, or public authority, Kohesio can in principle confirm whether it appears as a Cohesion Policy beneficiary, under which fund, for which project, and for how much EU contribution, directly answering the "did company X get cohesion money" query pattern that NGOs, journalists, and funds bring to Brubru.
- **Entity resolution challenge**: Kohesio's beneficiary names come from national managing-authority lists and are not standardised across Member States (no consistent use of LEI or a single national company-register identifier). This is the same entity-resolution problem the financial-data-spine brief identifies as the foundational build (LEI where available, name + country matching otherwise). Kohesio is a strong *source* for that spine but is not itself pre-resolved to stable company identifiers.
- **Complementary to CORDIS**: where CORDIS (`cordis_research_projects_database.md`) covers Horizon Europe/Horizon 2020 research and innovation grants, Kohesio covers shared-management structural/cohesion funding. A single beneficiary can plausibly appear in both, which is a useful cross-check when building a company's full EU-funding footprint.
- **Open-data reuse**: Kohesio's CSV/XLSX/RDF exports and Wikibase/LOD model make it a realistic bulk-ingestion candidate for a Brubru-side beneficiaries table, subject to the entity-resolution work above; see also `data_europa_eu_open_data_portal.md` for the broader EU open-data harvesting pattern Brubru already uses.

## Caveats

- Coverage is uneven: mature and broad for 2014-2020, thinner and still growing for 2021-2027.
- Update frequency depends on each Member State's managing authority; Kohesio is a derived, periodically refreshed layer, not a live feed.
- No single verified "total projects" or "cumulative EUR" figure should be quoted as current without re-checking the live platform; reported figures have ranged from "over 1.5 million projects" (March 2022 launch) to "more than 1.7-1.8 million projects" in later secondary sources, and no confirmed platform-level cumulative EUR total was found.
- Beneficiary name strings are not standardised across countries, complicating cross-border entity resolution.
- Project titles and descriptions are machine-translated into EU languages, which can introduce minor translation artefacts.
- Kohesio does not cover RRF, EMFAF, AMIF, ISF, or BMVI funding, even though some of those funds share the same Common Provisions Regulation audit architecture.
- No confirmed public API/SPARQL endpoint; bulk CSV/XLSX/RDF download is the verified reuse pattern.

## Brubru tracking angles

- Add a "check Kohesio" step to any chat answer about whether a named company or organisation has received EU cohesion funding, alongside the existing CORDIS-check pattern for research funding.
- Flag Kohesio as a candidate source (with the entity-resolution caveat above) for the entity-spine build described in `data/financial_data.md`, specifically for the "auditing" (single-entity dossier) and "monitoring" (watchlist) product shapes.
- When advising users on EU cohesion transparency obligations (e.g. under Article 49 of Regulation (EU) 2021/1060), cite Kohesio and the national managing-authority operations list as the two disclosure surfaces, and cohesiondata.ec.europa.eu as the programme-level complement.
- Watch for DG REGIO announcements on 2021-2027 coverage milestones and any future documented API/SPARQL endpoint, which would materially change Kohesio's suitability for automated ingestion.

## Cross-references

- See also: `cohesion_policy_audit.md` for the Common Provisions Regulation audit framework, Arachne risk scoring, and the fund list (ERDF, ESF+, Cohesion Fund, JTF, EMFAF, AMIF, ISF, BMVI) that governs the beneficiary-disclosure obligation Kohesio aggregates.
- See also: `cohesion_policy_midterm_review.md` for the 2021-2027 mid-term review, reallocation flexibility, and the political context shaping which programmes feed Kohesio next.
- See also: `interreg_european_territorial_cooperation.md` (planned) for detail on the ERDF-funded cross-border/transnational programmes that appear in Kohesio as a distinct category.
- See also: `eu_just_transition_fund.md` for the JTF programme detail behind JTF-tagged Kohesio projects.
- See also: `team_europe_explorer_iati` (planned) for the equivalent beneficiary-transparency pattern applied to EU external-action and development funding.
- See also: `cordis_research_projects_database.md` for the Horizon Europe/Horizon 2020 counterpart covering research and innovation grants rather than cohesion structural funds.
- See also: `data_europa_eu_open_data_portal.md` for the broader EU open-data harvesting pattern and metadata standards Brubru already consumes.
- See also: `rrf_scoreboard_data_product` (planned) for the separate Recovery and Resilience Facility transparency platform, which is not integrated with Kohesio.
- See also: `data/financial_data.md` for the Brubru financial/corporate-intelligence vertical strategy brief that motivates tracking Kohesio as an entity-spine data source.
